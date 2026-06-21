package summary

type Counts struct {
	Started, BackendConnected, BackendActive, BackendRejected, BackendClosed int
	HeartbeatOK, HeartbeatFailed, Errors                                     int
	LiveKitConnected, LiveKitActive, LiveKitFailed, LiveKitDisconnected      int
	AudioTracksSubscribed, WorkersWithAudioTrack, WorkersWithoutAudioTrack   int
	RTPPackets, RTPBytes, RTPReadErrors                                      int64
	TransportUDP, TransportTCP, TransportUnknown                             int
	RampDone, BackendTargetReached, LiveKitTargetReached, HoldCompleted      bool
	BackendClosedDuringHold, HeartbeatFailedDuringHold                       int
	LiveKitDisconnectedDuringHold                                            int
	FatalSetupError                                                          bool
	LiveKitRequired, MediaRequired, AudioTargetReached                       bool
}

func Classify(target int, c Counts) string {
	livekitOK := !c.LiveKitRequired || c.LiveKitTargetReached
	mediaOK := !c.MediaRequired || c.AudioTargetReached
	livekitHoldOK := !c.LiveKitRequired || c.LiveKitDisconnectedDuringHold == 0
	if target > 0 && c.Started >= target && c.BackendTargetReached && livekitOK && mediaOK && c.HoldCompleted && c.BackendRejected == 0 && c.BackendClosedDuringHold == 0 && c.HeartbeatFailedDuringHold == 0 && c.RTPReadErrors == 0 && livekitHoldOK && !c.FatalSetupError {
		return "VALID_RUN"
	}
	if c.Started > 0 || c.BackendConnected > 0 || c.BackendActive > 0 || c.BackendRejected > 0 || c.BackendClosed > 0 || c.Errors > 0 || c.LiveKitConnected > 0 || c.LiveKitFailed > 0 || c.LiveKitDisconnected > 0 || c.AudioTracksSubscribed > 0 || c.RTPPackets > 0 || c.RTPReadErrors > 0 {
		return "PARTIAL_RUN"
	}
	return "INVALID_RUN"
}
