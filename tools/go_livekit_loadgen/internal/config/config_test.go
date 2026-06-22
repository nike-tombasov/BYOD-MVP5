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

func TestParseAcceptsGateC(t *testing.T) {
	c, err := Parse(baseArgs(ModeLiveKitSubscribeDiscardRTP))
	if err != nil {
		t.Fatalf("unexpected err %v", err)
	}
	if c.Mode != ModeLiveKitSubscribeDiscardRTP {
		t.Fatalf("mode = %q", c.Mode)
	}
}

func TestListenerWSURL(t *testing.T) {
	c := Config{Profile: "vps-nginx", Mode: ModeBackendWSOnly, Server: "http://1.2.3.4", Listeners: 1, RampPerSec: 1, HoldSec: 1, RunnerID: "r", LoadgenKey: "k"}
	got, err := c.ListenerWSURL()
	if err != nil || got != "ws://1.2.3.4/ws/listener" {
		t.Fatalf("got %q err %v", got, err)
	}
}

func TestParseStartModesAndSubscribeMode(t *testing.T) {
	burstArgs := append(baseArgs(ModeBackendWSOnly), "-start-mode", "burst", "-burst-size", "50", "-burst-interval-ms", "0")
	c, err := Parse(burstArgs)
	if err != nil {
		t.Fatalf("burst parse err %v", err)
	}
	if c.StartMode != "burst" || c.BurstSize != 50 || c.BurstIntervalMS != 0 {
		t.Fatalf("unexpected burst config: %+v", c)
	}
	startAtArgs := append(baseArgs(ModeLiveKitConnectOnly), "-start-mode", "start-at", "-start-at", "2026-06-22T20:15:00+03:00")
	if _, err := Parse(startAtArgs); err != nil {
		t.Fatalf("start-at parse err %v", err)
	}
	gateCArgs := append(baseArgs(ModeLiveKitSubscribeDiscardRTP), "-subscribe-mode", "all")
	if _, err := Parse(gateCArgs); err != nil {
		t.Fatalf("subscribe-mode all parse err %v", err)
	}
}
