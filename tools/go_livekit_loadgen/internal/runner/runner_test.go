package runner

import (
	"byod-loadgen/internal/backendws"
	"byod-loadgen/internal/config"
	"testing"
)

func TestActiveCounterDecreasesOnConnectedClose(t *testing.T) {
	r := &Runner{C: config.Config{Listeners: 1}, errs: map[string]int{}, workersWithAudioTrack: map[string]bool{}, workersWithRTP: map[string]bool{}}
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
	r := &Runner{C: config.Config{Listeners: 2, Mode: config.ModeBackendWSOnly}, errs: map[string]int{}, workersWithAudioTrack: map[string]bool{}, workersWithRTP: map[string]bool{}}
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
	r := &Runner{C: config.Config{Listeners: 2, Mode: config.ModeLiveKitConnectOnly}, errs: map[string]int{}, workersWithAudioTrack: map[string]bool{}, workersWithRTP: map[string]bool{}}
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

func TestAudioTrackAndRTPEventsCountUniqueWorkers(t *testing.T) {
	r := &Runner{C: config.Config{Listeners: 2, Mode: config.ModeLiveKitSubscribeDiscardRTP}, errs: map[string]int{}, workersWithAudioTrack: map[string]bool{}, workersWithRTP: map[string]bool{}}
	r.apply(backendws.Event{Kind: "worker_audio_track_subscribed", WorkerID: "w1"}, false)
	r.apply(backendws.Event{Kind: "worker_audio_track_subscribed", WorkerID: "w1"}, false)
	if r.counts.AudioTracksSubscribed != 2 {
		t.Fatalf("audio tracks subscribed = %d", r.counts.AudioTracksSubscribed)
	}
	if r.counts.WorkersWithAudioTrack != 1 {
		t.Fatalf("workers with audio = %d", r.counts.WorkersWithAudioTrack)
	}
	r.apply(backendws.Event{Kind: "worker_rtp_packet", WorkerID: "w1", RTPPackets: 2, RTPBytes: 20}, false)
	r.apply(backendws.Event{Kind: "worker_rtp_packet", WorkerID: "w1", RTPPackets: 3, RTPBytes: 30}, false)
	if r.counts.WorkersWithRTP != 1 {
		t.Fatalf("workers with rtp = %d", r.counts.WorkersWithRTP)
	}
	if r.counts.RTPPackets != 5 || r.counts.RTPBytes != 50 {
		t.Fatalf("rtp totals packets=%d bytes=%d", r.counts.RTPPackets, r.counts.RTPBytes)
	}
}

func TestGateCHoldRequiresAudioAndRTPActiveTargets(t *testing.T) {
	r := &Runner{C: config.Config{Listeners: 1, Mode: config.ModeLiveKitSubscribeDiscardRTP}, errs: map[string]int{}, workersWithAudioTrack: map[string]bool{}, workersWithRTP: map[string]bool{}}
	r.counts.RampDone = true
	r.counts.BackendActive = 1
	r.counts.LiveKitActive = 1
	r.counts.WorkersWithAudioTrack = 1
	if r.shouldStartHold() {
		t.Fatal("Gate C hold started before RTP target")
	}
	r.counts.WorkersWithRTP = 1
	if !r.shouldStartHold() {
		t.Fatal("Gate C hold did not start after audio and RTP targets")
	}
}

func TestConnectionRateLimitRejectIncrementsDedicatedCounter(t *testing.T) {
	r := &Runner{C: config.Config{Listeners: 1, Mode: config.ModeBackendWSOnly}, errs: map[string]int{}, workersWithAudioTrack: map[string]bool{}, workersWithRTP: map[string]bool{}}
	r.apply(backendws.Event{Kind: "rejected", WorkerID: "w1", Error: "CONNECTION_RATE_LIMIT"}, false)
	if r.counts.BackendRejected != 1 {
		t.Fatalf("backend rejected = %d", r.counts.BackendRejected)
	}
	if r.counts.BackendRejectedConnectionRateLimit != 1 {
		t.Fatalf("rate-limit rejects = %d", r.counts.BackendRejectedConnectionRateLimit)
	}
	r.apply(backendws.Event{Kind: "rejected", WorkerID: "w2", Error: "ROOM_FULL"}, false)
	if r.counts.BackendRejected != 2 {
		t.Fatalf("backend rejected after generic reject = %d", r.counts.BackendRejected)
	}
	if r.counts.BackendRejectedConnectionRateLimit != 1 {
		t.Fatalf("generic reject changed rate-limit rejects to %d", r.counts.BackendRejectedConnectionRateLimit)
	}
}
