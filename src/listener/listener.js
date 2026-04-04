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

function clearPlayback() {
  if (!player.paused) {
    player.pause();
  }
  player.srcObject = null;
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
    clearPlayback();
    return;
  }

  const track = trackByChannel.get(selectedChannel);
  if (!track) {
    log(`selected channel=${selectedChannel} has no subscribed track yet`);
    clearPlayback();
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
  return publication?.trackName || publication?.track?.name || publication?.trackSid || publication?.name || null;
}

function toArrayFromCollection(collection) {
  if (!collection) return [];
  if (Array.isArray(collection)) return collection;
  if (typeof collection.values === 'function') return Array.from(collection.values());
  if (typeof collection.forEach === 'function') {
    const items = [];
    collection.forEach((value) => items.push(value));
    return items;
  }
  if (typeof collection === 'object') return Object.values(collection);
  return [];
}

function getRemoteParticipants() {
  return toArrayFromCollection(room?.remoteParticipants);
}

function getAudioPublications(participant) {
  const candidates = [
    ...toArrayFromCollection(participant?.trackPublications),
    ...toArrayFromCollection(participant?.audioTrackPublications),
    ...toArrayFromCollection(participant?.tracks),
    ...toArrayFromCollection(participant?.audioTracks),
  ];

  const filtered = [];
  for (const publication of candidates) {
    if (!publication) continue;
    const kind = publication?.kind || publication?.track?.kind;
    if (kind === LivekitClient.Track.Kind.Audio) {
      filtered.push(publication);
      continue;
    }

    const trackName = getTrackName(publication);
    if (trackName && trackName.startsWith('channel_')) {
      filtered.push(publication);
      continue;
    }

    if (publication?.isSubscribed !== undefined && typeof publication?.setSubscribed === 'function') {
      filtered.push(publication);
    }
  }

  const uniq = new Map();
  for (const publication of filtered) {
    const key = publication?.trackSid || publication?.sid || getTrackName(publication) || `pub_${uniq.size}`;
    if (!uniq.has(key)) {
      uniq.set(key, publication);
    }
  }

  return Array.from(uniq.values());
}

function safeSetSubscribed(publication, shouldSubscribe) {
  if (!publication || typeof publication.setSubscribed !== 'function') {
    log(`setSubscribed skipped: no setSubscribed, track=${getTrackName(publication)}`);
    return;
  }

  try {
    publication.setSubscribed(shouldSubscribe);
  } catch (error) {
    log(`setSubscribed error: ${error.message}`);
  }
}

async function reconcileSubscribeState() {
  if (!room) return;
  const participants = getRemoteParticipants();
  log(`reconcileSubscribeState participants=${participants.length}`);

  for (const participant of participants) {
    const publications = getAudioPublications(participant);
    log(`participant=${participant?.identity} audioPublications=${publications.length}`);

    for (const publication of publications) {
      const trackName = getTrackName(publication);
      const shouldSubscribe = selectedChannel !== null && trackName === selectedChannel;
      log(`setSubscribed(${shouldSubscribe}) participant=${participant?.identity} track=${trackName}`);
      safeSetSubscribed(publication, shouldSubscribe);
    }
  }
}

async function applySelectiveSubscribe() {
  if (!room) {
    log('applySelectiveSubscribe skipped: room is null');
    return;
  }

  log(`applySelectiveSubscribe selectedChannel=${selectedChannel}`);
  await reconcileSubscribeState();

  if (!selectedChannel) {
    trackByChannel.clear();
    clearPlayback();
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
      clearPlayback();
    }
  });

  room.on(LivekitClient.RoomEvent.TrackPublished, (publication, participant) => {
    log(`TrackPublished participant=${participant?.identity} track=${getTrackName(publication)}`);
    applySelectiveSubscribe().catch((error) => log(`applySelectiveSubscribe error: ${error.message}`));
  });

  room.on(LivekitClient.RoomEvent.TrackUnpublished, (publication, participant) => {
    log(`TrackUnpublished participant=${participant?.identity} track=${getTrackName(publication)}`);
    const trackName = getTrackName(publication);
    if (trackName) {
      trackByChannel.delete(trackName);
    }
    attachCurrentTrack();
  });

  room.on(LivekitClient.RoomEvent.ParticipantConnected, (participant) => {
    log(`ParticipantConnected participant=${participant?.identity}`);
    applySelectiveSubscribe().catch((error) => log(`applySelectiveSubscribe error: ${error.message}`));
  });

  room.on(LivekitClient.RoomEvent.ParticipantDisconnected, (participant) => {
    log(`ParticipantDisconnected participant=${participant?.identity}`);
    applySelectiveSubscribe().catch((error) => log(`applySelectiveSubscribe error: ${error.message}`));
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
