package backendws

import "testing"

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
