/* Turntable Recognition Lovelace card. */
const CARD_TYPE = "turntable-now-playing-card";

class TurntableNowPlayingCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
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

    const entity = this._hass?.states?.[this._config.entity];
    const attributes = entity?.attributes || {};
    const title = attributes.title || (entity?.state !== "Nothing playing" ? entity?.state : "") || "";
    const artist = attributes.artist || "";
    const album = attributes.album || "";
    const year = attributes.year || attributes.master_year || attributes.release_year || "";
    const artwork = attributes.artwork_url || attributes.master_artwork_url || attributes.release_artwork_url || "";
    const idle = !entity || !title || ["unknown", "unavailable", "Nothing playing"].includes(entity.state);
    const renderKey = JSON.stringify([entity?.state, title, artist, album, year, artwork, idle]);
    if (renderKey === this._renderKey) return;
    this._renderKey = renderKey;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card {
          box-sizing: border-box;
          padding: 18px;
          color: var(--primary-text-color);
          background: var(--ha-card-background, var(--card-background-color, var(--primary-background-color)));
          overflow: hidden;
        }
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
      <ha-card>
        <div class="layout ${idle ? "idle" : ""}">
          <div class="art"></div>
          <div class="details">
            <div class="eyebrow">${idle ? "Turntable" : "Now playing"}</div>
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
