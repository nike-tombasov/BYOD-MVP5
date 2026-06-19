package summary

type Counts struct {
	Started, BackendConnected, BackendRejected, BackendClosed, HeartbeatOK, HeartbeatFailed int
	RampDone, HoldCompleted                                                                 bool
}

func Classify(target int, c Counts) string {
	if target > 0 && c.Started >= target && c.BackendConnected >= target && c.BackendRejected == 0 && c.BackendClosed == 0 && c.HoldCompleted {
		return "VALID_RUN"
	}
	if c.Started > 0 || c.BackendConnected > 0 || c.BackendRejected > 0 || c.BackendClosed > 0 {
		return "PARTIAL_RUN"
	}
	return "INVALID_RUN"
}
