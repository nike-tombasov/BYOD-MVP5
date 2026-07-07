package livekitconn

import "testing"

func TestMatchTrackToSelectedChannel(t *testing.T) {
	if !MatchTrackToSelectedChannel(PublicationInfo{TrackName: "channel_1"}, "channel_1") {
		t.Fatal("track name did not match selected channel")
	}
	if MatchTrackToSelectedChannel(PublicationInfo{TrackName: "channel_2"}, "channel_1") {
		t.Fatal("wrong track matched selected channel")
	}
}
