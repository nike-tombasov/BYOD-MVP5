package runner

import (
	"byod-loadgen/internal/backendws"
	"byod-loadgen/internal/config"
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
	C            config.Config
	target       string
	counts       summary.Counts
	firstFailure string
	errs         map[string]int
}

func New(c config.Config) (*Runner, error) {
	t, err := c.ListenerWSURL()
	if err != nil {
		return nil, err
	}
	return &Runner{C: c, target: t, errs: map[string]int{}}, nil
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
	var rampDone atomic.Bool
	go func() {
		defer rampDone.Store(true)
		delay := time.Second / time.Duration(r.C.RampPerSec)
		for i := 1; i <= r.C.Listeners; i++ {
			select {
			case <-ctx.Done():
				return
			default:
				go backendws.RunWorker(ctx, r.target, r.C.RunnerID, r.C.LoadgenKey, i, events)
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
			lg.Event(map[string]any{"ts_iso": TS(), "event": e.Kind, "worker_id": e.WorkerID, "listener_id": e.ListenerID, "error": e.Error, "close_code": e.CloseCode})
			if !holdStarted && r.shouldStartHold() {
				holdStarted = true
				r.counts.ActiveTargetReached = true
				holdStart = time.Now()
				holdTimer = time.After(time.Duration(r.C.HoldSec) * time.Second)
			}
			if !holdStarted && r.targetCannotBeReached() {
				cancel()
			}
		case <-live.C:
			r.counts.RampDone = rampDone.Load()
			if !holdStarted && r.shouldStartHold() {
				holdStarted = true
				r.counts.ActiveTargetReached = true
				holdStart = time.Now()
				holdTimer = time.After(time.Duration(r.C.HoldSec) * time.Second)
			}
			if !holdStarted && r.targetCannotBeReached() {
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
			lg.Event(map[string]any{"ts_iso": TS(), "event": e.Kind, "worker_id": e.WorkerID, "error": e.Error})
		default:
			drain = false
		}
	}
	r.counts.RampDone = rampDone.Load()
	r.counts.HoldCompleted = holdCompleted
	class := summary.Classify(r.C.Listeners, r.counts)
	out := map[string]any{"ts_iso": TS(), "mode": r.C.Mode, "profile": r.C.Profile, "server": r.C.Server, "target_listeners": r.C.Listeners, "ramp_per_second": r.C.RampPerSec, "hold_requested": r.C.HoldSec, "hold_actual": holdElapsedSeconds(holdStart, holdStarted), "workers_started": r.counts.Started, "backend_connected": r.counts.BackendConnected, "backend_active": r.counts.BackendActive, "backend_rejected": r.counts.BackendRejected, "backend_closed": r.counts.BackendClosed, "heartbeat_ok_count": r.counts.HeartbeatOK, "heartbeat_failed_count": r.counts.HeartbeatFailed, "first_failure_timestamp": r.firstFailure, "top_error_categories": r.topErrors(), "pass_classification": class, "events_path": evpath, "summary_path": sumpath}
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
	case "connected":
		r.counts.BackendConnected++
		r.counts.BackendActive++
	case "rejected":
		r.counts.BackendRejected++
		r.fail(e.Error)
	case "closed":
		r.counts.BackendClosed++
		if e.WasConnected && r.counts.BackendActive > 0 {
			r.counts.BackendActive--
		}
		if holdStarted {
			r.counts.BackendClosedDuringHold++
		}
		r.fail(e.Error)
	case "heartbeat_ok":
		r.counts.HeartbeatOK++
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
	return r.counts.RampDone && r.counts.BackendActive >= r.C.Listeners && !r.counts.FatalSetupError && r.counts.BackendRejected == 0 && r.counts.BackendClosed == 0
}

func (r *Runner) targetCannotBeReached() bool {
	return r.counts.RampDone && (r.counts.FatalSetupError || r.counts.BackendRejected > 0 || r.counts.BackendClosed > 0) && r.counts.BackendActive < r.C.Listeners
}

func holdElapsedSeconds(start time.Time, started bool) float64 {
	if !started {
		return 0
	}
	return time.Since(start).Seconds()
}

func (r *Runner) liveLine(holdStart time.Time, holdStarted bool) string {
	return fmt.Sprintf("ts_iso=%s mode=%s profile=%s target_listeners=%d target_ws=%s started=%d backend_connected=%d backend_active=%d backend_rejected=%d backend_closed=%d heartbeat_ok=%d heartbeat_failed=%d ramp_done=%t hold_elapsed=%.0fs errors_top=%v transport_udp_tcp=n/a", TS(), r.C.Mode, r.C.Profile, r.C.Listeners, r.target, r.counts.Started, r.counts.BackendConnected, r.counts.BackendActive, r.counts.BackendRejected, r.counts.BackendClosed, r.counts.HeartbeatOK, r.counts.HeartbeatFailed, r.counts.RampDone, holdElapsedSeconds(holdStart, holdStarted), r.topErrors())
}
