"""Software-only tests for identity, view completeness and archive durability."""

from concurrent.futures import ThreadPoolExecutor
import csv
import io
import json
from pathlib import Path
import sqlite3

import cv2
import numpy as np
import pytest

from src.week3.models import CameraState, FramePacket
from src.week7.store import ANGLES, EVIDENCE_LABEL, LIGHTING_MODES, SampleStore


def packet(frame_id=1, source_name="week7-synthetic"):
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    image[8:15, 12:20] = (32, 127, 244)
    return FramePacket(
        source_name=source_name, frame_id=frame_id,
        captured_at_utc="2026-09-07T00:00:00.000+00:00",
        received_at_utc="2026-09-07T00:00:00.001+00:00",
        camera_state=CameraState.HEALTHY, image=image,
    )


def capture(store, session_id, angle=0, mode="bright_field", **kwargs):
    frame = kwargs.pop("packet", packet())
    return store.save_capture(
        session_id, angle, mode, frame, frame.image.copy(),
        kwargs.pop("candidates", []), lighting_metadata={"commanded_mode": mode}, **kwargs,
    )


def full_sample(store, sample_id="FIL-001"):
    sample = store.create_sample(sample_id)
    for angle in ANGLES:
        for mode in LIGHTING_MODES:
            capture(store, sample["session_id"], angle, mode)
    return store.get_sample(sample["session_id"])


def test_operator_label_is_not_session_identity_or_filesystem_path(tmp_path):
    store = SampleStore(tmp_path / "archive")
    label = "../../outside\\FIL-001"
    first = store.create_sample(label)
    second = store.create_sample(label)
    assert first["session_id"] != second["session_id"]
    assert first["sample_id"] == second["sample_id"] == label
    saved = capture(store, first["session_id"])
    path = store.image_path(saved["capture_id"], "raw")
    assert path.is_relative_to(store.root)
    assert label not in saved["raw_image_path"]
    assert store.get_sample(second["session_id"])["captures"] == []
    assert len(store.list_samples()) == 2
    assert store.path.name == "week7_samples.sqlite3"
    with pytest.raises(KeyError):
        store.get_sample(label)


def test_zero_candidates_still_archive_lossless_original_and_annotation(tmp_path):
    store = SampleStore(tmp_path)
    sample = store.create_sample("无候选样本")
    frame = packet()
    saved = capture(store, sample["session_id"], packet=frame)
    assert saved["candidates"] == []
    assert saved["candidate_count"] == 0
    assert saved["evidence_label"] == EVIDENCE_LABEL
    assert saved["calibration_id"] is None
    assert saved["size_mm"] is saved["position_mm"] is None
    assert saved["physical_outputs_allowed"] is False
    assert saved["captured_at_utc"] == frame.captured_at_utc
    assert saved["received_at_utc"] == frame.received_at_utc
    for kind in ("raw", "annotated"):
        restored = cv2.imread(str(store.image_path(saved["capture_id"], kind)))
        np.testing.assert_array_equal(restored, frame.image)
    store.close()
    reopened = SampleStore(tmp_path).get_sample(sample["session_id"])
    assert reopened["completed_views"] == 1


def test_requires_all_twelve_distinct_views_before_completion(tmp_path):
    store = SampleStore(tmp_path)
    sample = store.create_sample("FIL-002")
    assert sample["completed_views"] == 0
    assert len(sample["missing_views"]) == 12
    with pytest.raises(ValueError, match="All 12"):
        store.complete_sample(sample["session_id"])
    for angle in ANGLES:
        for mode in LIGHTING_MODES:
            capture(store, sample["session_id"], angle, mode)
    completed = store.complete_sample(sample["session_id"])
    assert completed["completed_views"] == completed["required_views"] == 12
    assert completed["missing_views"] == []
    assert completed["status"] == "completed"
    assert len(list(tmp_path.rglob("*.png"))) == 24
    assert store.complete_sample(sample["session_id"])["completed_at_utc"] == completed["completed_at_utc"]
    with pytest.raises(ValueError, match="Completed"):
        capture(store, sample["session_id"], retake=True)


def test_retake_is_explicit_and_preserves_previous_attempt(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample("FIL-003")["session_id"]
    first = capture(store, session)
    first_bytes = store.image_path(first["capture_id"], "raw").read_bytes()
    with pytest.raises(ValueError, match="explicit retake"):
        capture(store, session)
    second = capture(store, session, packet=packet(2), retake=True)
    third = capture(store, session, packet=packet(3), retake=True)
    assert second["supersedes_capture_id"] == first["capture_id"]
    assert third["supersedes_capture_id"] == second["capture_id"]
    sample = store.get_sample(session)
    assert len(sample["captures"]) == 3
    assert sample["completed_views"] == 1
    assert [c["capture_id"] for c in sample["current_views"]] == [third["capture_id"]]
    assert [c["is_current"] for c in sample["captures"]] == [False, False, True]
    assert store.image_path(first["capture_id"], "raw").read_bytes() == first_bytes
    with pytest.raises(ValueError, match="no previous"):
        capture(store, session, 60, retake=True)


def test_missing_current_image_cannot_be_replaced_by_historical_attempt(tmp_path):
    store = SampleStore(tmp_path)
    sample = full_sample(store)
    new = capture(store, sample["session_id"], retake=True)
    store.image_path(new["capture_id"], "annotated").unlink()
    sample = store.get_sample(sample["session_id"])
    assert sample["completed_views"] == 11
    assert sample["missing_views"] == [{"angle_deg": 0, "lighting_mode": "bright_field"}]
    with pytest.raises(ValueError, match="All 12"):
        store.complete_sample(sample["session_id"])
    with pytest.raises(FileNotFoundError):
        store.image_path(new["capture_id"], "annotated")


def test_completed_archive_reports_later_missing_file_and_stays_locked(tmp_path):
    store = SampleStore(tmp_path)
    sample = full_sample(store)
    store.complete_sample(sample["session_id"])
    store.image_path(sample["captures"][0]["capture_id"], "raw").unlink()
    damaged = store.get_sample(sample["session_id"])
    assert damaged["status"] == "incomplete_archive"
    assert damaged["completed_views"] == 11
    with pytest.raises(ValueError, match="Completed"):
        capture(store, sample["session_id"], retake=True)


def test_second_image_write_failure_rolls_back_and_leaves_previous_current(tmp_path, monkeypatch):
    store = SampleStore(tmp_path)
    session = store.create_sample("FIL-004")["session_id"]
    first = capture(store, session)
    old_paths = set(tmp_path.rglob("*.png"))
    write_image = store._write_image

    def fail_annotation(path, encoded):
        if path.name == "annotated.png":
            raise OSError("simulated disk full")
        write_image(path, encoded)

    monkeypatch.setattr(store, "_write_image", fail_annotation)
    with pytest.raises(OSError, match="disk full"):
        capture(store, session, retake=True)
    sample = store.get_sample(session)
    assert len(sample["captures"]) == 1
    assert sample["current_views"][0]["capture_id"] == first["capture_id"]
    assert set(tmp_path.rglob("*.png")) == old_paths
    assert not list(tmp_path.rglob("*.pending"))


def test_database_insert_failure_compensates_images_and_retake_pointer(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample("FIL-005")["session_id"]
    first = capture(store, session)
    old_paths = set(tmp_path.rglob("*.png"))
    with sqlite3.connect(store.path) as connection:
        connection.execute("CREATE TRIGGER fail_capture BEFORE INSERT ON captures "
                           "BEGIN SELECT RAISE(ABORT, 'simulated insert failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="simulated insert"):
        capture(store, session, retake=True)
    sample = store.get_sample(session)
    assert len(sample["captures"]) == 1
    assert sample["current_views"][0]["capture_id"] == first["capture_id"]
    assert set(tmp_path.rglob("*.png")) == old_paths


def test_duplicate_parallel_capture_is_serialized_across_store_instances(tmp_path):
    first_store = SampleStore(tmp_path)
    second_store = SampleStore(tmp_path)
    session = first_store.create_sample("FIL-006")["session_id"]

    def attempt(store):
        try:
            return capture(store, session)
        except ValueError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (first_store, second_store)))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, ValueError) for result in results) == 1
    assert len(first_store.get_sample(session)["captures"]) == 1
    assert len(list(tmp_path.rglob("*.png"))) == 2


@pytest.mark.parametrize("label", ["=1+1", " +SUM(A1:A2)", "-cmd", "@SUM(1,2)", "\tFIL", "\rFIL", "\nFIL"])
def test_csv_escapes_operator_formula_cells_without_changing_archive(tmp_path, label):
    store = SampleStore(tmp_path)
    session = store.create_sample(label)["session_id"]
    capture(store, session, packet=packet(source_name="=malicious"))
    rows = list(csv.DictReader(io.StringIO(store.export_csv(session))))
    assert len(rows) == 1
    assert rows[0]["sample_id"] == "'" + label
    assert rows[0]["source_name"] == "'=malicious"
    assert rows[0]["candidates_json"] == "[]"
    assert rows[0]["size_mm"] == rows[0]["position_mm"] == ""
    assert rows[0]["evidence_label"] == EVIDENCE_LABEL
    assert store.get_sample(session)["sample_id"] == label


def test_csv_preserves_attempts_candidate_json_and_calibration_metadata(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample("样本-七")["session_id"]
    first = capture(store, session, candidates=[{"defect_type": "pit_candidate", "area_px": 12.5}],
                    calibration={"calibration_id": "SYNTH-01", "status": "synthetic_reference"})
    second = capture(store, session, retake=True)
    rows = list(csv.DictReader(io.StringIO(store.export_csv(session))))
    assert [row["capture_id"] for row in rows] == [first["capture_id"], second["capture_id"]]
    assert rows[0]["sample_id"] == "样本-七"
    assert rows[0]["is_current"] == "False"
    assert rows[1]["supersedes_capture_id"] == first["capture_id"]
    assert rows[0]["calibration_id"] == "SYNTH-01"
    assert json.loads(rows[0]["candidates_json"])[0]["area_px"] == 12.5
    assert json.loads(rows[0]["lighting_metadata_json"])["commanded_mode"] == "bright_field"


@pytest.mark.parametrize("kwargs", [
    {"angle": 360}, {"angle": True}, {"angle": 0.0}, {"mode": "ambient"},
    {"retake": "false"}, {"candidates": [{"size_mm": [1, 2]}]},
    {"calibration": {"calibration_id": ""}},
])
def test_invalid_capture_inputs_do_not_create_rows_or_images(tmp_path, kwargs):
    store = SampleStore(tmp_path)
    session = store.create_sample("FIL-invalid")["session_id"]
    with pytest.raises(ValueError):
        capture(store, session, **kwargs)
    assert store.get_sample(session)["captures"] == []
    assert not list(tmp_path.rglob("*.png"))


def test_events_are_isolated_by_session_even_when_operator_labels_match(tmp_path):
    store = SampleStore(tmp_path)
    first = store.create_sample("FIL-repeated")["session_id"]
    second = store.create_sample("FIL-repeated")["session_id"]
    details = {"angle_deg": 60, "lighting_mode": "dark_field", "request_id": "request-1"}
    event = store.append_event(first, "CAPTURE_REQUESTED", details)
    details["angle_deg"] = 300
    assert event["details"]["angle_deg"] == 60
    assert event["evidence_label"] == EVIDENCE_LABEL
    assert store.get_sample(first)["events"] == [event]
    assert store.get_sample(second)["events"] == []
    assert store.get_sample(first)["completed_views"] == 0
    with pytest.raises(KeyError):
        store.append_event("unknown-session", "CAPTURE_FAILED", {"reason": "missing"})
    assert len(store.get_sample(first)["events"]) == 1


def test_workflow_failure_and_off_events_survive_store_restart_in_order(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample("FIL-events")["session_id"]
    expected = [
        store.append_event(session, "CAPTURE_REQUESTED", {"request_id": "request-2"}),
        store.append_event(session, "CAPTURE_FAILED", {"reason": "simulated stale frame"}),
        store.append_event(session, "LIGHTING_OFF", {"simulated": True, "acknowledged": True}),
    ]
    store.close()
    restarted = SampleStore(tmp_path)
    assert restarted.get_sample(session)["events"] == expected
    assert restarted.list_samples()[0]["events"] == expected
    assert restarted.get_sample(session)["captures"] == []
    # Invalid metadata fails before a partial event row can be committed.
    with pytest.raises(ValueError):
        restarted.append_event(session, "CAPTURE_FAILED", {"value": float("nan")})
    assert restarted.get_sample(session)["events"] == expected

def test_analysis_is_stored_with_its_capture_and_legacy_captures_stay_unassessed(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample("FIL-ANALYSIS")["session_id"]
    legacy = capture(store, session)
    analysis = {"algorithm_version": "static-rpla-geometry-1", "geometry_status": "rejected",
                "reason_codes": ["FOCUS_INADEQUATE"], "candidates": [], "metrics": {"edge_spread_px_median": 64.2}}
    saved = capture(store, session, angle=60, analysis=analysis)
    assert saved["analysis"]["capture_id"] == saved["capture_id"]
    assert saved["analysis_status"] == "rejected"
    sample = store.get_sample(session)
    by_id = {item["capture_id"]: item for item in sample["captures"]}
    assert by_id[legacy["capture_id"]]["analysis"] is None
    assert by_id[legacy["capture_id"]]["analysis_status"] == "legacy_unassessed"
    assert by_id[saved["capture_id"]]["analysis"]["metrics"]["edge_spread_px_median"] == 64.2
    rows = {row["capture_id"]: row for row in csv.DictReader(io.StringIO(store.export_csv(session)))}
    assert rows[saved["capture_id"]]["analysis_status"] == "rejected"
    assert rows[saved["capture_id"]]["analysis_reason_codes"] == "FOCUS_INADEQUATE"
    assert rows[legacy["capture_id"]]["analysis_status"] == "legacy_unassessed"


@pytest.mark.parametrize("analysis", [{"reason_codes": []}, {"geometry_status": "valid", "x": float("nan")}])
def test_invalid_analysis_creates_no_capture(tmp_path, analysis):
    store = SampleStore(tmp_path)
    session = store.create_sample("FIL-BAD")["session_id"]
    with pytest.raises(ValueError):
        capture(store, session, analysis=analysis)
    sample = store.get_sample(session)
    assert sample["captures"] == [] and sample["events"] == []
    assert list(tmp_path.rglob("*.png")) == []


def test_failed_commit_leaves_no_orphan_analysis_event(tmp_path):
    store = SampleStore(tmp_path)
    session = store.create_sample("FIL-GUARD")["session_id"]

    class Guard:
        def __enter__(self):
            raise ConnectionError("camera lost before commit")

        def __exit__(self, *exc):
            return False

    with pytest.raises(ConnectionError):
        capture(store, session, analysis={"geometry_status": "valid", "candidates": []}, commit_guard=Guard)
    sample = store.get_sample(session)
    assert sample["captures"] == []
    assert not any(event["event_type"] == "CAPTURE_ANALYSIS" for event in sample["events"])
