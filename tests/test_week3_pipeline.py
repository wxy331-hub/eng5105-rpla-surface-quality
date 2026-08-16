import json
import sqlite3

import numpy as np
import pytest

from src.week3 import (
    BaselineVisionProcessor,
    CameraState,
    DetectionRecord,
    FramePacket,
    QualityGrade,
    SQLiteInspectionRepository,
    SyntheticCameraSource,
)
from src.week3.models import utc_now_iso
from src.week3_offline_demo import run_offline_pipeline


def test_synthetic_source_uses_stable_frame_contract() -> None:
    source = SyntheticCameraSource(width_px=320, height_px=180)
    assert source.state is CameraState.DISCONNECTED
    source.connect()
    packet = next(source.frames(1))
    assert packet.source_name == "SYNTHETIC_OFFLINE"
    assert packet.image.shape == (180, 320, 3)
    assert packet.camera_state is CameraState.HEALTHY
    source.disconnect()
    assert source.state is CameraState.DISCONNECTED


def test_physical_values_require_calibration() -> None:
    with pytest.raises(ValueError, match="calibration_id"):
        DetectionRecord(
            detection_id="DET-1",
            batch_id="B-1",
            camera_source="SYNTHETIC_OFFLINE",
            frame_id=0,
            received_at_utc=utc_now_iso(),
            defect_type="pit_candidate",
            bbox_px=(1, 2, 3, 4),
            area_px=12.0,
            confidence=0.7,
            quality_grade=QualityGrade.WARNING,
            algorithm_version="test",
            size_mm=(1.0, 1.0),
        )


def test_repository_deletes_only_requested_detection_records(tmp_path) -> None:
    path = tmp_path / "delete-records.db"
    with SQLiteInspectionRepository(path) as repository:
        repository.start_batch("B-DELETE", "TEST", "test")
        for detection_id in ("DET-KEEP", "DET-DELETE"):
            repository.append_detection(DetectionRecord(
                detection_id=detection_id,
                batch_id="B-DELETE",
                camera_source="TEST",
                frame_id=1,
                received_at_utc=utc_now_iso(),
                defect_type="contamination_candidate",
                bbox_px=(1, 2, 3, 4),
                area_px=12.0,
                confidence=0.7,
                quality_grade=QualityGrade.WARNING,
                algorithm_version="test",
            ))

        assert repository.delete_detections("B-DELETE", ["DET-DELETE"]) == 1
        assert [item["detection_id"] for item in repository.list_detections("B-DELETE")] == ["DET-KEEP"]

        # The delete is irreversible, so the audit event must survive it and must
        # still name what was removed.
        audit = repository.connection.execute(
            "SELECT details_json FROM system_events WHERE event_type = 'DETECTION_RECORDS_DELETED'"
        ).fetchall()
        assert len(audit) == 1
        details = json.loads(audit[0][0])
        assert details["requested_ids"] == ["DET-DELETE"]
        assert details["deleted_count"] == 1
        assert details["deletion_mode"] == "DEVELOPMENT_HARD_DELETE"


def test_repository_enforces_foreign_keys_and_enables_wal(tmp_path) -> None:
    with SQLiteInspectionRepository(tmp_path / "integrity.db") as repository:
        assert repository.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert repository.connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"

        with pytest.raises(sqlite3.IntegrityError):
            repository.append_detection(DetectionRecord(
                detection_id="DET-ORPHAN",
                batch_id="NO-SUCH-BATCH",
                camera_source="TEST",
                frame_id=0,
                received_at_utc=utc_now_iso(),
                defect_type="pit_candidate",
                bbox_px=(1, 2, 3, 4),
                area_px=12.0,
                confidence=0.7,
                quality_grade=QualityGrade.WARNING,
                algorithm_version="test",
            ))


def test_processor_marks_results_as_synthetic_candidates() -> None:
    source = SyntheticCameraSource()
    source.connect()
    packet = next(source.frames(1))
    _, records = BaselineVisionProcessor().process(packet, "B-1")
    assert records
    assert all(record.data_mode == "synthetic_baseline" for record in records)
    assert all(record.defect_type.endswith("_candidate") for record in records)
    assert all(record.position_mm is None and record.size_mm is None for record in records)


def test_synthetic_sequence_exercises_three_candidate_types() -> None:
    source = SyntheticCameraSource()
    source.connect()
    processor = BaselineVisionProcessor()
    types = {
        record.defect_type
        for packet in source.frames(3)
        for record in processor.process(packet, "B-1")[1]
    }
    assert types == {
        "pit_candidate",
        "scratch_candidate",
        "contamination_candidate",
    }


def test_offline_pipeline_writes_database_json_csv_and_frames(tmp_path) -> None:
    config = {
        "batch_id": "TEST-BATCH",
        "frame_count": 4,
        "width_px": 320,
        "height_px": 180,
        "seed": 5105,
        "threshold": 145,
        "min_area_px": 40,
    }
    summary = run_offline_pipeline(config, tmp_path)

    assert summary["status"] == "PASS"
    assert summary["evidence_level"] == "OFFLINE_SYNTHETIC_ONLY"
    assert summary["frames_processed"] == 4
    assert summary["detections_recorded"] >= 3
    assert (tmp_path / "detections.json").is_file()
    assert (tmp_path / "detections.csv").is_file()
    assert len(list((tmp_path / "annotated").glob("*.jpg"))) == 4

    with sqlite3.connect(tmp_path / "week3_offline.db") as connection:
        detections = connection.execute(
            "SELECT COUNT(*), COUNT(position_mm), COUNT(size_mm_json) FROM detections"
        ).fetchone()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert detections[0] == summary["detections_recorded"]
    assert detections[1:] == (0, 0)
    assert {"batches", "detections", "system_events", "calibrations"} <= tables
