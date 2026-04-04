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
  console.log(`[listener] ${message}`);
  logEl.textContent = `[${new Date().toISOString()}] ${message}\n` + logEl.textContent;
}

function renderState(state) {
  log(`renderState room=${state.room_name} status=${state.room_status}`);
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
      log(`button click channel=${channel.channel_id} current=${selectedChannel}`);
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
    log('no selected channel -> pause and clear player');
    player.pause();
    player.srcObject = null;
    return;
  }

  const track = trackByChannel.get(selectedChannel);
  if (!track) {
    log(`selected channel=${selectedChannel} has no subscribed track yet`);
    player.pause();
    player.srcObject = null;
    return;
  }

  const mediaStream = new MediaStream([track.mediaStreamTrack]);
  log(`attach and play channel=${selectedChannel}`);
  player.srcObject = mediaStream;
  player.play().catch((error) => {
    log(`player.play failed: ${error.message}`);
  });
}

function getTrackName(publication) {
  return publication?.trackName || publication?.trackSid || publication?.name || null;
}

function getAudioPublications(participant) {
  const publications = [];

  if (participant?.trackPublications?.values) {
    for (const publication of participant.trackPublications.values()) {
      if (publication?.kind === LivekitClient.Track.Kind.Audio) {
        publications.push(publication);
      }
    }
  }

  if (publications.length === 0 && participant?.audioTrackPublications?.values) {
    for (const publication of participant.audioTrackPublications.values()) {
      publications.push(publication);
    }
  }

  return publications;
}

async function applySelectiveSubscribe() {
  if (!room) {
    log('applySelectiveSubscribe skipped: room is null');
    return;
  }

  log(`applySelectiveSubscribe selectedChannel=${selectedChannel}`);

  for (const participant of room.remoteParticipants.values()) {
    const publications = getAudioPublications(participant);
    for (const publication of publications) {
      const trackName = getTrackName(publication);
      const shouldSubscribe = selectedChannel !== null && trackName === selectedChannel;
      log(`setSubscribed(${shouldSubscribe}) participant=${participant.identity} track=${trackName}`);
      publication.setSubscribed(shouldSubscribe);
    }
  }

  if (!selectedChannel) {
    player.pause();
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
    const trackName = getTrackName(publication);
    log(`TrackSubscribed track=${trackName}`);
    if (trackName) {
      trackByChannel.set(trackName, track);
    }
    attachCurrentTrack();
  });

  room.on(LivekitClient.RoomEvent.TrackUnsubscribed, (track, publication) => {
    if (track.kind !== LivekitClient.Track.Kind.Audio) return;
    const trackName = getTrackName(publication);
    log(`TrackUnsubscribed track=${trackName}`);
    if (trackName) {
      trackByChannel.delete(trackName);
    }
    if (trackName === selectedChannel) {
      player.pause();
      player.srcObject = null;
    }
  });

  room.on(LivekitClient.RoomEvent.TrackPublished, (publication, participant) => {
    log(`TrackPublished participant=${participant?.identity} track=${getTrackName(publication)}`);
    applySelectiveSubscribe().catch(() => {});
  });

  room.on(LivekitClient.RoomEvent.TrackUnpublished, (publication, participant) => {
    log(`TrackUnpublished participant=${participant?.identity} track=${getTrackName(publication)}`);
    const trackName = getTrackName(publication);
    if (trackName) {
      trackByChannel.delete(trackName);
    }
    attachCurrentTrack();
  });

  await room.connect(livekitUrl, token);
  log('Connected to LiveKit');
  await applySelectiveSubscribe();
}

async function connectBackend() {
  backendWs = new WebSocket(backendUrl);

  backendWs.onopen = () => {
    log(`backend websocket opened: ${backendUrl}`);
    backendWs.send(JSON.stringify({ type: 'connecting' }));
  };

  backendWs.onmessage = async (event) => {
    const msg = JSON.parse(event.data);
    log(`backend message type=${msg.type}`);

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

  backendWs.onerror = (event) => {
    log(`Backend WS error: ${event.type}`);
  };
}

connectBackend().catch((error) => {
  log(`Fatal error: ${error.message}`);
});
