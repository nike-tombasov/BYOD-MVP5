package livekitconn

import (
	"strings"

	lksdk "github.com/livekit/server-sdk-go/v2"
)

type PublicationInfo struct {
	ParticipantIdentity string
	ParticipantName     string
	ParticipantMetadata string
	TrackSID            string
	TrackName           string
	TrackSource         string
	TrackKind           string
}

func PublicationInfoFromSDK(pub *lksdk.RemoteTrackPublication, rp *lksdk.RemoteParticipant) PublicationInfo {
	return PublicationInfo{ParticipantIdentity: rp.Identity(), ParticipantName: rp.Name(), ParticipantMetadata: rp.Metadata(), TrackSID: pub.SID(), TrackName: pub.Name(), TrackSource: pub.Source().String(), TrackKind: string(pub.Kind())}
}

func MatchTrackToSelectedChannel(info PublicationInfo, selectedChannel string) bool {
	selected := strings.TrimSpace(strings.ToLower(selectedChannel))
	if selected == "" {
		return false
	}
	candidates := []string{info.TrackName, info.ParticipantIdentity, info.ParticipantName, info.ParticipantMetadata}
	for _, candidate := range candidates {
		value := strings.ToLower(strings.TrimSpace(candidate))
		if value == selected || strings.Contains(value, selected) {
			return true
		}
	}
	return false
}
