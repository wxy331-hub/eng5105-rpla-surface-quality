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
  constructor({ baseUrl = "http://127.0.0.1:8766", fetchImpl = globalThis.fetch.bind(globalThis) } = {}) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.fetchImpl = fetchImpl;
  }

  async request(path, body, method = body === undefined ? "GET" : "POST") {
    let response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}/api/week7${path}`, {
        method,
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
    if (!Array.isArray(payload.image_size_px) || payload.image_size_px.length !== 2
      || !payload.image_size_px.every((value) => Number.isInteger(value) && value > 0)) {
      throw new Week7ApiError("Invalid capture configuration response");
    }
    return payload;
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
  baseUrl: import.meta.env?.VITE_WEEK7_API_URL?.trim() || "http://127.0.0.1:8766",
});
