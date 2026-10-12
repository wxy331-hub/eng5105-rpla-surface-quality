#!/usr/bin/env python3
"""Record bounded Week 8 observations from the service that owns the camera.

This tool issues only HTTP GET requests. It neither opens a camera nor changes
camera controls. JSONL retains service responses; summary.json describes sampled
observations, without claiming optical, latency, or endurance acceptance.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
MAX_DURATION_S = 300.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REAL_SOURCES = {"usb_uvc", "esp32_mjpeg"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _dimensions(width: Any, height: Any, combined: Any = None) -> list[int] | None:
    if isinstance(combined, (list, tuple)) and len(combined) == 2:
        width, height = combined
    numbers = [_number(width), _number(height)]
    if any(value is None or value <= 0 or not value.is_integer() for value in numbers):
        return None
    return [int(value) for value in numbers]


def normalize_observation(payload: dict[str, Any]) -> dict[str, Any]:
    """Read the workbench health and continuous-service snapshot contracts."""
    base = _mapping(payload.get("summary")) or payload
    camera = _mapping(base.get("camera"))
    requested = _mapping(camera.get("requested_mode")) or _mapping(camera.get("requested"))
    actual = _mapping(camera.get("actual"))
    state = _first(camera.get("camera_state"), camera.get("status"), base.get("camera_state"))
    evidence = _first(camera.get("source_evidence"), base.get("source_evidence"), base.get("evidence_label"), base.get("evidence_level"))
    return {
        "evidence_label": evidence,
        "source_type": _first(camera.get("source_type"), base.get("source_type")),
        "source_name": _first(camera.get("source_name"), base.get("source_name"), base.get("camera_source")),
        "camera_state": state.upper() if isinstance(state, str) else None,
        "connected": camera.get("connected"),
        "capture_available": camera.get("capture_available"),
        "connection_generation": camera.get("generation"),
        "hardware_stream_verified": _first(camera.get("hardware_stream_verified"), base.get("hardware_stream_verified")),
        "driver_reported_properties": _mapping(camera.get("reported_properties")),
        "driver_reported_properties_basis": camera.get("reported_properties_basis"),
        "frames_received": _number(_first(camera.get("frames_received"), base.get("frames_received"))),
        "frame_age_ms": _number(_first(camera.get("frame_age_ms"), base.get("frame_age_ms"))),
        "reported_fps": _number(_first(camera.get("measured_acquisition_fps"), camera.get("measured_pipeline_fps"), base.get("measured_pipeline_fps"))),
        "requested_image_size_px": _dimensions(
            _first(requested.get("width_px"), camera.get("requested_width_px"), base.get("requested_width_px")),
            _first(requested.get("height_px"), camera.get("requested_height_px"), base.get("requested_height_px")),
            _first(requested.get("image_size_px"), camera.get("requested_image_size_px")),
        ),
        "actual_image_size_px": _dimensions(
            _first(actual.get("width_px"), camera.get("frame_width_px"), base.get("frame_width_px")),
            _first(actual.get("height_px"), camera.get("frame_height_px"), base.get("frame_height_px")),
            _first(actual.get("image_size_px"), camera.get("actual_image_size_px")),
        ),
        "requested_pixel_format": _first(requested.get("pixel_format"), camera.get("requested_pixel_format"), base.get("requested_pixel_format")),
        "requested_fps": _number(_first(requested.get("fps"), camera.get("requested_fps"), base.get("requested_fps"))),
        "last_error": _first(camera.get("last_error"), base.get("last_error"), base.get("last_fault")),
    }


def fetch_json(url: str, timeout_s: float, *, opener: Callable = urlopen) -> dict[str, Any]:
    def invalid_constant(value: str) -> None:
        raise ValueError(f"Non-finite JSON number: {value}")

    with opener(url, timeout=timeout_s) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Service response exceeds 2 MiB limit")
    payload = json.loads(data, parse_constant=invalid_constant)
    if not isinstance(payload, dict):
        raise ValueError("Service response must be a JSON object")
    return payload


def summarize_observations(records: list[dict[str, Any]]) -> dict[str, Any]:
    good = [record for record in records if record.get("observation") is not None]
    observations = [record["observation"] for record in good]
    changes: list[dict[str, Any]] = []
    counter_resets = 0
    received_delta = 0.0
    counted_elapsed = 0.0
    previous = None
    for record in records:
        current = record.get("observation")
        if current is None:
            # An HTTP gap cannot prove continuity of a cumulative counter.
            previous = None
            continue
        if previous is not None:
            old = previous["observation"]
            if current["camera_state"] != old["camera_state"]:
                changes.append({"elapsed_s": record["elapsed_s"], "from": old["camera_state"], "to": current["camera_state"]})
            same_source = (current["source_type"], current["source_name"]) == (old["source_type"], old["source_name"])
            same_generation = current["connection_generation"] == old["connection_generation"]
            before, after = old["frames_received"], current["frames_received"]
            elapsed = record["elapsed_s"] - previous["elapsed_s"]
            if same_source and before is not None and after is not None and elapsed > 0:
                if after < before:
                    counter_resets += 1
                elif same_generation:
                    received_delta += after - before
                    counted_elapsed += elapsed
        previous = record
    labels = sorted({str(row["evidence_label"]) for row in observations if row["evidence_label"] is not None})
    live_reported = bool(observations) and all(
        row["evidence_label"] == "LIVE_INTEGRATION_ONLY" and row["source_type"] in REAL_SOURCES
        and row["hardware_stream_verified"] is not False
        for row in observations
    )
    if len(labels) == 1 and labels[0] in {"OFFLINE_SYNTHETIC_ONLY", "OFFLINE_FAULT_INJECTION_ONLY"}:
        evidence = labels[0]
    elif live_reported and received_delta > 0:
        evidence = "LIVE_INTEGRATION_ONLY"
    else:
        evidence = "PENDING_REAL_MATERIAL"
    fps = [row["reported_fps"] for row in observations if row["reported_fps"] is not None]
    sizes = {tuple(row["actual_image_size_px"]) for row in observations if row["actual_image_size_px"] is not None}
    requested_sizes = {tuple(row["requested_image_size_px"]) for row in observations if row["requested_image_size_px"] is not None}
    return {
        "evidence_label": evidence,
        "service_evidence_labels": labels,
        "observation_status": "recorded" if good else "service_unavailable",
        "samples": len(records),
        "successful_samples": len(good),
        "http_error_samples": len(records) - len(good),
        "service_error_samples": sum(bool(row["last_error"]) for row in observations),
        "camera_states_observed": sorted({row["camera_state"] for row in observations if row["camera_state"] is not None}),
        "state_transitions_observed": changes,
        "disconnect_transitions_observed": sum(change["to"] == "DISCONNECTED" for change in changes),
        "recovery_transitions_observed": sum(change["to"] == "HEALTHY" and change["from"] not in {None, "HEALTHY"} for change in changes),
        "counter_resets_observed": counter_resets,
        "frames_received_delta_in_contiguous_samples": int(received_delta),
        "counted_interval_s": round(counted_elapsed, 6),
        "observed_received_fps": round(received_delta / counted_elapsed, 3) if counted_elapsed > 0 else None,
        "service_reported_fps": {"min": min(fps), "median": statistics.median(fps), "max": max(fps)} if fps else None,
        "requested_image_sizes_px": [list(size) for size in sorted(requested_sizes)],
        "actual_image_sizes_px": [list(size) for size in sorted(sizes)],
        "actual_image_size_basis": "service_accepted_frame_dimensions",
        "last_observation": observations[-1] if observations else None,
        "interpretation": "Sampled service observations only. FPS is received-frame throughput or a service-reported rate, not R4/R5 latency. Unobserved intervals may contain disconnects. Device identity, exposure/control lock, optical quality, calibration, physical safety, and R7 event-record completeness require separate evidence.",
        "physical_measurements_verified": False,
        "hardware_acceptance_passed": False,
        "r4_r5_r7_verified": False,
    }


def record_readiness(
    endpoint: str,
    output_root: Path,
    *,
    duration_s: float = 30.0,
    interval_s: float = 1.0,
    timeout_s: float = 3.0,
    fetch: Callable[[str, float], dict[str, Any]] = fetch_json,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[Path, dict[str, Any]]:
    """Write a new run directory; injected HTTP and clock keep tests hardware-free."""
    for name, value, lower, upper in (
        ("duration_s", duration_s, 0.1, MAX_DURATION_S),
        ("interval_s", interval_s, 0.1, 30.0),
        ("timeout_s", timeout_s, 0.1, 10.0),
    ):
        number = _number(value)
        if number is None or not lower <= number <= upper:
            raise ValueError(f"{name} must be between {lower} and {upper}")
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("endpoint must be an HTTP(S) URL without embedded credentials")
    if parsed.path not in {"/api/week7/health", "/api/snapshot"} or parsed.query or parsed.fragment:
        raise ValueError("endpoint must end in /api/week7/health or /api/snapshot")
    started_at = utc_now()
    run_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:10]
    run_dir = Path(output_root) / run_name
    run_dir.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, Any]] = []
    start = monotonic()
    with (run_dir / "observations.jsonl").open("x", encoding="utf-8") as stream:
        while True:
            requested_at = monotonic()
            record: dict[str, Any] = {"observed_at_utc": utc_now()}
            try:
                payload = fetch(endpoint, min(timeout_s, max(0.1, duration_s - (requested_at - start))))
                if not isinstance(payload, dict):
                    raise ValueError("Service response must be a JSON object")
                record.update(payload=payload, observation=normalize_observation(payload), error=None)
            except (OSError, ValueError) as exc:
                record.update(payload=None, observation=None, error={"type": type(exc).__name__, "message": str(exc)})
            finished = monotonic()
            record.update(elapsed_s=round(finished - start, 6), request_duration_s=round(finished - requested_at, 6))
            records.append(record)
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            remaining = duration_s - (finished - start)
            if remaining <= 0:
                break
            sleep(min(interval_s, remaining))
            if monotonic() - start >= duration_s:
                break
    summary = {
        "schema_version": 1, "started_at_utc": started_at, "finished_at_utc": utc_now(),
        "endpoint": endpoint, "configured_duration_s": duration_s, "observed_duration_s": round(monotonic() - start, 6),
        "poll_interval_s": interval_s, "request_timeout_s": timeout_s,
        "host_platform": platform.platform(), "python_version": platform.python_version(),
        "raw_observations": "observations.jsonl", **summarize_observations(records),
    }
    with (run_dir / "summary.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return run_dir, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8765/api/week7/health")
    parser.add_argument("--output", type=Path, default=ROOT / "data/output/week8_camera_readiness")
    parser.add_argument("--duration", type=float, default=30.0, help="Observation seconds, 0.1 to 300 (default 30)")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()
    try:
        path, summary = record_readiness(args.endpoint, args.output, duration_s=args.duration, interval_s=args.interval, timeout_s=args.timeout)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Could not record camera observations: {exc}\n")
    print(json.dumps({"output": str(path.resolve()), "evidence_label": summary["evidence_label"],
                      "successful_samples": summary["successful_samples"], "http_error_samples": summary["http_error_samples"],
                      "observed_received_fps": summary["observed_received_fps"]}, ensure_ascii=False, indent=2))
    return 0 if summary["successful_samples"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
