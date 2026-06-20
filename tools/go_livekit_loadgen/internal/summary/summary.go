package summary

type Counts struct {
	Started, BackendConnected, BackendActive, BackendRejected, BackendClosed int
	HeartbeatOK, HeartbeatFailed, Errors                                     int
	RampDone, ActiveTargetReached, HoldCompleted                             bool
	BackendClosedDuringHold, HeartbeatFailedDuringHold                       int
	FatalSetupError                                                          bool
}

func Classify(target int, c Counts) string {
	if target > 0 && c.Started >= target && c.ActiveTargetReached && c.HoldCompleted && c.BackendRejected == 0 && c.BackendClosedDuringHold == 0 && c.HeartbeatFailedDuringHold == 0 && !c.FatalSetupError {
		return "VALID_RUN"
	}
	if c.Started > 0 || c.BackendConnected > 0 || c.BackendActive > 0 || c.BackendRejected > 0 || c.BackendClosed > 0 || c.Errors > 0 {
		return "PARTIAL_RUN"
	}
	return "INVALID_RUN"
}
