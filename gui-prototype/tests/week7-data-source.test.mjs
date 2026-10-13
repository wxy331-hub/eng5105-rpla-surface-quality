import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { WEEK7_ANGLES, WEEK7_LIGHTS, Week7ApiError, Week7DataSource, sampleCaptureState } from "../src/services/week7DataSource.js";

function response(payload, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload };
}

test("sample health polling backs off, recovers, and stops after unmount", async () => {
  // Run the component's polling effect with a fake timer, without a browser or service.
  const source = readFileSync(new URL("../src/Week7SamplePanel.jsx", import.meta.url), "utf8");
  const effect = source.match(/\/\/ Poll only while the workbench is mounted\.[\s\S]*?useEffect\(\(\) => \{([\s\S]*?)\}, \[dataSource\]\);/);
  assert.ok(effect, "the sample health polling effect must exist");
  const runEffect = new Function("dataSource", "window", "setServiceHealth", "setPendingDeletions", "pendingDeletionSessions", effect[1]);
  let timer;
  let fail = true;
  let release;
  let pending = false;
  const delays = [];
  const updates = [];
  const health = { camera: { connected: true, capture_available: true } };
  const cleanup = runEffect({ getHealth: async () => {
    if (pending) await new Promise((resolve) => { release = resolve; });
    if (fail) throw new Error("service unavailable");
    return health;
  } }, {
    setTimeout(callback, delay) { timer = callback; delays.push(delay); return callback; },
    clearTimeout(handle) { if (timer === handle) timer = null; },
  }, (value) => updates.push(value), () => {}, () => []);

  for (let failure = 0; failure < 5; failure += 1) await timer();
  assert.deepEqual(delays, [2000, 4000, 8000, 16000, 30000, 30000]);
  assert.deepEqual(updates, [null, null, null, null, null], "each failure revokes capture");
  fail = false;
  await timer();
  assert.equal(delays.at(-1), 2000, "the first success restores normal polling");
  assert.equal(updates.at(-1), health);
  fail = true;
  await timer();
  assert.equal(delays.at(-1), 4000, "a new failure starts from the normal interval");

  pending = true;
  const inFlight = timer();
  cleanup();
  const countBeforeCompletion = [delays.length, updates.length];
  release();
  await inFlight;
  assert.equal(timer, null);
  assert.deepEqual([delays.length, updates.length], countBeforeCompletion, "an unmounted request must not update state or schedule another poll");
});

test("a sample session can be created, resumed, captured and retaken one view at a time, and completed", async () => {
  const calls = [];
  const sample = { sample_id: "W7-001", session_id: "session-001", status: "in_progress", captures: [], evidence_label: "OFFLINE_SYNTHETIC_ONLY" };
  const adapter = new Week7DataSource({
    baseUrl: "http://127.0.0.1:8766/",
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return response(url.endsWith("/samples") && options.method === "GET" ? { samples: [sample] } : sample);
    },
  });
  assert.equal(calls.length, 0, "constructing an adapter must not connect to either service");
  assert.deepEqual(await adapter.listSamples(), [sample]);
  assert.equal((await adapter.createSample("  W7-001  ")).session_id, sample.session_id);
  assert.equal((await adapter.getSample(sample.session_id)).evidence_label, "OFFLINE_SYNTHETIC_ONLY");
  await adapter.capture(sample.session_id, 60, { lightingMode: "bright_field" });
  await adapter.capture(sample.session_id, 60, { lightingMode: "bright_field", retake: true });
  await adapter.completeSample(sample.session_id);
  assert.ok(calls.every(({ url }) => url.startsWith("http://127.0.0.1:8766/api/week7/")));
  assert.deepEqual(JSON.parse(calls[1].options.body), { sample_id: "W7-001" });
  assert.equal(calls[2].options.method, "GET");
  assert.deepEqual(JSON.parse(calls[3].options.body), { angle_deg: 60, lighting_mode: "bright_field", retake: false }, "one request identifies exactly one lighting view");
  assert.deepEqual(JSON.parse(calls[4].options.body), { angle_deg: 60, lighting_mode: "bright_field", retake: true }, "retaking identifies the same individual view");
  assert.equal(calls[5].url, "http://127.0.0.1:8766/api/week7/samples/session-001/complete");
  assert.equal(calls[5].options.method, "POST");
  assert.equal(calls[5].options.headers["Content-Type"], "application/json");
});

test("the default browser fetch keeps the global receiver when called through the adapter", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = function () {
    assert.equal(this, globalThis, "browser fetch requires the Window/global receiver");
    return Promise.resolve(response({ samples: [] }));
  };
  try {
    const adapter = new Week7DataSource();
    assert.deepEqual(await adapter.listSamples(), []);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("new capture dimensions come from the health API and remain separate from archived session dimensions", async () => {
  const current = {
    source_name: "PLAN_A_SYNTHETIC_TRIGGERED", image_size_px: [3840, 2160],
    roi_px: [168, 864, 3504, 432], evidence_label: "OFFLINE_SYNTHETIC_ONLY",
  };
  const archived = {
    session_id: "archive-small", capture_compatible: false,
    capture_configuration: { source_name: "WEEK7_SYNTHETIC_TRIGGERED", image_size_px: [640, 360] },
    capture_block_reason: "This session uses a different capture configuration. Create a new sample session to use the current configuration.",
  };
  const urls = [];
  const adapter = new Week7DataSource({ fetchImpl: async (url) => {
    urls.push(url);
    return response(url.endsWith("/health") ? current : archived);
  } });
  assert.equal(await adapter.getHealth(), current);
  assert.equal(await adapter.getSample("archive-small"), archived);
  assert.deepEqual(current.image_size_px, [3840, 2160]);
  assert.deepEqual(archived.capture_configuration.image_size_px, [640, 360]);
  assert.equal(archived.capture_compatible, false);
  assert.ok(urls[0].endsWith("/api/week7/health"));
  current.image_size_px = [1920, 1080];
  assert.deepEqual((await adapter.getHealth()).image_size_px, [1920, 1080], "configuration is never replaced by a hardcoded UHD value");
});

test("invalid or missing capture dimensions cannot be advertised as a valid new-session configuration", async () => {
  for (const size of [undefined, null, [3840], [3840, 2160, 1], [0, 2160], [3840, -1], [3840, "2160"]]) {
    const adapter = new Week7DataSource({ fetchImpl: async () => response({ image_size_px: size }) });
    await assert.rejects(adapter.getHealth(), /Invalid capture configuration/);
  }
});

test("sample and capture identifiers stay inside a single encoded API path segment", async () => {
  const urls = [];
  const adapter = new Week7DataSource({ fetchImpl: async (url) => { urls.push(url); return response({}); } });
  await adapter.getSample("specimen / 2?");
  assert.ok(urls[0].endsWith("/samples/specimen%20%2F%202%3F"));
  assert.equal(adapter.imageUrl("capture / 3", "raw"), "http://127.0.0.1:8765/api/week7/captures/capture%20%2F%203/raw.png");
  assert.ok(adapter.imageUrl("capture-3", "annotated").endsWith("/capture-3/annotated.png"));
  assert.ok(adapter.exportUrl("session / 3").endsWith("/samples/session%20%2F%203/export.csv"));
  assert.equal(urls.length, 1, "image and export links do not fetch until requested by the user/browser");
});

test("invalid capture angles and empty sample identifiers never reach the service", () => {
  let calls = 0;
  const adapter = new Week7DataSource({ fetchImpl: async () => { calls += 1; return response({}); } });
  assert.deepEqual(WEEK7_ANGLES, [0, 60, 120, 180, 240, 300]);
  assert.deepEqual(WEEK7_LIGHTS, ["bright_field", "dark_field"]);
  for (const value of [-60, 30, 360, "60", null]) {
    assert.throws(() => adapter.capture("session-1", value, { lightingMode: "bright_field" }), Week7ApiError);
  }
  for (const value of [undefined, null, "both", "bright", "BRIGHT_FIELD", 0]) {
    assert.throws(() => adapter.capture("session-1", 0, { lightingMode: value }), /Unsupported lighting mode/);
  }
  assert.throws(() => adapter.createSample("  "), /Sample ID/);
  assert.throws(() => adapter.imageUrl("capture-1", "../../image"), /Unsupported image/);
  assert.equal(calls, 0);
});

test("backend completion refusal and archive conflict remain visible errors", async () => {
  const adapter = new Week7DataSource({ fetchImpl: async () => response({ detail: "Missing views: 240/dark_field" }, 409) });
  await assert.rejects(adapter.completeSample("session-1"), (error) => {
    assert.equal(error.status, 409);
    assert.equal(error.message, "Missing views: 240/dark_field");
    return true;
  });
});

test("a failed dark-field capture refreshes the durable archive without replacing the original error", async () => {
  const calls = [];
  const partial = {
    session_id: "partial-1", status: "in_progress", completed_views: 1,
    current_views: [{ capture_id: "bright-1", angle_deg: 0, lighting_mode: "bright_field" }],
    missing_views: [{ angle_deg: 0, lighting_mode: "dark_field" }],
    events: [{ event_type: "CAPTURE_FAILED", details: { reason: "Dark field timed out" } }],
  };
  const adapter = new Week7DataSource({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return options.method === "POST" ? response({ detail: "Dark field timed out" }, 409) : response(partial);
  } });
  await assert.rejects(adapter.capture("partial-1", 0, { lightingMode: "dark_field" }), (error) => {
    assert.equal(error.message, "Dark field timed out");
    assert.equal(error.status, 409);
    assert.equal(error.sample, partial);
    assert.equal(error.sample.current_views[0].lighting_mode, "bright_field");
    return true;
  });
  assert.equal(calls.length, 2);
  assert.ok(calls[1].url.endsWith("/samples/partial-1"));
  assert.equal(calls[1].options.method, "GET");
});

test("a failed session refresh retains both the capture error and the refresh failure", async () => {
  const adapter = new Week7DataSource({ fetchImpl: async (_url, options) => {
    if (options.method === "POST") return response({ detail: "Camera unavailable" }, 409);
    throw new TypeError("Failed to fetch session");
  } });
  await assert.rejects(adapter.capture("partial-1", 0, { lightingMode: "bright_field" }), (error) => {
    assert.equal(error.message, "Camera unavailable");
    assert.equal(error.sample, undefined);
    assert.equal(error.sampleRefreshError.message, "Failed to fetch session");
    return true;
  });
});

test("dark-field selection sends only one capture request and never triggers bright-field capture", async () => {
  const calls = [];
  const adapter = new Week7DataSource({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return response({ session_id: "one-view" });
  } });
  await adapter.capture("one-view", 120, { lightingMode: "dark_field" });
  assert.equal(calls.length, 1);
  assert.deepEqual(JSON.parse(calls[0].options.body), { angle_deg: 120, lighting_mode: "dark_field", retake: false });
});

test("deletion targets one encoded session and preserves pending file-cleanup status", async () => {
  const calls = [];
  const deleted = { deleted_session_id: "sample / 3", sample_id: "SAMPLE-3", deleted_capture_count: 2, deleted_image_count: 4, cleanup_pending: true };
  const adapter = new Week7DataSource({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return response(deleted);
  } });
  assert.equal(await adapter.deleteSample("sample / 3"), deleted);
  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.endsWith("/samples/sample%20%2F%203"));
  assert.equal(calls[0].options.method, "DELETE");
  assert.equal(calls[0].options.body, undefined);
  const failed = new Week7DataSource({ fetchImpl: async () => response({ detail: "Archive unavailable" }, 503) });
  await assert.rejects(failed.deleteSample("sample-3"), error => error.status === 503 && error.message === "Archive unavailable");
});

test("unavailable service and invalid responses do not appear as empty archives", async () => {
  const unavailable = new Week7DataSource({ fetchImpl: async () => { throw new TypeError("Failed to fetch"); } });
  await assert.rejects(unavailable.listSamples(), (error) => error instanceof Week7ApiError && error.status === 0);
  const malformed = new Week7DataSource({ fetchImpl: async () => response({ samples: null }) });
  await assert.rejects(malformed.listSamples(), /Invalid samples response/);
  const notJson = new Week7DataSource({ fetchImpl: async () => ({ ok: false, status: 502, json: async () => { throw new Error("not JSON"); } }) });
  await assert.rejects(notJson.listSamples(), /HTTP 502/);
});

test("camera preview and reconnect share the capture service origin", async () => {
  const calls = [];
  const source = new Week7DataSource({ fetchImpl: async (url, options) => { calls.push({ url, options }); return response({ status: "RECONNECTING" }); } });
  assert.equal(source.previewUrl(3), "http://127.0.0.1:8765/api/stream.mjpg?session=3");
  // A split-preview service (Raspberry Pi) names its unanalysed live stream; only API paths are taken.
  assert.equal(source.previewUrl(3, "/api/preview.mjpg"), "http://127.0.0.1:8765/api/preview.mjpg?session=3");
  assert.equal(source.previewUrl(3, "http://elsewhere/x"), "http://127.0.0.1:8765/api/stream.mjpg?session=3");
  await source.reconnect();
  assert.equal(calls[0].url, "http://127.0.0.1:8765/api/control/reconnect");
  assert.equal(calls[0].options.method, "POST");
});

test("hardware capture fails closed until the service grants a fresh connected frame", async () => {
  for (const health of [null, {}, { camera: { connected: true } }, { camera: { connected: false, capture_available: true } }, { camera: { connected: true, capture_available: false } }]) {
    assert.equal(sampleCaptureState(health).available, false);
    assert.equal(sampleCaptureState(health).synthetic, false);
  }
  const live = { evidence_label: "LIVE_INTEGRATION_ONLY", source_name: "ALC_IMX258_USB", camera: { connected: true, capture_available: true, status: "HEALTHY" }, image_size_px: [3840, 2160] };
  assert.equal(sampleCaptureState(live).available, true);
  assert.equal(sampleCaptureState(live).sourceName, "ALC_IMX258_USB");
  assert.equal(sampleCaptureState({ evidence_label: "OFFLINE_SYNTHETIC_ONLY" }).available, true);
  const waiting = { image_size_px: null, camera: { connected: false, capture_available: false } };
  const adapter = new Week7DataSource({ fetchImpl: async () => response(waiting) });
  assert.equal(await adapter.getHealth(), waiting, "missing hardware frames still expose connection state");
});
