package config

import (
	"errors"
	"flag"
	"fmt"
	"net/url"
	"strings"
	"time"
)

const (
	ModeBackendWSOnly              = "backend-ws-only"
	ModeLiveKitConnectOnly         = "livekit-connect-only"
	ModeLiveKitSubscribeDiscardRTP = "livekit-subscribe-discard-rtp"
)

type Config struct {
	Profile, Mode, Server                                      string
	Listeners, RampPerSec, HoldSec                             int
	RequiredListeners, BackendConnectTimeoutSec, TargetWaitSec int
	ExactTarget                                                bool
	RunnerID, LoadgenKey, OutDir                               string
	SubscribeMode, StartMode                                   string
	StartAt                                                    string
	BurstSize, BurstIntervalMS                                 int
}

func Parse(args []string) (Config, error) {
	var c Config
	fs := flag.NewFlagSet("byod-loadgen", flag.ContinueOnError)
	fs.StringVar(&c.Profile, "profile", "", "local-direct|vps-nginx")
	fs.StringVar(&c.Mode, "mode", "", "backend-ws-only")
	fs.StringVar(&c.Server, "server", "", "http://host[:port]")
	fs.IntVar(&c.Listeners, "listeners", 0, "target listeners")
	fs.IntVar(&c.RampPerSec, "ramp-per-sec", 0, "listeners per second")
	fs.IntVar(&c.HoldSec, "hold-sec", 0, "hold seconds")
	fs.IntVar(&c.BackendConnectTimeoutSec, "backend-connect-timeout-sec", 10, "backend connect/first-message timeout seconds")
	fs.IntVar(&c.TargetWaitSec, "target-wait-sec", 15, "seconds to wait for target after all workers launch")
	fs.IntVar(&c.RequiredListeners, "required-listeners", 0, "required listeners for HOLD; defaults to listeners")
	fs.BoolVar(&c.ExactTarget, "exact-target", true, "require full listeners target for official proof")
	fs.StringVar(&c.RunnerID, "runner-id", "", "runner id")
	fs.StringVar(&c.LoadgenKey, "loadgen-key", "", "loadgen key")
	fs.StringVar(&c.OutDir, "out-dir", "./out", "output dir")
	fs.StringVar(&c.SubscribeMode, "subscribe-mode", "selected", "selected|all")
	fs.StringVar(&c.StartAt, "start-at", "now", "when to start launching workers: now or RFC3339 timestamp")
	fs.StringVar(&c.StartMode, "start-mode", "ramp", "worker launch shape after start-at: ramp or burst")
	fs.IntVar(&c.BurstSize, "burst-size", 0, "workers per burst")
	fs.IntVar(&c.BurstIntervalMS, "burst-interval-ms", 1000, "milliseconds between bursts")
	if err := fs.Parse(args); err != nil {
		return c, err
	}
	return c, c.Validate()
}
func (c *Config) Validate() error {
	switch c.Profile {
	case "local-direct", "vps-nginx":
	default:
		return fmt.Errorf("unsupported profile %q", c.Profile)
	}
	switch c.Mode {
	case ModeBackendWSOnly, ModeLiveKitConnectOnly, ModeLiveKitSubscribeDiscardRTP:
	default:
		return fmt.Errorf("unsupported mode %q", c.Mode)
	}
	if _, err := url.ParseRequestURI(c.Server); err != nil {
		return fmt.Errorf("invalid server: %w", err)
	}
	if c.Listeners < 1 {
		return errors.New("listeners must be >= 1")
	}
	if c.RampPerSec < 1 {
		if c.StartMode == "ramp" {
			return errors.New("ramp-per-sec must be >= 1")
		}
		c.RampPerSec = 1
	}
	if c.SubscribeMode != "selected" && c.SubscribeMode != "all" {
		return fmt.Errorf("unsupported subscribe-mode %q", c.SubscribeMode)
	}
	if c.Mode != ModeLiveKitSubscribeDiscardRTP && c.SubscribeMode != "selected" {
		return errors.New("subscribe-mode is only valid for Gate C")
	}
	if _, err := c.StartAtTime(time.Now()); err != nil {
		return err
	}
	switch c.StartMode {
	case "ramp":
	case "burst":
		if c.BurstSize < 1 {
			return errors.New("burst-size must be >= 1")
		}
		if c.BurstIntervalMS < 0 {
			return errors.New("burst-interval-ms must be >= 0")
		}
	default:
		return fmt.Errorf("unsupported start-mode %q", c.StartMode)
	}
	if c.HoldSec < 1 {
		return errors.New("hold-sec must be >= 1")
	}
	if c.BackendConnectTimeoutSec < 1 {
		return errors.New("backend-connect-timeout-sec must be >= 1")
	}
	if c.TargetWaitSec < 1 {
		return errors.New("target-wait-sec must be >= 1")
	}
	if c.RequiredListeners == 0 {
		c.RequiredListeners = c.Listeners
	}
	if c.RequiredListeners < 1 || c.RequiredListeners > c.Listeners {
		return errors.New("required-listeners must be between 1 and listeners")
	}
	if c.ExactTarget && c.RequiredListeners != c.Listeners {
		return errors.New("required-listeners below listeners requires -exact-target=false")
	}
	if strings.TrimSpace(c.RunnerID) == "" {
		return errors.New("runner-id is required")
	}
	if strings.TrimSpace(c.LoadgenKey) == "" {
		return errors.New("loadgen-key is required")
	}
	return nil
}

func (c Config) StartAtTime(now time.Time) (time.Time, error) {
	if strings.EqualFold(strings.TrimSpace(c.StartAt), "now") {
		return now, nil
	}
	startAt, err := time.Parse(time.RFC3339, c.StartAt)
	if err != nil {
		return time.Time{}, fmt.Errorf("invalid start-at: use now or RFC3339 timestamp: %w", err)
	}
	if !startAt.After(now) {
		return time.Time{}, fmt.Errorf("start-at %s is in the past; choose a future RFC3339 timestamp or use now", c.StartAt)
	}
	return startAt, nil
}
func (c Config) ListenerWSURL() (string, error) {
	u, err := url.Parse(c.Server)
	if err != nil {
		return "", err
	}
	scheme := "ws"
	if u.Scheme == "https" {
		scheme = "wss"
	}
	return (&url.URL{Scheme: scheme, Host: u.Host, Path: "/ws/listener"}).String(), nil
}
