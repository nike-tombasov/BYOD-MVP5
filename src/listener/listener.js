const backendOverride = new URLSearchParams(location.search).get('backend');
const backendProtocol = location.protocol === 'https:' ? 'wss' : 'ws';
const backendDefaultUrl = `${backendProtocol}://${location.host}/ws/listener`;
const backendUrl = backendOverride || backendDefaultUrl;
const HEARTBEAT_INTERVAL_MS = 10_000;
const ATTACH_DETACH_TIMEOUT_MS = 1_000;
const RETRYING_RECONNECT_DELAY_MS = 3_000;
const UNAVAILABLE_RECONNECT_DELAY_MS = 10_000;
const SYSTEM_PAUSE_EXPIRE_MS = 60_000;
const ANDROID_CHROME_RECOVERY_THROTTLE_MS = 2_000;
const ANDROID_CHROME_RECOVERY_MAX_ATTEMPTS_PER_EPISODE = 3;
const ANDROID_CHROME_NATIVE_AUDIO_CONTROLS_EXPERIMENT = false;

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
let lastReconnectReason = null;
let heartbeatSuppressedReason = null;
let clientEnvironment = null;
let lastPlayerEvent = null;
let lastPlayerEventAtMs = null;
let lastPlayerPaused = null;
let lastPlayerReadyState = null;
let lastPlayerNetworkState = null;
let lastPlayerError = null;
let lastVisibilityState = document.visibilityState;
let androidChromeRecoveryAttemptCount = 0;
let androidChromeRecoverySuccessCount = 0;
let androidChromeRecoveryFailureCount = 0;
let androidChromeRecoveryEpisodeAttemptCount = 0;
let lastAndroidChromeRecoveryReason = null;
let lastAndroidChromeRecoveryAttemptAtMs = 0;
let androidChromeSuspiciousMediaEvent = false;
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
let attachInProgress = false;
let detachInProgress = false;
let systemPauseActive = false;
let systemPauseExpired = false;
let systemPauseStartedAtMs = null;
let systemPauseExpireTimerId = null;
let lastSystemPausedChannel = null;
let lastSystemPauseExpiredAtMs = null;
let lastPlaybackEvent = null;
let lastPlaybackError = null;
let intentionalPauseExpiryCleanup = false;

const publicationByChannel = new Map();
const trackByChannel = new Map();

const player = document.getElementById('player');
const mediaSession = 'mediaSession' in navigator ? navigator.mediaSession : null;
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

function getSystemPauseElapsedMs() {
  if (!systemPauseStartedAtMs) return 0;
  return Math.max(0, Date.now() - systemPauseStartedAtMs);
}

function updateDiagnosticsSnapshot() {
  window.__listenerDiagnostics = {
    connectionState,
    reconnectAttemptCount,
    reconnectSuccessCount,
    reconnectFailureCount,
    heartbeatSentCount,
    heartbeatSuppressedReason,
    systemPauseActive,
    systemPauseExpired,
    systemPauseStartedAtMs,
    systemPauseElapsedMs: getSystemPauseElapsedMs(),
    lastSystemPausedChannel,
    lastSystemPauseExpiredAtMs,
    playbackState,
    lastPlaybackEvent,
    lastPlaybackError,
    lastReconnectReason,
    clientEnvironment,
    lastPlayerEvent,
    lastPlayerEventAtMs,
    lastPlayerPaused,
    lastPlayerReadyState,
    lastPlayerNetworkState,
    lastPlayerError,
    lastVisibilityState,
    androidChromeRecoveryAttemptCount,
    androidChromeRecoverySuccessCount,
    androidChromeRecoveryFailureCount,
    lastAndroidChromeRecoveryReason,
    i18nApplyCount,
    i18nMismatchCount,
    sdkSource: window.__livekitSdkSource || 'unknown',
    lastBackendActivityMs,
  };
}

function detectClientEnvironment() {
  const ua = navigator.userAgent || 'unknown';
  const platform = navigator.platform || 'unknown';
  const uaDataBrands = navigator.userAgentData?.brands?.map((brand) => brand.brand).join(',') || '';
  const isMobile = /android|iphone|ipad|ipod|mobile/i.test(ua);
  const isAndroid = /android/i.test(ua);
  const isSamsungBrowser = /SamsungBrowser/i.test(ua) || /Samsung Internet/i.test(uaDataBrands);
  const isChrome = /(Chrome|CriOS|Chromium)\//i.test(ua) || /Chromium|Google Chrome/i.test(uaDataBrands);
  const isAndroidChrome = isAndroid && isChrome && !isSamsungBrowser;
  return { ua, platform, isMobile, isAndroid, isChrome, isSamsungBrowser, isAndroidChrome };
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
  return selectedChannel !== null && (playbackState === 'WAITING' || playbackState === 'PLAYING');
}

function hasAudioOpInProgress() {
  return attachInProgress || detachInProgress;
}

function recordPlayerEvent(eventName) {
  lastPlayerEvent = eventName;
  lastPlayerEventAtMs = Date.now();
  lastPlayerPaused = player.paused;
  lastPlayerReadyState = player.readyState;
  lastPlayerNetworkState = player.networkState;
  if (player.error) {
    lastPlayerError = `${player.error.code}:${player.error.message || 'media error'}`;
  }
  updateDiagnosticsSnapshot();
  log(`player event=${eventName} paused=${player.paused} readyState=${player.readyState} networkState=${player.networkState}`);
}

function isAndroidChromeClient() {
  return clientEnvironment?.isAndroidChrome === true;
}

function isPlaybackExpectedToContinue() {
  return selectedChannel !== null
    && playbackState === 'PLAYING'
    && !!player.srcObject
    && !!currentTrack
    && !systemPauseActive
    && !intentionalPauseExpiryCleanup
    && !isRoomClosed()
    && !isRoomBlocked()
    && !hasAudioOpInProgress();
}

async function attemptAndroidChromeResumeExistingMedia(reason) {
  if (!isAndroidChromeClient()) return false;
  if (!isPlaybackExpectedToContinue()) return false;
  if (!player.paused && !androidChromeSuspiciousMediaEvent) return false;

  const nowMs = Date.now();
  if (nowMs - lastAndroidChromeRecoveryAttemptAtMs < ANDROID_CHROME_RECOVERY_THROTTLE_MS) return false;
  if (androidChromeRecoveryEpisodeAttemptCount >= ANDROID_CHROME_RECOVERY_MAX_ATTEMPTS_PER_EPISODE) return false;

  androidChromeRecoveryAttemptCount += 1;
  androidChromeRecoveryEpisodeAttemptCount += 1;
  lastAndroidChromeRecoveryAttemptAtMs = nowMs;
  lastAndroidChromeRecoveryReason = reason;
  updateDiagnosticsSnapshot();
  log(`android chrome recovery attempt reason=${reason}`);

  try {
    await player.play();
    playbackState = 'PLAYING';
    setMediaSessionPlaybackState('playing');
    lastPlaybackEvent = 'android chrome recovery resume';
    androidChromeSuspiciousMediaEvent = false;
    androidChromeRecoverySuccessCount += 1;
    updateDiagnosticsSnapshot();
    log(`android chrome recovery success reason=${reason}`);
    return true;
  } catch (error) {
    lastPlaybackError = `${error.name || 'Error'}: ${error.message}`;
    androidChromeRecoveryFailureCount += 1;
    updateDiagnosticsSnapshot();
    log(`android chrome recovery failed reason=${reason} error=${error.name || 'Error'}:${error.message}`);
    return false;
  }
}

function maybeAttemptAndroidChromeRecovery(reason) {
  attemptAndroidChromeResumeExistingMedia(reason).catch((error) => {
    lastPlaybackError = error.message;
    log(`android chrome recovery error reason=${reason} error=${error.message}`);
    updateDiagnosticsSnapshot();
  });
}

function initializePlayerDiagnostics() {
  for (const eventName of ['play', 'playing', 'pause', 'waiting', 'stalled', 'suspend', 'emptied', 'abort', 'ended', 'error', 'volumechange']) {
    player.addEventListener(eventName, () => {
      recordPlayerEvent(eventName);
      if (['pause', 'waiting', 'stalled', 'suspend'].includes(eventName)) {
        androidChromeSuspiciousMediaEvent = true;
        maybeAttemptAndroidChromeRecovery(eventName);
      }
    });
  }
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
  if (systemPauseActive || intentionalPauseExpiryCleanup) {
    log(`auto-retry suppressed reason=${reason}`);
    return;
  }
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
  if (systemPauseActive || intentionalPauseExpiryCleanup) {
    log(`connection stale auto-reconnect suppressed reason=${reason}`);
  }
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
  heartbeatSuppressedReason = null;
  if (connectionState !== CONNECTION_STATE.CONNECTED) { heartbeatSuppressedReason = 'connection not connected'; updateDiagnosticsSnapshot(); return; }
  if (!hasActivePlayRequest()) { heartbeatSuppressedReason = systemPauseActive ? 'system pause active' : (systemPauseExpired ? 'system pause expired' : 'no active playback'); updateDiagnosticsSnapshot(); return; }
  if (!isBackendWsOpen()) { heartbeatSuppressedReason = 'backend websocket not open'; updateDiagnosticsSnapshot(); return; }
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

function stopPlayback() {
  player.pause();
  player.srcObject = null;
  currentTrack = null;
  currentTrackName = null;
  playbackState = 'IDLE';
}

function clearSystemPauseTimer() {
  if (!systemPauseExpireTimerId) return;
  clearTimeout(systemPauseExpireTimerId);
  systemPauseExpireTimerId = null;
}

function setMediaSessionPlaybackState(state) {
  if (!mediaSession) return;
  try {
    mediaSession.playbackState = state;
  } catch (error) {
    log(`media session playbackState warning: ${error.message}`);
  }
}

function setMediaSessionMetadata(channelId) {
  if (!mediaSession || typeof MediaMetadata === 'undefined') return;
  const channel = (currentState?.channels || []).find((item) => item.channel_id === channelId);
  try {
    mediaSession.metadata = new MediaMetadata({
      title: channel ? channel.channel_label : channelId,
      artist: getLocalizedRoomName(),
      album: 'BYOD Listener',
    });
  } catch (error) {
    log(`media session metadata warning: ${error.message}`);
  }
}

function clearMediaSessionMetadata() {
  if (!mediaSession) return;
  try {
    mediaSession.metadata = null;
  } catch (error) {
    log(`media session metadata clear warning: ${error.message}`);
  }
}

function resetSystemPauseState() {
  clearSystemPauseTimer();
  systemPauseActive = false;
  systemPauseExpired = false;
  systemPauseStartedAtMs = null;
  lastSystemPausedChannel = null;
  updateDiagnosticsSnapshot();
}

function scheduleSystemPauseExpiryTimer() {
  clearSystemPauseTimer();
  systemPauseExpireTimerId = setTimeout(() => {
    systemPauseExpireTimerId = null;
    expireSystemPause('system pause timer');
  }, SYSTEM_PAUSE_EXPIRE_MS);
}

function closeBackendSocketForSystemPauseExpiry() {
  if (!backendWs) return;
  suppressBackendCloseEvent = true;
  try {
    backendWs.close();
  } catch (error) {
    log(`backend close warning: ${error.message}`);
  }
  backendWs = null;
}

async function closeLiveKitForSystemPauseExpiry() {
  if (!room) return;
  try {
    await room.disconnect();
  } catch (error) {
    log(`livekit disconnect warning: ${error.message}`);
  }
  room = null;
  publicationByChannel.clear();
  trackByChannel.clear();
}

function expireSystemPause(reason) {
  if (!systemPauseActive) return false;
  const elapsedMs = getSystemPauseElapsedMs();
  if (elapsedMs < SYSTEM_PAUSE_EXPIRE_MS) return false;

  log(`system pause expired reason=${reason} elapsedMs=${elapsedMs}`);
  intentionalPauseExpiryCleanup = true;
  clearSystemPauseTimer();
  systemPauseActive = false;
  systemPauseExpired = true;
  lastSystemPauseExpiredAtMs = Date.now();
  systemPauseStartedAtMs = null;
  lastSystemPausedChannel = null;
  selectedChannel = null;
  player.pause();
  player.srcObject = null;
  currentTrack = null;
  currentTrackName = null;
  playbackState = 'IDLE';
  setMediaSessionPlaybackState('none');
  clearMediaSessionMetadata();
  syncSubscriptions();
  if (currentState) renderState(currentState);
  closeLiveKitForSystemPauseExpiry().catch((error) => log(`livekit system-pause cleanup warning: ${error.message}`));
  closeBackendSocketForSystemPauseExpiry();
  livekitConnected = false;
  setConnectionState(CONNECTION_STATE.STALE, 'system pause expired');
  clearAutoRetryTimer();
  intentionalPauseExpiryCleanup = false;
  updateDiagnosticsSnapshot();
  return true;
}

function expireSystemPauseIfOverdue(reason) {
  if (!systemPauseActive) return false;
  return expireSystemPause(reason);
}

function handleMediaSessionPause() {
  if (!selectedChannel) {
    lastPlaybackEvent = 'system pause ignored: no selected channel';
    log(lastPlaybackEvent);
    updateDiagnosticsSnapshot();
    return;
  }
  systemPauseActive = true;
  systemPauseExpired = false;
  systemPauseStartedAtMs = Date.now();
  lastSystemPausedChannel = selectedChannel;
  lastPlaybackEvent = 'system pause';
  player.pause();
  playbackState = 'PAUSED_BY_SYSTEM';
  setMediaSessionPlaybackState('paused');
  scheduleSystemPauseExpiryTimer();
  if (currentState) renderState(currentState);
  updateDiagnosticsSnapshot();
  log(`system pause active channel=${selectedChannel}`);
}

async function handleMediaSessionPlay() {
  expireSystemPauseIfOverdue('media session play');
  if (systemPauseExpired) {
    lastPlaybackEvent = 'media session play ignored: system pause expired';
    playbackState = 'IDLE';
    setMediaSessionPlaybackState('none');
    log(`${lastPlaybackEvent}; page interaction required`);
    updateDiagnosticsSnapshot();
    return;
  }
  if (!systemPauseActive || playbackState !== 'PAUSED_BY_SYSTEM' || !player.srcObject) {
    lastPlaybackEvent = 'media session play ignored: no resumable local media';
    log(lastPlaybackEvent);
    updateDiagnosticsSnapshot();
    return;
  }
  if (connectionState !== CONNECTION_STATE.CONNECTED || !room || !livekitConnected) {
    lastPlaybackEvent = 'media session play ignored: stale connection requires page interaction';
    log(lastPlaybackEvent);
    updateDiagnosticsSnapshot();
    return;
  }
  try {
    await player.play();
    clearSystemPauseTimer();
    systemPauseActive = false;
    playbackState = 'PLAYING';
    setMediaSessionPlaybackState('playing');
    lastPlaybackEvent = 'media session local resume';
  } catch (error) {
    lastPlaybackError = error.message;
    log(`media session play warning: ${error.message}`);
  }
  updateDiagnosticsSnapshot();
}

function initializeMediaSession() {
  if (!mediaSession) return;
  try { mediaSession.setActionHandler('pause', handleMediaSessionPause); } catch (error) { log(`media session pause handler warning: ${error.message}`); }
  try {
    mediaSession.setActionHandler('play', () => {
      handleMediaSessionPlay().catch((error) => log(`media session play error: ${error.message}`));
    });
  } catch (error) { log(`media session play handler warning: ${error.message}`); }
  try {
    mediaSession.setActionHandler('stop', () => {
      resetSystemPauseState();
      selectedChannel = null;
      syncSubscriptions();
      detachPlayback('media session stop', { force: true }).catch((error) => log(`detach error: ${error.message}`));
      clearMediaSessionMetadata();
      setMediaSessionPlaybackState('none');
      if (currentState) renderState(currentState);
    });
  } catch (error) { log(`media session stop handler warning: ${error.message}`); }
  for (const action of ['seekbackward', 'seekforward', 'seekto', 'previoustrack', 'nexttrack']) {
    try { mediaSession.setActionHandler(action, null); } catch (_error) { /* action unsupported */ }
  }
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
      setMediaSessionMetadata(trackName);
      await player.play();
    }, ATTACH_DETACH_TIMEOUT_MS, `attach timeout (${trackName})`);

    currentTrack = track;
    currentTrackName = trackName;
    playbackState = 'PLAYING';
    setMediaSessionMetadata(trackName);
    setMediaSessionPlaybackState('playing');
    lastPlaybackEvent = 'playback attached';
    androidChromeSuspiciousMediaEvent = false;
    androidChromeRecoveryEpisodeAttemptCount = 0;
    log(`attach done channel=${trackName}`);
    return true;
  } catch (error) {
    lastPlaybackError = `${error.name || 'Error'}: ${error.message}`;
    stopPlayback();
    log(`attach reset to IDLE channel=${trackName} error=${error.name || 'Error'}:${error.message}`);
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

async function attachSelectedIfPossible() {
  expireSystemPauseIfOverdue('before attach');
  if (systemPauseActive) { log('attach skipped: system pause active'); return; }
  if (!selectedChannel || !isRoomOpened()) return;

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
      expireSystemPauseIfOverdue('button click');
      if (isRoomClosed()) return;
      if (hasAudioOpInProgress()) {
        log('click ignored: attach/detach in progress');
        return;
      }

      if (selectedChannel === channel.channel_id) {
        if (systemPauseActive && playbackState === 'PAUSED_BY_SYSTEM') {
          clearSystemPauseTimer();
          systemPauseActive = false;
          systemPauseExpired = false;
          systemPauseStartedAtMs = null;
          lastSystemPausedChannel = null;
          playbackState = 'WAITING';
          lastPlaybackEvent = 'page resumed system pause';
          renderState(currentState);
          if (connectionState === CONNECTION_STATE.STALE) {
            try {
              await reconnectListener('system pause page resume');
            } catch (error) {
              log(`reconnect error: ${error.message}`);
              return;
            }
          }
          syncSubscriptions();
          if (isRoomBlocked()) return;
          await attachSelectedIfPossible();
          return;
        }
        resetSystemPauseState();
        selectedChannel = null;
        syncSubscriptions();
        await detachPlayback('button stop');
        clearMediaSessionMetadata();
        setMediaSessionPlaybackState('none');
        renderState(currentState);
        return;
      }

      resetSystemPauseState();
      selectedChannel = channel.channel_id;
      playbackState = 'WAITING';
      setMediaSessionMetadata(selectedChannel);
      renderState(currentState);
      if (connectionState === CONNECTION_STATE.STALE) {
        try {
          await reconnectListener('channel click');
        } catch (error) {
          log(`reconnect error: ${error.message}`);
          return;
        }
      }
      syncSubscriptions();
      if (isRoomBlocked()) return;
      await attachSelectedIfPossible();
    };

    buttonsEl.appendChild(button);
  }

  previousRoomStatus = state.room_status || null;
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
  lastReconnectReason = reason;
  updateDiagnosticsSnapshot();
  if ((systemPauseActive || intentionalPauseExpiryCleanup) && reason !== 'channel click' && reason !== 'system pause page resume') {
    log(`reconnect skipped: system pause state (${reason})`);
    return;
  }
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

initLanguageDetection();
clientEnvironment = detectClientEnvironment();
if (ANDROID_CHROME_NATIVE_AUDIO_CONTROLS_EXPERIMENT && clientEnvironment.isAndroidChrome) player.controls = true;
log(`client env: platform=${clientEnvironment.platform} mobile=${clientEnvironment.isMobile} android=${clientEnvironment.isAndroid} chrome=${clientEnvironment.isChrome} samsung=${clientEnvironment.isSamsungBrowser}`);
log(`client env: ua=${clientEnvironment.ua}`);
updateDiagnosticsSnapshot();
initializeMediaSession();
initializePlayerDiagnostics();
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
  lastVisibilityState = document.visibilityState;
  expireSystemPauseIfOverdue('visibilitychange');
  if (document.visibilityState === 'hidden') {
    androidChromeRecoveryEpisodeAttemptCount = 0;
    maybeAttemptAndroidChromeRecovery('visibility hidden');
  }
  if (document.visibilityState === 'visible') {
    maybeAttemptAndroidChromeRecovery('visibility visible');
  }
  if (document.visibilityState === 'visible' && !systemPauseActive && !intentionalPauseExpiryCleanup && connectionState === CONNECTION_STATE.STALE) {
    reconnectListener('page visible').catch((error) => log(`reconnect error: ${error.message}`));
  }
});

window.addEventListener('online', () => {
  expireSystemPauseIfOverdue('online');
  if (!systemPauseActive && !intentionalPauseExpiryCleanup && connectionState === CONNECTION_STATE.STALE) {
    reconnectListener('network online').catch((error) => log(`reconnect error: ${error.message}`));
  }
});

window.addEventListener('pageshow', () => {
  lastVisibilityState = document.visibilityState;
  expireSystemPauseIfOverdue('pageshow');
  maybeAttemptAndroidChromeRecovery('pageshow');
  if (!systemPauseActive && !intentionalPauseExpiryCleanup && connectionState === CONNECTION_STATE.STALE) {
    reconnectListener('pageshow').catch((error) => log(`reconnect error: ${error.message}`));
  }
});

window.addEventListener('focus', () => {
  lastVisibilityState = document.visibilityState;
  expireSystemPauseIfOverdue('focus');
  maybeAttemptAndroidChromeRecovery('focus');
  if (!systemPauseActive && !intentionalPauseExpiryCleanup && connectionState === CONNECTION_STATE.STALE) {
    reconnectListener('focus').catch((error) => log(`reconnect error: ${error.message}`));
  }
});

window.addEventListener('pagehide', () => {
  lastVisibilityState = document.visibilityState;
  androidChromeRecoveryEpisodeAttemptCount = 0;
  expireSystemPauseIfOverdue('pagehide');
  maybeAttemptAndroidChromeRecovery('pagehide');
});
