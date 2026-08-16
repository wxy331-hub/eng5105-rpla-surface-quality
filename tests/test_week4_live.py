from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.week4_live_demo import EVIDENCE_LEVEL, load_config, parse_roi, run_live_pipeline


class FakeCapture:
    def __init__(self, _url: str) -> None:
        self.opened = True

    def isOpened(self) -> bool:
        return self.opened

    def read(self):
        image = np.full((180, 320, 3), 70, dtype=np.uint8)
        cv2.circle(image, (160, 90), 14, (230, 230, 230), -1)
        return True, image

    def release(self) -> None:
        self.opened = False


def live_config() -> dict:
    return {
        "batch_id": "TEST-W4-LIVE",
        "source_name": "ESP32S3_OV3660",
        "frame_count": 6,
        "roi_px": [20, 40, 280, 100],
        "threshold": 145,
        "min_area_px": 30,
    }


def test_parse_roi() -> None:
    assert parse_roi("1,2,30,40") == (1, 2, 30, 40)
    with pytest.raises(Exception):
        parse_roi("1,2,-3,4")


def test_live_pipeline_writes_honest_integration_evidence(tmp_path) -> None:
    summary = run_live_pipeline(
        "http://192.0.2.1:81/stream",
        live_config(),
        tmp_path,
        capture_factory=FakeCapture,
    )
    assert summary["status"] == "PASS"
    assert summary["evidence_level"] == EVIDENCE_LEVEL
    assert summary["hardware_stream_verified"] is True
    assert summary["rpla_defect_performance_verified"] is False
    assert summary["physical_measurements_available"] is False
    assert summary["frames_received"] == 6
    assert summary["recovery_frames_skipped"] == 2
    assert summary["frames_processed_when_healthy"] == 4
    assert (tmp_path / "raw_frame.jpg").is_file()
    assert (tmp_path / "annotated_frame.jpg").is_file()
    assert (tmp_path / "detections.json").is_file()
    assert (tmp_path / "detections.csv").is_file()
    assert (tmp_path / "summary.json").is_file()
    with sqlite3.connect(tmp_path / "week4_live.db") as connection:
        physical_values = connection.execute(
            "SELECT COUNT(position_mm), COUNT(size_mm_json) FROM detections"
        ).fetchone()
        modes = {row[0] for row in connection.execute("SELECT DISTINCT data_mode FROM detections")}
    assert physical_values == (0, 0)
    assert modes == {EVIDENCE_LEVEL}


def test_live_config_file_is_valid() -> None:
    path = Path(__file__).resolve().parents[1] / "config" / "week4_live.json"
    config = load_config(path)
    assert config["source_name"] == "ESP32S3_OV3660"
    assert len(config["roi_px"]) == 4
    assert json.loads(path.read_text(encoding="utf-8"))["frame_count"] == 12
