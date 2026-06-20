package runner

import (
	"byod-loadgen/internal/backendws"
	"byod-loadgen/internal/config"
	"testing"
)

func TestActiveCounterDecreasesOnConnectedClose(t *testing.T) {
	r := &Runner{C: config.Config{Listeners: 1}, errs: map[string]int{}}
	r.apply(backendws.Event{Kind: "worker_backend_connected", WorkerID: "w1"}, false)
	if r.counts.BackendActive != 1 {
		t.Fatalf("active after connect = %d", r.counts.BackendActive)
	}
	r.apply(backendws.Event{Kind: "worker_closed", WorkerID: "w1", WasConnected: true, Error: "close"}, true)
	if r.counts.BackendActive != 0 {
		t.Fatalf("active after close = %d", r.counts.BackendActive)
	}
	if r.counts.BackendClosedDuringHold != 1 {
		t.Fatalf("closed during hold = %d", r.counts.BackendClosedDuringHold)
	}
}

func TestShouldStartHoldRequiresActiveTarget(t *testing.T) {
	r := &Runner{C: config.Config{Listeners: 2, Mode: config.ModeBackendWSOnly}, errs: map[string]int{}}
	r.counts.RampDone = true
	r.counts.Started = 2
	r.counts.BackendConnected = 2
	r.counts.BackendActive = 1
	if r.shouldStartHold() {
		t.Fatal("hold started before active target was reached")
	}
	r.counts.BackendActive = 2
	if !r.shouldStartHold() {
		t.Fatal("hold did not start after active target was reached")
	}
}

func TestGateBHoldRequiresBackendAndLiveKitActiveTargets(t *testing.T) {
	r := &Runner{C: config.Config{Listeners: 2, Mode: config.ModeLiveKitConnectOnly}, errs: map[string]int{}}
	r.counts.RampDone = true
	r.counts.BackendActive = 2
	r.counts.LiveKitActive = 1
	if r.shouldStartHold() {
		t.Fatal("Gate B hold started before LiveKit active target")
	}
	r.counts.LiveKitActive = 2
	if !r.shouldStartHold() {
		t.Fatal("Gate B hold did not start after backend and LiveKit active targets")
	}
}
