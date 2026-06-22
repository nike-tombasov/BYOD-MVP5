package backendws

import (
	"bufio"
	"context"
	"crypto/sha1"
	"encoding/base64"
	"fmt"
	"net"
	"net/http"
	"testing"
	"time"
)

func TestFirstListenableChannelID(t *testing.T) {
	got, err := FirstListenableChannelID(map[string]any{
		"payload": map[string]any{
			"channels": []any{
				map[string]any{"channel_id": "floor", "listen": false},
				map[string]any{"channel_id": "ru", "listen": true},
				map[string]any{"channel_id": "en", "listen": true},
			},
		},
	})
	if err != nil {
		t.Fatalf("unexpected err %v", err)
	}
	if got != "ru" {
		t.Fatalf("got %q", got)
	}
}

func TestFirstListenableChannelIDRejectsMissingListenableChannel(t *testing.T) {
	_, err := FirstListenableChannelID(map[string]any{
		"payload": map[string]any{
			"channels": []any{
				map[string]any{"channel_id": "floor", "listen": false},
				map[string]any{"channel_id": "", "listen": true},
			},
		},
	})
	if err == nil || err.Error() != "no_listenable_channel" {
		t.Fatalf("unexpected err %v", err)
	}
}

func TestLiveKitConnectInfoFromConnectingMissingFields(t *testing.T) {
	_, err := LiveKitConnectInfoFromConnecting(map[string]any{"payload": map[string]any{"livekit_url": "ws://lk"}})
	if err == nil || err.Error() != "missing_livekit_token" {
		t.Fatalf("unexpected token err %v", err)
	}
	_, err = LiveKitConnectInfoFromConnecting(map[string]any{"payload": map[string]any{"token": "t"}})
	if err == nil || err.Error() != "missing_livekit_url" {
		t.Fatalf("unexpected url err %v", err)
	}
}

func TestBackendConnectTimeoutEmitsTerminalWithoutOSTimeout(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer ln.Close()
	done := make(chan struct{})
	go func() {
		defer close(done)
		conn, err := ln.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		br := bufio.NewReader(conn)
		req, err := http.ReadRequest(br)
		if err != nil {
			return
		}
		key := req.Header.Get("Sec-WebSocket-Key")
		h := sha1.New()
		h.Write([]byte(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))
		accept := base64.StdEncoding.EncodeToString(h.Sum(nil))
		_, _ = fmt.Fprintf(conn, "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n", accept)
		time.Sleep(2 * time.Second)
	}()

	events := make(chan Event, 16)
	start := time.Now()
	RunWorker(context.Background(), "ws://"+ln.Addr().String()+"/ws/listener", "r", "k", 1, "backend-ws-only", "selected", 1, nil, events)
	if time.Since(start) > 1500*time.Millisecond {
		t.Fatalf("backend timeout waited too long: %s", time.Since(start))
	}
	var finished Event
	for len(events) > 0 {
		e := <-events
		if e.Kind == "worker_finished" {
			finished = e
		}
	}
	if finished.TerminalStatus != "backend_connect_timeout" || finished.TerminalStage != "backend_connect" || finished.ErrorCategory != "backend_connect_timeout" {
		t.Fatalf("unexpected terminal event: %+v", finished)
	}
}
