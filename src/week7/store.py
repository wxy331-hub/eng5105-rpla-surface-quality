"""Immutable image attempts and sample-level SQLite records for Week 7.

Each public operation owns a short-lived SQLite connection, allowing a store to
be shared by FastAPI worker threads. A write transaction serializes capture and
completion decisions, including across separate SampleStore instances. Image
files are staged before the row is committed; an ordinary write/commit failure
removes only the new attempt's files. A process/power loss can leave an unindexed
attempt directory, but can never make that attempt satisfy sample completeness.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
import csv
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from typing import Any, Iterator
from uuid import UUID, uuid4

import cv2
import numpy as np

from ..week3.models import DetectionRecord, FramePacket, utc_now_iso


ANGLES = (0, 60, 120, 180, 240, 300)
LIGHTING_MODES = ("bright_field", "dark_field")
EVIDENCE_LABEL = "OFFLINE_SYNTHETIC_ONLY"

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    session_id TEXT PRIMARY KEY,
    sample_id TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    completed_at_utc TEXT
);
CREATE TABLE IF NOT EXISTS captures (
    capture_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES samples(session_id),
    angle_deg INTEGER NOT NULL CHECK(angle_deg IN (0,60,120,180,240,300)),
    lighting_mode TEXT NOT NULL CHECK(lighting_mode IN ('bright_field','dark_field')),
    created_at_utc TEXT NOT NULL,
    source_name TEXT NOT NULL,
    frame_id INTEGER NOT NULL,
    captured_at_utc TEXT NOT NULL,
    received_at_utc TEXT NOT NULL,
    camera_state TEXT NOT NULL,
    image_width_px INTEGER NOT NULL,
    image_height_px INTEGER NOT NULL,
    image_dtype TEXT NOT NULL,
    raw_image_path TEXT NOT NULL,
    annotated_image_path TEXT NOT NULL,
    candidates_json TEXT NOT NULL,
    lighting_metadata_json TEXT NOT NULL,
    calibration_json TEXT NOT NULL,
    calibration_id TEXT,
    calibration_status TEXT NOT NULL,
    evidence_label TEXT NOT NULL CHECK(evidence_label = 'OFFLINE_SYNTHETIC_ONLY'),
    supersedes_capture_id TEXT REFERENCES captures(capture_id),
    is_current INTEGER NOT NULL CHECK(is_current IN (0,1))
);
CREATE UNIQUE INDEX IF NOT EXISTS current_view
    ON captures(session_id, angle_deg, lighting_mode) WHERE is_current = 1;
CREATE TABLE IF NOT EXISTS sample_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES samples(session_id),
    occurred_at_utc TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details_json TEXT NOT NULL,
    evidence_label TEXT NOT NULL CHECK(evidence_label = 'OFFLINE_SYNTHETIC_ONLY')
);
CREATE INDEX IF NOT EXISTS sample_events_session ON sample_events(session_id);
CREATE TABLE IF NOT EXISTS sample_deletion_cleanup (
    session_id TEXT PRIMARY KEY,
    sample_id TEXT NOT NULL,
    staging_directory TEXT,
    capture_count INTEGER NOT NULL,
    image_count INTEGER NOT NULL
);
"""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


def _csv_cell(value: Any) -> Any:
    """Prevent user identifiers from becoming spreadsheet formulas on export."""
    if isinstance(value, str) and (
        value.startswith(("\t", "\r", "\n"))
        or value.lstrip().startswith(("=", "+", "-", "@"))
    ):
        return "'" + value
    return value


class SampleStore:
    """Archive twelve views per independently identified inspection session.

    ``sample_id`` is an operator's label; repeated labels create different
    sessions. Paths contain generated UUIDs only. This database is independent
    of the live inspection database and never opens or migrates it.
    """

    def __init__(self, root: Path, *, evidence_label: str = EVIDENCE_LABEL,
                 database_name: str = "week7_samples.sqlite3") -> None:
        if evidence_label not in {EVIDENCE_LABEL, "LIVE_INTEGRATION_ONLY", "OFFLINE_FAULT_INJECTION_ONLY"}:
            raise ValueError("Unsupported sample archive evidence label")
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.sqlite3", database_name):
            raise ValueError("database_name must be a simple sqlite3 filename")
        self.evidence_label = evidence_label
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / database_name
        with self._connection() as connection:
            for table in ("captures", "sample_events"):
                existing = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if existing is not None and f"evidence_label = '{evidence_label}'" not in existing[0]:
                    raise ValueError("Archive evidence differs; use a separate database without migration")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA.replace(EVIDENCE_LABEL, evidence_label))

    @contextmanager
    def _connection(self, commit_guard: Callable[[], AbstractContextManager] | None = None) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            if commit_guard is None:
                connection.commit()
            else:
                with commit_guard():
                    connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def close(self) -> None:
        """Compatibility hook; connections already close after every operation."""

    def create_sample(self, sample_id: str) -> dict[str, Any]:
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise ValueError("sample_id must be a non-empty string")
        if len(sample_id) > 200 or "\x00" in sample_id:
            raise ValueError("sample_id must be at most 200 characters without NUL")
        session_id = uuid4().hex
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO samples VALUES (?, ?, ?, NULL)",
                (session_id, sample_id, utc_now_iso()),
            )
        return self.get_sample(session_id)

    def list_samples(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            # A read transaction presents each list as a consistent DB snapshot.
            connection.execute("BEGIN")
            rows = connection.execute(
                "SELECT * FROM samples ORDER BY created_at_utc DESC, session_id"
            ).fetchall()
            return [self._sample(connection, row) for row in rows]

    def get_sample(self, session_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            connection.execute("BEGIN")
            return self._sample(connection, self._require_sample(connection, session_id))

    @staticmethod
    def _generated_id(value: str) -> bool:
        return (isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) is not None
                and UUID(value).version == 4)

    def _delete_entry(self, path: Path, *, directory: bool) -> bool:
        """Validate an existing owned entry without following filesystem links."""
        try:
            info = path.lstat()
        except FileNotFoundError:
            return False
        if (path.is_symlink()
                or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                or not path.resolve().is_relative_to(self.root)):
            raise ValueError("Refusing deletion through an archive link or outside the store root")
        valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if not valid_type:
            raise ValueError("Unexpected file type in the sample archive")
        return True

    def _delete_tree_files(self, directory: Path) -> list[Path]:
        """Only generated attempt folders and their two image names are owned."""
        if not self._delete_entry(directory, directory=True):
            return []
        files = []
        for attempt in directory.iterdir():
            attempt_id = attempt.name
            if attempt_id.startswith(".") and attempt_id.endswith(".pending"):
                attempt_id = attempt_id[1:-8]
            if not self._generated_id(attempt_id):
                raise ValueError("Unexpected directory in the sample archive")
            self._delete_entry(attempt, directory=True)
            for image in attempt.iterdir():
                if image.name not in ("raw.png", "annotated.png"):
                    raise ValueError("Unexpected file in the sample archive")
                if self._delete_entry(image, directory=False):
                    files.append(image)
        return files

    def _deletion_stage(self, session_id: str, name: str) -> Path:
        prefix, suffix = f".delete-{session_id}.", ".pending"
        if (not name.startswith(prefix) or not name.endswith(suffix)
                or not self._generated_id(name[len(prefix):-len(suffix)])):
            raise ValueError("Invalid sample deletion staging directory")
        return self.root / name

    def delete_sample(self, session_id: str) -> dict[str, Any]:
        """Permanently delete exactly one session, including superseded images.

        The archive is renamed inside this store before the SQL deletion commits.
        An ordinary SQL/commit failure restores the archive. If the process stops
        before commit, another delete of the same ID restores the named staging
        directory before retrying. After commit a durable cleanup row makes any
        interrupted or failed image purge retryable with the same session ID.

        ``cleanup_pending=True`` explicitly means DB records were deleted but
        permanent image cleanup needs retrying. ``deleted_image_count`` is the
        cumulative number already removed, and ``pending_image_count`` remains.
        """
        if not self._generated_id(session_id):
            raise ValueError("session_id must be a generated session UUID")
        archive = self.root / "images" / session_id
        moved: Path | None = None
        try:
            with self._connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._delete_entry(self.root, directory=True)
                self._delete_entry(self.root / "images", directory=True)
                pending = connection.execute(
                    "SELECT * FROM sample_deletion_cleanup WHERE session_id = ?", (session_id,),
                ).fetchone()
                if pending is None:
                    sample = self._require_sample(connection, session_id)
                    # A pre-commit process interruption rolls SQLite back. The
                    # owned staging name preserves enough information to restore.
                    staged = list(self.root.glob(f".delete-{session_id}.*.pending"))
                    if staged:
                        if len(staged) != 1 or archive.exists() or archive.is_symlink():
                            raise ValueError("Conflicting interrupted sample deletion archives")
                        recovered = self._deletion_stage(session_id, staged[0].name)
                        self._delete_tree_files(recovered)
                        archive.parent.mkdir(exist_ok=True)
                        recovered.rename(archive)
                    captures = connection.execute(
                        "SELECT * FROM captures WHERE session_id = ?", (session_id,),
                    ).fetchall()
                    for capture in captures:
                        if not self._generated_id(capture["capture_id"]):
                            raise ValueError("Invalid capture UUID in the sample archive")
                        for field, filename in (("raw_image_path", "raw.png"),
                                                ("annotated_image_path", "annotated.png")):
                            expected = f"images/{session_id}/{capture['capture_id']}/{filename}"
                            if capture[field] != expected:
                                raise ValueError("Capture image path is not owned by this session")
                    for other in connection.execute(
                        "SELECT raw_image_path, annotated_image_path FROM captures WHERE session_id != ?",
                        (session_id,),
                    ):
                        if any((self.root / path).resolve().is_relative_to(archive)
                               for path in other):
                            raise ValueError("Sample archive is shared by another session")
                    image_count = len(self._delete_tree_files(archive))
                    if archive.exists():
                        staging = self._deletion_stage(
                            session_id, f".delete-{session_id}.{uuid4().hex}.pending",
                        )
                        if staging.exists() or staging.is_symlink():
                            raise FileExistsError("Sample deletion staging directory already exists")
                        archive.rename(staging)
                        moved = staging
                    connection.execute("DELETE FROM sample_events WHERE session_id = ?", (session_id,))
                    connection.execute("DELETE FROM captures WHERE session_id = ?", (session_id,))
                    connection.execute("DELETE FROM samples WHERE session_id = ?", (session_id,))
                    connection.execute(
                        "INSERT INTO sample_deletion_cleanup VALUES (?, ?, ?, ?, ?)",
                        (session_id, sample["sample_id"], moved.name if moved else None,
                         len(captures), image_count),
                    )
                    pending = connection.execute(
                        "SELECT * FROM sample_deletion_cleanup WHERE session_id = ?", (session_id,),
                    ).fetchone()
                result = dict(pending)
        except BaseException:
            if moved is not None and moved.exists():
                if archive.exists() or archive.is_symlink():
                    raise RuntimeError("Sample deletion rollback requires archive recovery")
                moved.rename(archive)
            raise
        return self._finish_sample_deletion(result)

    def _purge_sample_deletion(self, directory: Path) -> None:
        """Unlink only validated image files; never use recursive tree removal."""
        files = self._delete_tree_files(directory)
        for image in files:
            self._delete_entry(directory, directory=True)
            self._delete_entry(image.parent, directory=True)
            if self._delete_entry(image, directory=False):
                image.unlink()
        if self._delete_entry(directory, directory=True):
            for attempt in directory.iterdir():
                self._delete_entry(attempt, directory=True)
                attempt.rmdir()
            directory.rmdir()

    def _finish_sample_deletion(self, pending: dict[str, Any]) -> dict[str, Any]:
        result = {
            "deleted_session_id": pending["session_id"], "sample_id": pending["sample_id"],
            "deleted_capture_count": pending["capture_count"],
            "deleted_image_count": pending["image_count"],
            "cleanup_pending": False, "pending_image_count": 0,
        }
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM sample_deletion_cleanup WHERE session_id = ?",
                                  (pending["session_id"],)).fetchone() is None:
                return result
            if pending["staging_directory"] is not None:
                directory = self._deletion_stage(pending["session_id"], pending["staging_directory"])
                try:
                    self._purge_sample_deletion(directory)
                except (OSError, ValueError) as error:
                    # A partial purge cannot be rolled back. Keep the journal and
                    # state that fact rather than reporting complete deletion.
                    result.update(cleanup_pending=True, cleanup_error=str(error))
                    try:
                        remaining = len(self._delete_tree_files(directory))
                    except (OSError, ValueError):
                        remaining = pending["image_count"]
                    result["pending_image_count"] = remaining
                    result["deleted_image_count"] = max(0, pending["image_count"] - remaining)
                    return result
            connection.execute("DELETE FROM sample_deletion_cleanup WHERE session_id = ?",
                               (pending["session_id"],))
        return result

    def list_pending_deletions(self) -> list[dict[str, Any]]:
        """List durable cleanup jobs after refresh, without inspecting image files.

        The stored image count is an upper bound because an interrupted purge
        may already have removed some images. Calling ``delete_sample`` with the
        returned ID retries cleanup and reports its current result.
        """
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT session_id, sample_id, capture_count, image_count "
                "FROM sample_deletion_cleanup ORDER BY rowid"
            ).fetchall()
            return [{
                "deleted_session_id": row["session_id"], "sample_id": row["sample_id"],
                "deleted_capture_count": row["capture_count"], "cleanup_pending": True,
                "pending_image_count_upper_bound": row["image_count"],
            } for row in rows]

    def append_event(
        self, session_id: str, event_type: str, details: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Append a durable per-session workflow event, including failed attempts.

        Events may also describe an already completed archive. They do not
        modify its completion timestamp, current views, or immutable images.
        """
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event_type must be a non-empty string")
        details_json = _json(dict(details))
        event = {
            "event_id": uuid4().hex,
            "session_id": session_id,
            "occurred_at_utc": utc_now_iso(),
            "event_type": event_type,
            "details": json.loads(details_json),
            "evidence_label": self.evidence_label,
        }
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_sample(connection, session_id)
            connection.execute(
                "INSERT INTO sample_events VALUES (?, ?, ?, ?, ?, ?)",
                (event["event_id"], session_id, event["occurred_at_utc"], event_type,
                 details_json, self.evidence_label),
            )
        return event

    @staticmethod
    def _require_sample(connection: sqlite3.Connection, session_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM samples WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown session_id: {session_id}")
        return row

    def _archive_path(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Archive path escapes the store root")
        return path

    def _capture(self, row: sqlite3.Row, analysis: dict[str, Any] | None = None) -> dict[str, Any]:
        result = dict(row)
        for field in ("candidates", "lighting_metadata", "calibration"):
            result[field] = json.loads(result.pop(f"{field}_json"))
        result["is_current"] = bool(result["is_current"])
        result["files_present"] = all(
            self._archive_path(result[field]).is_file()
            for field in ("raw_image_path", "annotated_image_path")
        )
        result["candidate_count"] = len(result["candidates"])
        result["analysis"] = analysis
        result["analysis_status"] = "legacy_unassessed" if analysis is None else analysis["geometry_status"]
        result["physical_outputs_allowed"] = False
        result["size_mm"] = None
        result["position_mm"] = None
        return result

    def _sample(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["events"] = []
        for event_row in connection.execute(
            "SELECT * FROM sample_events WHERE session_id = ? ORDER BY rowid",
            (row["session_id"],),
        ).fetchall():
            event = dict(event_row)
            event["details"] = json.loads(event.pop("details_json"))
            result["events"].append(event)
        analyses = {event["details"]["capture_id"]: event["details"] for event in result["events"]
                    if event["event_type"] == "CAPTURE_ANALYSIS"}
        result["captures"] = [
            self._capture(capture, analyses.get(capture["capture_id"]))
            for capture in connection.execute(
                "SELECT * FROM captures WHERE session_id = ? ORDER BY rowid",
                (row["session_id"],),
            ).fetchall()
        ]
        result["current_views"] = [item for item in result["captures"] if item["is_current"]]
        valid = {
            (item["angle_deg"], item["lighting_mode"])
            for item in result["current_views"] if item["files_present"]
        }
        result["missing_views"] = [
            {"angle_deg": angle, "lighting_mode": mode}
            for angle in ANGLES for mode in LIGHTING_MODES if (angle, mode) not in valid
        ]
        result["completed_views"] = len(valid)
        result["required_views"] = len(ANGLES) * len(LIGHTING_MODES)
        result["status"] = (
            "incomplete_archive" if result["missing_views"] else "completed"
        ) if row["completed_at_utc"] else "in_progress"
        result["evidence_label"] = self.evidence_label
        result["physical_outputs_allowed"] = False
        result["size_mm"] = None
        result["position_mm"] = None
        return result

    @staticmethod
    def _encode_png(image: np.ndarray) -> bytes:
        if not isinstance(image, np.ndarray) or image.size == 0:
            raise ValueError("Image must be a non-empty numpy array")
        if image.dtype not in (np.dtype("uint8"), np.dtype("uint16")):
            raise ValueError("PNG archival requires uint8 or uint16 image data")
        if image.ndim != 2 and not (image.ndim == 3 and image.shape[2] in (1, 3, 4)):
            raise ValueError("PNG images must be greyscale, BGR, or BGRA")
        success, encoded = cv2.imencode(".png", image)
        if not success:
            raise OSError("PNG encoding failed")
        return encoded.tobytes()

    @staticmethod
    def _write_image(path: Path, encoded: bytes) -> None:
        with path.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())

    def _remove_attempt_files(self, directory: Path) -> None:
        # Compensation is restricted to this operation's generated directory.
        if not directory.resolve().is_relative_to(self.root):
            raise ValueError("Refusing cleanup outside the store root")
        if directory.exists():
            for name in ("raw.png", "annotated.png"):
                (directory / name).unlink(missing_ok=True)
            directory.rmdir()

    def save_capture(
        self,
        session_id: str,
        angle_deg: int,
        lighting_mode: str,
        packet: FramePacket,
        annotated: np.ndarray,
        candidates: Sequence[DetectionRecord | Mapping[str, Any]],
        *,
        lighting_metadata: Mapping[str, Any],
        calibration: Mapping[str, Any] | None = None,
        retake: bool = False,
        commit_guard: Callable[[], AbstractContextManager] | None = None,
        request_id: str | None = None,
        analysis: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Save one attempt, keeping both images even when no candidates exist.

        ``retake=True`` must target an existing view. The previous attempt stays
        archived and is linked by ``supersedes_capture_id``. These uncalibrated
        archives never accept physical measurement values, including when a
        proposed calibration identifier is supplied as metadata. ``commit_guard``
        can recheck a live connection after writes and guard the final commit.
        Supplying ``request_id`` records CAPTURE_ARCHIVED in the same transaction,
        so a failed success-event write also rolls back the new attempt and files.
        ``analysis`` (a ``ViewInspectionResult.to_dict``) is stored as a
        CAPTURE_ANALYSIS event in that transaction too; captures without one
        read back as ``legacy_unassessed``.
        """
        if isinstance(angle_deg, bool) or not isinstance(angle_deg, int) or angle_deg not in ANGLES:
            raise ValueError(f"angle_deg must be one of {ANGLES}")
        if lighting_mode not in LIGHTING_MODES:
            raise ValueError(f"lighting_mode must be one of {LIGHTING_MODES}")
        if not isinstance(retake, bool):
            raise ValueError("retake must be boolean")
        if request_id is not None and (not isinstance(request_id, str) or not request_id.strip()):
            raise ValueError("request_id must be null or a non-empty string")
        original_png = self._encode_png(packet.image)
        annotated_png = self._encode_png(annotated)
        if annotated.shape[:2] != packet.image.shape[:2]:
            raise ValueError("Annotated image dimensions must match the original")
        candidate_data = []
        for candidate in candidates:
            data = candidate.to_dict() if isinstance(candidate, DetectionRecord) else dict(candidate)
            if data.get("size_mm") is not None or data.get("position_mm") is not None:
                raise ValueError("Uncalibrated sample captures cannot store physical measurements")
            data.update(size_mm=None, position_mm=None, evidence_label=self.evidence_label,
                        physical_outputs_allowed=False)
            candidate_data.append(data)
        calibration_data = dict(calibration or {})
        calibration_id = calibration_data.get("calibration_id")
        if calibration_id is not None and (
            not isinstance(calibration_id, str) or not calibration_id.strip()
        ):
            raise ValueError("calibration_id must be null or a non-empty string")
        calibration_status = calibration_data.get("status", "not_calibrated")
        if not isinstance(calibration_status, str) or not calibration_status.strip():
            raise ValueError("calibration status must be a non-empty string")
        # Serialize before creating files so unsupported metadata cannot orphan images.
        candidates_json = _json(candidate_data)
        lighting_json = _json(dict(lighting_metadata))
        calibration_json = _json(calibration_data)
        if analysis is not None and not isinstance(analysis.get("geometry_status"), str):
            raise ValueError("analysis must include a geometry_status")
        capture_id = uuid4().hex
        analysis_json = None if analysis is None else _json({**analysis, "capture_id": capture_id})
        attempt_dir: Path | None = None
        staging_dir: Path | None = None
        staging_created = False
        attempt_created = False
        try:
            with self._connection(commit_guard=commit_guard) as connection:
                connection.execute("BEGIN IMMEDIATE")
                sample = self._require_sample(connection, session_id)
                if sample["completed_at_utc"] is not None:
                    raise ValueError("Completed samples cannot accept captures")
                previous = connection.execute(
                    "SELECT capture_id FROM captures WHERE session_id = ? "
                    "AND angle_deg = ? AND lighting_mode = ? AND is_current = 1",
                    (session_id, angle_deg, lighting_mode),
                ).fetchone()
                if previous is not None and not retake:
                    raise ValueError("View already captured; use an explicit retake")
                if previous is None and retake:
                    raise ValueError("Cannot retake a view that has no previous capture")
                # session_id came from our database; it was generated at creation.
                relative = Path("images") / sample["session_id"] / capture_id
                attempt_dir = self._archive_path(relative.as_posix())
                staging_dir = self._archive_path(
                    (relative.parent / f".{capture_id}.pending").as_posix()
                )
                staging_dir.mkdir(parents=True)
                staging_created = True
                self._write_image(staging_dir / "raw.png", original_png)
                self._write_image(staging_dir / "annotated.png", annotated_png)
                staging_dir.rename(attempt_dir)
                staging_created = False
                attempt_created = True
                if previous is not None:
                    connection.execute(
                        "UPDATE captures SET is_current = 0 WHERE capture_id = ?",
                        (previous["capture_id"],),
                    )
                connection.execute(
                    """INSERT INTO captures (
                        capture_id, session_id, angle_deg, lighting_mode, created_at_utc,
                        source_name, frame_id, captured_at_utc, received_at_utc,
                        camera_state, image_width_px, image_height_px, image_dtype,
                        raw_image_path, annotated_image_path, candidates_json,
                        lighting_metadata_json, calibration_json, calibration_id,
                        calibration_status, evidence_label, supersedes_capture_id, is_current
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                    (capture_id, session_id, angle_deg, lighting_mode, utc_now_iso(),
                     packet.source_name, packet.frame_id, packet.captured_at_utc,
                     packet.received_at_utc, str(packet.camera_state),
                     int(packet.image.shape[1]), int(packet.image.shape[0]), str(packet.image.dtype),
                     (relative / "raw.png").as_posix(), (relative / "annotated.png").as_posix(),
                     candidates_json, lighting_json, calibration_json, calibration_id,
                     calibration_status, self.evidence_label, previous["capture_id"] if previous else None),
                )
                if request_id is not None:
                    connection.execute(
                        "INSERT INTO sample_events VALUES (?, ?, ?, ?, ?, ?)",
                        (uuid4().hex, session_id, utc_now_iso(), "CAPTURE_ARCHIVED",
                         _json({"capture_id": capture_id, "request_id": request_id,
                                "angle_deg": angle_deg, "lighting_mode": lighting_mode}),
                         self.evidence_label),
                    )
                if analysis_json is not None:
                    connection.execute(
                        "INSERT INTO sample_events VALUES (?, ?, ?, ?, ?, ?)",
                        (uuid4().hex, session_id, utc_now_iso(), "CAPTURE_ANALYSIS",
                         analysis_json, self.evidence_label),
                    )
                saved = self._capture(connection.execute(
                    "SELECT * FROM captures WHERE capture_id = ?", (capture_id,)
                ).fetchone(), None if analysis_json is None else json.loads(analysis_json))
        except BaseException:
            for directory, created in ((staging_dir, staging_created), (attempt_dir, attempt_created)):
                if directory is not None and created:
                    self._remove_attempt_files(directory)
            raise
        return saved

    def complete_sample(self, session_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            sample = self._require_sample(connection, session_id)
            result = self._sample(connection, sample)
            if result["missing_views"]:
                raise ValueError("All 12 current views and both image files are required for completion")
            if sample["completed_at_utc"] is None:
                connection.execute(
                    "UPDATE samples SET completed_at_utc = ? WHERE session_id = ?",
                    (utc_now_iso(), session_id),
                )
            return self._sample(connection, self._require_sample(connection, session_id))

    def image_path(self, capture_id: str, kind: str) -> Path:
        """Resolve a database-owned image; kinds are raw/original or annotated."""
        fields = {"raw": "raw_image_path", "original": "raw_image_path", "annotated": "annotated_image_path"}
        if kind not in fields:
            raise ValueError("Image kind must be raw, original, or annotated")
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM captures WHERE capture_id = ?", (capture_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown capture_id: {capture_id}")
            path = self._archive_path(row[fields[kind]])
            if not path.is_file():
                raise FileNotFoundError(f"Archived {kind} image is missing for capture {capture_id}")
            return path

    def export_csv(self, session_id: str) -> str:
        """Return one row per capture attempt, including zero-candidate views."""
        sample = self.get_sample(session_id)
        fields = [
            "sample_id", "session_id", "sample_status", "completed_views", "capture_id",
            "angle_deg", "lighting_mode", "created_at_utc", "source_name", "frame_id",
            "captured_at_utc", "received_at_utc", "camera_state", "image_width_px",
            "image_height_px", "image_dtype", "is_current", "supersedes_capture_id",
            "raw_image_path", "annotated_image_path", "files_present", "candidate_count",
            "candidates_json", "lighting_metadata_json", "calibration_json",
            "calibration_id", "calibration_status", "evidence_label",
            "physical_outputs_allowed", "size_mm", "position_mm",
            "analysis_status", "analysis_reason_codes", "analysis_algorithm_version",
        ]
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for capture in sample["captures"]:
            row = {key: capture.get(key) for key in fields}
            row.update(sample_id=sample["sample_id"], session_id=session_id,
                       sample_status=sample["status"], completed_views=sample["completed_views"])
            for key in ("candidates", "lighting_metadata", "calibration"):
                row[f"{key}_json"] = _json(capture[key])
            analysis = capture["analysis"] or {}
            row.update(analysis_reason_codes=" ".join(analysis.get("reason_codes", [])),
                       analysis_algorithm_version=analysis.get("algorithm_version"))
            writer.writerow({key: _csv_cell(value) for key, value in row.items()})
        return output.getvalue()
