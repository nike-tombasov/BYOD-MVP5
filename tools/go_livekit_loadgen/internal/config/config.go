package config

import (
	"errors"
	"flag"
	"fmt"
	"net/url"
	"strings"
)

const (
	ModeBackendWSOnly      = "backend-ws-only"
	ModeLiveKitConnectOnly = "livekit-connect-only"
)

type Config struct {
	Profile, Mode, Server          string
	Listeners, RampPerSec, HoldSec int
	RunnerID, LoadgenKey, OutDir   string
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
	fs.StringVar(&c.RunnerID, "runner-id", "", "runner id")
	fs.StringVar(&c.LoadgenKey, "loadgen-key", "", "loadgen key")
	fs.StringVar(&c.OutDir, "out-dir", "./out", "output dir")
	if err := fs.Parse(args); err != nil {
		return c, err
	}
	return c, c.Validate()
}
func (c Config) Validate() error {
	switch c.Profile {
	case "local-direct", "vps-nginx":
	default:
		return fmt.Errorf("unsupported profile %q", c.Profile)
	}
	switch c.Mode {
	case ModeBackendWSOnly, ModeLiveKitConnectOnly:
	case "livekit-subscribe-discard-rtp":
		return errors.New("mode livekit-subscribe-discard-rtp is documented but not implemented in this PR")
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
		return errors.New("ramp-per-sec must be >= 1")
	}
	if c.HoldSec < 1 {
		return errors.New("hold-sec must be >= 1")
	}
	if strings.TrimSpace(c.RunnerID) == "" {
		return errors.New("runner-id is required")
	}
	if strings.TrimSpace(c.LoadgenKey) == "" {
		return errors.New("loadgen-key is required")
	}
	return nil
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
