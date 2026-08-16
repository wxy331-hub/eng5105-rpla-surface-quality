"""SQLite persistence for the Week 3 inspection contracts."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import DetectionRecord, utc_now_iso


SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    started_at_utc TEXT NOT NULL,
    source_name TEXT NOT NULL,
    data_mode TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS detections (
    detection_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES batches(batch_id),
    camera_source TEXT NOT NULL,
    frame_id INTEGER NOT NULL,
    received_at_utc TEXT NOT NULL,
    defect_type TEXT NOT NULL,
    bbox_px_json TEXT NOT NULL,
    area_px REAL NOT NULL,
    confidence REAL NOT NULL,
    quality_grade TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    data_mode TEXT NOT NULL,
    position_mm REAL,
    size_mm_json TEXT,
    calibration_id TEXT,
    image_path TEXT
);
CREATE TABLE IF NOT EXISTS system_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at_utc TEXT NOT NULL,
    source_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calibrations (
    calibration_id TEXT PRIMARY KEY,
    created_at_utc TEXT NOT NULL,
    camera_source TEXT NOT NULL,
    pixels_per_mm REAL NOT NULL,
    evidence_path TEXT NOT NULL
);
"""


class SQLiteInspectionRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        # Both pragmas must run outside a transaction or SQLite silently ignores
        # them. WAL lets the acquisition thread keep writing while an API-thread
        # connection reads or deletes; without it the two connections contend for
        # the same write lock and raise "database is locked". Foreign keys are off
        # by default, which would leave the detections -> batches reference
        # decorative and allow orphaned evidence rows.
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteInspectionRepository":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def start_batch(self, batch_id: str, source_name: str, data_mode: str) -> None:
        self.connection.execute(
            "INSERT INTO batches(batch_id, started_at_utc, source_name, data_mode) "
            "VALUES (?, ?, ?, ?)",
            (batch_id, utc_now_iso(), source_name, data_mode),
        )
        self.connection.commit()

    def append_detection(self, record: DetectionRecord) -> None:
        data = record.to_dict()
        self.connection.execute(
            """INSERT INTO detections(
                detection_id, batch_id, camera_source, frame_id, received_at_utc,
                defect_type, bbox_px_json, area_px, confidence, quality_grade,
                algorithm_version, data_mode, position_mm, size_mm_json,
                calibration_id, image_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["detection_id"], data["batch_id"], data["camera_source"],
                data["frame_id"], data["received_at_utc"], data["defect_type"],
                json.dumps(data["bbox_px"]), data["area_px"], data["confidence"],
                data["quality_grade"], data["algorithm_version"], data["data_mode"],
                data["position_mm"], json.dumps(data["size_mm"]) if data["size_mm"] else None,
                data["calibration_id"], data["image_path"],
            ),
        )
        self.connection.commit()

    def append_event(self, source_name: str, event_type: str, details: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO system_events(occurred_at_utc, source_name, event_type, details_json) "
            "VALUES (?, ?, ?, ?)",
            (utc_now_iso(), source_name, event_type, json.dumps(details, sort_keys=True)),
        )
        self.connection.commit()

    def list_detections(self, batch_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM detections WHERE batch_id = ? ORDER BY frame_id, detection_id",
            (batch_id,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["bbox_px"] = json.loads(item.pop("bbox_px_json"))
            item["size_mm"] = (
                json.loads(item.pop("size_mm_json")) if item["size_mm_json"] else None
            )
            result.append(item)
        return result

    def delete_detections(
        self,
        batch_id: str,
        detection_ids: list[str],
        *,
        source_name: str = "EVIDENCE_ADMIN",
    ) -> int:
        """Delete selected records from one batch and return the affected count.

        Development-only. The deletion stays irreversible, so the requested
        identifiers are written to ``system_events`` first: after the rows are
        gone, that event is the only remaining trace of what was removed. An
        evidence-release configuration must replace this with role-identified
        quarantine or tombstone handling.
        """
        unique_ids = list(dict.fromkeys(detection_ids))
        if not unique_ids:
            return 0
        placeholders = ", ".join("?" for _ in unique_ids)
        cursor = self.connection.execute(
            f"DELETE FROM detections WHERE batch_id = ? AND detection_id IN ({placeholders})",
            (batch_id, *unique_ids),
        )
        deleted = max(0, cursor.rowcount)
        self.append_event(
            source_name,
            "DETECTION_RECORDS_DELETED",
            {
                "batch_id": batch_id,
                "requested_ids": unique_ids,
                "deleted_count": deleted,
                "deletion_mode": "DEVELOPMENT_HARD_DELETE",
            },
        )
        self.connection.commit()
        return deleted
