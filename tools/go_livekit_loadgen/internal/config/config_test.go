package config

import "testing"

func baseArgs(mode string) []string {
	return []string{"-profile", "local-direct", "-mode", mode, "-server", "http://127.0.0.1:8000", "-listeners", "1", "-ramp-per-sec", "1", "-hold-sec", "1", "-runner-id", "r", "-loadgen-key", "k"}
}

func TestParseAcceptsLiveKitConnectOnly(t *testing.T) {
	c, err := Parse(baseArgs(ModeLiveKitConnectOnly))
	if err != nil {
		t.Fatalf("unexpected err %v", err)
	}
	if c.Mode != ModeLiveKitConnectOnly {
		t.Fatalf("mode = %q", c.Mode)
	}
}

func TestParseRejectsGateC(t *testing.T) {
	_, err := Parse(baseArgs("livekit-subscribe-discard-rtp"))
	if err == nil || err.Error() != "mode livekit-subscribe-discard-rtp is documented but not implemented in this PR" {
		t.Fatalf("unexpected err %v", err)
	}
}

func TestListenerWSURL(t *testing.T) {
	c := Config{Profile: "vps-nginx", Mode: ModeBackendWSOnly, Server: "http://1.2.3.4", Listeners: 1, RampPerSec: 1, HoldSec: 1, RunnerID: "r", LoadgenKey: "k"}
	got, err := c.ListenerWSURL()
	if err != nil || got != "ws://1.2.3.4/ws/listener" {
		t.Fatalf("got %q err %v", got, err)
	}
}
