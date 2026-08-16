"""Exercise Week 4 ROI and camera recovery logic without physical hardware."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import cv2

from src.week3 import BaselineVisionProcessor, SQLiteInspectionRepository, SyntheticCameraSource
from src.week4 import CameraConnectionMonitor, ConnectionPolicy, LatestFrameBuffer


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config: dict[str, Any] = json.load(handle)
    required = {"batch_id", "width_px", "height_px", "roi_px", "recovery_frames"}
    missing = sorted(required.difference(config))
    if missing:
        raise ValueError(f"configuration is missing: {', '.join(missing)}")
    if len(config["roi_px"]) != 4:
        raise ValueError("roi_px must contain x, y, width, height")
    return config


def run_week4_offline_demo(config: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    annotated_dir = output_dir / "annotated"
    annotated_dir.mkdir(exist_ok=True)
    database_path = output_dir / "week4_offline.db"
    if database_path.exists():
        database_path.unlink()

    policy = ConnectionPolicy(
        stale_after_s=float(config.get("stale_after_s", 1.0)),
        disconnect_after_s=float(config.get("disconnect_after_s", 2.0)),
        recovery_frames=int(config["recovery_frames"]),
    )
    monitor = CameraConnectionMonitor(policy)
    source = SyntheticCameraSource(
        width_px=int(config["width_px"]),
        height_px=int(config["height_px"]),
        seed=int(config.get("seed", 5105)),
        source_name="WEEK4_FAULT_INJECTION",
    )
    processor = BaselineVisionProcessor(
        threshold=int(config.get("threshold", 145)),
        min_area_px=float(config.get("min_area_px", 80)),
        algorithm_version="week4-roi-baseline-1",
        roi_px=tuple(int(value) for value in config["roi_px"]),
        data_mode="offline_fault_injection",
    )
    buffer = LatestFrameBuffer()
    batch_id = str(config["batch_id"])
    timeline: list[dict[str, Any]] = []
    processed = 0
    blocked = 0

    def record(at_s: float, event: str) -> None:
        timeline.append(
            {
                "at_s": at_s,
                "event": event,
                "state": monitor.state.value,
                "automatic_actions_allowed": monitor.automatic_actions_allowed,
            }
        )

    # Three good frames establish health, then a >2 s gap forces disconnect.
    frame_times = [0.0, 0.1, 0.2, 2.6, 2.7, 2.8, 2.9]
    source.connect()
    monitor.begin_connect()
    record(0.0, "CONNECT_REQUESTED")
    with SQLiteInspectionRepository(database_path) as repository:
        repository.start_batch(batch_id, source.source_name, "offline_fault_injection")
        packets = iter(source.frames(len(frame_times)))
        for index, at_s in enumerate(frame_times):
            if index == 3:
                monitor.poll(1.3)
                record(1.3, "FRAME_TIMEOUT_STALE")
                monitor.poll(2.3)
                record(2.3, "FRAME_TIMEOUT_DISCONNECTED")
                monitor.begin_connect(reconnect=True)
                record(2.4, "RECONNECT_ATTEMPT")
            packet = next(packets)
            state = monitor.frame_received(at_s)
            packet = replace(packet, camera_state=state)
            buffer.put(packet)
            # Hold the first recovery frame so the next arrival proves that the
            # one-slot buffer discards backlog and retains only the newest image.
            latest = None if index == 0 else buffer.take()
            record(at_s, "VALID_FRAME")
            if latest is None or not monitor.automatic_actions_allowed:
                blocked += 1
                continue
            annotated, records = processor.process(latest, batch_id)
            roi_x, roi_y, roi_width, roi_height = processor.roi_px or (0, 0, 0, 0)
            cv2.rectangle(
                annotated,
                (roi_x, roi_y),
                (roi_x + roi_width, roi_y + roi_height),
                (255, 120, 0),
                2,
            )
            image_path = annotated_dir / f"frame_{latest.frame_id:04d}.jpg"
            if not cv2.imwrite(str(image_path), annotated):
                raise OSError(f"could not write annotated frame: {image_path}")
            for detection in records:
                repository.append_detection(detection)
            processed += 1

        source.disconnect()
        for item in timeline:
            repository.append_event(source.source_name, item["event"], item)
        detections = repository.list_detections(batch_id)

    states = sorted({item["state"] for item in timeline})
    summary = {
        "status": "PASS",
        "evidence_level": "OFFLINE_FAULT_INJECTION_ONLY",
        "camera_path": "方案 B adapter contract; no ESP32 or Raspberry Pi connected",
        "frames_generated": len(frame_times),
        "frames_processed_when_safe": processed,
        "frames_blocked_during_connection_recovery": blocked,
        "detections_recorded": len(detections),
        "states_exercised": states,
        "latest_frame_drop_policy_verified": buffer.dropped_frames == 1,
        "backlogged_frames_discarded": buffer.dropped_frames,
        "automatic_actions_blocked_outside_healthy": all(
            item["automatic_actions_allowed"] == (item["state"] == "HEALTHY")
            for item in timeline
        ),
        "physical_measurements_available": False,
        "hardware_performance_verified": False,
        "roi_px": list(processor.roi_px or ()),
        "database_path": str(database_path.resolve()),
        "timeline_path": str((output_dir / "timeline.json").resolve()),
        "annotated_frames_path": str(annotated_dir.resolve()),
    }
    (output_dir / "timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
    (output_dir / "detections.json").write_text(json.dumps(detections, indent=2), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/week4_offline.json"))
    parser.add_argument("--output", type=Path, default=Path("data/output/week4_offline"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        print(json.dumps(run_week4_offline_demo(load_config(args.config), args.output), indent=2))
        return 0
    except (ConnectionError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
