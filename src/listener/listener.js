const backendUrl = (new URLSearchParams(location.search).get('backend')) || 'ws://127.0.0.1:8000/ws/listener';

let backendWs = null;
let room = null;
let selectedChannel = null;
let trackByChannel = new Map();

const player = document.getElementById('player');
const roomNameEl = document.getElementById('roomName');
const buttonsEl = document.getElementById('buttons');
const statusBox = document.getElementById('statusBox');
const logEl = document.getElementById('log');

function log(message) {
  logEl.textContent = `[${new Date().toISOString()}] ${message}\n` + logEl.textContent;
}

function renderState(state) {
  roomNameEl.textContent = state.room_name || 'Room';

  if (state.room_status && state.room_status !== 'OPENED') {
    statusBox.style.display = 'block';
    statusBox.textContent = state.status_custom_text || state.room_status;
  } else {
    statusBox.style.display = 'none';
  }

  buttonsEl.innerHTML = '';
  for (const channel of state.channels || []) {
    if (!channel.listen) continue;

    const button = document.createElement('button');
    button.className = 'btn';
    button.textContent = `${channel.channel_id} — ${channel.channel_label}`;
    if (selectedChannel === channel.channel_id) {
      button.classList.add('active');
    }

    button.onclick = async () => {
      if (selectedChannel === channel.channel_id) {
        selectedChannel = null;
      } else {
        selectedChannel = channel.channel_id;
      }
      renderState(state);
      await applySelectiveSubscribe();
      attachCurrentTrack();
    };

    buttonsEl.appendChild(button);
  }
}

function attachCurrentTrack() {
  if (!selectedChannel) {
    player.srcObject = null;
    return;
  }

  const track = trackByChannel.get(selectedChannel);
  if (!track) {
    return;
  }

  const mediaStream = new MediaStream([track.mediaStreamTrack]);
  player.srcObject = mediaStream;
  player.play().catch(() => {});
}

async function applySelectiveSubscribe() {
  if (!room) return;

  for (const participant of room.remoteParticipants.values()) {
    for (const publication of participant.audioTrackPublications.values()) {
      const shouldSubscribe = selectedChannel !== null && publication.trackName === selectedChannel;
      publication.setSubscribed(shouldSubscribe);
    }
  }

  if (!selectedChannel) {
    player.srcObject = null;
  }
}

async function connectLiveKit(livekitUrl, token) {
  room = new LivekitClient.Room({
    adaptiveStream: false,
    dynacast: false,
    autoSubscribe: false,
  });

  room.on(LivekitClient.RoomEvent.TrackSubscribed, async (track, publication) => {
    if (track.kind !== LivekitClient.Track.Kind.Audio) return;
    trackByChannel.set(publication.trackName, track);
    attachCurrentTrack();
  });

  room.on(LivekitClient.RoomEvent.TrackUnsubscribed, (track, publication) => {
    if (track.kind !== LivekitClient.Track.Kind.Audio) return;
    trackByChannel.delete(publication.trackName);
    if (publication.trackName === selectedChannel) {
      player.srcObject = null;
    }
  });

  room.on(LivekitClient.RoomEvent.TrackPublished, () => {
    applySelectiveSubscribe().catch(() => {});
  });

  await room.connect(livekitUrl, token);
  log('Connected to LiveKit');
  await applySelectiveSubscribe();
}

async function connectBackend() {
  backendWs = new WebSocket(backendUrl);

  backendWs.onopen = () => {
    backendWs.send(JSON.stringify({ type: 'connecting' }));
  };

  backendWs.onmessage = async (event) => {
    const msg = JSON.parse(event.data);

    if (msg.type === 'connected') {
      renderState(msg.state);
      await connectLiveKit(msg.livekit_url, msg.token);
      return;
    }

    if (msg.type === 'state') {
      renderState(msg.state);
      await applySelectiveSubscribe();
      return;
    }
  };

  backendWs.onclose = () => {
    log('Backend WS closed');
  };
}

connectBackend().catch((error) => {
  log(`Fatal error: ${error.message}`);
});
