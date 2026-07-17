const backendOverride = new URLSearchParams(location.search).get('backend');
const backendProtocol = location.protocol === 'https:' ? 'wss' : 'ws';
const backendDefaultUrl = `${backendProtocol}://${location.host}/ws/listener`;
const backendUrl = backendOverride || backendDefaultUrl;
const HEARTBEAT_INTERVAL_MS = 10_000;
const ATTACH_DETACH_TIMEOUT_MS = 1_000;
const RETRYING_RECONNECT_DELAY_MS = 3_000;
const UNAVAILABLE_RECONNECT_DELAY_MS = 10_000;

let backendWs = null;
let room = null;
let currentState = null;
let previousRoomStatus = null;
let i18nLibrary = null;
let immutableI18nFingerprint = null;
let pendingToken = null;
let pendingLivekitUrl = null;
let hasConnectingOk = false;
let hasI18nLibrary = false;
let hasListenerState = false;
let livekitConnected = false;
let suppressBackendCloseEvent = false;
let reconnectPromise = null;
let tokenGeneration = 0;
let activeToken = null;
let lastBackendActivityMs = Date.now();
let heartbeatIntervalId = null;
let connectionBannerIntervalId = null;
let backendUnavailableSinceMs = Date.now();
let autoRetryTimeoutId = null;
let reconnectAttemptCount = 0;
let reconnectSuccessCount = 0;
let reconnectFailureCount = 0;
let heartbeatSentCount = 0;
let i18nApplyCount = 0;
let i18nMismatchCount = 0;

const CONNECTION_STATE = {
  CONNECTED: 'CONNECTED',
  STALE: 'STALE',
  RECONNECTING: 'RECONNECTING',
};
let connectionState = CONNECTION_STATE.RECONNECTING;

let selectedChannel = null;
let playbackState = 'IDLE';
let currentTrack = null;
let currentTrackName = null;
let lastSelectedChannel = null;
let lastSystemResumeChannel = null;
let systemPausedChannel = null;
let attachInProgress = false;
let detachInProgress = false;

const publicationByChannel = new Map();
const trackByChannel = new Map();

const listenerDiagnostics = {
  mediaSessionSupported: false,
  mediaSessionHandlersRegistered: {},
  mediaSessionLastAction: null,
  lastPlaybackEvent: null,
  lastPlaybackError: null,
  lastVisibilityState: document.visibilityState,
};

const player = document.getElementById('player');
const roomNameEl = document.getElementById('roomName');
const buttonsEl = document.getElementById('buttons');
const connectionBox = document.getElementById('connectionBox');
const statusBox = document.getElementById('statusBox');
const logEl = document.getElementById('log');

const languageContext = { detectedRaw: 'unknown', candidates: [], uiLanguage: 'en' };

function log(message) {
  console.log(`[listener] ${message}`);
  logEl.textContent = `[${new Date().toISOString()}] ${message}\n` + logEl.textContent;
}

function updateDiagnosticsSnapshot() {
  window.__listenerDiagnostics = {
    connectionState,
    reconnectAttemptCount,
    reconnectSuccessCount,
    reconnectFailureCount,
    heartbeatSentCount,
    i18nApplyCount,
    i18nMismatchCount,
    sdkSource: window.__livekitSdkSource || 'unknown',
    lastBackendActivityMs,
    mediaSessionSupported: listenerDiagnostics.mediaSessionSupported,
    mediaSessionHandlersRegistered: listenerDiagnostics.mediaSessionHandlersRegistered,
    mediaSessionLastAction: listenerDiagnostics.mediaSessionLastAction,
    lastSystemResumeChannel,
    systemPausedChannel,
    playbackState,
    lastPlaybackEvent: listenerDiagnostics.lastPlaybackEvent,
    lastPlaybackError: listenerDiagnostics.lastPlaybackError,
    lastVisibilityState: listenerDiagnostics.lastVisibilityState,
  };
}

function detectClientEnvironment() {
  const ua = navigator.userAgent || 'unknown';
  const platform = navigator.platform || 'unknown';
  const isMobile = /android|iphone|ipad|ipod|mobile/i.test(ua);
  return { ua, platform, isMobile };
}

function nowTs() { return Math.floor(Date.now() / 1000); }

function makeRequestIdSuffix() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function') {
    return globalThis.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isBackendWsOpen() {
  return backendWs && backendWs.readyState === WebSocket.OPEN;
}

function noteBackendActivity(source) {
  lastBackendActivityMs = Date.now();
  updateDiagnosticsSnapshot();
  log(`backend activity source=${source}`);
}

function hasActivePlayRequest() {
  return selectedChannel !== null && playbackState !== 'IDLE';
}

function hasAudioOpInProgress() {
  return attachInProgress || detachInProgress;
}

function getAvailabilityText(elapsedMs) {
  if (elapsedMs < 3_000) return 'Connecting...';
  if (elapsedMs < 10_000) return 'Trying to reconnect...';
  return 'Unable to connect. Waiting for service...';
}

function refreshConnectionBanner() {
  if (connectionState === CONNECTION_STATE.CONNECTED) {
    backendUnavailableSinceMs = null;
    connectionBox.style.display = 'none';
    connectionBox.textContent = '';
    return;
  }

  if (backendUnavailableSinceMs === null) {
    backendUnavailableSinceMs = Date.now();
  }
  const elapsedMs = Math.max(0, Date.now() - backendUnavailableSinceMs);
  connectionBox.style.display = 'block';
  connectionBox.textContent = getAvailabilityText(elapsedMs);
}

function startConnectionBannerLoop() {
  if (connectionBannerIntervalId) return;
  connectionBannerIntervalId = setInterval(refreshConnectionBanner, 500);
  refreshConnectionBanner();
}

function clearAutoRetryTimer() {
  if (!autoRetryTimeoutId) return;
  clearTimeout(autoRetryTimeoutId);
  autoRetryTimeoutId = null;
}

function scheduleAutoRetry(reason) {
  if (connectionState === CONNECTION_STATE.CONNECTED) return;
  if (autoRetryTimeoutId) return;
  if (reconnectPromise) return;
  const unavailableElapsed = backendUnavailableSinceMs === null ? 0 : Date.now() - backendUnavailableSinceMs;
  const delayMs = unavailableElapsed >= 10_000 ? UNAVAILABLE_RECONNECT_DELAY_MS : RETRYING_RECONNECT_DELAY_MS;
  log(`auto-retry scheduled in ${delayMs}ms reason=${reason}`);
  autoRetryTimeoutId = setTimeout(() => {
    autoRetryTimeoutId = null;
    reconnectListener(`auto-retry:${reason}`).catch((error) => log(`reconnect error: ${error.message}`));
  }, delayMs);
}

function runWithTimeout(promiseFactory, timeoutMs, timeoutLabel) {
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      reject(new Error(timeoutLabel));
    }, timeoutMs);

    Promise.resolve()
      .then(() => promiseFactory())
      .then((result) => {
        clearTimeout(timeoutId);
        resolve(result);
      })
      .catch((error) => {
        clearTimeout(timeoutId);
        reject(error);
      });
  });
}

function makeEnvelope(type, payload = {}) {
  return { type, schema_version: 1, ts: nowTs(), request_id: `${type}-${makeRequestIdSuffix()}`, payload };
}

function normalizeLanguageTag(tag) {
  if (typeof tag !== 'string') return '';
  return tag.trim().replaceAll('_', '-').toLowerCase();
}

function languageBase(tag) { return normalizeLanguageTag(tag).split('-')[0] || ''; }

function initLanguageDetection() {
  const browserLanguages = [];
  if (Array.isArray(navigator.languages)) browserLanguages.push(...navigator.languages);
  if (typeof navigator.language === 'string') browserLanguages.push(navigator.language);

  const normalized = browserLanguages.map(normalizeLanguageTag).filter((value) => value !== '');
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
  const maps = [i18n?.room_name_i18n, i18n?.custom_status_text_blocked_i18n, i18n?.custom_status_text_closed_i18n];
  for (const map of maps) {
    if (!map || typeof map !== 'object') continue;
    for (const key of Object.keys(map)) {
      const normalized = normalizeLanguageTag(key);
      if (normalized) tags.add(normalized);
    }
  }

  for (const candidate of languageContext.candidates) {
    if (tags.has(candidate)) {
      languageContext.uiLanguage = languageBase(candidate) || 'en';
      log(`language autodetect: ui=${languageContext.uiLanguage}`);
      return;
    }
  }

  languageContext.uiLanguage = tags.has('en') ? 'en' : languageBase(tags.values().next().value || 'en');
  log(`language autodetect: ui=${languageContext.uiLanguage}`);
}

function resolveTextByUiLanguage(map, fallbackText = '') {
  if (!map || typeof map !== 'object') return fallbackText;

  const normalizedMap = new Map();
  Object.entries(map).forEach(([key, value]) => {
    if (typeof value === 'string' && value.trim() !== '') {
      normalizedMap.set(normalizeLanguageTag(key), value);
    }
  });

  const uiLang = languageContext.uiLanguage || 'en';
  if (normalizedMap.has(uiLang)) return normalizedMap.get(uiLang);
  if (normalizedMap.has('en')) return normalizedMap.get('en');
  const firstValue = normalizedMap.values().next().value;
  return firstValue || fallbackText;
}

function getLocalizedRoomName() {
  return resolveTextByUiLanguage(i18nLibrary?.room_name_i18n, 'Room');
}

function getChannelLabel(channelId) {
  const channel = (currentState?.channels || []).find((candidate) => candidate.channel_id === channelId);
  return channel?.channel_label || channelId || '';
}

function getLocalizedStatusText(status) {
  if (status === 'BLOCKED') {
    return resolveTextByUiLanguage(i18nLibrary?.custom_status_text_blocked_i18n, 'BLOCKED');
  }
  if (status === 'CLOSED') {
    return resolveTextByUiLanguage(i18nLibrary?.custom_status_text_closed_i18n, 'CLOSED');
  }
  return '';
}

function isValidI18nLibrary(value) {
  if (!value || typeof value !== 'object') return false;
  const required = ['room_name_i18n', 'custom_status_text_blocked_i18n', 'custom_status_text_closed_i18n'];
  return required.every((key) => value[key] && typeof value[key] === 'object');
}

function makeI18nFingerprint(value) {
  if (!isValidI18nLibrary(value)) return 'invalid';
  return JSON.stringify(value);
}

function applyI18nLibrary(nextLibrary) {
  if (!isValidI18nLibrary(nextLibrary)) {
    if (i18nLibrary) {
      log('i18n reconnect fallback: keep previous immutable library');
      hasI18nLibrary = true;
      return;
    }
    throw new Error('Protocol error: invalid i18n_library payload');
  }

  const nextFingerprint = makeI18nFingerprint(nextLibrary);
  if (immutableI18nFingerprint && immutableI18nFingerprint !== nextFingerprint) {
    log('i18n warning: immutable library changed on reconnect, keeping first version');
    i18nMismatchCount += 1;
    updateDiagnosticsSnapshot();
    hasI18nLibrary = true;
    return;
  }

  i18nLibrary = nextLibrary;
  immutableI18nFingerprint = nextFingerprint;
  hasI18nLibrary = true;
  i18nApplyCount += 1;
  updateDiagnosticsSnapshot();
  chooseUiLanguage(i18nLibrary);

  if (currentState) {
    roomNameEl.textContent = getLocalizedRoomName();
    if (currentState.room_status && currentState.room_status !== 'OPENED') {
      statusBox.style.display = 'block';
      statusBox.textContent = getLocalizedStatusText(currentState.room_status);
    }
  }
  log('i18n library applied for current session');
}

function isLiveKitReady() {
  return typeof window.LivekitClient !== 'undefined' && typeof LivekitClient.Room === 'function';
}

async function ensureLiveKitClientLoaded() {
  if (window.__livekitLoadPromise && typeof window.__livekitLoadPromise.then === 'function') {
    await window.__livekitLoadPromise;
  }
  if (!isLiveKitReady()) {
    throw new Error('LiveKit client script is not loaded');
  }
  if (window.__livekitSdkSource) {
    log(`LiveKit SDK source=${window.__livekitSdkSource}`);
  }
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

function isRoomOpened() { return currentState?.room_status === 'OPENED'; }
function isRoomBlocked() { return currentState?.room_status === 'BLOCKED'; }
function isRoomClosed() { return currentState?.room_status === 'CLOSED'; }

function setConnectionState(nextState, reason = '') {
  if (connectionState === nextState) return;
  if (nextState !== CONNECTION_STATE.CONNECTED && connectionState === CONNECTION_STATE.CONNECTED) {
    backendUnavailableSinceMs = Date.now();
  }
  connectionState = nextState;
  log(`connection state -> ${nextState}${reason ? ` (${reason})` : ''}`);
  if (nextState === CONNECTION_STATE.CONNECTED) {
    clearAutoRetryTimer();
  }
  updateDiagnosticsSnapshot();
  refreshConnectionBanner();
}

function markConnectionStale(reason) {
  setConnectionState(CONNECTION_STATE.STALE, reason);
  livekitConnected = false;
}

function resetHandshakeFlagsForReconnect() {
  hasConnectingOk = false;
  hasI18nLibrary = false;
  hasListenerState = false;
  livekitConnected = false;
  pendingToken = null;
  pendingLivekitUrl = null;
}

async function closeBackendSocketForReconnect() {
  if (!backendWs) return;
  suppressBackendCloseEvent = true;
  try {
    backendWs.close();
  } catch (error) {
    log(`backend close warning: ${error.message}`);
  }
  backendWs = null;
}

function sendHeartbeatIfNeeded() {
  if (connectionState !== CONNECTION_STATE.CONNECTED) return;
  if (!hasActivePlayRequest()) return;
  if (!isBackendWsOpen()) return;
  backendWs.send(JSON.stringify(makeEnvelope('heartbeat', {
    client_role: 'listener',
    selected_channel: selectedChannel,
    playback_state: playbackState,
  })));
  heartbeatSentCount += 1;
  updateDiagnosticsSnapshot();
  log(`heartbeat sent channel=${selectedChannel} playback=${playbackState}`);
}

function startHeartbeatLoops() {
  if (!heartbeatIntervalId) {
    heartbeatIntervalId = setInterval(sendHeartbeatIfNeeded, HEARTBEAT_INTERVAL_MS);
  }
}

async function closeLiveKitForReconnect() {
  if (!room) return;
  try {
    await room.disconnect();
  } catch (error) {
    log(`livekit disconnect warning: ${error.message}`);
  }
  room = null;
  publicationByChannel.clear();
  trackByChannel.clear();
  currentTrack = null;
  currentTrackName = null;
}

function noteMediaSessionAction(action) {
  listenerDiagnostics.mediaSessionLastAction = action;
  updateDiagnosticsSnapshot();
  log(`mediaSession action=${action}`);
}

function notePlaybackEvent(eventName, detail = '') {
  listenerDiagnostics.lastPlaybackEvent = eventName;
  updateDiagnosticsSnapshot();
  log(`playback event=${eventName}${detail ? ` ${detail}` : ''}`);
}

function notePlaybackError(error, context) {
  const name = error?.name || 'Error';
  const message = error?.message || String(error);
  listenerDiagnostics.lastPlaybackError = `${context}: ${name}: ${message}`;
  updateDiagnosticsSnapshot();
  log(`playback error context=${context} name=${name} message=${message}`);
}

function setMediaSessionPlaybackState(nextState) {
  if (!listenerDiagnostics.mediaSessionSupported || !('playbackState' in navigator.mediaSession)) return;
  try {
    navigator.mediaSession.playbackState = nextState;
  } catch (error) {
    log(`mediaSession playbackState warning: ${error.message}`);
  }
}

function updateMediaSessionMetadata(channelId) {
  if (!listenerDiagnostics.mediaSessionSupported || !channelId) return;
  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: getLocalizedRoomName() || 'Room',
      artist: getChannelLabel(channelId) || channelId,
      album: 'BYOD Listener',
    });
    log(`mediaSession metadata updated channel=${channelId}`);
  } catch (error) {
    log(`mediaSession metadata warning: ${error.message}`);
  }
}

async function playCurrentMedia(reason, channelId) {
  const playPromise = player.play();
  if (playPromise && typeof playPromise.then === 'function') {
    await playPromise;
  }
  playbackState = 'PLAYING';
  setMediaSessionPlaybackState('playing');
  notePlaybackEvent('player.play.success', `reason=${reason} channel=${channelId}`);
}

function stopPlayback() {
  player.pause();
  player.srcObject = null;
  currentTrack = null;
  currentTrackName = null;
  playbackState = 'IDLE';
  setMediaSessionPlaybackState('none');
}

function detachCurrentMediaForSystemPause() {
  player.pause();
  player.srcObject = null;
  currentTrack = null;
  currentTrackName = null;
}

async function detachPlayback(reason, { force = false } = {}) {
  if (!force && hasAudioOpInProgress()) {
    log(`detach skipped (busy) reason=${reason}`);
    return false;
  }
  detachInProgress = true;
  try {
    await runWithTimeout(async () => {
      stopPlayback();
    }, ATTACH_DETACH_TIMEOUT_MS, `detach timeout (${reason})`);
    log(`detach done reason=${reason}`);
    return true;
  } catch (error) {
    stopPlayback();
    log(`detach reset to IDLE reason=${reason} error=${error.message}`);
    return false;
  } finally {
    detachInProgress = false;
  }
}

async function attachPlaybackTrack(track, trackName) {
  if (hasAudioOpInProgress()) {
    log(`attach skipped (busy) channel=${trackName}`);
    return false;
  }

  attachInProgress = true;
  try {
    await runWithTimeout(async () => {
      const mediaStream = new MediaStream([track.mediaStreamTrack]);
      player.pause();
      player.srcObject = mediaStream;
      await playCurrentMedia('attach', trackName);
    }, ATTACH_DETACH_TIMEOUT_MS, `attach timeout (${trackName})`);

    currentTrack = track;
    currentTrackName = trackName;
    log(`attach done channel=${trackName}`);
    return true;
  } catch (error) {
    stopPlayback();
    notePlaybackError(error, `player.play channel=${trackName}`);
    log(`attach reset to IDLE channel=${trackName} error=${error.message}`);
    return false;
  } finally {
    attachInProgress = false;
  }
}

function cachePublication(publication) {
  const trackName = getTrackName(publication);
  if (!trackName) return null;
  publicationByChannel.set(trackName, publication);
  if (publication.track) trackByChannel.set(trackName, publication.track);
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

async function stopCurrentChannel(reason) {
  lastSystemResumeChannel = null;
  systemPausedChannel = null;
  selectedChannel = null;
  syncSubscriptions();
  await detachPlayback(reason);
  if (currentState) renderState(currentState);
}

async function selectChannel(channelId, reason) {
  if (isRoomClosed()) return;
  if (hasAudioOpInProgress()) {
    log(`${reason} ignored: attach/detach in progress`);
    return;
  }

  if (selectedChannel === channelId) {
    await stopCurrentChannel(`${reason} stop`);
    return;
  }

  selectedChannel = channelId;
  lastSelectedChannel = channelId;
  lastSystemResumeChannel = channelId;
  systemPausedChannel = null;
  playbackState = 'WAITING';
  updateMediaSessionMetadata(channelId);
  renderState(currentState);
  if (connectionState === CONNECTION_STATE.STALE) {
    try {
      await reconnectListener(reason);
    } catch (error) {
      log(`reconnect error: ${error.message}`);
      return;
    }
  }
  syncSubscriptions();
  if (isRoomBlocked()) return;
  await attachSelectedIfPossible();
}

async function suspendCurrentChannelFromSystem(reason) {
  noteMediaSessionAction('pause');
  log(`system pause requested reason=${reason}`);
  if (!selectedChannel) {
    log('system pause ignored: no active selected channel');
    return;
  }

  const channelId = selectedChannel;
  lastSystemResumeChannel = channelId;
  systemPausedChannel = channelId;
  selectedChannel = null;
  syncSubscriptions();
  detachCurrentMediaForSystemPause();
  playbackState = 'SYSTEM_PAUSED_DETACHED';
  updateMediaSessionMetadata(channelId);
  setMediaSessionPlaybackState('paused');
  updateDiagnosticsSnapshot();
  if (currentState) renderState(currentState);
  log(`system pause completed channel=${channelId}`);
}

function isListenerTransportReady() {
  return connectionState === CONNECTION_STATE.CONNECTED && isBackendWsOpen() && livekitConnected && room;
}

function waitForListenerReady(reason, timeoutMs = 5000) {
  const startedAt = Date.now();
  return new Promise((resolve, reject) => {
    const intervalId = setInterval(() => {
      if (isListenerTransportReady() && currentState) {
        clearInterval(intervalId);
        resolve();
        return;
      }
      if (Date.now() - startedAt >= timeoutMs) {
        clearInterval(intervalId);
        reject(new Error(`listener ready timeout (${reason})`));
      }
    }, 100);
  });
}

function findListenableChannel(channelId) {
  return (currentState?.channels || []).find((channel) => channel.channel_id === channelId && channel.listen);
}

async function resumeLastSystemChannelFromSystem(reason) {
  noteMediaSessionAction('play');
  log(`system play requested reason=${reason}`);
  if (!lastSystemResumeChannel) {
    log('system play ignored: no remembered system resume channel');
    return;
  }
  if (isRoomBlocked()) {
    log('system play ignored: room is BLOCKED');
    return;
  }
  if (isRoomClosed()) {
    log('system play ignored: room is CLOSED');
    return;
  }

  try {
    if (!isListenerTransportReady()) {
      if (connectionState === CONNECTION_STATE.CONNECTED) {
        markConnectionStale('mediaSession play transport not ready');
      }
      await reconnectListener('mediaSession play');
      await waitForListenerReady('mediaSession play');
    }
  } catch (error) {
    notePlaybackError(error, `mediaSession play reconnect channel=${lastSystemResumeChannel}`);
    setMediaSessionPlaybackState('paused');
    log(`system play reconnect failed channel=${lastSystemResumeChannel} error=${error.message}`);
    return;
  }

  if (!currentState) {
    log('system play ignored: listener state unavailable after reconnect');
    return;
  }
  if (isRoomBlocked()) {
    log('system play ignored after reconnect: room is BLOCKED');
    return;
  }
  if (isRoomClosed()) {
    log('system play ignored after reconnect: room is CLOSED');
    return;
  }
  if (!isRoomOpened()) {
    log('system play ignored after reconnect: room is not OPENED');
    return;
  }

  const channelId = lastSystemResumeChannel;
  if (!findListenableChannel(channelId)) {
    log(`system play ignored: remembered channel unavailable channel=${channelId}`);
    return;
  }

  selectedChannel = channelId;
  lastSelectedChannel = channelId;
  systemPausedChannel = null;
  playbackState = 'WAITING';
  updateMediaSessionMetadata(channelId);
  updateDiagnosticsSnapshot();
  renderState(currentState);
  syncSubscriptions();
  await attachSelectedIfPossible();
  if (playbackState === 'PLAYING') {
    log(`system play success channel=${channelId}`);
  } else {
    log(`system play waiting channel=${channelId}`);
  }
}

async function attachSelectedIfPossible() {
  if (!selectedChannel || !isRoomOpened()) return;
  updateMediaSessionMetadata(selectedChannel);

  const publication = publicationByChannel.get(selectedChannel);
  const track = trackByChannel.get(selectedChannel) || publication?.track || null;
  if (!track) {
    playbackState = 'WAITING';
    log(`attach waiting channel=${selectedChannel}`);
    return;
  }

  if (currentTrack === track && currentTrackName === selectedChannel && playbackState === 'PLAYING') return;
  await attachPlaybackTrack(track, selectedChannel);
}

function enforceRoomStatusRules(state) {
  const nextStatus = state.room_status || 'OPENED';

  if (nextStatus === 'BLOCKED') {
    detachPlayback('room BLOCKED', { force: true }).catch((error) => log(`detach error: ${error.message}`));
    syncSubscriptions();
    return;
  }

  if (nextStatus === 'CLOSED') {
    lastSystemResumeChannel = null;
    systemPausedChannel = null;
    selectedChannel = null;
    detachPlayback('room CLOSED', { force: true }).catch((error) => log(`detach error: ${error.message}`));
    syncSubscriptions();
    return;
  }

  if (nextStatus === 'OPENED' && previousRoomStatus === 'BLOCKED' && selectedChannel) {
    playbackState = 'WAITING';
    syncSubscriptions();
    attachSelectedIfPossible().catch((error) => log(`resume attach error: ${error.message}`));
  }
}

function renderState(state) {
  currentState = state;
  enforceRoomStatusRules(state);

  roomNameEl.textContent = getLocalizedRoomName();

  if (state.room_status && state.room_status !== 'OPENED') {
    statusBox.style.display = 'block';
    statusBox.textContent = getLocalizedStatusText(state.room_status);
  } else {
    statusBox.style.display = 'none';
    statusBox.textContent = '';
  }

  const allowedChannels = new Set((state.channels || []).filter((ch) => ch.listen).map((ch) => ch.channel_id));
  if (selectedChannel && !allowedChannels.has(selectedChannel)) {
    if (lastSystemResumeChannel === selectedChannel) lastSystemResumeChannel = null;
    if (systemPausedChannel === selectedChannel) systemPausedChannel = null;
    selectedChannel = null;
    syncSubscriptions();
    detachPlayback('channel hidden by listen=false', { force: true })
      .catch((error) => log(`detach error: ${error.message}`));
  }

  buttonsEl.innerHTML = '';
  for (const channel of state.channels || []) {
    if (!channel.listen) continue;

    const button = document.createElement('button');
    button.className = 'btn';
    button.textContent = `${channel.channel_id} — ${channel.channel_label}`;
    if (selectedChannel === channel.channel_id) button.classList.add('active');
    button.disabled = isRoomClosed();

    button.onclick = async () => {
      await selectChannel(channel.channel_id, 'button');
    };

    buttonsEl.appendChild(button);
  }

  previousRoomStatus = state.room_status || null;
}


function setupPlaybackDiagnostics() {
  ['pause', 'ended', 'stalled', 'suspend', 'waiting', 'playing'].forEach((eventName) => {
    player.addEventListener(eventName, () => notePlaybackEvent(eventName));
  });
}

function registerMediaSessionAction(action, handler) {
  try {
    navigator.mediaSession.setActionHandler(action, handler);
    listenerDiagnostics.mediaSessionHandlersRegistered[action] = true;
    log(`mediaSession action handler registered action=${action}`);
  } catch (error) {
    listenerDiagnostics.mediaSessionHandlersRegistered[action] = false;
    log(`mediaSession action handler not registered action=${action} error=${error.message}`);
  }
  updateDiagnosticsSnapshot();
}

function disableMediaSessionAction(action) {
  try {
    navigator.mediaSession.setActionHandler(action, null);
    listenerDiagnostics.mediaSessionHandlersRegistered[action] = false;
    log(`mediaSession unwanted action disabled action=${action}`);
  } catch (error) {
    listenerDiagnostics.mediaSessionHandlersRegistered[action] = false;
    log(`mediaSession unwanted action unsupported action=${action} error=${error.message}`);
  }
  updateDiagnosticsSnapshot();
}

function setupMediaSession() {
  listenerDiagnostics.mediaSessionSupported = 'mediaSession' in navigator;
  updateDiagnosticsSnapshot();
  if (!listenerDiagnostics.mediaSessionSupported) {
    log('mediaSession not supported');
    return;
  }

  log('mediaSession supported');
  setMediaSessionPlaybackState('none');
  registerMediaSessionAction('play', () => {
    notePlaybackEvent('mediaSession.play');
    resumeLastSystemChannelFromSystem('mediaSession play')
      .catch((error) => log(`mediaSession play error: ${error.message}`));
  });
  registerMediaSessionAction('pause', () => {
    notePlaybackEvent('mediaSession.pause');
    suspendCurrentChannelFromSystem('mediaSession pause')
      .catch((error) => log(`mediaSession pause error: ${error.message}`));
  });
  registerMediaSessionAction('stop', () => {
    noteMediaSessionAction('stop');
    notePlaybackEvent('mediaSession.stop');
    stopCurrentChannel('mediaSession stop').catch((error) => log(`mediaSession stop error: ${error.message}`));
  });
  ['seekbackward', 'seekforward', 'seekto', 'previoustrack', 'nexttrack'].forEach(disableMediaSessionAction);
}

async function connectLiveKit(livekitUrl, token) {
  if (!isLiveKitReady()) throw new Error('LiveKit client script is not loaded');

  if (room) {
    await room.disconnect();
    room = null;
  }

  room = new LivekitClient.Room({ adaptiveStream: false, dynacast: false, autoSubscribe: false });

  room.on(LivekitClient.RoomEvent.Disconnected, () => {
    markConnectionStale('livekit disconnected');
  });

  room.on(LivekitClient.RoomEvent.TrackPublished, async (publication) => {
    const trackName = cachePublication(publication);
    syncSubscriptions();
    if (trackName && selectedChannel === trackName && isRoomOpened()) await attachSelectedIfPossible();
  });

  room.on(LivekitClient.RoomEvent.TrackSubscribed, async (track, publication) => {
    if (track.kind !== LivekitClient.Track.Kind.Audio) return;
    const trackName = cachePublication(publication);
    if (trackName) trackByChannel.set(trackName, track);
    if (trackName && selectedChannel === trackName && isRoomOpened()) await attachSelectedIfPossible();
  });

  room.on(LivekitClient.RoomEvent.TrackUnsubscribed, async (track, publication) => {
    if (track.kind !== LivekitClient.Track.Kind.Audio) return;
    const trackName = getTrackName(publication);
    if (!trackName) return;

    trackByChannel.delete(trackName);
    if (selectedChannel === trackName && currentTrackName === trackName) {
      await detachPlayback('track unsubscribed', { force: true });
      playbackState = isRoomOpened() ? 'WAITING' : 'IDLE';
      if (isRoomOpened()) await attachSelectedIfPossible();
    }
  });

  room.on(LivekitClient.RoomEvent.TrackUnpublished, (publication) => {
    const trackName = getTrackName(publication);
    if (!trackName) return;
    publicationByChannel.delete(trackName);
    trackByChannel.delete(trackName);
    if (selectedChannel === trackName && currentTrackName === trackName) {
      detachPlayback('track unpublished', { force: true }).catch((error) => log(`detach error: ${error.message}`));
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
  livekitConnected = true;
  log('Connected to LiveKit');

  refreshPublicationsFromRoom();
  syncSubscriptions();
  await attachSelectedIfPossible();
}

async function maybeInitializeListener() {
  if (!hasConnectingOk || !hasI18nLibrary || !hasListenerState) return;
  if (!livekitConnected) {
    await connectLiveKit(pendingLivekitUrl, pendingToken);
  }
  if (currentState) {
    renderState(currentState);
  }
  setConnectionState(CONNECTION_STATE.CONNECTED, 'ready');
}

function validateEnvelope(msg) {
  return msg
    && typeof msg.type === 'string'
    && msg.schema_version === 1
    && typeof msg.request_id === 'string'
    && typeof msg.payload === 'object'
    && msg.payload !== null;
}

async function handleBackendMessage(msg) {
  if (!validateEnvelope(msg)) {
    throw new Error('Protocol error: invalid envelope');
  }

  const payload = msg.payload;

  if (msg.type === 'connecting') {
    if (payload.ok === true && payload.client_role === 'listener') {
      if (typeof payload.token !== 'string' || payload.token.trim() === '') {
        throw new Error('Protocol error: token is missing');
      }
      if (typeof payload.livekit_url !== 'string' || payload.livekit_url.trim() === '') {
        throw new Error('Protocol error: livekit_url is missing');
      }
      hasConnectingOk = true;
      pendingToken = payload.token;
      pendingLivekitUrl = payload.livekit_url;
      if (activeToken !== pendingToken) {
        tokenGeneration += 1;
        activeToken = pendingToken;
        log(`token updated generation=${tokenGeneration}`);
      } else {
        log(`token reused generation=${tokenGeneration}`);
      }
      await maybeInitializeListener();
      return;
    }
    throw new Error('Protocol error: invalid connecting payload');
  }

  if (msg.type === 'i18n_library') {
    applyI18nLibrary(payload);
    await maybeInitializeListener();
    return;
  }

  if (msg.type === 'listener_state') {
    currentState = payload;
    hasListenerState = true;
    await maybeInitializeListener();
    return;
  }

  if (msg.type === 'error') {
    log(`backend error code=${payload.code || 'UNKNOWN'}`);
    return;
  }

  if (msg.type === 'reconnect_required') {
    log(`backend reconnect_required code=${payload.code || 'UNKNOWN'} reason=${payload.reason || 'UNKNOWN'}`);
    markConnectionStale('backend reconnect_required');
    return;
  }

  throw new Error(`Protocol error: unsupported message type ${msg.type}`);
}

async function connectBackend(reason = 'connect') {
  return new Promise((resolve, reject) => {
    backendWs = new WebSocket(backendUrl);
    let isSettled = false;
    const openTimeout = setTimeout(() => {
      if (isSettled) return;
      isSettled = true;
      try {
        backendWs.close();
      } catch (error) {
        log(`backend timeout close warning: ${error.message}`);
      }
      reject(new Error('backend websocket open timeout'));
    }, 5000);

    backendWs.onopen = () => {
      if (isSettled) return;
      isSettled = true;
      clearTimeout(openTimeout);
      log(`backend websocket opened: ${backendUrl}`);
      log(`backend connect reason=${reason}`);
      noteBackendActivity('ws_open');
      backendWs.send(JSON.stringify(makeEnvelope('connecting', { client_role: 'listener' })));
      resolve();
    };

    backendWs.onmessage = async (event) => {
      try {
        noteBackendActivity('ws_message');
        const msg = JSON.parse(event.data);
        await handleBackendMessage(msg);
      } catch (error) {
        log(`backend protocol error: ${error.message}`);
        backendWs.close();
      }
    };

    backendWs.onclose = () => {
      clearTimeout(openTimeout);
      log('Backend WS closed');
      if (suppressBackendCloseEvent) {
        suppressBackendCloseEvent = false;
        return;
      }
      markConnectionStale('backend websocket closed');
    };

    backendWs.onerror = (event) => {
      clearTimeout(openTimeout);
      log(`Backend WS error: ${event.type}`);
      if (!isSettled) {
        isSettled = true;
        reject(new Error(`backend websocket error: ${event.type}`));
      }
    };
  });
}

async function reconnectListener(reason) {
  if (connectionState === CONNECTION_STATE.CONNECTED) {
    log(`reconnect skipped: already CONNECTED (${reason})`);
    return;
  }
  if (reconnectPromise) {
    log(`reconnect already running (${reason})`);
    return reconnectPromise;
  }

  reconnectPromise = (async () => {
    reconnectAttemptCount += 1;
    updateDiagnosticsSnapshot();
    setConnectionState(CONNECTION_STATE.RECONNECTING, reason);
    await closeBackendSocketForReconnect();
    await closeLiveKitForReconnect();
    resetHandshakeFlagsForReconnect();
    await connectBackend(`reconnect:${reason}`);
    reconnectSuccessCount += 1;
    updateDiagnosticsSnapshot();
  })();

  try {
    await reconnectPromise;
  } catch (error) {
    reconnectFailureCount += 1;
    updateDiagnosticsSnapshot();
    markConnectionStale(`reconnect failed: ${error.message}`);
    if (reason.startsWith('auto-retry:')) {
      scheduleAutoRetry(`reconnect failed: ${reason}`);
    }
    throw error;
  } finally {
    reconnectPromise = null;
  }
}

setupPlaybackDiagnostics();
setupMediaSession();
initLanguageDetection();
const env = detectClientEnvironment();
log(`client env: platform=${env.platform} mobile=${env.isMobile}`);
log(`client env: ua=${env.ua}`);
updateDiagnosticsSnapshot();
startHeartbeatLoops();
startConnectionBannerLoop();
ensureLiveKitClientLoaded()
  .then(() => connectBackend('initial'))
  .catch((error) => {
    log(`initial connect error: ${error.message}`);
    markConnectionStale('initial connect failed');
    scheduleAutoRetry('initial connect failed');
  });

document.addEventListener('visibilitychange', () => {
  listenerDiagnostics.lastVisibilityState = document.visibilityState;
  notePlaybackEvent('visibilitychange', `state=${document.visibilityState}`);
  if (document.visibilityState === 'visible' && connectionState === CONNECTION_STATE.STALE) {
    reconnectListener('page visible').catch((error) => log(`reconnect error: ${error.message}`));
  }
});

window.addEventListener('online', () => {
  if (connectionState === CONNECTION_STATE.STALE) {
    reconnectListener('network online').catch((error) => log(`reconnect error: ${error.message}`));
  }
});
