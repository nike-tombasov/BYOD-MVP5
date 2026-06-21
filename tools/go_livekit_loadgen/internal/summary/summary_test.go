package summary

import "testing"

func TestClassifyGateA(t *testing.T) {
	if got := Classify(2, Counts{Started: 2, BackendConnected: 2, BackendActive: 2, BackendTargetReached: true, HoldCompleted: true}); got != "VALID_RUN" {
		t.Fatal(got)
	}
	if got := Classify(2, Counts{Started: 1}); got != "PARTIAL_RUN" {
		t.Fatal(got)
	}
	if got := Classify(2, Counts{}); got != "INVALID_RUN" {
		t.Fatal(got)
	}
}

func TestClassifyCannotBeValidBeforeActiveTargetReached(t *testing.T) {
	got := Classify(2, Counts{Started: 2, BackendConnected: 2, BackendActive: 1, HoldCompleted: true})
	if got == "VALID_RUN" {
		t.Fatal("cumulative connects produced VALID_RUN without active target")
	}
}

func TestClassifyGateBRequiresLiveKitTarget(t *testing.T) {
	got := Classify(2, Counts{Started: 2, BackendConnected: 2, BackendActive: 2, BackendTargetReached: true, HoldCompleted: true, LiveKitRequired: true, LiveKitConnected: 1, LiveKitActive: 1})
	if got == "VALID_RUN" {
		t.Fatal("Gate B produced VALID_RUN before LiveKit target")
	}
	got = Classify(2, Counts{Started: 2, BackendConnected: 2, BackendActive: 2, BackendTargetReached: true, LiveKitRequired: true, LiveKitConnected: 2, LiveKitActive: 2, LiveKitTargetReached: true, HoldCompleted: true})
	if got != "VALID_RUN" {
		t.Fatal(got)
	}
}

func TestClassifyRejectsHoldFailures(t *testing.T) {
	base := Counts{Started: 2, BackendConnected: 2, BackendActive: 2, BackendTargetReached: true, HoldCompleted: true}
	base.BackendClosedDuringHold = 1
	if got := Classify(2, base); got == "VALID_RUN" {
		t.Fatal("backend close during hold produced VALID_RUN")
	}
	base.BackendClosedDuringHold = 0
	base.HeartbeatFailedDuringHold = 1
	if got := Classify(2, base); got == "VALID_RUN" {
		t.Fatal("heartbeat failure during hold produced VALID_RUN")
	}
}

func TestClassifyGateCRequiresAudioTarget(t *testing.T) {
	got := Classify(2, Counts{Started: 2, BackendConnected: 2, BackendActive: 2, BackendTargetReached: true, LiveKitRequired: true, MediaRequired: true, LiveKitConnected: 2, LiveKitActive: 2, LiveKitTargetReached: true, HoldCompleted: true})
	if got == "VALID_RUN" {
		t.Fatal("Gate C produced VALID_RUN without audio target")
	}
	got = Classify(2, Counts{Started: 2, BackendConnected: 2, BackendActive: 2, BackendTargetReached: true, LiveKitRequired: true, MediaRequired: true, LiveKitConnected: 2, LiveKitActive: 2, LiveKitTargetReached: true, AudioTracksSubscribed: 2, WorkersWithAudioTrack: 2, AudioTargetReached: true, RTPPackets: 10, HoldCompleted: true})
	if got != "VALID_RUN" {
		t.Fatal(got)
	}
}

func TestClassifyGateCRejectsRTPReadErrors(t *testing.T) {
	got := Classify(1, Counts{Started: 1, BackendConnected: 1, BackendActive: 1, BackendTargetReached: true, LiveKitRequired: true, MediaRequired: true, LiveKitConnected: 1, LiveKitActive: 1, LiveKitTargetReached: true, AudioTracksSubscribed: 1, WorkersWithAudioTrack: 1, AudioTargetReached: true, RTPPackets: 1, RTPReadErrors: 1, HoldCompleted: true})
	if got == "VALID_RUN" {
		t.Fatal("Gate C produced VALID_RUN with RTP read errors")
	}
}
