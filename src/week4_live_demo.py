"""Run the Week 4 live OV3660 camera-to-storage integration pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import cv2

from src.week3 import (
    BaselineVisionProcessor,
    CameraState,
    DetectionRecord,
    QualityGrade,
    SQLiteInspectionRepository,
)
from src.week4 import Esp32MjpegSource


EVIDENCE_LEVEL = "LIVE_INTEGRATION_ONLY"


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config: dict[str, Any] = json.load(handle)
    required = {"batch_id", "source_name", "frame_count", "roi_px", "threshold", "min_area_px"}
    missing = sorted(required.difference(config))
    if missing:
        raise ValueError(f"configuration is missing: {', '.join(missing)}")
    if len(config["roi_px"]) != 4:
        raise ValueError("roi_px must contain x, y, width, height")
    if int(config["frame_count"]) <= 0:
        raise ValueError("frame_count must be positive")
    return config


def parse_roi(value: str) -> tuple[int, int, int, int]:
    try:
        roi = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ROI must use integer x,y,width,height") from exc
    if len(roi) != 4 or roi[0] < 0 or roi[1] < 0 or roi[2] <= 0 or roi[3] <= 0:
        raise argparse.ArgumentTypeError("ROI must have non-negative origin and positive size")
    return roi


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_live_pipeline(
    stream_url: str,
    config: dict[str, Any],
    output_dir: Path,
    *,
    roi_override: tuple[int, int, int, int] | None = None,
    frame_count_override: int | None = None,
    capture_factory: Callable[[str], Any] = cv2.VideoCapture,
) -> dict[str, Any]:
    """Acquire real frames and verify integration without claiming defect accuracy."""
    if "<ESP32_IP>" in stream_url:
        raise ValueError("replace <ESP32_IP> with the actual device address")
    frame_count = frame_count_override or int(config["frame_count"])
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    roi_px = roi_override or tuple(int(value) for value in config["roi_px"])

    output_dir.mkdir(parents=True, exist_ok=True)
    database_path = output_dir / "week4_live.db"
    pending_database_path = output_dir / "week4_live.pending.db"
    if pending_database_path.exists():
        pending_database_path.unlink()
    raw_path = output_dir / "raw_frame.jpg"
    annotated_path = output_dir / "annotated_frame.jpg"
    pending_raw_path = output_dir / "raw_frame.pending.jpg"
    pending_annotated_path = output_dir / "annotated_frame.pending.jpg"
    json_path = output_dir / "detections.json"
    csv_path = output_dir / "detections.csv"

    source = Esp32MjpegSource(
        stream_url,
        source_name=str(config["source_name"]),
        capture_factory=capture_factory,
    )
    processor = BaselineVisionProcessor(
        threshold=int(config["threshold"]),
        min_area_px=float(config["min_area_px"]),
        algorithm_version="week4-live-roi-baseline-1",
        roi_px=roi_px,
        data_mode=EVIDENCE_LEVEL,
    )
    batch_id = str(config["batch_id"])
    frames_received = 0
    frames_processed = 0
    recovery_frames_skipped = 0
    states_seen: list[str] = []
    first_shape: tuple[int, int] | None = None
    started = time.perf_counter()

    with SQLiteInspectionRepository(pending_database_path) as repository:
        repository.start_batch(batch_id, source.source_name, EVIDENCE_LEVEL)
        source.connect()
        repository.append_event(
            source.source_name,
            "CAMERA_CONNECT_REQUESTED",
            {"state": source.state.value, "evidence_level": EVIDENCE_LEVEL},
        )
        previous_state = source.state
        try:
            for packet in source.frames(frame_count):
                frames_received += 1
                state_name = packet.camera_state.value
                if state_name not in states_seen:
                    states_seen.append(state_name)
                if packet.camera_state is not previous_state:
                    repository.append_event(
                        source.source_name,
                        "CAMERA_STATE_CHANGED",
                        {"from": previous_state.value, "to": state_name},
                    )
                    previous_state = packet.camera_state

                height, width = packet.image.shape[:2]
                if first_shape is None:
                    first_shape = (width, height)
                if packet.camera_state is not CameraState.HEALTHY:
                    recovery_frames_skipped += 1
                    continue

                if not pending_raw_path.exists() and not cv2.imwrite(str(pending_raw_path), packet.image):
                    raise OSError(f"could not write raw frame: {pending_raw_path}")
                annotated, records = processor.process(packet, batch_id)
                roi_x, roi_y, roi_width, roi_height = roi_px
                cv2.rectangle(
                    annotated,
                    (roi_x, roi_y),
                    (roi_x + roi_width, roi_y + roi_height),
                    (255, 120, 0),
                    2,
                )
                for record in records:
                    repository.append_detection(
                        replace(record, image_path=str(annotated_path.resolve()))
                    )
                if not cv2.imwrite(str(pending_annotated_path), annotated):
                    raise OSError(f"could not write annotated frame: {pending_annotated_path}")
                frames_processed += 1
        finally:
            source.disconnect()
            repository.append_event(
                source.source_name,
                "CAMERA_DISCONNECTED_BY_CLIENT",
                {"state": source.state.value},
            )
        detections = repository.list_detections(batch_id)

    elapsed_s = time.perf_counter() - started
    if first_shape is None or frames_received == 0:
        raise ConnectionError("no valid live frames were received")
    if frames_processed == 0:
        raise ConnectionError("camera never reached HEALTHY state")

    pending_database_path.replace(database_path)
    pending_raw_path.replace(raw_path)
    pending_annotated_path.replace(annotated_path)
    json_path.write_text(json.dumps(detections, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(csv_path, detections)
    summary = {
        "status": "PASS",
        "evidence_level": EVIDENCE_LEVEL,
        "camera_path": "PLAN_B_ESP32S3_OV3660_MJPEG",
        "camera_source": source.source_name,
        "batch_id": batch_id,
        "stream_url": stream_url,
        "frames_received": frames_received,
        "frames_processed_when_healthy": frames_processed,
        "recovery_frames_skipped": recovery_frames_skipped,
        "elapsed_s": round(elapsed_s, 3),
        "measured_pipeline_fps": round(frames_received / elapsed_s, 2),
        "frame_width_px": first_shape[0],
        "frame_height_px": first_shape[1],
        "roi_px": list(roi_px),
        "states_seen": states_seen,
        "recovery_frames_required": source.monitor.policy.recovery_frames,
        "candidate_records": len(detections),
        "hardware_stream_verified": True,
        "rpla_defect_performance_verified": False,
        "physical_measurements_available": False,
        "raw_frame_path": str(raw_path.resolve()),
        "annotated_frame_path": str(annotated_path.resolve()),
        "database_path": str(database_path.resolve()),
        "json_path": str(json_path.resolve()),
        "csv_path": str(csv_path.resolve()),
        "interpretation": (
            "Candidate regions only verify the live image-processing and persistence path; "
            "they are not validated rPLA defects."
        ),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def rebuild_live_database(output_dir: Path) -> Path:
    """Recreate SQLite from completed JSON evidence after an interrupted refresh."""
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    records = json.loads((output_dir / "detections.json").read_text(encoding="utf-8"))
    if not records:
        raise ValueError("detections.json contains no completed records")
    batch_id = str(summary.get("batch_id") or records[0]["batch_id"])
    database_path = output_dir / "week4_live.db"
    pending_path = output_dir / "week4_live.rebuild.db"
    if pending_path.exists():
        pending_path.unlink()
    with SQLiteInspectionRepository(pending_path) as repository:
        repository.start_batch(batch_id, str(summary["camera_source"]), EVIDENCE_LEVEL)
        repository.append_event(
            str(summary["camera_source"]),
            "EVIDENCE_DATABASE_REBUILT",
            {"source": "detections.json", "record_count": len(records)},
        )
        for item in records:
            repository.append_detection(
                DetectionRecord(
                    detection_id=item["detection_id"],
                    batch_id=item["batch_id"],
                    camera_source=item["camera_source"],
                    frame_id=int(item["frame_id"]),
                    received_at_utc=item["received_at_utc"],
                    defect_type=item["defect_type"],
                    bbox_px=tuple(int(value) for value in item["bbox_px"]),
                    area_px=float(item["area_px"]),
                    confidence=float(item["confidence"]),
                    quality_grade=QualityGrade(item["quality_grade"]),
                    algorithm_version=item["algorithm_version"],
                    data_mode=item["data_mode"],
                    position_mm=item["position_mm"],
                    size_mm=tuple(item["size_mm"]) if item["size_mm"] else None,
                    calibration_id=item["calibration_id"],
                    image_path=item["image_path"],
                )
            )
    pending_path.replace(database_path)
    return database_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="MJPEG URL, e.g. http://192.168.0.8:81/stream")
    parser.add_argument("--config", type=Path, default=Path("config/week4_live.json"))
    parser.add_argument("--output", type=Path, default=Path("data/output/week4_live"))
    parser.add_argument("--frames", type=int, help="Override the configured frame count")
    parser.add_argument("--roi", type=parse_roi, help="Override ROI as x,y,width,height")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_live_pipeline(
            args.url,
            load_config(args.config),
            args.output,
            roi_override=args.roi,
            frame_count_override=args.frames,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ConnectionError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
