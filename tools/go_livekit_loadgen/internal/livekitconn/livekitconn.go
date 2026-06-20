package livekitconn

import (
	"bufio"
	"context"
	"crypto/rand"
	"crypto/sha1"
	"crypto/tls"
	"encoding/base64"
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
)

type Room interface {
	Disconnect()
}

type Connector interface {
	Connect(ctx context.Context, livekitURL, token string) (Room, error)
}

type ConnectorFunc func(ctx context.Context, livekitURL, token string) (Room, error)

func (f ConnectorFunc) Connect(ctx context.Context, livekitURL, token string) (Room, error) {
	return f(ctx, livekitURL, token)
}

type SDKConnector struct{}

type rawRoom struct {
	c net.Conn
}

func (r *rawRoom) Disconnect() { _ = r.c.Close() }

func (SDKConnector) Connect(ctx context.Context, livekitURL, token string) (Room, error) {
	// Minimal LiveKit signaling connect-only path for Gate B. It opens the room
	// signaling WebSocket with auto_subscribe=false and intentionally does not
	// subscribe, publish, decode audio, or read RTP. TODO(PR47 diagnostic
	// hardening): replace/augment this with SDK transport stats collection when
	// adding UDP/TCP candidate diagnostics.
	u, err := url.Parse(livekitURL)
	if err != nil {
		return nil, err
	}
	if u.Scheme == "http" {
		u.Scheme = "ws"
	} else if u.Scheme == "https" {
		u.Scheme = "wss"
	}
	u.Path = "/rtc"
	q := u.Query()
	q.Set("access_token", token)
	q.Set("auto_subscribe", "false")
	q.Set("sdk", "go")
	q.Set("version", "byod-loadgen")
	q.Set("protocol", "15")
	u.RawQuery = q.Encode()
	nc, br, err := websocketDial(ctx, u)
	if err != nil {
		return nil, err
	}
	room := &rawRoom{c: nc}
	go pumpControlFrames(br, nc)
	return room, nil
}

func websocketDial(ctx context.Context, u *url.URL) (net.Conn, *bufio.Reader, error) {
	host := u.Host
	if !strings.Contains(host, ":") {
		if u.Scheme == "wss" {
			host += ":443"
		} else {
			host += ":80"
		}
	}
	nc, err := (&net.Dialer{}).DialContext(ctx, "tcp", host)
	if err != nil {
		return nil, nil, err
	}
	if u.Scheme == "wss" {
		tlsConn := tls.Client(nc, &tls.Config{ServerName: u.Hostname()})
		if err := tlsConn.HandshakeContext(ctx); err != nil {
			nc.Close()
			return nil, nil, err
		}
		nc = tlsConn
	}
	keyb := make([]byte, 16)
	_, _ = rand.Read(keyb)
	key := base64.StdEncoding.EncodeToString(keyb)
	req := fmt.Sprintf("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n", u.RequestURI(), u.Host, key)
	if _, err := io.WriteString(nc, req); err != nil {
		nc.Close()
		return nil, nil, err
	}
	br := bufio.NewReader(nc)
	resp, err := http.ReadResponse(br, &http.Request{Method: "GET"})
	if err != nil {
		nc.Close()
		return nil, nil, err
	}
	h := sha1.New()
	h.Write([]byte(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))
	accept := base64.StdEncoding.EncodeToString(h.Sum(nil))
	if resp.StatusCode != 101 || resp.Header.Get("Sec-WebSocket-Accept") != accept {
		nc.Close()
		return nil, nil, fmt.Errorf("livekit websocket handshake failed: %s", resp.Status)
	}
	return nc, br, nil
}

func pumpControlFrames(br *bufio.Reader, nc net.Conn) {
	for {
		op, payload, err := readFrame(br)
		if err != nil {
			return
		}
		if op == 8 {
			_ = nc.Close()
			return
		}
		if op == 9 {
			_ = writeFrame(nc, 10, payload)
		}
	}
}

func readFrame(r *bufio.Reader) (byte, []byte, error) {
	h, err := r.ReadByte()
	if err != nil {
		return 0, nil, err
	}
	op := h & 0x0f
	b, err := r.ReadByte()
	if err != nil {
		return 0, nil, err
	}
	ln := int(b & 0x7f)
	if ln == 126 {
		var x [2]byte
		if _, err := io.ReadFull(r, x[:]); err != nil {
			return 0, nil, err
		}
		ln = int(binary.BigEndian.Uint16(x[:]))
	} else if ln == 127 {
		var x [8]byte
		if _, err := io.ReadFull(r, x[:]); err != nil {
			return 0, nil, err
		}
		ln = int(binary.BigEndian.Uint64(x[:]))
	}
	masked := b&0x80 != 0
	var mask [4]byte
	if masked {
		if _, err := io.ReadFull(r, mask[:]); err != nil {
			return 0, nil, err
		}
	}
	p := make([]byte, ln)
	if _, err := io.ReadFull(r, p); err != nil {
		return 0, nil, err
	}
	if masked {
		for i := range p {
			p[i] ^= mask[i%4]
		}
	}
	return op, p, nil
}

func writeFrame(c net.Conn, op byte, p []byte) error {
	hdr := []byte{0x80 | op}
	n := len(p)
	if n < 126 {
		hdr = append(hdr, byte(n))
	} else if n < 65536 {
		hdr = append(hdr, 126, byte(n>>8), byte(n))
	} else {
		hdr = append(hdr, 127)
		var b [8]byte
		binary.BigEndian.PutUint64(b[:], uint64(n))
		hdr = append(hdr, b[:]...)
	}
	_, err := c.Write(append(hdr, p...))
	return err
}
