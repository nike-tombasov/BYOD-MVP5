package runner

import (
	"byod-loadgen/internal/backendws"
	"byod-loadgen/internal/config"
	"byod-loadgen/internal/livekitconn"
	"byod-loadgen/internal/logjsonl"
	"byod-loadgen/internal/summary"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync/atomic"
	"time"
)

var moscow = time.FixedZone("MSK", 3*3600)

func TS() string {
	return time.Now().In(moscow).Truncate(100 * time.Millisecond).Format("2006-01-02T15:04:05.0-07:00")
}

type Runner struct {
	C                      config.Config
	target                 string
	counts                 summary.Counts
	firstFailure           string
	errs                   map[string]int
	workersWithAudioTrack  map[string]bool
	workersWithRTP         map[string]bool
	audioTracksByWorker    map[string]int
	finishedWorkers        map[string]bool
	failedTerminalWorkers  map[string]bool
	partialReasonOverride  string
	targetImpossibleAt     string
	targetImpossibleReason string
}

func New(c config.Config) (*Runner, error) {
	t, err := c.ListenerWSURL()
	if err != nil {
		return nil, err
	}
	return &Runner{C: c, target: t, errs: map[string]int{}, workersWithAudioTrack: map[string]bool{}, workersWithRTP: map[string]bool{}, audioTracksByWorker: map[string]int{}, finishedWorkers: map[string]bool{}, failedTerminalWorkers: map[string]bool{}}, nil
}
func (r *Runner) Run(ctx context.Context) error {
	if err := os.MkdirAll(r.C.OutDir, 0755); err != nil {
		return err
	}
	stamp := strings.ReplaceAll(strings.ReplaceAll(TS(), ":", ""), "+", "")
	evpath := filepath.Join(r.C.OutDir, "events_"+stamp+".jsonl")
	sumpath := filepath.Join(r.C.OutDir, "summary_"+stamp+".json")
	lg, err := logjsonl.New(evpath)
	if err != nil {
		return err
	}
	defer lg.Close()
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	events := make(chan backendws.Event, 1024)
	r.counts.LiveKitRequired = r.C.Mode == config.ModeLiveKitConnectOnly || r.C.Mode == config.ModeLiveKitSubscribeDiscardRTP
	r.counts.MediaRequired = r.C.Mode == config.ModeLiveKitSubscribeDiscardRTP
	var rampDone atomic.Bool
	go func() {
		defer rampDone.Store(true)
		launch := func(i int) {
			go backendws.RunWorker(ctx, r.target, r.C.RunnerID, r.C.LoadgenKey, i, r.C.Mode, r.C.SubscribeMode, r.C.BackendConnectTimeoutSec, livekitconn.SDKConnector{}, events)
		}
		if startAt, err := r.C.StartAtTime(time.Now()); err == nil {
			if wait := time.Until(startAt); wait > 0 {
				select {
				case <-ctx.Done():
					return
				case <-time.After(wait):
				}
			}
		}
		if r.C.StartMode == "burst" {
			for i := 1; i <= r.C.Listeners; {
				for n := 0; n < r.C.BurstSize && i <= r.C.Listeners; n++ {
					select {
					case <-ctx.Done():
						return
					default:
						launch(i)
						i++
					}
				}
				if i <= r.C.Listeners && r.C.BurstIntervalMS > 0 {
					time.Sleep(time.Duration(r.C.BurstIntervalMS) * time.Millisecond)
				}
			}
			return
		}
		delay := time.Second / time.Duration(r.C.RampPerSec)
		for i := 1; i <= r.C.Listeners; i++ {
			select {
			case <-ctx.Done():
				return
			default:
				launch(i)
				time.Sleep(delay)
			}
		}
	}()
	live := time.NewTicker(time.Second)
	defer live.Stop()
	holdCompleted := false
	holdStarted := false
	var holdStart time.Time
	var holdTimer <-chan time.Time
	var targetWaitStart time.Time
	for !holdCompleted {
		select {
		case <-ctx.Done():
			holdCompleted = false
			goto END
		case <-holdTimer:
			holdCompleted = true
			cancel()
		case e := <-events:
			r.apply(e, holdStarted)
			lg.Event(r.eventPayload(e))
			if !holdStarted && r.shouldStartHold() {
				holdStarted = true
				r.counts.BackendTargetReached = true
				if r.C.Mode == config.ModeLiveKitConnectOnly || r.C.Mode == config.ModeLiveKitSubscribeDiscardRTP {
					r.counts.LiveKitTargetReached = true
				}
				holdStart = time.Now()
				holdTimer = time.After(time.Duration(r.C.HoldSec) * time.Second)
			}
			if !holdStarted && r.targetCannotBeReached() {
				r.markTargetImpossible()
				cancel()
			}
		case <-live.C:
			r.counts.RampDone = rampDone.Load()
			if r.counts.RampDone && targetWaitStart.IsZero() {
				targetWaitStart = time.Now()
			}
			if !holdStarted && r.shouldStartHold() {
				holdStarted = true
				r.counts.BackendTargetReached = true
				if r.C.Mode == config.ModeLiveKitConnectOnly || r.C.Mode == config.ModeLiveKitSubscribeDiscardRTP {
					r.counts.LiveKitTargetReached = true
				}
				holdStart = time.Now()
				holdTimer = time.After(time.Duration(r.C.HoldSec) * time.Second)
			}
			if !holdStarted && r.targetCannotBeReached() {
				r.markTargetImpossible()
				cancel()
			}
			if !holdStarted && !targetWaitStart.IsZero() && time.Since(targetWaitStart) >= time.Duration(r.C.TargetWaitSec)*time.Second {
				r.partialReasonOverride = "target_wait_timeout"
				cancel()
			}
			fmt.Println(r.liveLine(holdStart, holdStarted))
		}
	}
END:
	time.Sleep(200 * time.Millisecond)
	drain := true
	for drain {
		select {
		case e := <-events:
			r.apply(e, holdStarted)
			lg.Event(r.eventPayload(e))
		default:
			drain = false
		}
	}
	r.counts.RampDone = rampDone.Load()
	r.counts.HoldCompleted = holdCompleted
	r.counts.WorkersWithoutTerminalEvent = r.workersWithoutTerminalEvent()
	r.counts.WorkersStartedOnly = r.workersStartedOnly()
	class := summary.Classify(r.requiredListeners(), r.counts)
	out := map[string]any{"ts_iso": TS(), "event": "summary", "mode": r.C.Mode, "profile": r.C.Profile, "server": r.C.Server, "subscribe_mode": r.C.SubscribeMode, "start_mode": r.C.StartMode, "selected_channel": "per-worker", "target_listeners": r.C.Listeners, "required_listeners": r.C.RequiredListeners, "exact_target": r.C.ExactTarget, "ramp_per_second": r.C.RampPerSec, "hold_requested": r.C.HoldSec, "hold_actual": holdElapsedSeconds(holdStart, holdStarted), "workers_started": r.counts.Started, "backend_connected": r.counts.BackendConnected, "backend_active": r.counts.BackendActive, "backend_rejected": r.counts.BackendRejected, "backend_rejected_connection_rate_limit": r.counts.BackendRejectedConnectionRateLimit, "backend_closed": r.counts.BackendClosed, "livekit_connected": r.counts.LiveKitConnected, "livekit_active": r.counts.LiveKitActive, "livekit_failed": r.counts.LiveKitFailed, "livekit_disconnected": r.counts.LiveKitDisconnected, "audio_tracks_subscribed": r.counts.AudioTracksSubscribed, "unexpected_extra_audio_tracks": r.counts.UnexpectedExtraAudioTracks, "track_channel_unmatched": r.counts.TrackChannelUnmatched, "audio_tracks_per_worker_min": r.audioTracksMin(), "audio_tracks_per_worker_max": r.audioTracksMax(), "audio_tracks_per_worker_avg": r.audioTracksAvg(), "workers_finished": r.counts.WorkersFinished, "workers_failed_terminal": r.counts.WorkersFailedTerminal, "workers_backend_connect_timeout": r.counts.WorkersBackendConnectTimeout, "workers_backend_ws_dial_failed": r.counts.WorkersBackendWSDialFailed, "workers_backend_first_message_failed": r.counts.WorkersBackendFirstMessageFailed, "workers_without_terminal_event": r.workersWithoutTerminalEvent(), "workers_started_only": r.workersStartedOnly(), "workers_terminal_error_top": r.topErrors(), "partial_reason": r.partialReason(holdCompleted), "target_impossible_at": r.targetImpossibleAt, "target_impossible_reason": r.targetImpossibleReason, "backend_pending": r.backendPending(), "livekit_pending": r.livekitPending(), "audio_pending": r.audioPending(), "rtp_pending": r.rtpPending(), "first_target_shortfall_stage": r.firstShortfallStage(), "backend_shortfall": maxInt(0, r.C.Listeners-r.counts.BackendConnected), "livekit_shortfall": maxInt(0, r.C.Listeners-r.counts.LiveKitConnected), "audio_shortfall": maxInt(0, r.C.Listeners-r.counts.WorkersWithAudioTrack), "rtp_shortfall": maxInt(0, r.C.Listeners-r.counts.WorkersWithRTP), "workers_with_audio_track": r.counts.WorkersWithAudioTrack, "workers_with_rtp": r.counts.WorkersWithRTP, "rtp_target_reached": r.counts.RTPTargetReached, "workers_without_audio_track": r.workersWithoutAudioTrack(), "rtp_packets": r.counts.RTPPackets, "rtp_bytes": r.counts.RTPBytes, "rtp_read_errors": r.counts.RTPReadErrors, "transport_udp": r.counts.TransportUDP, "transport_tcp": r.counts.TransportTCP, "transport_unknown": r.counts.TransportUnknown, "udp_tcp_ratio": r.udpTCPRatio(), "heartbeat_ok_count": r.counts.HeartbeatOK, "heartbeat_failed_count": r.counts.HeartbeatFailed, "first_failure_timestamp": r.firstFailure, "top_error_categories": r.topErrors(), "pass_classification": class, "events_path": evpath, "summary_path": sumpath}
	lg.Event(out)
	b, _ := json.MarshalIndent(out, "", "  ")
	if err := os.WriteFile(sumpath, b, 0644); err != nil {
		return err
	}
	fmt.Printf("\nFinal summary\n%s\n", string(b))
	return nil
}
func (r *Runner) apply(e backendws.Event, holdStarted bool) {
	switch e.Kind {
	case "started":
		r.counts.Started++
	case "connected", "worker_backend_connected":
		r.counts.BackendConnected++
		r.counts.BackendActive++
	case "rejected":
		r.counts.BackendRejected++
		if strings.Contains(e.Error, "CONNECTION_RATE_LIMIT") {
			r.counts.BackendRejectedConnectionRateLimit++
		}
		r.fail(e.Error)
	case "closed", "worker_closed":
		r.counts.BackendClosed++
		if e.WasConnected && r.counts.BackendActive > 0 {
			r.counts.BackendActive--
		}
		if e.WasLiveKitConnected && r.counts.LiveKitActive > 0 {
			r.counts.LiveKitActive--
			r.counts.LiveKitDisconnected++
			if holdStarted {
				r.counts.LiveKitDisconnectedDuringHold++
			}
		}
		if holdStarted {
			r.counts.BackendClosedDuringHold++
		}
		r.fail(e.Error)
	case "heartbeat_ok":
		r.counts.HeartbeatOK++
	case "worker_livekit_connected":
		r.counts.LiveKitConnected++
		r.counts.LiveKitActive++
		switch e.Transport {
		case "udp":
			r.counts.TransportUDP++
		case "tcp":
			r.counts.TransportTCP++
		default:
			r.counts.TransportUnknown++
		}
	case "worker_livekit_failed":
		r.counts.LiveKitFailed++
		r.fail(e.Error)
	case "worker_audio_track_subscribed":
		r.counts.AudioTracksSubscribed++
		if r.audioTracksByWorker == nil {
			r.audioTracksByWorker = map[string]int{}
		}
		r.audioTracksByWorker[e.WorkerID]++
		if r.audioTracksByWorker[e.WorkerID] > 1 {
			r.counts.UnexpectedExtraAudioTracks++
		}
		if !r.workersWithAudioTrack[e.WorkerID] {
			r.workersWithAudioTrack[e.WorkerID] = true
			r.counts.WorkersWithAudioTrack++
		}
	case "worker_track_channel_unmatched":
		r.counts.TrackChannelUnmatched++
	case "worker_finished":
		r.counts.WorkersFinished++
		if r.finishedWorkers == nil {
			r.finishedWorkers = map[string]bool{}
		}
		r.finishedWorkers[e.WorkerID] = true
		if e.TerminalStatus != "completed" && e.TerminalStatus != "normal_shutdown" {
			r.counts.WorkersFailedTerminal++
			if r.failedTerminalWorkers == nil {
				r.failedTerminalWorkers = map[string]bool{}
			}
			r.failedTerminalWorkers[e.WorkerID] = true
			switch e.TerminalStatus {
			case "backend_connect_timeout":
				r.counts.WorkersBackendConnectTimeout++
			case "backend_ws_dial_failed":
				r.counts.WorkersBackendWSDialFailed++
			case "backend_ws_read_first_message_failed":
				r.counts.WorkersBackendFirstMessageFailed++
			}
			r.fail(e.TerminalStatus)
		}
	case "worker_rtp_packet":
		r.counts.RTPPackets += e.RTPPackets
		r.counts.RTPBytes += e.RTPBytes
		if e.RTPPackets > 0 && !r.workersWithRTP[e.WorkerID] {
			r.workersWithRTP[e.WorkerID] = true
			r.counts.WorkersWithRTP++
		}
	case "worker_rtp_read_error":
		r.counts.RTPReadErrors++
		if holdStarted {
			r.counts.FatalSetupError = true
		}
		r.fail(e.Error)
	case "worker_no_audio_track_timeout":
		r.counts.WorkersWithoutAudioTrack++
		r.fail(e.Error)
	case "worker_livekit_disconnected":
		r.counts.LiveKitDisconnected++
		if r.counts.LiveKitActive > 0 {
			r.counts.LiveKitActive--
		}
		if holdStarted {
			r.counts.LiveKitDisconnectedDuringHold++
		}
		r.fail(e.Error)
	case "heartbeat_failed":
		r.counts.HeartbeatFailed++
		if holdStarted {
			r.counts.HeartbeatFailedDuringHold++
		}
		r.fail(e.Error)
	case "error":
		r.counts.Errors++
		r.counts.FatalSetupError = true
		r.fail(e.Error)
	}
}
func (r *Runner) fail(s string) {
	if r.firstFailure == "" {
		r.firstFailure = TS()
	}
	if s == "" {
		s = "unknown"
	}
	r.errs[s]++
}
func (r *Runner) topErrors() []string {
	xs := make([]string, 0, len(r.errs))
	for k, v := range r.errs {
		xs = append(xs, fmt.Sprintf("%s=%d", k, v))
	}
	sort.Strings(xs)
	if len(xs) > 5 {
		return xs[:5]
	}
	return xs
}
func (r *Runner) shouldStartHold() bool {
	required := r.requiredListeners()
	backendReady := r.counts.RampDone && r.counts.BackendActive >= required
	livekitReady := (r.C.Mode != config.ModeLiveKitConnectOnly && r.C.Mode != config.ModeLiveKitSubscribeDiscardRTP) || r.counts.LiveKitActive >= required
	audioReady := r.C.Mode != config.ModeLiveKitSubscribeDiscardRTP || r.counts.WorkersWithAudioTrack >= required
	rtpReady := r.C.Mode != config.ModeLiveKitSubscribeDiscardRTP || r.counts.WorkersWithRTP >= required
	if audioReady {
		r.counts.AudioTargetReached = true
	}
	if rtpReady {
		r.counts.RTPTargetReached = true
	}
	return backendReady && livekitReady && audioReady && rtpReady && !r.counts.FatalSetupError && r.counts.BackendRejected == 0 && r.counts.BackendClosed == 0 && r.counts.LiveKitFailed == 0
}

func (r *Runner) targetCannotBeReached() bool {
	baseFailure := r.counts.FatalSetupError || r.counts.BackendRejected > 0 || r.counts.BackendClosed > 0
	if r.C.Mode == config.ModeLiveKitConnectOnly || r.C.Mode == config.ModeLiveKitSubscribeDiscardRTP {
		baseFailure = baseFailure || r.counts.LiveKitFailed > 0 || r.counts.LiveKitDisconnected > 0
	}
	required := r.requiredListeners()
	return r.counts.RampDone && (baseFailure || r.counts.WorkersFailedTerminal > 0) && (r.counts.BackendConnected+r.backendPending() < required || ((r.C.Mode == config.ModeLiveKitConnectOnly || r.C.Mode == config.ModeLiveKitSubscribeDiscardRTP) && r.counts.LiveKitConnected+r.livekitPending() < required) || (r.C.Mode == config.ModeLiveKitSubscribeDiscardRTP && r.counts.WorkersWithAudioTrack+r.audioPending() < required) || (r.C.Mode == config.ModeLiveKitSubscribeDiscardRTP && r.counts.WorkersWithRTP+r.rtpPending() < required))
}

func holdElapsedSeconds(start time.Time, started bool) float64 {
	if !started {
		return 0
	}
	return time.Since(start).Seconds()
}

func (r *Runner) liveLine(holdStart time.Time, holdStarted bool) string {
	return fmt.Sprintf("ts_iso=%s mode=%s profile=%s target_listeners=%d target_ws=%s started=%d backend_active=%d backend_rejected=%d backend_closed=%d livekit_connected=%d livekit_failed=%d livekit_disconnected=%d transport_udp=%d transport_tcp=%d transport_unknown=%d udp_tcp_ratio=%s audio_tracks_subscribed=%d workers_with_audio_track=%d workers_with_rtp=%d workers_without_audio_track=%d rtp_target_reached=%t rtp_packets=%d rtp_bytes=%d rtp_read_errors=%d heartbeat_ok=%d heartbeat_failed=%d ramp_done=%t hold_elapsed=%.0fs errors_top=%v", TS(), r.C.Mode, r.C.Profile, r.C.Listeners, r.target, r.counts.Started, r.counts.BackendActive, r.counts.BackendRejected, r.counts.BackendClosed, r.counts.LiveKitConnected, r.counts.LiveKitFailed, r.counts.LiveKitDisconnected, r.counts.TransportUDP, r.counts.TransportTCP, r.counts.TransportUnknown, r.udpTCPRatio(), r.counts.AudioTracksSubscribed, r.counts.WorkersWithAudioTrack, r.counts.WorkersWithRTP, r.workersWithoutAudioTrack(), r.counts.RTPTargetReached, r.counts.RTPPackets, r.counts.RTPBytes, r.counts.RTPReadErrors, r.counts.HeartbeatOK, r.counts.HeartbeatFailed, r.counts.RampDone, holdElapsedSeconds(holdStart, holdStarted), r.topErrors())
}

func (r *Runner) eventPayload(e backendws.Event) map[string]any {
	return map[string]any{"ts_iso": TS(), "event": e.Kind, "runner_id": r.C.RunnerID, "worker_id": e.WorkerID, "worker_index": e.WorkerIndex, "mode": r.C.Mode, "profile": r.C.Profile, "listener_id": e.ListenerID, "livekit_url": e.LiveKitURL, "transport": e.Transport, "error": e.Error, "close_code": e.CloseCode, "rtp_packets": e.RTPPackets, "rtp_bytes": e.RTPBytes, "selected_channel": e.SelectedChannel, "terminal_status": e.TerminalStatus, "terminal_stage": e.TerminalStage, "error_category": e.ErrorCategory, "error_message": e.ErrorMessage, "elapsed_ms": e.ElapsedMS, "backend_connected": e.BackendConnected, "livekit_connected": e.LiveKitConnected, "audio_track_subscribed": e.AudioTrackSubscribed, "rtp_received": e.RTPReceived, "context_cancelled": e.ContextCancelled, "normal_shutdown": e.NormalShutdown, "participant_identity": e.ParticipantIdentity, "participant_name": e.ParticipantName, "participant_metadata": e.ParticipantMetadata, "track_sid": e.TrackSID, "track_name": e.TrackName, "track_source": e.TrackSource, "track_kind": e.TrackKind}
}

func (r *Runner) udpTCPRatio() string {
	if r.counts.TransportTCP == 0 {
		if r.counts.TransportUDP == 0 {
			return "n/a"
		}
		return "inf"
	}
	return fmt.Sprintf("%.2f", float64(r.counts.TransportUDP)/float64(r.counts.TransportTCP))
}

func (r *Runner) workersWithoutAudioTrack() int {
	if r.C.Mode != config.ModeLiveKitSubscribeDiscardRTP {
		return 0
	}
	missing := r.counts.LiveKitActive - r.counts.WorkersWithAudioTrack
	if missing < 0 {
		return 0
	}
	return missing
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
func (r *Runner) workersWithoutTerminalEvent() int {
	return maxInt(0, r.counts.Started-r.counts.WorkersFinished)
}
func (r *Runner) workersStartedOnly() int { return r.workersWithoutTerminalEvent() }
func (r *Runner) audioTracksMin() int {
	if len(r.audioTracksByWorker) == 0 {
		return 0
	}
	m := 1 << 30
	for _, v := range r.audioTracksByWorker {
		if v < m {
			m = v
		}
	}
	return m
}
func (r *Runner) audioTracksMax() int {
	m := 0
	for _, v := range r.audioTracksByWorker {
		if v > m {
			m = v
		}
	}
	return m
}
func (r *Runner) audioTracksAvg() float64 {
	if len(r.audioTracksByWorker) == 0 {
		return 0
	}
	total := 0
	for _, v := range r.audioTracksByWorker {
		total += v
	}
	return float64(total) / float64(len(r.audioTracksByWorker))
}
func (r *Runner) partialReason(holdCompleted bool) string {
	if r.partialReasonOverride != "" {
		return r.partialReasonOverride
	}
	if !holdCompleted {
		return "manual_or_context_cancelled"
	}
	if r.firstShortfallStage() != "" {
		return "target_shortfall"
	}
	return ""
}
func (r *Runner) firstShortfallStage() string {
	if r.counts.BackendConnected < r.C.Listeners {
		return "backend"
	}
	if (r.C.Mode == config.ModeLiveKitConnectOnly || r.C.Mode == config.ModeLiveKitSubscribeDiscardRTP) && r.counts.LiveKitConnected < r.C.Listeners {
		return "livekit"
	}
	if r.C.Mode == config.ModeLiveKitSubscribeDiscardRTP && r.counts.WorkersWithAudioTrack < r.C.Listeners {
		return "audio"
	}
	if r.C.Mode == config.ModeLiveKitSubscribeDiscardRTP && r.counts.WorkersWithRTP < r.C.Listeners {
		return "rtp"
	}
	return ""
}

func (r *Runner) requiredListeners() int {
	if r.C.RequiredListeners > 0 {
		return r.C.RequiredListeners
	}
	return r.C.Listeners
}
func (r *Runner) backendPending() int {
	return maxInt(0, r.counts.Started-r.counts.BackendConnected-r.counts.WorkersFailedTerminal)
}
func (r *Runner) livekitPending() int {
	if r.C.Mode == config.ModeBackendWSOnly {
		return 0
	}
	return maxInt(0, r.counts.BackendConnected-r.counts.LiveKitConnected-r.counts.LiveKitFailed-r.counts.LiveKitDisconnected)
}
func (r *Runner) audioPending() int {
	if r.C.Mode != config.ModeLiveKitSubscribeDiscardRTP {
		return 0
	}
	return maxInt(0, r.counts.LiveKitConnected-r.counts.WorkersWithAudioTrack-r.counts.WorkersWithoutAudioTrack)
}
func (r *Runner) rtpPending() int {
	if r.C.Mode != config.ModeLiveKitSubscribeDiscardRTP {
		return 0
	}
	return maxInt(0, r.counts.WorkersWithAudioTrack-r.counts.WorkersWithRTP-int(r.counts.RTPReadErrors))
}
func (r *Runner) markTargetImpossible() {
	if r.partialReasonOverride == "" {
		r.partialReasonOverride = "target_impossible_after_terminal_failure"
	}
	if r.targetImpossibleAt == "" {
		r.targetImpossibleAt = TS()
	}
	if r.targetImpossibleReason == "" {
		r.targetImpossibleReason = r.firstShortfallStage()
	}
}
