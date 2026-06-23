package config

import (
	"os"
	"strings"
	"testing"
)

func TestPortableBuildScriptReferencesRussianInstructions(t *testing.T) {
	body, err := os.ReadFile("../../scripts/build_portable_windows.ps1")
	if err != nil {
		t.Fatalf("read build script: %v", err)
	}
	text := string(body)
	for _, want := range []string{"PORTABLE_RU.md", "run_a50_backend_now.bat", "run_b100_livekit_at_time.bat", "BYOD-Loadgen-Portable-Win64.zip"} {
		if !strings.Contains(text, want) {
			t.Fatalf("build script missing %q", want)
		}
	}
	if _, err := os.Stat("../../PORTABLE_RU.md"); err != nil {
		t.Fatalf("PORTABLE_RU.md missing: %v", err)
	}
}
