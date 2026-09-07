function pixelDimension(value) {
  return Number.isInteger(value) && value > 0 ? value : null;
}

/**
 * Keep delivered image dimensions separate from a requested camera mode.
 * Missing image dimensions stay unknown even when a capture request is known.
 * A matching request and image size does not establish rate or hardware quality.
 */
export function createResolutionMetadata({
  widthPx, heightPx, synthetic = false,
  requestedWidthPx, requestedHeightPx, requestedPixelFormat, requestedFps,
} = {}) {
  const hasFrame = pixelDimension(widthPx) !== null && pixelDimension(heightPx) !== null;
  const hasRequest = pixelDimension(requestedWidthPx) !== null && pixelDimension(requestedHeightPx) !== null;
  return {
    frameWidthPx: hasFrame ? widthPx : null,
    frameHeightPx: hasFrame ? heightPx : null,
    resolution: hasFrame ? `${widthPx} × ${heightPx}` : "Waiting for frame",
    resolutionKind: hasFrame ? (synthetic ? "synthetic" : "decoded") : "unavailable",
    requestedWidthPx: hasRequest ? requestedWidthPx : null,
    requestedHeightPx: hasRequest ? requestedHeightPx : null,
    requestedResolution: hasRequest ? `${requestedWidthPx} × ${requestedHeightPx}` : null,
    requestedPixelFormat: typeof requestedPixelFormat === "string" ? requestedPixelFormat.trim() || null : null,
    requestedFps: Number.isFinite(requestedFps) && requestedFps > 0 ? requestedFps : null,
  };
}
