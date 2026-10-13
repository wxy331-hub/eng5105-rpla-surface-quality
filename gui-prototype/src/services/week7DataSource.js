export const WEEK7_ANGLES = Object.freeze([0, 60, 120, 180, 240, 300]);
export const WEEK7_LIGHTS = Object.freeze(["bright_field", "dark_field"]);

export class Week7ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "Week7ApiError";
    this.status = status;
  }
}

/** The sample workbench talks only to this adapter; importing it makes no requests. */
export class Week7DataSource {
  constructor({ baseUrl = "http://127.0.0.1:8765", fetchImpl = globalThis.fetch.bind(globalThis) } = {}) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.fetchImpl = fetchImpl;
  }

  async request(path, body, method = body === undefined ? "GET" : "POST", prefix = "/api/week7") {
    let response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}${prefix}${path}`, {
        method,
        cache: "no-store",
        // A capture inspects a 4K frame and writes two PNGs; on a Raspberry Pi 4B
        // the inspection alone took about 4.7 s (2026-10-13), so allow a minute.
        signal: AbortSignal.timeout(path === "/health" ? 3500 : 60000),
        headers: body === undefined ? { Accept: "application/json" } : {
          Accept: "application/json", "Content-Type": "application/json",
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch (error) {
      throw new Week7ApiError(error.message || "Local sample service unavailable");
    }
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Week7ApiError(payload?.detail || `HTTP ${response.status}`, response.status);
    }
    if (payload === null) throw new Week7ApiError("Invalid JSON response", response.status);
    return payload;
  }

  async listSamples() {
    const payload = await this.request("/samples");
    if (!Array.isArray(payload.samples)) throw new Week7ApiError("Invalid samples response");
    return payload.samples;
  }

  async getHealth() {
    const payload = await this.request("/health");
    const pendingCamera = payload.camera && payload.camera.capture_available === false
      && (payload.image_size_px == null || (Array.isArray(payload.image_size_px)
        && payload.image_size_px.length === 2 && payload.image_size_px.every((value) => value == null || value === 0)));
    if (!pendingCamera && (!Array.isArray(payload.image_size_px) || payload.image_size_px.length !== 2
      || !payload.image_size_px.every((value) => Number.isInteger(value) && value > 0))) {
      throw new Week7ApiError("Invalid capture configuration response");
    }
    return payload;
  }

  reconnect() {
    return this.request("/reconnect", undefined, "POST", "/api/control");
  }

  /** previewPath comes from the service health; a split-preview service names its unanalysed live stream. */
  previewUrl(revision = 0, previewPath = null) {
    const path = typeof previewPath === "string" && previewPath.startsWith("/api/") ? previewPath : "/api/stream.mjpg";
    return `${this.baseUrl}${path}?session=${encodeURIComponent(revision)}`;
  }

  createSample(sampleId) {
    const id = sampleId.trim();
    if (!id) throw new Week7ApiError("Sample ID is required");
    return this.request("/samples", { sample_id: id });
  }

  getSample(sessionId) {
    return this.request(`/samples/${encodeURIComponent(sessionId)}`);
  }

  capture(sessionId, angleDeg, { lightingMode, retake = false } = {}) {
    if (!WEEK7_ANGLES.includes(angleDeg)) throw new Week7ApiError("Unsupported angle");
    if (!WEEK7_LIGHTS.includes(lightingMode)) throw new Week7ApiError("Unsupported lighting mode");
    return this.request(`/samples/${encodeURIComponent(sessionId)}/capture`, {
      angle_deg: angleDeg, lighting_mode: lightingMode, retake: Boolean(retake),
    }).catch(async (error) => {
      // A failure after archival may still have saved the requested view.
      // Recover durable state while preserving the original capture error.
      try { error.sample = await this.getSample(sessionId); }
      catch (refreshError) { error.sampleRefreshError = refreshError; }
      throw error;
    });
  }

  deleteSample(sessionId) {
    return this.request(`/samples/${encodeURIComponent(sessionId)}`, undefined, "DELETE");
  }

  completeSample(sessionId) {
    return this.request(`/samples/${encodeURIComponent(sessionId)}/complete`, {});
  }

  imageUrl(captureId, variant = "raw") {
    if (!["raw", "annotated"].includes(variant)) throw new Week7ApiError("Unsupported image variant");
    return `${this.baseUrl}/api/week7/captures/${encodeURIComponent(captureId)}/${variant}.png`;
  }

  exportUrl(sessionId) {
    return `${this.baseUrl}/api/week7/samples/${encodeURIComponent(sessionId)}/export.csv`;
  }
}

export const week7DataSource = new Week7DataSource({
  // A same-origin build is served by the camera service itself (Raspberry Pi
  // demonstration), so another computer's browser must not fall back to its own 127.0.0.1.
  baseUrl: (import.meta.env?.VITE_SERVICE_SAME_ORIGIN === "1" ? globalThis.location?.origin : null)
    || import.meta.env?.VITE_SAMPLE_API_URL?.trim() || import.meta.env?.VITE_WEEK7_API_URL?.trim()
    || import.meta.env?.VITE_INSPECTION_API_URL?.trim() || "http://127.0.0.1:8765",
});

/** Camera capture requires an explicit fresh-state grant; old synthetic APIs stay opt-in. */
export function sampleCaptureState(health) {
  const synthetic = health?.evidence_label === "OFFLINE_SYNTHETIC_ONLY";
  const camera = health?.camera;
  return {
    synthetic,
    connected: camera?.connected === true,
    available: synthetic ? Boolean(health) : camera?.connected === true && camera?.capture_available === true,
    status: camera?.status || (synthetic ? "SYNTHETIC" : "DISCONNECTED"),
    sourceName: health?.source_name || camera?.source_name || null,
  };
}
