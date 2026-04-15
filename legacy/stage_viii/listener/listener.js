const backendUrl = (new URLSearchParams(location.search).get('backend')) || 'ws://127.0.0.1:8000/ws/listener';

let backendWs = null;
let room = null;
let currentState = null;
let previousRoomStatus = null;
let i18nLibrary = null;
let wsMode = 'unknown'; // unknown | schema | legacy

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

const languageContext = {
  detectedRaw: 'unknown',
  candidates: [],
  uiLanguage: 'en',
};

function log(message) {
  console.log(`[listener] ${message}`);
  logEl.textContent = `[${new Date().toISOString()}] ${message}\n` + logEl.textContent;
}

function nowTs() {
  return Math.floor(Date.now() / 1000);
}

function normalizeLanguageTag(tag) {
  if (typeof tag !== 'string') return '';
  return tag.trim().replaceAll('_', '-').toLowerCase();
}

function languageBase(tag) {
  return normalizeLanguageTag(tag).split('-')[0] || '';
}

function initLanguageDetection() {
  const browserLanguages = [];

  if (Array.isArray(navigator.languages)) {
    browserLanguages.push(...navigator.languages);
  }
  if (typeof navigator.language === 'string') {
    browserLanguages.push(navigator.language);
  }

  const normalized = browserLanguages
    .map(normalizeLanguageTag)
    .filter((value) => value !== '');

  const candidates = [];
  const seen = new Set();

  for (const tag of normalized) {
    const base = languageBase(tag);
    for (const candidate of [tag, base]) {
      if (candidate && !seen.has(candidate)) {
        seen.add(candidate);
        candidates.push(candidate);
      }
    }
  }

  languageContext.candidates = candidates;

  if (candidates.length === 0) {
    languageContext.detectedRaw = 'unknown';
    log('language autodetect: detected=unknown');
    return;
  }

  languageContext.detectedRaw = candidates[0];
  log(`language autodetect: detected=${languageBase(candidates[0]) || 'unknown'}`);
}

function chooseUiLanguage(i18n) {
  const tags = new Set();

  const maps = [
    i18n?.room_name_i18n,
    i18n?.custom_status_text_blocked_i18n,
    i18n?.custom_status_text_closed_i18n,
  ];

  for (const map of maps) {
    if (!map || typeof map !== 'object') continue;
    for (const key of Object.keys(map)) {
      const normalized = normalizeLanguageTag(key);
      if (normalized) {
        tags.add(normalized);
      }
    }
  }

  for (const candidate of languageContext.candidates) {
    if (tags.has(candidate)) {
      languageContext.uiLanguage = languageBase(candidate) || 'en';
      log(`language autodetect: ui=${languageContext.uiLanguage}`);
      return;
    }
  }

  if (tags.has('en')) {
    languageContext.uiLanguage = 'en';
    log('language autodetect: ui=en');
    return;
  }

  const firstAvailable = tags.values().next().value;
  languageContext.uiLanguage = languageBase(firstAvailable || 'en') || 'en';
  log(`language autodetect: ui=${languageContext.uiLanguage}`);
}

function makeEnvelope(type, payload = {}) {
  return {
    type,
    schema_version: 1,
    ts: nowTs(),
    request_id: `${type}-${crypto.randomUUID()}`,
    payload,
  };
}

function getPayload(message) {
  if (message && typeof message.payload === 'object' && message.payload !== null) {
    return message.payload;
  }
  return message || {};
}

function resolveTextByUiLanguage(map, fallbackText = '') {
  if (!map || typeof map !== 'object') {
    return fallbackText;
  }

  const normalizedMap = new Map();
  Object.entries(map).forEach(([key, value]) => {
    if (typeof value === 'string' && value.trim() !== '') {
      normalizedMap.set(normalizeLanguageTag(key), value);
    }
  });

  const uiLang = languageContext.uiLanguage || 'en';

  if (normalizedMap.has(uiLang)) {
    return normalizedMap.get(uiLang);
  }

  if (normalizedMap.has('en')) {
    return normalizedMap.get('en');
  }

  const firstValue = normalizedMap.values().next().value;
  return firstValue || fallbackText;
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

function isRoomOpened() {
  return currentState?.room_status === 'OPENED';
}

function isRoomBlocked() {
  return currentState?.room_status === 'BLOCKED';
}

function isRoomClosed() {
  return currentState?.room_status === 'CLOSED';
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
    const shouldSubscribe = isRoomOpened() && selectedChannel !== null && trackName === selectedChannel;
    publication.setSubscribed(shouldSubscribe);
    log(`setSubscribed(${shouldSubscribe}) track=${trackName}`);
  }
}

async function attachSelectedIfPossible() {
  if (!selectedChannel || !isRoomOpened()) {
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

function getLocalizedRoomName(fallbackName) {
  return resolveTextByUiLanguage(i18nLibrary?.room_name_i18n, fallbackName || 'Room');
}

function getLocalizedStatusText(status, fallbackText) {
  if (status === 'BLOCKED') {
    return resolveTextByUiLanguage(i18nLibrary?.custom_status_text_blocked_i18n, fallbackText || 'BLOCKED');
  }
  if (status === 'CLOSED') {
    return resolveTextByUiLanguage(i18nLibrary?.custom_status_text_closed_i18n, fallbackText || 'CLOSED');
  }
  return '';
}

function enforceRoomStatusRules(state) {
  const nextStatus = state.room_status || 'OPENED';

  if (nextStatus === 'BLOCKED') {
    if (currentTrack || currentTrackName) {
      log('room_status BLOCKED: stop audio immediately, keep buttons clickable');
    }
    stopPlayback();
    syncSubscriptions();
    return;
  }

  if (nextStatus === 'CLOSED') {
    if (selectedChannel !== null || currentTrack || currentTrackName) {
      log('room_status CLOSED: stop audio, unpush current button, lock controls');
    }
    selectedChannel = null;
    stopPlayback();
    syncSubscriptions();
    return;
  }

  if (nextStatus === 'OPENED' && previousRoomStatus === 'BLOCKED' && selectedChannel) {
    log(`room_status OPENED after BLOCKED: resume selected channel=${selectedChannel}`);
    playbackState = 'WAITING';
    syncSubscriptions();
    attachSelectedIfPossible().catch((error) => {
      log(`resume attach error: ${error.message}`);
    });
  }
}

function renderState(state) {
  currentState = state;
  enforceRoomStatusRules(state);

  const roomName = getLocalizedRoomName(state.room_name || 'Room');
  roomNameEl.textContent = roomName;

  if (state.room_status && state.room_status !== 'OPENED') {
    statusBox.style.display = 'block';

    const hasOverride = typeof state.status_custom_text === 'string' && state.status_custom_text.trim() !== '';
    statusBox.textContent = hasOverride
      ? state.status_custom_text
      : getLocalizedStatusText(state.room_status, state.room_status);
  } else {
    statusBox.style.display = 'none';
    statusBox.textContent = '';
  }

  const allowedChannels = new Set((state.channels || []).filter((ch) => ch.listen).map((ch) => ch.channel_id));
  if (selectedChannel && !allowedChannels.has(selectedChannel)) {
    log(`forced stop, selected channel became hidden: ${selectedChannel}`);
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
    button.disabled = isRoomClosed();

    button.onclick = async () => {
      if (isRoomClosed()) {
        log('click ignored, room_status=CLOSED');
        return;
      }

      const nextAction = selectedChannel === channel.channel_id ? 'STOP' : 'PLAY';
      log(`button click action=${nextAction} channel=${channel.channel_id} current=${selectedChannel} playbackState=${playbackState}`);

      if (selectedChannel === channel.channel_id) {
        selectedChannel = null;
        syncSubscriptions();
        stopPlayback();
        renderState(currentState);
        return;
      }

      selectedChannel = channel.channel_id;
      playbackState = 'WAITING';
      renderState(currentState);
      syncSubscriptions();

      if (isRoomBlocked()) {
        log('room_status BLOCKED: keep highlighted button, no audio attach');
        return;
      }

      try {
        await attachSelectedIfPossible();
      } catch (error) {
        log(`attach error: ${error.message}`);
      }
    };

    buttonsEl.appendChild(button);
  }

  previousRoomStatus = state.room_status || null;
}

async function connectLiveKit(livekitUrl, token) {
  if (!isLiveKitReady()) {
    throw new Error('LiveKit client script is not loaded');
  }

  if (room) {
    await room.disconnect();
    room = null;
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
    if (trackName && selectedChannel === trackName && isRoomOpened()) {
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

    if (trackName && selectedChannel === trackName && isRoomOpened()) {
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
      playbackState = isRoomOpened() ? 'WAITING' : 'IDLE';
      if (isRoomOpened()) {
        await attachSelectedIfPossible();
      }
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
      playbackState = isRoomOpened() ? 'WAITING' : 'IDLE';
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

function markWsMode(message) {
  const hasSchema = typeof message?.schema_version === 'number';
  if (hasSchema && wsMode !== 'schema') {
    wsMode = 'schema';
    log('ws mode: schema');
    return;
  }
  if (!hasSchema && wsMode === 'unknown') {
    wsMode = 'legacy';
    log('ws mode: legacy');
  }
}

async function handleBackendMessage(msg) {
  const msgType = msg?.type;
  const payload = getPayload(msg);
  markWsMode(msg);
  log(`backend message type=${msgType}`);

  if (msgType === 'connected' && wsMode !== 'schema') {
    renderState(payload.state || msg.state || payload || {});
    try {
      await connectLiveKit(msg.livekit_url || payload.livekit_url, msg.token || payload.token);
    } catch (error) {
      log(`LiveKit connect failed: ${error.message}`);
    }
    return;
  }

  if (msgType === 'connecting' && payload.ok === true && payload.client_role === 'listener') {
    try {
      await connectLiveKit(payload.livekit_url, payload.token);
    } catch (error) {
      log(`LiveKit connect failed: ${error.message}`);
    }
    return;
  }

  if (msgType === 'i18n_library') {
    i18nLibrary = payload;
    chooseUiLanguage(i18nLibrary);
    log('i18n_library received');
    if (currentState) {
      renderState(currentState);
    }
    return;
  }

  if (msgType === 'listener_state') {
    renderState(payload);
    if (room) {
      syncSubscriptions();
      await attachSelectedIfPossible();
    }
    return;
  }

  if (msgType === 'state' && wsMode !== 'schema') {
    const statePayload = payload.channels ? payload : (msg.state || {});
    renderState(statePayload);
    if (room) {
      syncSubscriptions();
      await attachSelectedIfPossible();
    }
    return;
  }

  if (msgType === 'error') {
    log(`backend error code=${payload.code || msg.code || 'UNKNOWN'}`);
  }
}

async function connectBackend() {
  backendWs = new WebSocket(backendUrl);

  backendWs.onopen = () => {
    log(`backend websocket opened: ${backendUrl}`);
    backendWs.send(JSON.stringify(makeEnvelope('connecting', { client_role: 'listener' })));
  };

  backendWs.onmessage = async (event) => {
    try {
      const msg = JSON.parse(event.data);
      await handleBackendMessage(msg);
    } catch (error) {
      log(`backend message parse/handle error: ${error.message}`);
    }
  };

  backendWs.onclose = () => {
    log('Backend WS closed');
  };

  backendWs.onerror = (event) => {
    log(`Backend WS error: ${event.type}`);
  };
}

initLanguageDetection();
connectBackend().catch((error) => {
  log(`Fatal error: ${error.message}`);
});
