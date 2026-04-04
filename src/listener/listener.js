const backendUrl = (new URLSearchParams(location.search).get('backend')) || 'ws://127.0.0.1:8000/ws/listener';

let backendWs = null;
let room = null;
let currentState = null;

let selectedChannel = null;
let playbackState = 'IDLE'; // IDLE | WAITING | PLAYING
let currentTrack = null;
let currentTrackName = null;

const publicationByChannel = new Map();
const trackByChannel = new Map();

const player = document.getElementById('player');
const roomNameEl = document.getElementById('roomName');
const buttonsEl = document.getElementById('buttons');
const statusBox = document.getElementById('statusBox');
const logEl = document.getElementById('log');

function log(message) {
  console.log(`[listener] ${message}`);
  logEl.textContent = `[${new Date().toISOString()}] ${message}\n` + logEl.textContent;
}

function isLiveKitReady() {
  return typeof window.LivekitClient !== 'undefined' && typeof LivekitClient.Room === 'function';
}

function listValues(collection) {
  if (!collection) return [];
  if (typeof collection.values === 'function') return Array.from(collection.values());
  if (Array.isArray(collection)) return collection;
  if (typeof collection === 'object') return Object.values(collection);
  return [];
}

function getTrackName(publication) {
  return publication?.trackName || publication?.name || publication?.trackSid || null;
}

function getParticipants() {
  return room ? listValues(room.remoteParticipants) : [];
}

function getAudioPublications(participant) {
  const raw = listValues(participant?.trackPublications);
  if (raw.length > 0) {
    return raw.filter((publication) => {
      const kind = publication?.kind;
      return kind === LivekitClient.Track.Kind.Audio || kind === 'audio';
    });
  }

  return listValues(participant?.audioTrackPublications);
}

function stopPlayback() {
  player.pause();
  player.srcObject = null;
  currentTrack = null;
  currentTrackName = null;
  playbackState = 'IDLE';
}

function cachePublication(publication) {
  const trackName = getTrackName(publication);
  if (!trackName) return null;

  publicationByChannel.set(trackName, publication);
  if (publication.track) {
    trackByChannel.set(trackName, publication.track);
  }

  return trackName;
}

function refreshPublicationsFromRoom() {
  for (const participant of getParticipants()) {
    for (const publication of getAudioPublications(participant)) {
      cachePublication(publication);
    }
  }
}

function syncSubscriptions() {
  if (!room) return;

  refreshPublicationsFromRoom();
  for (const [trackName, publication] of publicationByChannel.entries()) {
    const shouldSubscribe = selectedChannel !== null && trackName === selectedChannel;
    publication.setSubscribed(shouldSubscribe);
    log(`setSubscribed(${shouldSubscribe}) track=${trackName}`);
  }
}

async function attachSelectedIfPossible() {
  if (!selectedChannel) {
    return;
  }

  const publication = publicationByChannel.get(selectedChannel);
  const track = trackByChannel.get(selectedChannel) || publication?.track || null;

  if (!track) {
    playbackState = 'WAITING';
    log(`attach waiting channel=${selectedChannel}`);
    return;
  }

  if (currentTrack === track && currentTrackName === selectedChannel && playbackState === 'PLAYING') {
    return;
  }

  const mediaStream = new MediaStream([track.mediaStreamTrack]);
  player.pause();
  player.srcObject = mediaStream;
  await player.play();

  currentTrack = track;
  currentTrackName = selectedChannel;
  playbackState = 'PLAYING';
  log(`attach done channel=${selectedChannel}`);
}

function renderState(state) {
  currentState = state;
  roomNameEl.textContent = state.room_name || 'Room';

  if (state.room_status && state.room_status !== 'OPENED') {
    statusBox.style.display = 'block';
    statusBox.textContent = state.status_custom_text || state.room_status;
  } else {
    statusBox.style.display = 'none';
  }

  const allowedChannels = new Set((state.channels || []).filter((ch) => ch.listen).map((ch) => ch.channel_id));
  if (selectedChannel && (!allowedChannels.has(selectedChannel) || state.room_status === 'BLOCKED' || state.room_status === 'CLOSED')) {
    log(`forced stop channel=${selectedChannel}`);
    selectedChannel = null;
    syncSubscriptions();
    stopPlayback();
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
      if (currentState?.room_status && currentState.room_status !== 'OPENED') {
        log(`click ignored, room_status=${currentState.room_status}`);
        return;
      }

      log(`button click channel=${channel.channel_id} current=${selectedChannel} playbackState=${playbackState}`);

      if (selectedChannel === channel.channel_id) {
        // STOP ACTION
        selectedChannel = null;
        syncSubscriptions();
        stopPlayback();
        renderState(currentState);
        return;
      }

      // PLAY ACTION
      selectedChannel = channel.channel_id;
      playbackState = 'WAITING';
      renderState(currentState);
      syncSubscriptions();

      try {
        await attachSelectedIfPossible();
      } catch (error) {
        log(`attach error: ${error.message}`);
      }
    };

    buttonsEl.appendChild(button);
  }
}

async function connectLiveKit(livekitUrl, token) {
  if (!isLiveKitReady()) {
    throw new Error('LiveKit client script is not loaded');
  }

  room = new LivekitClient.Room({
    adaptiveStream: false,
    dynacast: false,
    autoSubscribe: false,
  });

  room.on(LivekitClient.RoomEvent.TrackPublished, async (publication, participant) => {
    const trackName = cachePublication(publication);
    log(`TrackPublished participant=${participant?.identity} track=${trackName}`);
    syncSubscriptions();
    if (trackName && selectedChannel === trackName) {
      await attachSelectedIfPossible();
    }
  });

  room.on(LivekitClient.RoomEvent.TrackSubscribed, async (track, publication) => {
    if (track.kind !== LivekitClient.Track.Kind.Audio) return;

    const trackName = cachePublication(publication);
    if (trackName) {
      trackByChannel.set(trackName, track);
      log(`TrackSubscribed track=${trackName}`);
    }

    if (trackName && selectedChannel === trackName) {
      await attachSelectedIfPossible();
    }
  });

  room.on(LivekitClient.RoomEvent.TrackUnsubscribed, async (track, publication) => {
    if (track.kind !== LivekitClient.Track.Kind.Audio) return;

    const trackName = getTrackName(publication);
    log(`TrackUnsubscribed track=${trackName}`);
    if (!trackName) return;

    trackByChannel.delete(trackName);
    if (selectedChannel === trackName && currentTrackName === trackName) {
      player.pause();
      player.srcObject = null;
      currentTrack = null;
      currentTrackName = null;
      playbackState = 'WAITING';
      await attachSelectedIfPossible();
    }
  });

  room.on(LivekitClient.RoomEvent.TrackUnpublished, (publication, participant) => {
    const trackName = getTrackName(publication);
    log(`TrackUnpublished participant=${participant?.identity} track=${trackName}`);
    if (!trackName) return;

    publicationByChannel.delete(trackName);
    trackByChannel.delete(trackName);
    if (selectedChannel === trackName && currentTrackName === trackName) {
      player.pause();
      player.srcObject = null;
      currentTrack = null;
      currentTrackName = null;
      playbackState = 'WAITING';
    }
  });

  room.on(LivekitClient.RoomEvent.ParticipantConnected, () => {
    refreshPublicationsFromRoom();
    syncSubscriptions();
  });

  room.on(LivekitClient.RoomEvent.ParticipantDisconnected, () => {
    refreshPublicationsFromRoom();
    syncSubscriptions();
  });

  await room.connect(livekitUrl, token);
  log('Connected to LiveKit');

  refreshPublicationsFromRoom();
  syncSubscriptions();
  await attachSelectedIfPossible();
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
      try {
        await connectLiveKit(msg.livekit_url, msg.token);
      } catch (error) {
        log(`LiveKit connect failed: ${error.message}`);
      }
      return;
    }

    if (msg.type === 'state') {
      renderState(msg.state);
      if (room) {
        syncSubscriptions();
        await attachSelectedIfPossible();
      }
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
