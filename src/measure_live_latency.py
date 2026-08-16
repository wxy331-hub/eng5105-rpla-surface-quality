"""Measure the physical OV3660 path from a camera control change to the API image.

The OV3660 MJPEG stream does not expose a sensor capture timestamp. This test
therefore uses a reversible brightness transition as the observable input and
measures until that transition appears in the resident service's JPEG output.
It is live hardware evidence, but it is not exposure-to-screen latency.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _get_json(url: str, timeout_s: float = 3.0) -> dict[str, Any]:
    request = Request(url, headers={"Cache-Control": "no-cache"})
    with urlopen(request, timeout=timeout_s) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_bytes(url: str, timeout_s: float = 3.0) -> bytes:
    request = Request(url, headers={"Cache-Control": "no-cache"})
    with urlopen(request, timeout=timeout_s) as response:
        return response.read()


def _set_control(control_base_url: str, name: str, value: int) -> None:
    query = urlencode({"var": name, "val": value})
    with urlopen(f"{control_base_url}/control?{query}", timeout=5) as response:
        response.read()


def _mean_luma(jpeg: bytes) -> float:
    encoded = np.frombuffer(jpeg, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("the resident service returned an invalid JPEG")
    return float(np.mean(image))


def _next_frame(
    api_base_url: str,
    after_frame_id: int,
    deadline: float,
) -> tuple[dict[str, Any], float]:
    while time.perf_counter() < deadline:
        health = _get_json(f"{api_base_url}/api/health")
        frame_id = int(health.get("current_frame_id", -1))
        if frame_id > after_frame_id:
            cache_key = time.time_ns()
            jpeg = _get_bytes(f"{api_base_url}/api/frame.jpg?v={cache_key}")
            return health, _mean_luma(jpeg)
        time.sleep(0.02)
    raise TimeoutError("no new resident-service frame arrived before the deadline")


def _wait_for_transition(
    api_base_url: str,
    reference_luma: float,
    after_frame_id: int,
    minimum_luma_delta: float,
    timeout_s: float,
) -> tuple[dict[str, Any], float, float]:
    deadline = time.perf_counter() + timeout_s
    latest_frame_id = after_frame_id
    largest_delta = 0.0
    while time.perf_counter() < deadline:
        health, luma = _next_frame(api_base_url, latest_frame_id, deadline)
        latest_frame_id = int(health["current_frame_id"])
        delta = abs(luma - reference_luma)
        largest_delta = max(largest_delta, delta)
        if delta >= minimum_luma_delta:
            return health, luma, delta
    raise TimeoutError(
        f"brightness transition was not visible; largest mean-luma delta was {largest_delta:.2f}"
    )


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def measure(args: argparse.Namespace) -> dict[str, Any]:
    status = _get_json(f"{args.control_base_url}/status")
    original_brightness = int(status["brightness"])
    target_brightness = -2 if original_brightness > -2 else 2
    initial = _get_json(f"{args.api_base_url}/api/health")
    if initial.get("camera_state") != "HEALTHY":
        raise RuntimeError(f"camera must be HEALTHY, got {initial.get('camera_state')}")
    if (initial.get("frame_width_px"), initial.get("frame_height_px")) != (800, 600):
        raise RuntimeError("the latency test must use the selected SVGA 800x600 profile")

    transitions: list[dict[str, Any]] = []
    try:
        baseline_health, baseline_luma = _next_frame(
            args.api_base_url,
            int(initial.get("current_frame_id", -1)),
            time.perf_counter() + args.transition_timeout_s,
        )
        for trial in range(1, args.trials + 1):
            start = time.perf_counter()
            _set_control(args.control_base_url, "brightness", target_brightness)
            changed_health, changed_luma, changed_delta = _wait_for_transition(
                args.api_base_url,
                baseline_luma,
                int(baseline_health["current_frame_id"]),
                args.minimum_luma_delta,
                args.transition_timeout_s,
            )
            transitions.append(
                {
                    "trial": trial,
                    "direction": f"brightness_{original_brightness}_to_{target_brightness}",
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                    "frame_id": int(changed_health["current_frame_id"]),
                    "mean_luma": round(changed_luma, 2),
                    "mean_luma_delta": round(changed_delta, 2),
                }
            )

            start = time.perf_counter()
            _set_control(args.control_base_url, "brightness", original_brightness)
            restored_health, restored_luma, restored_delta = _wait_for_transition(
                args.api_base_url,
                changed_luma,
                int(changed_health["current_frame_id"]),
                args.minimum_luma_delta,
                args.transition_timeout_s,
            )
            transitions.append(
                {
                    "trial": trial,
                    "direction": f"brightness_{target_brightness}_to_{original_brightness}",
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                    "frame_id": int(restored_health["current_frame_id"]),
                    "mean_luma": round(restored_luma, 2),
                    "mean_luma_delta": round(restored_delta, 2),
                }
            )
            baseline_health = restored_health
            baseline_luma = restored_luma
            time.sleep(args.settle_s)
    finally:
        _set_control(args.control_base_url, "brightness", original_brightness)

    latencies = [float(item["latency_ms"]) for item in transitions]
    return {
        "evidence_level": "LIVE_CAMERA_CONTROL_TO_API_IMAGE_RESPONSE",
        "tested_at_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "camera_path": "PLAN_B_ESP32S3_OV3660_MJPEG",
        "resolution": "SVGA 800x600",
        "api_base_url": args.api_base_url,
        "camera_control_base_url": args.control_base_url,
        "trials": args.trials,
        "transition_count": len(transitions),
        "median_latency_ms": round(statistics.median(latencies), 2),
        "p95_latency_ms": round(_percentile(latencies, 0.95), 2),
        "minimum_latency_ms": round(min(latencies), 2),
        "maximum_latency_ms": round(max(latencies), 2),
        "transitions": transitions,
        "scope": "Camera control request through physical OV3660, Wi-Fi MJPEG, Python processing, and resident API JPEG publication.",
        "not_included": "Scene/exposure timestamp and browser paint latency; the OV3660 MJPEG stream exposes no sensor capture timestamp.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-base-url", default="http://172.20.10.2")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--minimum-luma-delta", type=float, default=4.0)
    parser.add_argument("--transition-timeout-s", type=float, default=5.0)
    parser.add_argument("--settle-s", type=float, default=0.25)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "output" / "latency" / "latency_20260811.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = measure(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
