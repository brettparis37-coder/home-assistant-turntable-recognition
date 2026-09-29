/* Turntable Recognition Lovelace card. */
const CARD_TYPE = "turntable-now-playing-card";

class TurntableNowPlayingCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._states = null;
    this._unsubscribeStates = null;
  }

  connectedCallback() {
    const event = new CustomEvent("context-request", {
      bubbles: true,
      composed: true,
      cancelable: true,
    });
    event.context = "states";
    event.subscribe = true;
    event.callback = (states, unsubscribe) => {
      this._states = states;
      if (typeof unsubscribe === "function") this._unsubscribeStates = unsubscribe;
      this._render();
    };
    this.dispatchEvent(event);
    this._render();
  }

  disconnectedCallback() {
    this._unsubscribeStates?.();
    this._unsubscribeStates = null;
  }

  setConfig(config) {
    this._config = {
      entity: config?.entity || "sensor.turntable_now_playing",
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  static getStubConfig() {
    return { entity: "sensor.turntable_now_playing" };
  }

  getCardSize() {
    return 3;
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;

    const entity = this._states?.[this._config.entity] || this._hass?.states?.[this._config.entity];
    const attributes = entity?.attributes || {};
    const title = attributes.title || (entity?.state !== "Nothing playing" ? entity?.state : "") || "";
    const artist = attributes.artist || "";
    const album = attributes.album || "";
    const year = attributes.year || attributes.master_year || attributes.release_year || "";
    const artwork = attributes.artwork_url || attributes.master_artwork_url || attributes.release_artwork_url || "";
    const dominantColor = /^#[0-9a-f]{6}$/i.test(attributes.dominant_color || "")
      ? attributes.dominant_color : "";
    const idle = !entity || !title || ["unknown", "unavailable", "Nothing playing"].includes(entity.state);
    const renderKey = JSON.stringify([entity?.state, title, artist, album, year, artwork,
      attributes.recognition_status, attributes.dominant_color, idle]);
    if (renderKey === this._renderKey) return;
    this._renderKey = renderKey;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card {
          box-sizing: border-box;
          padding: 18px;
          color: var(--primary-text-color);
          background-color: var(--ha-card-background, var(--card-background-color, var(--primary-background-color)));
          overflow: hidden;
          transition: background-color .45s ease;
        }
        ha-card.colored { color: #fff; }
        ha-card.colored .eyebrow, ha-card.colored .album, ha-card.colored .year { color: rgb(255 255 255 / 80%); }
        .layout { display: grid; grid-template-columns: minmax(96px, 34%) 1fr; gap: 18px; align-items: center; min-height: 132px; }
        .cover { width: 100%; aspect-ratio: 1; border-radius: 12px; object-fit: cover; background: var(--secondary-background-color); }
        .placeholder { display: grid; place-items: center; width: 100%; aspect-ratio: 1; border-radius: 12px; background: var(--secondary-background-color); color: var(--secondary-text-color); font-size: 42px; }
        .eyebrow { color: var(--secondary-text-color); font-size: 12px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 7px; }
        h2 { font-size: clamp(20px, 3vw, 28px); line-height: 1.15; margin: 0 0 7px; overflow-wrap: anywhere; }
        .artist { font-size: 16px; font-weight: 500; margin-bottom: 7px; }
        .album, .year { color: var(--secondary-text-color); font-size: 14px; line-height: 1.45; }
        .idle h2 { font-size: 21px; font-weight: 500; color: var(--secondary-text-color); }
        @media (max-width: 420px) {
          ha-card { padding: 12px; }
          .layout { grid-template-columns: 96px 1fr; gap: 13px; min-height: 96px; }
          .placeholder { font-size: 34px; }
          .artist { font-size: 14px; }
          .album, .year { font-size: 12px; }
        }
      </style>
      <ha-card class="${dominantColor ? "colored" : ""}" style="background-color:${dominantColor || "var(--ha-card-background, var(--card-background-color, var(--primary-background-color)))"}">
        <div class="layout ${idle ? "idle" : ""}">
          <div class="art"></div>
          <div class="details">
            <div class="eyebrow">${idle ? "Turntable" : attributes.recognition_status === "predicted" ? "Predicted next track · Discogs" : "Now playing"}</div>
            <h2 class="title"></h2>
            <div class="artist"></div>
            <div class="album"></div>
            <div class="year"></div>
          </div>
        </div>
      </ha-card>`;

    const root = this.shadowRoot;
    root.querySelector(".title").textContent = idle ? "Nothing playing" : title;
    root.querySelector(".artist").textContent = idle ? "" : artist;
    root.querySelector(".album").textContent = idle ? "" : album;
    root.querySelector(".year").textContent = idle || !year ? "" : year;

    const art = root.querySelector(".art");
    let safeArtwork = "";
    try {
      const url = new URL(artwork);
      if (url.protocol === "https:" || url.protocol === "http:") safeArtwork = url.href;
    } catch (_) {
      // Missing or invalid artwork falls back to the record glyph.
    }
    if (!idle && safeArtwork) {
      const image = document.createElement("img");
      image.className = "cover";
      image.src = safeArtwork;
      image.alt = album ? `${album} album artwork` : "Album artwork";
      image.loading = "lazy";
      image.addEventListener("error", () => {
        art.replaceChildren(this._placeholder());
      }, { once: true });
      art.replaceChildren(image);
    } else {
      art.replaceChildren(this._placeholder());
    }
  }

  _placeholder() {
    const element = document.createElement("div");
    element.className = "placeholder";
    element.setAttribute("aria-hidden", "true");
    element.textContent = "◉";
    return element;
  }
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, TurntableNowPlayingCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
  window.customCards.push({
    type: CARD_TYPE,
    name: "Turntable Now Playing",
    description: "Album art and track details from Turntable Recognition.",
    preview: false,
    documentationURL: "https://github.com/brettparis37-coder/home-assistant-turntable-recognition",
    getEntitySuggestion: (hass, entityId) => {
      if (entityId !== "sensor.turntable_now_playing" || !hass.states[entityId]) return null;
      return { config: { type: `custom:${CARD_TYPE}`, entity: entityId } };
    },
  });
}

const DIAGNOSTICS_CARD_TYPE = "turntable-recognition-diagnostics-card";

class TurntableRecognitionDiagnosticsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._countdownTimer = null;
  }

  connectedCallback() {
    if (!this._countdownTimer) this._countdownTimer = setInterval(() => this._updateCountdown(), 1000);
    this._updateCountdown();
  }

  disconnectedCallback() {
    if (this._countdownTimer) clearInterval(this._countdownTimer);
    this._countdownTimer = null;
  }

  setConfig(config) {
    this._prefix = (config?.entity_prefix || "turntable").replace(/[^a-z0-9_]/g, "");
    if (!this._prefix) throw new Error("entity_prefix must contain lowercase letters, numbers, or underscores");
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  static getStubConfig() {
    return { entity_prefix: "turntable" };
  }

  getCardSize() {
    return 4;
  }

  _state(suffix) {
    return this._hass?.states?.[`sensor.${this._prefix}_${suffix}`] || null;
  }

  _render() {
    if (!this.shadowRoot || !this._prefix) return;
    const status = this._state("recognition_status");
    const playback = this._state("playback_state");
    const level = this._state("audio_level");
    const peak = this._state("audio_peak");
    const signal = this._state("audio_signal");
    const input = this._state("audio_input_status");
    const usage = this._state("audd_usage");
    const statusAttrs = status?.attributes || {};
    const playbackAttrs = playback?.attributes || {};
    const usageAttrs = usage?.attributes || {};
    const key = JSON.stringify([status?.state, statusAttrs.last_error, statusAttrs.last_attempt_outcome,
      statusAttrs.last_attempt_at, statusAttrs.last_attempt_finished_at, statusAttrs.last_attempt_duration_seconds,
      statusAttrs.last_attempt_error, statusAttrs.consecutive_failures, statusAttrs.retry_seconds,
      statusAttrs.check_reason, statusAttrs.next_check_at, statusAttrs.prediction_title, playback?.state, playbackAttrs,
      level?.state, peak?.state, signal?.state, signal?.attributes?.threshold_dbfs,
      input?.state, input?.attributes?.last_error, input?.attributes?.audio_source,
      usage?.state, usageAttrs.requests_this_cycle, usageAttrs.allowance, usageAttrs.remaining,
      usageAttrs.usage_percent, usageAttrs.cycle_end]);
    if (key === this._renderKey) {
      this._updateCountdown();
      return;
    }
    this._renderKey = key;

    const rawState = status?.state || "unavailable";
    const labels = {
      idle: "Idle", listening: "Listening", capturing: "Capturing audio",
      recognizing: "Recognizing", recognized: "Track recognized", no_match: "No match",
      predicted: "Showing Discogs prediction",
      error: "Recognition error", api_limit_reached: "Monthly limit reached",
      daily_limit_reached: "Daily limit reached", input_unavailable: "Audio input unavailable",
    };
    const label = labels[rawState] || (rawState === "unavailable" ? "Waiting for app" : rawState.replaceAll("_", " "));
    const active = playbackAttrs.active === true || playback?.state === "playing";
    const tone = ["error", "input_unavailable", "api_limit_reached", "daily_limit_reached"].includes(rawState)
      ? "bad" : ["no_match", "capturing", "recognizing", "listening"].includes(rawState)
        ? "warn" : rawState === "recognized" ? "good" : "neutral";
    const defaultHelp = {
      idle: "Waiting for sustained audio above the start threshold.",
      listening: "Audio crossed the start threshold; monitoring the playback session.",
      capturing: "Recording a sample from the USB audio input.",
      recognizing: "Sample captured and sent for track recognition.",
      recognized: "Recognition succeeded. The next check follows the song timing when available.",
      no_match: "The service returned no track match. The app will retry with backoff.",
      predicted: "Recognition missed, so the next track on the matched Discogs release is shown until the next estimated song-end check.",
      error: "The latest recognition attempt failed. Review the error details below.",
      api_limit_reached: "The configured monthly safety limit is reached; requests are paused.",
      daily_limit_reached: "The configured daily safety limit is reached; requests are paused.",
      input_unavailable: "The USB capture source is disconnected or not delivering audio.",
    }[rawState] || "Waiting for recognition status from the app.";
    const help = rawState === "no_match" && statusAttrs.prediction_title
      ? `Recognition missed; showing the predicted track “${statusAttrs.prediction_title}” until the next scheduled check.`
      : defaultHelp;
    const displayState = (entity) => entity?.state && !["unknown", "unavailable"].includes(entity.state)
      ? entity.state : "—";
    const number = (value) => {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    };
    const db = number(level?.state);
    const peakDb = number(peak?.state);
    const dbPercent = db === null ? 0 : Math.max(0, Math.min(100, ((db + 80) / 70) * 100));
    const startDb = number(playbackAttrs.start_threshold_dbfs) ?? -30;
    const thresholdPercent = Math.max(0, Math.min(100, ((startDb + 80) / 70) * 100));
    const usagePercent = number(usageAttrs.usage_percent) ?? 0;
    const requestCount = number(usageAttrs.requests_this_cycle) ?? number(usage?.state);
    const allowance = number(usageAttrs.allowance);
    const remaining = number(usageAttrs.remaining);
    const source = input?.attributes?.audio_source || playbackAttrs.audio_source || "Auto-select UFO202";
    const error = statusAttrs.last_attempt_error || statusAttrs.last_error || input?.attributes?.last_error || "";
    const attemptOutcome = statusAttrs.last_attempt_outcome || "none";
    const attemptTime = this._formatTime(statusAttrs.last_attempt_finished_at || statusAttrs.last_attempt_at);
    const nextCheck = this._formatTime(playbackAttrs.next_check_at || statusAttrs.next_check_at);
    const retrySeconds = number(statusAttrs.retry_seconds);
    const reason = this._reason(playbackAttrs.check_reason || statusAttrs.check_reason || "");
    const attemptDuration = number(statusAttrs.last_attempt_duration_seconds);
    const failures = number(statusAttrs.consecutive_failures) ?? 0;
    const cycleEnd = usageAttrs.cycle_end ? this._formatDate(usageAttrs.cycle_end) : "";
    const inputState = displayState(input);
    const signalState = displayState(signal);
    const usageStatus = usageAttrs.limit_reached ? "Limit reached" : "Within limit";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; }
        ha-card { padding:18px; color:var(--primary-text-color); background:var(--ha-card-background,var(--card-background-color,var(--primary-background-color))); }
        .top { display:flex; align-items:flex-start; justify-content:space-between; gap:14px; }
        .heading { min-width:0; }
        h2 { font-size:20px; line-height:1.2; margin:0 0 5px; }
        .subtitle, .muted { color:var(--secondary-text-color); font-size:13px; line-height:1.45; }
        .badge { display:inline-flex; align-items:center; gap:7px; border-radius:999px; padding:7px 10px; white-space:nowrap; font-size:12px; font-weight:700; background:var(--secondary-background-color); }
        .dot { width:8px; height:8px; border-radius:50%; background:var(--secondary-text-color); }
        .good .dot { background:var(--success-color,#43a047); }
        .warn .dot { background:var(--warning-color,#f9a825); }
        .bad .dot { background:var(--error-color,#db4437); }
        .message { margin:15px 0; font-size:14px; }
        .section { border-top:1px solid var(--divider-color); padding-top:14px; margin-top:14px; }
        .section-title { color:var(--secondary-text-color); font-size:11px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; margin-bottom:9px; }
        .meter-label, .row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
        .meter-label strong { font-size:15px; font-variant-numeric:tabular-nums; }
        .meter { height:12px; margin:9px 0 6px; position:relative; border-radius:999px; overflow:hidden; background:var(--secondary-background-color); }
        .fill { height:100%; width:var(--fill,0%); border-radius:inherit; background:linear-gradient(90deg,var(--success-color,#43a047),var(--warning-color,#f9a825),var(--error-color,#db4437)); transition:width .25s ease; }
        .marker { position:absolute; top:0; bottom:0; left:var(--threshold,71.4%); width:2px; background:var(--primary-text-color); opacity:.75; }
        .scale { display:flex; justify-content:space-between; color:var(--secondary-text-color); font-size:11px; }
        .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
        .metric { min-width:0; border-radius:10px; padding:11px 12px; background:var(--secondary-background-color); }
        .metric-label { color:var(--secondary-text-color); font-size:11px; margin-bottom:4px; }
        .metric-value { font-size:14px; font-weight:600; overflow-wrap:anywhere; }
        .countdown { margin-top:5px; font-size:20px; font-weight:700; font-variant-numeric:tabular-nums; letter-spacing:.03em; }
        .usage-meter { height:7px; margin-top:8px; border-radius:99px; background:var(--primary-background-color); overflow:hidden; }
        .usage-fill { height:100%; width:var(--usage,0%); border-radius:inherit; background:var(--primary-color); }
        .error { border-left:3px solid var(--error-color,#db4437); padding:10px 12px; background:var(--secondary-background-color); white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; line-height:1.45; }
        .error-title { font-size:11px; font-weight:700; text-transform:uppercase; color:var(--error-color,#db4437); margin-bottom:5px; }
        @media(max-width:420px) { ha-card{padding:14px}.top{display:block}.badge{margin-top:10px}.grid{gap:8px}.metric{padding:9px} }
      </style>
      <ha-card>
        <div class="top">
          <div class="heading"><h2>Turntable diagnostics</h2><div class="subtitle session"></div></div>
          <div class="badge ${tone}"><span class="dot"></span><span class="status-label"></span></div>
        </div>
        <div class="message help"></div>
        <div class="section">
          <div class="section-title">Live audio input</div>
          <div class="meter-label"><span>Average level</span><strong class="db-value"></strong></div>
          <div class="meter"><div class="fill"></div><div class="marker" title="Playback start threshold"></div></div>
          <div class="scale"><span>−80 dBFS</span><span class="threshold-label"></span><span>−10 dBFS</span></div>
          <div class="muted audio-summary"></div>
        </div>
        <div class="section grid">
          <div class="metric"><div class="metric-label">USB input</div><div class="metric-value input-value"></div><div class="muted source"></div></div>
          <div class="metric"><div class="metric-label">Playback session</div><div class="metric-value playback-value"></div><div class="muted next-check"></div><div class="metric-label countdown-label">Time to recheck</div><div class="countdown">—</div></div>
          <div class="metric"><div class="metric-label">Last recognition</div><div class="metric-value attempt-value"></div><div class="muted attempt-meta"></div></div>
          <div class="metric"><div class="metric-label">AudD cycle usage</div><div class="metric-value usage-value"></div><div class="usage-meter"><div class="usage-fill"></div></div><div class="muted usage-meta"></div></div>
        </div>
        <div class="section error-section" hidden><div class="error"><div class="error-title">Latest issue</div><div class="error-message"></div></div></div>
      </ha-card>`;

    const root = this.shadowRoot;
    const setText = (selector, text) => { root.querySelector(selector).textContent = text; };
    setText(".status-label", label);
    setText(".session", active ? "Playback session active" : "Waiting for record playback");
    setText(".help", help);
    setText(".db-value", db === null ? "Unavailable" : `${db.toFixed(1)} dBFS`);
    root.querySelector(".fill").style.setProperty("--fill", `${dbPercent}%`);
    root.querySelector(".marker").style.setProperty("--threshold", `${thresholdPercent}%`);
    setText(".threshold-label", `Start threshold ${startDb} dBFS`);
    setText(".audio-summary", `Peak ${peakDb === null ? "—" : `${peakDb.toFixed(1)} dBFS`} · Signal ${signalState}`);
    setText(".input-value", inputState === "monitoring" ? "Monitoring" : inputState);
    setText(".source", source);
    setText(".playback-value", active ? "Active" : "Idle");
    setText(".next-check", nextCheck ? `${reason ? `${reason} · ` : ""}Next check ${nextCheck}` : (playbackAttrs.quiet ? "Input is quiet" : "No check scheduled"));
    setText(".attempt-value", attemptOutcome.replaceAll("_", " "));
    const attemptDetails = [attemptTime, attemptDuration === null ? "" : `${attemptDuration.toFixed(1)} s`, failures ? `${failures} consecutive failures` : ""].filter(Boolean).join(" · ");
    setText(".attempt-meta", attemptDetails || "No recognition attempt yet");
    setText(".usage-value", requestCount === null ? "Unavailable" : `${requestCount}${allowance === null ? "" : ` / ${allowance}`} requests`);
    root.querySelector(".usage-fill").style.setProperty("--usage", `${Math.max(0, Math.min(100, usagePercent))}%`);
    setText(".usage-meta", `${remaining === null ? "—" : `${remaining} remaining`} · ${usageStatus}${cycleEnd ? ` · resets ${cycleEnd}` : ""}`);
    const errorSection = root.querySelector(".error-section");
    errorSection.hidden = !error;
    if (error) setText(".error-message", error);
    this._updateCountdown();
  }

  _updateCountdown() {
    const node = this.shadowRoot?.querySelector(".countdown");
    const label = this.shadowRoot?.querySelector(".countdown-label");
    if (!node || !label) return;
    const playback = this._state("playback_state");
    const attrs = playback?.attributes || {};
    const active = attrs.active === true || playback?.state === "playing";
    const target = Date.parse(attrs.next_check_at || this._state("recognition_status")?.attributes?.next_check_at || "");
    if (!active || !Number.isFinite(target)) {
      node.textContent = "—";
      label.hidden = true;
      return;
    }
    label.hidden = false;
    const seconds = Math.max(0, Math.ceil((target - Date.now()) / 1000));
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    node.textContent = `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  }

  _formatTime(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  _formatDate(value) {
    const date = new Date(`${value}T12:00:00`);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString([], { month: "short", day: "numeric" });
  }

  _reason(value) {
    const labels = {
      estimated_song_end: "Song-end check", same_song_retry: "Same-song recheck",
      predicted_song_end: "Predicted song-end check",
      missing_timing_fallback: "Fallback recheck", retry_after_no_match: "Retry after no match",
      retry_after_error: "Retry after error", new_session: "New session", waiting_for_audio: "Waiting for audio",
      request_limit: "Request limit", capturing: "Capturing sample", recognizing: "Recognizing",
    };
    return labels[value] || value.replaceAll("_", " ");
  }
}

if (!customElements.get(DIAGNOSTICS_CARD_TYPE)) {
  customElements.define(DIAGNOSTICS_CARD_TYPE, TurntableRecognitionDiagnosticsCard);
}

if (!window.customCards.some((card) => card.type === DIAGNOSTICS_CARD_TYPE)) {
  window.customCards.push({
    type: DIAGNOSTICS_CARD_TYPE,
    name: "Turntable Recognition Diagnostics",
    description: "Live USB input, playback, recognition, retry, and AudD usage status.",
    preview: false,
    documentationURL: "https://github.com/brettparis37-coder/home-assistant-turntable-recognition",
    getEntitySuggestion: (hass, entityId) => {
      const match = entityId.match(/^sensor\.(.+)_recognition_status$/);
      if (!match || !hass.states[entityId]) return null;
      return { config: { type: `custom:${DIAGNOSTICS_CARD_TYPE}`, entity_prefix: match[1] } };
    },
  });
}

