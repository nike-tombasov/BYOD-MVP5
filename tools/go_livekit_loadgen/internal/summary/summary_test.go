package summary

import "testing"

func TestClassify(t *testing.T) {
	if got := Classify(2, Counts{Started: 2, BackendConnected: 2, HoldCompleted: true}); got != "VALID_RUN" {
		t.Fatal(got)
	}
	if got := Classify(2, Counts{Started: 1}); got != "PARTIAL_RUN" {
		t.Fatal(got)
	}
	if got := Classify(2, Counts{}); got != "INVALID_RUN" {
		t.Fatal(got)
	}
}
