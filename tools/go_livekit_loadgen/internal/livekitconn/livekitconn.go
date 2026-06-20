package livekitconn

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	lksdk "github.com/livekit/server-sdk-go/v2"
)

type Room interface {
	Disconnect()
	Done() <-chan struct{}
	Err() error
}

type Connector interface {
	Connect(ctx context.Context, livekitURL, token string) (Room, error)
}

type ConnectorFunc func(ctx context.Context, livekitURL, token string) (Room, error)

func (f ConnectorFunc) Connect(ctx context.Context, livekitURL, token string) (Room, error) {
	return f(ctx, livekitURL, token)
}

type SDKConnector struct{}

type sdkRoom struct {
	room      *lksdk.Room
	done      chan struct{}
	once      sync.Once
	mu        sync.Mutex
	err       error
	initiated atomic.Bool
}

func (r *sdkRoom) Disconnect() {
	r.initiated.Store(true)
	r.room.Disconnect()
	r.close(nil)
}

func (r *sdkRoom) Done() <-chan struct{} { return r.done }

func (r *sdkRoom) Err() error {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.err
}

func (r *sdkRoom) close(err error) {
	r.once.Do(func() {
		r.mu.Lock()
		r.err = err
		r.mu.Unlock()
		close(r.done)
	})
}

func (SDKConnector) Connect(ctx context.Context, livekitURL, token string) (Room, error) {
	wrapped := &sdkRoom{done: make(chan struct{})}
	cb := lksdk.NewRoomCallback()
	cb.OnDisconnected = func() {
		if wrapped.initiated.Load() {
			wrapped.close(nil)
			return
		}
		wrapped.close(fmt.Errorf("livekit_disconnected"))
	}
	cb.OnDisconnectedWithReason = func(reason lksdk.DisconnectionReason) {
		if wrapped.initiated.Load() {
			wrapped.close(nil)
			return
		}
		wrapped.close(fmt.Errorf("livekit_disconnected:%v", reason))
	}
	// Gate B is connect-only: no publishing, no media subscription, no audio
	// decoding, and no RTP reads. TODO(PR47 diagnostic hardening): collect
	// selected ICE candidate / transport stats if the SDK exposes them cleanly.
	room, err := lksdk.ConnectToRoomWithToken(
		livekitURL,
		token,
		cb,
		lksdk.WithAutoSubscribe(false),
		lksdk.WithConnectTimeout(30*time.Second),
	)
	if err != nil {
		return nil, err
	}
	wrapped.room = room
	return wrapped, nil
}
