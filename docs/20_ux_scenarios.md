## 20. UX scenarios

### 20.1 Listener

Open page → visible of room name and channel buttons (if deployed backend exist), no sound.  
Click channel → channels sound, clicked button highlights.  
Switch channel → sound switches, button rehighlights to new one.  
Stop channel → silence, button unhighlights.  
System player pause (<60s) → silence, system player remains if browser/OS allows, selected channel button may remain highlighted; click highlighted button → sound resumes.
System player pause (≥60s expiry) → silence, system player clears if browser/OS allows, selected channel button unhighlights, no heartbeat; return to page may reconnect backend/LiveKit, but no sound until channel click.
System player play → best-effort local resume only before system-pause expiry; after expiry page interaction is required.
Publisher restart/change → auto recovery, no visible changes.
Publisher offline/STOP stream → silence, no visible changes.  
Page background with ACTIVE PLAY → sound should continue where browser/OS allows; system volume/player controls are best-effort; no visible page changes while playback remains active.  
Page background with stopped channel button → return after timeout → click → sound.  
Backend unavailable → CONNECTING (0-3s) / RETRYING (3-10s) / UNAVAILABLE (>10s) message shown.
Backend restored → availability message hides immediately.
Connection STALE (timeout/disconnect/expiry) → click channel button → reconnect → WAITING → sound on recovery.
System volume adjusting → sound volume changes.  
BLOCKED → no sound, appropriate language banner on top, buttons are clickable.  
CLOSED → no sound, button unhighlights, UI locked, appropriate language banner on top, buttons aren't clickable.  
BLOCKED → OPENED → sound from highlighted button channel, banner disappears.  
CLOSED → OPENED → no sound, buttons are clickable, UI available, banner disappears.

### 20.2 Publisher

Open Publisher UI → UI loads last IP, PIN, channel-device mapping (if exist), empty room name, room status, channel labels, actual channel statuses, UI locked except IP and PIN fields and CONNECT button.  
CONNECT push with wrong PIN → invalid PIN error, CONNECT button available.  
CONNECT push with valid PIN → IP and PIN fields (can be highlighted for copy) and CONNECT button locked, room name, room status, channel labels, actual channel statuses filled, audio device lists available.  
ON AIR push → button label changes to STOP, button color changes to yellow, channel status changes to Connecting...  
ON AIR backend approve → button color changes to red, channel status changes to STREAMING.  
STOP push → button label changes to ON AIR, button color changes to normal, channel status changes to Connecting...  
STOP backend approve → channel status changes to FREE.  
ENGAGE channel status → audio device channel list unavailable until gets to FREE channel status.  
Wrong audio device selected → ON AIR button unavailable and error status until no error audio device select.  
Audio device is None → ON AIR button unavailable, NO DEVICE error while mouse hover over ON AIR button.  
Network timeout drop → connection status Connection lost, ownership lost, all streaming stops.

### 20.3 Admin (to be updated)

change status  
change listen flag  
start recording
