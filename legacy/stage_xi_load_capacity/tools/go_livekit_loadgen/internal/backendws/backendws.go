package backendws

import (
	"bufio"
	"byod-loadgen/internal/livekitconn"
	"context"
	"crypto/rand"
	"crypto/sha1"
	"crypto/tls"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"sync/atomic"
	"time"
)

type Event struct {
	Kind, RunnerID, WorkerID, ListenerID, Error                                 string
	Mode, Profile, LiveKitURL, Transport                                        string
	SelectedChannel, TerminalStatus, TerminalStage, ErrorCategory, ErrorMessage string
	ParticipantIdentity, ParticipantName, ParticipantMetadata                   string
	TrackSID, TrackName, TrackSource, TrackKind                                 string
	WorkerIndex, CloseCode                                                      int
	RTPPackets, RTPBytes                                                        int64
	WasConnected, WasLiveKitConnected                                           bool
	BackendConnected, LiveKitConnected, AudioTrackSubscribed, RTPReceived       bool
	ContextCancelled, NormalShutdown                                            bool
	ElapsedMS                                                                   int64
}
type Conn struct {
	c net.Conn
	r *bufio.Reader
}

func envelope(t, req string, payload map[string]any) map[string]any {
	return map[string]any{"type": t, "schema_version": 1, "ts": time.Now().Unix(), "request_id": req, "payload": payload}
}
func dial(ctx context.Context, raw string) (*Conn, error) {
	u, err := url.Parse(raw)
	if err != nil {
		return nil, err
	}
	host := u.Host
	if !strings.Contains(host, ":") {
		if u.Scheme == "wss" {
			host += ":443"
		} else {
			host += ":80"
		}
	}
	d := net.Dialer{}
	nc, err := d.DialContext(ctx, "tcp", host)
	if err != nil {
		return nil, err
	}
	if deadline, ok := ctx.Deadline(); ok {
		_ = nc.SetDeadline(deadline)
	}
	if u.Scheme == "wss" {
		nc = tls.Client(nc, &tls.Config{ServerName: u.Hostname()})
		if err := nc.(*tls.Conn).HandshakeContext(ctx); err != nil {
			nc.Close()
			return nil, err
		}
	}
	keyb := make([]byte, 16)
	rand.Read(keyb)
	key := base64.StdEncoding.EncodeToString(keyb)
	path := u.RequestURI()
	if path == "" {
		path = "/"
	}
	req := fmt.Sprintf("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n", path, u.Host, key)
	if _, err := io.WriteString(nc, req); err != nil {
		nc.Close()
		return nil, err
	}
	br := bufio.NewReader(nc)
	resp, err := http.ReadResponse(br, &http.Request{Method: "GET"})
	if err != nil {
		nc.Close()
		return nil, err
	}
	h := sha1.New()
	h.Write([]byte(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))
	accept := base64.StdEncoding.EncodeToString(h.Sum(nil))
	if resp.StatusCode != 101 || resp.Header.Get("Sec-WebSocket-Accept") != accept {
		nc.Close()
		return nil, fmt.Errorf("websocket handshake failed: %s", resp.Status)
	}
	_ = nc.SetDeadline(time.Time{})
	return &Conn{c: nc, r: br}, nil
}
func (c *Conn) Close() { _ = c.c.Close() }
func (c *Conn) WriteJSON(v any) error {
	b, err := json.Marshal(v)
	if err != nil {
		return err
	}
	return c.writeFrame(1, b)
}
func (c *Conn) CloseNormal() { _ = c.writeFrame(8, []byte{3, 232}) }
func (c *Conn) writeFrame(op byte, p []byte) error {
	hdr := []byte{0x80 | op}
	n := len(p)
	if n < 126 {
		hdr = append(hdr, 0x80|byte(n))
	} else if n < 65536 {
		hdr = append(hdr, 0x80|126, byte(n>>8), byte(n))
	} else {
		hdr = append(hdr, 0x80|127)
		var b [8]byte
		binary.BigEndian.PutUint64(b[:], uint64(n))
		hdr = append(hdr, b[:]...)
	}
	mask := make([]byte, 4)
	rand.Read(mask)
	hdr = append(hdr, mask...)
	out := make([]byte, n)
	for i := range p {
		out[i] = p[i] ^ mask[i%4]
	}
	_, err := c.c.Write(append(hdr, out...))
	return err
}
func (c *Conn) ReadJSON(v any) error {
	for {
		op, p, err := c.readFrame()
		if err != nil {
			return err
		}
		if op == 1 {
			return json.Unmarshal(p, v)
		}
		if op == 8 {
			return fmt.Errorf("close: %s", string(p))
		}
		if op == 9 {
			_ = c.writeFrame(10, p)
		}
	}
}
func (c *Conn) readFrame() (byte, []byte, error) {
	h, err := c.r.ReadByte()
	if err != nil {
		return 0, nil, err
	}
	op := h & 0x0f
	b, err := c.r.ReadByte()
	if err != nil {
		return 0, nil, err
	}
	ln := int(b & 0x7f)
	if ln == 126 {
		var x [2]byte
		io.ReadFull(c.r, x[:])
		ln = int(binary.BigEndian.Uint16(x[:]))
	} else if ln == 127 {
		var x [8]byte
		io.ReadFull(c.r, x[:])
		ln = int(binary.BigEndian.Uint64(x[:]))
	}
	masked := b&0x80 != 0
	var mask [4]byte
	if masked {
		io.ReadFull(c.r, mask[:])
	}
	p := make([]byte, ln)
	_, err = io.ReadFull(c.r, p)
	if err != nil {
		return 0, nil, err
	}
	if masked {
		for i := range p {
			p[i] ^= mask[i%4]
		}
	}
	return op, p, nil
}

type LiveKitConnectInfo struct {
	Token, URL, ListenerID, RoomName string
}

func LiveKitConnectInfoFromConnecting(message map[string]any) (LiveKitConnectInfo, error) {
	payload, ok := message["payload"].(map[string]any)
	if !ok {
		return LiveKitConnectInfo{}, errors.New("missing_connecting_payload")
	}
	info := LiveKitConnectInfo{}
	if v, ok := payload["token"].(string); ok {
		info.Token = v
	}
	if v, ok := payload["livekit_url"].(string); ok {
		info.URL = v
	}
	if v, ok := payload["listener_id"].(string); ok {
		info.ListenerID = v
	}
	if v, ok := payload["room"].(string); ok {
		info.RoomName = v
	} else if v, ok := payload["room_name"].(string); ok {
		info.RoomName = v
	}
	if info.Token == "" {
		return info, errors.New("missing_livekit_token")
	}
	if info.URL == "" {
		return info, errors.New("missing_livekit_url")
	}
	return info, nil
}

func FirstListenableChannelID(message map[string]any) (string, error) {
	payload, ok := message["payload"].(map[string]any)
	if !ok {
		return "", errors.New("listener_state_missing_payload")
	}
	channels, ok := payload["channels"].([]any)
	if !ok {
		return "", errors.New("listener_state_missing_channels")
	}
	for _, item := range channels {
		channel, ok := item.(map[string]any)
		if !ok {
			continue
		}
		listen, _ := channel["listen"].(bool)
		channelID, _ := channel["channel_id"].(string)
		if listen && channelID != "" {
			return channelID, nil
		}
	}
	return "", errors.New("no_listenable_channel")
}

func RunWorker(ctx context.Context, target, runnerID, key string, idx int, mode string, subscribeMode string, backendConnectTimeoutSec int, connector livekitconn.Connector, events chan<- Event) {
	start := time.Now()
	wid := fmt.Sprintf("%s-L%04d", runnerID, idx)
	eventBase := Event{RunnerID: runnerID, WorkerID: wid, WorkerIndex: idx, Mode: mode}
	events <- withKind(eventBase, "started")
	events <- withKind(eventBase, "worker_backend_connect_start")
	terminal := withKind(eventBase, "worker_finished")
	terminal.TerminalStatus = "internal_error"
	terminal.TerminalStage = "start"
	defer func() {
		terminal.ElapsedMS = time.Since(start).Milliseconds()
		terminal.ContextCancelled = ctx.Err() != nil
		if terminal.ErrorMessage == "" {
			terminal.ErrorMessage = terminal.Error
		}
		events <- terminal
	}()
	connectCtx, connectCancel := context.WithTimeout(ctx, time.Duration(backendConnectTimeoutSec)*time.Second)
	defer connectCancel()
	var backendConnectedFlag atomic.Bool
	c, err := dial(connectCtx, target)
	if err != nil {
		kind := "worker_backend_tcp_or_ws_dial_failed"
		status := "backend_ws_dial_failed"
		if connectCtx.Err() == context.DeadlineExceeded {
			kind = "worker_backend_first_message_timeout"
			status = "backend_connect_timeout"
		}
		e := withKind(eventBase, kind)
		e.Error = err.Error()
		events <- e
		terminal.TerminalStatus = status
		terminal.TerminalStage = "backend_connect"
		terminal.Error = e.Error
		terminal.ErrorCategory = terminal.TerminalStatus
		terminal.ErrorMessage = e.Error
		return
	}
	defer c.Close()
	payload := map[string]any{"client_role": "listener", "client_type": "load_runner", "runner_id": runnerID, "worker_id": wid, "worker_index": idx, "loadgen_key": key, "loadgen_mode": mode}
	if err := c.WriteJSON(envelope("connecting", "connect-"+wid, payload)); err != nil {
		e := withKind(eventBase, "worker_backend_tcp_or_ws_dial_failed")
		e.Error = err.Error()
		events <- e
		terminal.TerminalStatus = "backend_ws_dial_failed"
		terminal.TerminalStage = "backend_connect"
		terminal.Error = e.Error
		terminal.ErrorCategory = terminal.TerminalStatus
		terminal.ErrorMessage = e.Error
		return
	}
	done := make(chan struct{})
	selectedChannel := make(chan string, 1)
	type roomReadyEvent struct {
		room       livekitconn.Room
		listenerID string
		livekitURL string
	}
	roomReady := make(chan roomReadyEvent, 1)
	var livekitRoom livekitconn.Room
	var livekitDone <-chan struct{}
	var livekitEvents <-chan livekitconn.Event
	var livekitListenerID string
	var livekitURL string
	var audioTrackTimer <-chan time.Time
	audioTrackReceived := false
	go func() {
		defer close(done)
		listenerID := ""
		backendConnected := false
		liveKitConnected := false
		gotListenerState := false
		var info LiveKitConnectInfo
		for {
			var msg map[string]any
			if err := c.ReadJSON(&msg); err != nil {
				if ctx.Err() == nil && (backendConnected || connectCtx.Err() == nil) {
					if mode != "backend-ws-only" && !gotListenerState {
						e := withKind(eventBase, "worker_backend_first_message_failed")
						e.ListenerID = listenerID
						e.Error = "missing_listener_state"
						events <- e
						terminal.TerminalStatus = "backend_ws_read_first_message_failed"
						terminal.TerminalStage = "backend_connect"
						terminal.ErrorCategory = terminal.TerminalStatus
						terminal.Error = e.Error
						terminal.ErrorMessage = e.Error
						return
					}
					kind := "worker_closed"
					if !backendConnected {
						kind = "worker_backend_first_message_failed"
					}
					e := withKind(eventBase, kind)
					e.ListenerID = listenerID
					e.Error = err.Error()
					e.WasConnected = backendConnected
					e.WasLiveKitConnected = liveKitConnected
					events <- e
					terminal.TerminalStatus = "backend_ws_read_first_message_failed"
					terminal.TerminalStage = "backend_connect"
					terminal.ErrorCategory = terminal.TerminalStatus
					terminal.Error = e.Error
					terminal.ErrorMessage = e.Error
				}
				return
			}
			if msg["type"] == "error" {
				e := withKind(eventBase, "rejected")
				e.ListenerID = listenerID
				e.Error = fmt.Sprint(msg["payload"])
				events <- e
				terminal.TerminalStatus = "backend_rejected"
				terminal.TerminalStage = "backend_admission"
				terminal.Error = e.Error
				terminal.ErrorMessage = e.Error
				return
			}
			if msg["type"] == "connecting" {
				parsed, err := LiveKitConnectInfoFromConnecting(msg)
				if parsed.ListenerID != "" {
					listenerID = parsed.ListenerID
				}
				if mode != "backend-ws-only" {
					if err != nil {
						e := withKind(eventBase, "error")
						e.ListenerID = listenerID
						e.Error = err.Error()
						events <- e
						return
					}
					info = parsed
					e := withKind(eventBase, "worker_token_received")
					e.ListenerID = listenerID
					e.LiveKitURL = info.URL
					events <- e
				} else if p, ok := msg["payload"].(map[string]any); ok && listenerID == "" {
					listenerID = fmt.Sprint(p["listener_id"])
				}
				continue
			}
			if msg["type"] == "listener_state" {
				gotListenerState = true
				channelID, err := FirstListenableChannelID(msg)
				if err != nil {
					e := withKind(eventBase, "error")
					e.ListenerID = listenerID
					e.Error = err.Error()
					events <- e
					return
				}
				if !backendConnected {
					backendConnected = true
					backendConnectedFlag.Store(true)
					connectCancel()
					terminal.BackendConnected = true
					terminal.SelectedChannel = channelID
					e := withKind(eventBase, "worker_backend_connected")
					e.ListenerID = listenerID
					events <- e
					selectedChannel <- channelID
				}
				if mode != "backend-ws-only" && !liveKitConnected {
					if info.Token == "" {
						e := withKind(eventBase, "error")
						e.ListenerID = listenerID
						e.Error = "missing_livekit_token"
						events <- e
						return
					}
					if info.URL == "" {
						e := withKind(eventBase, "error")
						e.ListenerID = listenerID
						e.Error = "missing_livekit_url"
						events <- e
						return
					}
					e := withKind(eventBase, "worker_livekit_connecting")
					e.ListenerID = listenerID
					e.LiveKitURL = info.URL
					events <- e
					room, err := connector.Connect(ctx, info.URL, info.Token, livekitconn.Mode(mode), subscribeMode, channelID)
					if err != nil {
						e := withKind(eventBase, "worker_livekit_failed")
						e.ListenerID = listenerID
						e.LiveKitURL = info.URL
						e.Error = err.Error()
						events <- e
						return
					}
					liveKitConnected = true
					terminal.LiveKitConnected = true
					e = withKind(eventBase, "worker_livekit_connected")
					e.ListenerID = listenerID
					e.LiveKitURL = info.URL
					// Transport is intentionally unknown until PR47 adds SDK stats plumbing.
					e.Transport = "unknown"
					events <- e
					roomReady <- roomReadyEvent{room: room, listenerID: listenerID, livekitURL: info.URL}
				}
			}
			if mode != "backend-ws-only" && !gotListenerState && msg["type"] == "i18n_library" {
				continue
			}
		}
	}()
	var heartbeatChannel string
	backendConnectDone := connectCtx.Done()
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()
	defer func() {
		if livekitRoom != nil {
			livekitRoom.Disconnect()
		}
	}()
	for {
		select {
		case <-backendConnectDone:
			if ctx.Err() == nil && !backendConnectedFlag.Load() {
				e := withKind(eventBase, "worker_backend_first_message_timeout")
				e.Error = "backend_connect_timeout"
				events <- e
				terminal.TerminalStatus = "backend_connect_timeout"
				terminal.TerminalStage = "backend_connect"
				terminal.ErrorCategory = "backend_connect_timeout"
				terminal.Error = e.Error
				terminal.ErrorMessage = e.Error
				c.Close()
				return
			}
			backendConnectDone = nil
		case <-ctx.Done():
			terminal.TerminalStatus = "normal_shutdown"
			terminal.TerminalStage = "hold"
			terminal.NormalShutdown = true
			c.CloseNormal()
			if livekitRoom != nil {
				livekitRoom.Disconnect()
			}
			return
		case <-done:
			if terminal.TerminalStatus == "internal_error" {
				terminal.TerminalStatus = "completed"
				terminal.TerminalStage = "backend"
			}
			return
		case heartbeatChannel = <-selectedChannel:
		case ready := <-roomReady:
			livekitRoom = ready.room
			livekitDone = ready.room.Done()
			livekitEvents = ready.room.Events()
			livekitListenerID = ready.listenerID
			livekitURL = ready.livekitURL
			if mode == "livekit-subscribe-discard-rtp" {
				audioTrackTimer = time.After(30 * time.Second)
			}
		case le := <-livekitEvents:
			switch le.Kind {
			case "audio_track_subscribed":
				audioTrackReceived = true
				audioTrackTimer = nil
				e := withKind(eventBase, "worker_audio_track_subscribed")
				e.ListenerID = livekitListenerID
				e.LiveKitURL = livekitURL
				e.SelectedChannel = heartbeatChannel
				e.ParticipantIdentity = le.ParticipantIdentity
				e.ParticipantName = le.ParticipantName
				e.ParticipantMetadata = le.ParticipantMetadata
				e.TrackSID = le.TrackSID
				e.TrackName = le.TrackName
				e.TrackSource = le.TrackSource
				e.TrackKind = le.TrackKind
				events <- e
				terminal.AudioTrackSubscribed = true
			case "track_channel_unmatched":
				e := withKind(eventBase, "worker_track_channel_unmatched")
				e.ListenerID = livekitListenerID
				e.LiveKitURL = livekitURL
				e.SelectedChannel = heartbeatChannel
				e.ParticipantIdentity = le.ParticipantIdentity
				e.ParticipantName = le.ParticipantName
				e.ParticipantMetadata = le.ParticipantMetadata
				e.TrackSID = le.TrackSID
				e.TrackName = le.TrackName
				e.TrackSource = le.TrackSource
				e.TrackKind = le.TrackKind
				events <- e
			case "rtp_packet":
				e := withKind(eventBase, "worker_rtp_packet")
				e.ListenerID = livekitListenerID
				e.LiveKitURL = livekitURL
				e.RTPPackets = le.Packets
				e.RTPBytes = le.Bytes
				events <- e
				terminal.RTPReceived = true
			case "rtp_read_error":
				e := withKind(eventBase, "worker_rtp_read_error")
				e.ListenerID = livekitListenerID
				e.LiveKitURL = livekitURL
				e.Error = le.Error
				events <- e
			}
		case <-audioTrackTimer:
			if ctx.Err() == nil && !audioTrackReceived {
				e := withKind(eventBase, "worker_no_audio_track_timeout")
				e.ListenerID = livekitListenerID
				e.LiveKitURL = livekitURL
				e.Error = "no_audio_track"
				events <- e
				terminal.TerminalStatus = "no_audio_track_timeout"
				terminal.TerminalStage = "audio"
				terminal.Error = e.Error
				terminal.ErrorMessage = e.Error
			}
			return
		case <-livekitDone:
			if ctx.Err() == nil {
				e := withKind(eventBase, "worker_livekit_disconnected")
				e.ListenerID = livekitListenerID
				e.LiveKitURL = livekitURL
				e.Error = "livekit_disconnected"
				if livekitRoom != nil && livekitRoom.Err() != nil {
					e.Error = livekitRoom.Err().Error()
				}
				events <- e
				terminal.TerminalStatus = "livekit_disconnected"
				terminal.TerminalStage = "livekit"
				terminal.Error = e.Error
				terminal.ErrorMessage = e.Error
			}
			return
		case <-ticker.C:
			if heartbeatChannel == "" {
				continue
			}
			if err := c.WriteJSON(envelope("heartbeat", "heartbeat-"+wid, map[string]any{"client_role": "listener", "selected_channel": heartbeatChannel, "playback_state": "PLAYING"})); err != nil {
				e := withKind(eventBase, "heartbeat_failed")
				e.Error = err.Error()
				events <- e
			} else {
				events <- withKind(eventBase, "heartbeat_ok")
			}
		}
	}
}

func withKind(e Event, kind string) Event {
	e.Kind = kind
	return e
}
