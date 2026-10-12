from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import cv2
import numpy as np
import pytest

from src.week4_live_demo import load_config, parse_roi, rebuild_live_database, run_live_pipeline


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


def test_injected_pipeline_keeps_offline_evidence_through_export_and_rebuild(tmp_path) -> None:
    summary = run_live_pipeline(
        "http://192.0.2.1:81/stream",
        live_config(),
        tmp_path,
        capture_factory=FakeCapture,
    )
    assert summary["status"] == "PASS"
    assert summary["evidence_level"] == "OFFLINE_FAULT_INJECTION_ONLY"
    assert summary["hardware_stream_verified"] is False
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
    with closing(sqlite3.connect(tmp_path / "week4_live.db")) as connection:
        physical_values = connection.execute(
            "SELECT COUNT(position_mm), COUNT(size_mm_json) FROM detections"
        ).fetchone()
        modes = {row[0] for row in connection.execute("SELECT DISTINCT data_mode FROM detections")}
        batch_modes = {row[0] for row in connection.execute("SELECT data_mode FROM batches")}
    assert physical_values == (0, 0)
    assert modes == batch_modes == {"OFFLINE_FAULT_INJECTION_ONLY"}
    rebuild_live_database(tmp_path)
    with closing(sqlite3.connect(tmp_path / "week4_live.db")) as connection:
        assert connection.execute("SELECT data_mode FROM batches").fetchone()[0] == "OFFLINE_FAULT_INJECTION_ONLY"


@pytest.mark.parametrize("url", [
    "local.avi", "C:\\captures\\replay.mp4", "file:///tmp/replay.avi", "ftp://camera/stream", "http:///stream",
])
def test_live_pipeline_rejects_non_http_camera_sources_before_writing(tmp_path, url):
    output = tmp_path / "capture"
    with pytest.raises(ValueError, match="HTTP"):
        run_live_pipeline(url, live_config(), output, capture_factory=FakeCapture)
    assert not output.exists()


def test_representative_images_share_a_frame_without_impersonating_record_images(tmp_path):
    class ChangingCapture(FakeCapture):
        frame_id = 0

        def read(self):
            self.frame_id += 1
            image = np.full((180, 320, 3), 20 * self.frame_id, dtype=np.uint8)
            cv2.circle(image, (100 + self.frame_id * 10, 90), 14, (230, 230, 230), -1)
            return True, image

    summary = run_live_pipeline(
        "https://192.0.2.1/stream", live_config(), tmp_path, capture_factory=ChangingCapture,
    )
    records = json.loads((tmp_path / "detections.json").read_text())
    assert len({record["frame_id"] for record in records}) > 1
    assert all(record["image_path"] is None for record in records)
    assert summary["representative_frame_id"] == 5
    raw = cv2.imread(str(tmp_path / "raw_frame.jpg"))
    annotated = cv2.imread(str(tmp_path / "annotated_frame.jpg"))
    np.testing.assert_allclose(raw[0, 0], [120, 120, 120], atol=2)
    np.testing.assert_array_equal(raw[0, 0], annotated[0, 0])


def test_live_config_file_is_valid() -> None:
    path = Path(__file__).resolve().parents[1] / "config" / "week4_live.json"
    config = load_config(path)
    assert config["source_name"] == "ESP32S3_OV3660"
    assert len(config["roi_px"]) == 4
    assert json.loads(path.read_text(encoding="utf-8"))["frame_count"] == 12
