package livekitconn

import (
	"context"
	"time"

	lksdk "github.com/livekit/server-sdk-go/v2"
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

func (SDKConnector) Connect(ctx context.Context, livekitURL, token string) (Room, error) {
	cb := lksdk.NewRoomCallback()
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
	return room, nil
}
