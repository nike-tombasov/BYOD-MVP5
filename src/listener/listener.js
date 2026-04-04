const backendUrl = (new URLSearchParams(location.search).get('backend')) || 'ws://127.0.0.1:8000/ws/listener';

let backendWs = null;
let room = null;
let currentState = null;

let selectedChannel = null;
let playbackState = 'IDLE'; // IDLE | WAITING | PLAYING
let currentTrack = null;
let currentTrackName = null;

let detachInProgress = false;
let attachInProgress = false;
let opCounter = 0;

const publicationByChannel = new Map();
const trackByChannel = new Map();

const OP_TIMEOUT_MS = 1000;

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

function withTimeout(promise, ms) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(`timeout ${ms}ms`)), ms)),
  ]);
}

function getTrackName(publication) {
  return publication?.trackName || publication?.name || publication?.trackSid || null;
}

function getAudioPublications(participant) {
  const publications = [];

  if (participant?.trackPublications?.values) {
    for (const publication of participant.trackPublications.values()) {
      const kind = publication?.kind;
      if (kind === LivekitClient.Track.Kind.Audio || kind === 'audio') {
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

function clearPlayerAndTrack() {
  player.pause();
  player.srcObject = null;
  currentTrack = null;
  currentTrackName = null;
}

async function detachAction() {
  if (detachInProgress) {
    log('detachAction skipped: already detaching');
    return;
  }

  detachInProgress = true;
  const myOp = ++opCounter;
  try {
    await withTimeout((async () => {
      clearPlayerAndTrack();
    })(), OP_TIMEOUT_MS);

    if (myOp === opCounter) {
      if (!selectedChannel) {
        playbackState = 'IDLE';
      } else {
        playbackState = 'WAITING';
      }
    }
  } catch (error) {
    log(`detachAction failed: ${error.message}`);
    selectedChannel = null;
    playbackState = 'IDLE';
    clearPlayerAndTrack();
  } finally {
    detachInProgress = false;
  }
}

async function attachAction(channelId) {
  if (!channelId) {
    return;
  }

  if (attachInProgress) {
    log('attachAction skipped: already attaching');
    return;
  }

  const track = trackByChannel.get(channelId);
  if (!track) {
    log(`attachAction waiting: no track for channel=${channelId}`);
    playbackState = 'WAITING';
    return;
  }

  if (currentTrack === track && currentTrackName === channelId && playbackState === 'PLAYING') {
    log(`attachAction skipped: already attached channel=${channelId}`);
    return;
  }

  attachInProgress = true;
  const myOp = ++opCounter;
  try {
    await withTimeout((async () => {
      const mediaStream = new MediaStream([track.mediaStreamTrack]);
      player.srcObject = mediaStream;
      await player.play();
    })(), OP_TIMEOUT_MS);

    if (myOp === opCounter) {
      currentTrack = track;
      currentTrackName = channelId;
      playbackState = 'PLAYING';
      log(`attachAction done channel=${channelId}`);
    }
  } catch (error) {
    log(`attachAction failed: ${error.message}`);
    selectedChannel = null;
    playbackState = 'IDLE';
    clearPlayerAndTrack();
  } finally {
    attachInProgress = false;
  }
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
      if (!trackName) continue;

      publicationByChannel.set(trackName, publication);
      const shouldSubscribe = selectedChannel !== null && trackName === selectedChannel;
      publication.setSubscribed(shouldSubscribe);
      log(`setSubscribed(${shouldSubscribe}) track=${trackName} participant=${participant.identity}`);
    }
  }
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

  const listeningChannels = new Set((state.channels || []).filter((ch) => ch.listen).map((ch) => ch.channel_id));

  if (selectedChannel && (!listeningChannels.has(selectedChannel) || state.room_status === 'CLOSED' || state.room_status === 'BLOCKED')) {
    log(`forced stop because selected channel unavailable or room restricted: ${selectedChannel}`);
    selectedChannel = null;
    playbackState = 'IDLE';
    clearPlayerAndTrack();
    applySelectiveSubscribe().catch((error) => log(`applySelectiveSubscribe failed: ${error.message}`));
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

    button.onclick = () => onChannelButtonClick(channel.channel_id);
    buttonsEl.appendChild(button);
  }
}

async function onChannelButtonClick(channelId) {
  if (detachInProgress || attachInProgress) {
    log(`click ignored channel=${channelId}: operation in progress`);
    return;
  }

  if (currentState?.room_status && currentState.room_status !== 'OPENED') {
    log(`click ignored: room status is ${currentState.room_status}`);
    return;
  }

  log(`button click channel=${channelId} current=${selectedChannel} playbackState=${playbackState}`);

  if (selectedChannel === channelId) {
    // STOP ACTION
    selectedChannel = null;
    await applySelectiveSubscribe();
    await detachAction();
    renderState(currentState);
    return;
  }

  // PLAY ACTION
  selectedChannel = channelId;
  playbackState = 'WAITING';
  renderState(currentState);

  await detachAction();
  await applySelectiveSubscribe();
  await attachAction(channelId);
}

function scanExistingPublications() {
  if (!room) return;

  for (const participant of room.remoteParticipants.values()) {
    const publications = getAudioPublications(participant);
    for (const publication of publications) {
      const trackName = getTrackName(publication);
      if (!trackName) continue;
      publicationByChannel.set(trackName, publication);

      if (publication.track) {
        trackByChannel.set(trackName, publication.track);
      }
    }
  }

  log(`scanExistingPublications done: publications=${publicationByChannel.size} tracks=${trackByChannel.size}`);
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

  room.on(LivekitClient.RoomEvent.TrackSubscribed, async (track, publication) => {
    if (track.kind !== LivekitClient.Track.Kind.Audio) return;
    const trackName = getTrackName(publication);
    if (!trackName) return;

    log(`TrackSubscribed track=${trackName}`);
    trackByChannel.set(trackName, track);

    if (playbackState === 'WAITING' && selectedChannel === trackName) {
      await attachAction(trackName);
      renderState(currentState);
    }
  });

  room.on(LivekitClient.RoomEvent.TrackUnsubscribed, async (track, publication) => {
    if (track.kind !== LivekitClient.Track.Kind.Audio) return;
    const trackName = getTrackName(publication);
    if (!trackName) return;

    log(`TrackUnsubscribed track=${trackName}`);
    trackByChannel.delete(trackName);

    if (selectedChannel === trackName && currentTrackName === trackName) {
      playbackState = 'WAITING';
      await detachAction();
      await applySelectiveSubscribe();
      await attachAction(trackName);
      renderState(currentState);
    }
  });

  room.on(LivekitClient.RoomEvent.TrackPublished, async (publication, participant) => {
    const trackName = getTrackName(publication);
    log(`TrackPublished participant=${participant?.identity} track=${trackName}`);
    if (trackName) {
      publicationByChannel.set(trackName, publication);
    }
    await applySelectiveSubscribe();
  });

  room.on(LivekitClient.RoomEvent.TrackUnpublished, async (publication, participant) => {
    const trackName = getTrackName(publication);
    log(`TrackUnpublished participant=${participant?.identity} track=${trackName}`);
    if (!trackName) return;

    publicationByChannel.delete(trackName);
    trackByChannel.delete(trackName);

    if (selectedChannel === trackName) {
      playbackState = 'WAITING';
      await detachAction();
      renderState(currentState);
    }
  });

  await room.connect(livekitUrl, token);
  log('Connected to LiveKit');

  scanExistingPublications();
  await applySelectiveSubscribe();

  if (selectedChannel) {
    playbackState = 'WAITING';
    await attachAction(selectedChannel);
    renderState(currentState);
  }
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
        await applySelectiveSubscribe();
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
