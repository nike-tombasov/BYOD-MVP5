package livekitconn

import (
	"context"
	"fmt"
	"io"
	"sync"
	"sync/atomic"
	"time"

	lksdk "github.com/livekit/server-sdk-go/v2"
	"github.com/pion/webrtc/v4"
)

type Mode string

const (
	ModeConnectOnly         Mode = "livekit-connect-only"
	ModeSubscribeDiscardRTP Mode = "livekit-subscribe-discard-rtp"
)

type Event struct {
	Kind    string
	Packets int64
	Bytes   int64
	Error   string
}

type Room interface {
	Disconnect()
	Done() <-chan struct{}
	Err() error
	Events() <-chan Event
}

type Connector interface {
	Connect(ctx context.Context, livekitURL, token string, mode Mode) (Room, error)
}

type ConnectorFunc func(ctx context.Context, livekitURL, token string, mode Mode) (Room, error)

func (f ConnectorFunc) Connect(ctx context.Context, livekitURL, token string, mode Mode) (Room, error) {
	return f(ctx, livekitURL, token, mode)
}

type SDKConnector struct{}

type sdkRoom struct {
	room      *lksdk.Room
	done      chan struct{}
	events    chan Event
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
func (r *sdkRoom) Events() <-chan Event  { return r.events }

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

func (SDKConnector) Connect(ctx context.Context, livekitURL, token string, mode Mode) (Room, error) {
	wrapped := &sdkRoom{done: make(chan struct{}), events: make(chan Event, 64)}
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
	if mode == ModeSubscribeDiscardRTP {
		cb.ParticipantCallback.OnTrackSubscribed = func(track *webrtc.TrackRemote, _ *lksdk.RemoteTrackPublication, _ *lksdk.RemoteParticipant) {
			if track.Kind() != webrtc.RTPCodecTypeAudio {
				return
			}
			select {
			case wrapped.events <- Event{Kind: "audio_track_subscribed"}:
			default:
			}
			go discardRTP(wrapped, track)
		}
	}
	opts := []lksdk.ConnectOption{lksdk.WithConnectTimeout(30 * time.Second)}
	if mode == ModeConnectOnly {
		opts = append(opts, lksdk.WithAutoSubscribe(false))
	}
	room, err := lksdk.ConnectToRoomWithToken(livekitURL, token, cb, opts...)
	if err != nil {
		return nil, err
	}
	wrapped.room = room
	return wrapped, nil
}

func discardRTP(room *sdkRoom, track *webrtc.TrackRemote) {
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	var packets int64
	var bytes int64
	flush := func() {
		if packets == 0 && bytes == 0 {
			return
		}
		e := Event{Kind: "rtp_packet", Packets: packets, Bytes: bytes}
		packets, bytes = 0, 0
		select {
		case room.events <- e:
		default:
		}
	}
	for {
		select {
		case <-room.done:
			flush()
			return
		case <-ticker.C:
			flush()
		default:
		}
		pkt, _, err := track.ReadRTP()
		if err != nil {
			flush()
			if err != io.EOF {
				select {
				case room.events <- Event{Kind: "rtp_read_error", Error: err.Error()}:
				default:
				}
			}
			return
		}
		packets++
		bytes += int64(pkt.MarshalSize())
	}
}
