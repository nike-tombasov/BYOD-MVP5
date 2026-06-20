package backendws

import (
	"bufio"
	"context"
	"crypto/rand"
	"crypto/sha1"
	"crypto/tls"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type Event struct {
	Kind, WorkerID, ListenerID, Error string
	CloseCode                         int
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
func RunWorker(ctx context.Context, target, runnerID, key string, idx int, events chan<- Event) {
	wid := fmt.Sprintf("%s-L%04d", runnerID, idx)
	events <- Event{Kind: "started", WorkerID: wid}
	c, err := dial(ctx, target)
	if err != nil {
		events <- Event{Kind: "error", WorkerID: wid, Error: err.Error()}
		return
	}
	defer c.Close()
	payload := map[string]any{"client_role": "listener", "client_type": "load_runner", "runner_id": runnerID, "worker_id": wid, "worker_index": idx, "loadgen_key": key, "loadgen_mode": "backend-ws-only"}
	if err := c.WriteJSON(envelope("connecting", "connect-"+wid, payload)); err != nil {
		events <- Event{Kind: "error", WorkerID: wid, Error: err.Error()}
		return
	}
	done := make(chan struct{})
	go func() {
		defer close(done)
		for {
			var msg map[string]any
			if err := c.ReadJSON(&msg); err != nil {
				if ctx.Err() == nil {
					events <- Event{Kind: "closed", WorkerID: wid, Error: err.Error()}
				}
				return
			}
			if msg["type"] == "error" {
				events <- Event{Kind: "rejected", WorkerID: wid, Error: fmt.Sprint(msg["payload"])}
				return
			}
			if msg["type"] == "connecting" {
				if p, ok := msg["payload"].(map[string]any); ok {
					events <- Event{Kind: "connected", WorkerID: wid, ListenerID: fmt.Sprint(p["listener_id"])}
				}
			}
		}
	}()
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			c.CloseNormal()
			return
		case <-done:
			return
		case <-ticker.C:
			if err := c.WriteJSON(envelope("heartbeat", "heartbeat-"+wid, map[string]any{"client_role": "listener", "selected_channel": "", "playback_state": "IDLE"})); err != nil {
				events <- Event{Kind: "heartbeat_failed", WorkerID: wid, Error: err.Error()}
			} else {
				events <- Event{Kind: "heartbeat_ok", WorkerID: wid}
			}
		}
	}
}
