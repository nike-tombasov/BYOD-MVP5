package summary

type Counts struct {
	Started, BackendConnected, BackendActive, BackendRejected, BackendClosed int
	HeartbeatOK, HeartbeatFailed, Errors                                     int
	LiveKitConnected, LiveKitActive, LiveKitFailed, LiveKitDisconnected      int
	TransportUDP, TransportTCP, TransportUnknown                             int
	RampDone, BackendTargetReached, LiveKitTargetReached, HoldCompleted      bool
	BackendClosedDuringHold, HeartbeatFailedDuringHold                       int
	LiveKitDisconnectedDuringHold                                            int
	FatalSetupError                                                          bool
	LiveKitRequired                                                          bool
}

func Classify(target int, c Counts) string {
	livekitOK := !c.LiveKitRequired || c.LiveKitTargetReached
	livekitHoldOK := !c.LiveKitRequired || c.LiveKitDisconnectedDuringHold == 0
	if target > 0 && c.Started >= target && c.BackendTargetReached && livekitOK && c.HoldCompleted && c.BackendRejected == 0 && c.BackendClosedDuringHold == 0 && c.HeartbeatFailedDuringHold == 0 && livekitHoldOK && !c.FatalSetupError {
		return "VALID_RUN"
	}
	if c.Started > 0 || c.BackendConnected > 0 || c.BackendActive > 0 || c.BackendRejected > 0 || c.BackendClosed > 0 || c.Errors > 0 || c.LiveKitConnected > 0 || c.LiveKitFailed > 0 || c.LiveKitDisconnected > 0 {
		return "PARTIAL_RUN"
	}
	return "INVALID_RUN"
}
