"""Run the Week 3 camera-to-database flow without physical hardware."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import cv2

from src.week3 import BaselineVisionProcessor, SQLiteInspectionRepository, SyntheticCameraSource


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config: dict[str, Any] = json.load(handle)
    required = {"batch_id", "frame_count", "width_px", "height_px", "threshold", "min_area_px"}
    missing = sorted(required.difference(config))
    if missing:
        raise ValueError(f"configuration is missing: {', '.join(missing)}")
    return config


def run_offline_pipeline(config: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    annotated_dir = output_dir / "annotated"
    annotated_dir.mkdir(exist_ok=True)
    database_path = output_dir / "week3_offline.db"
    if database_path.exists():
        database_path.unlink()

    source = SyntheticCameraSource(
        width_px=int(config["width_px"]),
        height_px=int(config["height_px"]),
        seed=int(config.get("seed", 5105)),
    )
    processor = BaselineVisionProcessor(
        threshold=int(config["threshold"]),
        min_area_px=float(config["min_area_px"]),
    )
    batch_id = str(config["batch_id"])
    frame_count = int(config["frame_count"])
    all_records: list[dict[str, Any]] = []

    with SQLiteInspectionRepository(database_path) as repository:
        source.connect()
        repository.start_batch(batch_id, source.source_name, "synthetic_baseline")
        repository.append_event(source.source_name, "CAMERA_STATE", {"state": source.state.value})
        try:
            for packet in source.frames(frame_count):
                annotated, records = processor.process(packet, batch_id)
                image_path = annotated_dir / f"frame_{packet.frame_id:04d}.jpg"
                if not cv2.imwrite(str(image_path), annotated):
                    raise OSError(f"could not write annotated frame: {image_path}")
                for record in records:
                    repository.append_detection(record)
            all_records = repository.list_detections(batch_id)
        finally:
            source.disconnect()
            repository.append_event(source.source_name, "CAMERA_STATE", {"state": source.state.value})

    json_path = output_dir / "detections.json"
    json_path.write_text(json.dumps(all_records, indent=2), encoding="utf-8")
    csv_path = output_dir / "detections.csv"
    if all_records:
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(all_records[0]))
            writer.writeheader()
            writer.writerows(all_records)
    else:
        csv_path.write_text("", encoding="utf-8")

    summary = {
        "status": "PASS",
        "evidence_level": "OFFLINE_SYNTHETIC_ONLY",
        "batch_id": batch_id,
        "camera_source": source.source_name,
        "frames_processed": frame_count,
        "detections_recorded": len(all_records),
        "physical_measurements_available": False,
        "database_path": str(database_path.resolve()),
        "json_path": str(json_path.resolve()),
        "csv_path": str(csv_path.resolve()),
        "annotated_frames_path": str(annotated_dir.resolve()),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("config/week3_offline.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/output/week3_offline")
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = run_offline_pipeline(load_config(args.config), args.output)
        print(json.dumps(result, indent=2))
        return 0
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
