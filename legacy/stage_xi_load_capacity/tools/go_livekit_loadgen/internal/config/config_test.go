package config

import (
	"strings"
	"testing"
	"time"
)

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
	gateCArgs := append(baseArgs(ModeLiveKitSubscribeDiscardRTP), "-subscribe-mode", "all")
	if _, err := Parse(gateCArgs); err != nil {
		t.Fatalf("subscribe-mode all parse err %v", err)
	}
}

func TestStartAtNowStartsImmediately(t *testing.T) {
	c, err := Parse(baseArgs(ModeBackendWSOnly))
	if err != nil {
		t.Fatalf("parse err %v", err)
	}
	now := time.Date(2026, 6, 22, 19, 30, 0, 0, time.UTC)
	startAt, err := c.StartAtTime(now)
	if err != nil {
		t.Fatalf("start-at now err %v", err)
	}
	if !startAt.Equal(now) {
		t.Fatalf("start-at now = %s, want %s", startAt, now)
	}
}

func TestRFC3339StartAtWaitsUntilTimestamp(t *testing.T) {
	now := time.Date(2026, 6, 22, 19, 29, 0, 0, time.UTC)
	c := Config{StartAt: "2026-06-22T22:30:00+03:00"}
	startAt, err := c.StartAtTime(now)
	if err != nil {
		t.Fatalf("future start-at err %v", err)
	}
	if got := startAt.Sub(now); got != time.Minute {
		t.Fatalf("wait = %s, want 1m", got)
	}
}

func TestPastStartAtFailsValidation(t *testing.T) {
	past := time.Now().Add(-time.Hour).Format(time.RFC3339)
	args := append(baseArgs(ModeLiveKitConnectOnly), "-start-at", past)
	_, err := Parse(args)
	if err == nil || !strings.Contains(err.Error(), "in the past") {
		t.Fatalf("err = %v, want past start-at validation error", err)
	}
}

func TestStartModeStartAtRejected(t *testing.T) {
	args := append(baseArgs(ModeLiveKitConnectOnly), "-start-mode", "start-at", "-start-at", time.Now().Add(time.Hour).Format(time.RFC3339))
	_, err := Parse(args)
	if err == nil || !strings.Contains(err.Error(), `unsupported start-mode "start-at"`) {
		t.Fatalf("err = %v, want unsupported start-mode", err)
	}
}

func TestParseProofTargetAndTimeoutFlags(t *testing.T) {
	args := append(baseArgs(ModeBackendWSOnly), "-backend-connect-timeout-sec", "3", "-target-wait-sec", "7", "-required-listeners", "1", "-exact-target=false")
	c, err := Parse(args)
	if err != nil {
		t.Fatalf("parse err %v", err)
	}
	if c.BackendConnectTimeoutSec != 3 || c.TargetWaitSec != 7 || c.RequiredListeners != 1 || c.ExactTarget {
		t.Fatalf("unexpected config: %+v", c)
	}
}
