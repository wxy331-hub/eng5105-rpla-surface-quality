"""Resident camera, inspection, REST, MJPEG, and WebSocket service."""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.parse import urlencode
from urllib.request import urlopen

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from src.week3 import (
    BaselineVisionProcessor,
    CameraSource,
    CameraState,
    DetectionRecord,
    FramePacket,
    SQLiteInspectionRepository,
)
from src.week4 import (
    CameraConnectionMonitor,
    ConnectionPolicy,
    Esp32MjpegSource,
    LatestFrameBuffer,
)


from src.camera_config import DEFAULT_CONFIG_PATH, LiveServiceConfig, load_service_config
from src.week4.uvc import UsbUvcSource


DATA_MODE = "LIVE_CONTINUOUS_CANDIDATE_ONLY"


def configure_camera(
    config: LiveServiceConfig,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    if config.source_type != "esp32_mjpeg":
        raise ValueError("ESP32 HTTP configuration is only valid for esp32_mjpeg")
    query = urlencode({"var": "framesize", "val": config.framesize_control_value})
    with opener(f"{config.control_base_url}/control?{query}", timeout=5) as response:
        response.read()
    with opener(f"{config.control_base_url}/status", timeout=5) as response:
        status = json.loads(response.read().decode("utf-8"))
    if int(status.get("framesize", -1)) != config.framesize_control_value:
        raise ConnectionError("camera did not accept the requested frame size")
    return status


def _batch_id(source_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    source_label = re.sub(r"[^A-Za-z0-9_-]+", "_", source_name)
    return f"RPLA-LIVE-{source_label}-{stamp}"


class InspectionRuntime:
    """Own exactly one camera connection and share its processed state."""

    def __init__(
        self,
        config: LiveServiceConfig,
        *,
        source_factory: Callable[[], CameraSource] | None = None,
    ) -> None:
        self.config = config
        self.batch_id = _batch_id(config.source_name)
        self._source_factory = source_factory or self._make_source
        self._processor = BaselineVisionProcessor(
            threshold=config.threshold,
            min_area_px=config.min_area_px,
            algorithm_version="live-service-roi-baseline-1",
            roi_px=config.roi_px,
            data_mode=DATA_MODE,
            **config.vision_options,
        )
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._stop_event = threading.Event()
        self._reconnect_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._process_thread: threading.Thread | None = None
        # Acquisition hands frames to processing through a one-slot buffer, so a
        # slow inspection pass discards the backlog instead of working through
        # progressively older images. Its own condition keeps frame hand-off from
        # waking the API threads waiting on _condition for a new JPEG version.
        self._buffer = LatestFrameBuffer()
        self._buffer_condition = threading.Condition()
        self._connection_generation = 0
        self._buffer_generation = 0
        # Service-level health. The source keeps its own monitor for read
        # failures; this one answers the question the source cannot: how old is
        # the newest frame we actually hold?
        self._monitor = CameraConnectionMonitor(
            ConnectionPolicy(
                stale_after_s=config.stale_after_s,
                disconnect_after_s=config.disconnect_after_s,
                recovery_frames=config.recovery_frames,
            )
        )
        # Acquisition must not touch SQLite: the repository lives on the
        # processing thread, which drains this queue.
        self._pending_events: deque[tuple[str, str, dict[str, Any]]] = deque(maxlen=200)
        self._last_frame_monotonic: float | None = None
        self._state = CameraState.DISCONNECTED
        self._last_error: str | None = None
        self._camera_configured = False
        self._frame_version = 0
        self._jpeg: bytes | None = None
        self._width = 0
        self._height = 0
        self._frames_received = 0
        self._frames_processed = 0
        self._inspection_frames = 0
        self._recovery_frames_skipped = 0
        self._frame_times: deque[float] = deque(maxlen=30)
        self._detections: deque[dict[str, Any]] = deque(maxlen=config.event_retention)
        self._latest_detection_count = 0
        self._target_present = False
        self._last_frame_received_at_utc: str | None = None
        self._last_frame_processed_at_utc: str | None = None
        self._last_processing_latency_ms: float | None = None
        self._started_at = time.monotonic()

    def _make_capture(self, url: str) -> Any:
        capture = cv2.VideoCapture()
        capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.config.open_timeout_ms)
        capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.config.read_timeout_ms)
        capture.open(url)
        return capture

    def _make_source(self) -> CameraSource:
        policy = ConnectionPolicy(
            stale_after_s=self.config.stale_after_s,
            disconnect_after_s=self.config.disconnect_after_s,
            recovery_frames=self.config.recovery_frames,
        )
        if self.config.source_type == "usb_uvc":
            return UsbUvcSource(
                self.config.camera_device,
                width_px=self.config.expected_width_px,
                height_px=self.config.expected_height_px,
                pixel_format=self.config.pixel_format,
                fps=self.config.requested_fps,
                backend=self.config.camera_backend,
                source_name=self.config.source_name,
                policy=policy,
            )
        return Esp32MjpegSource(
            self.config.stream_url,
            source_name=self.config.source_name,
            capture_factory=self._make_capture,
            configure=lambda: configure_camera(self.config),
            policy=policy,
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._process_thread = threading.Thread(
            target=self._process, name="rpla-inspection-process", daemon=True
        )
        self._process_thread.start()
        self._thread = threading.Thread(target=self._run, name="rpla-acquire", daemon=True)
        self._thread.start()

    def stop(self, timeout_s: float | None = None) -> None:
        # Acquisition can sit inside a blocking read for up to read_timeout_ms,
        # so the join budget has to exceed it or the thread outlives stop().
        if timeout_s is None:
            timeout_s = self.config.read_timeout_ms / 1000.0 + 2.0
        self._stop_event.set()
        self._reconnect_event.set()
        with self._condition:
            self._condition.notify_all()
        with self._buffer_condition:
            self._buffer_condition.notify_all()
        for thread in (self._thread, self._process_thread):
            if thread:
                thread.join(timeout=timeout_s)

    def request_reconnect(self) -> None:
        self._set_state(CameraState.RECONNECTING)
        self._reconnect_event.set()

    def delete_detections(self, detection_ids: list[str]) -> int:
        requested = {item.strip() for item in detection_ids if item.strip()}
        if not requested:
            return 0
        with SQLiteInspectionRepository(self.config.database_path) as repository:
            deleted = repository.delete_detections(
                self.batch_id, sorted(requested), source_name=self.config.source_name
            )
        with self._condition:
            self._detections = deque(
                (item for item in self._detections if item["detection_id"] not in requested),
                maxlen=self.config.event_retention,
            )
            current_frame_id = max(0, self._frames_received - 1)
            self._latest_detection_count = sum(
                item["frame_id"] == current_frame_id for item in self._detections
            )
            self._frame_version += 1
            self._condition.notify_all()
        return deleted

    def _set_state(self, state: CameraState, error: str | None = None) -> None:
        with self._condition:
            if state in {CameraState.CONNECTING, CameraState.RECONNECTING, CameraState.DISCONNECTED}:
                self._connection_generation += 1
            self._state = state
            self._last_error = error
            self._frame_version += 1
            self._condition.notify_all()

    def _queue_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Hand an event to the processing thread, which owns the database."""
        self._pending_events.append((self.config.source_name, event_type, details))

    def _publish_frame(self, packet: FramePacket, generation: int | None = None) -> None:
        with self._lock:
            generation = self._connection_generation if generation is None else generation
            if generation != self._connection_generation:
                return
            with self._buffer_condition:
                self._buffer.put(packet)
                self._buffer_generation = generation
                self._buffer_condition.notify()

    def _take_frame(self, timeout_s: float) -> FramePacket | None:
        item = self._take_buffered_frame(timeout_s)
        return None if item is None else item[0]

    def _take_buffered_frame(self, timeout_s: float) -> tuple[FramePacket, int] | None:
        with self._buffer_condition:
            packet = self._buffer.take()
            if packet is None:
                self._buffer_condition.wait(timeout_s)
                packet = self._buffer.take()
            return None if packet is None else (packet, self._buffer_generation)

    def _drain_events(self, repository: SQLiteInspectionRepository) -> None:
        while self._pending_events:
            source_name, event_type, details = self._pending_events.popleft()
            repository.append_event(source_name, event_type, details)

    def _age_out(self) -> None:
        """Downgrade health when the newest frame we hold has aged past policy."""
        if self._last_frame_monotonic is None:
            return
        state = self._monitor.poll(time.monotonic())
        with self._condition:
            # An acquisition-side CONNECTING/RECONNECTING notice outranks a
            # stale-frame downgrade: both are true, but the connection attempt is
            # the more actionable message for the operator.
            if self._state in {CameraState.HEALTHY, CameraState.STALE} and self._state is not state:
                self._state = state
                self._frame_version += 1
                self._condition.notify_all()

    def _run(self) -> None:
        """Acquisition thread: read frames and publish only the newest one."""
        while not self._stop_event.is_set():
            source: CameraSource | None = None
            try:
                self._set_state(CameraState.CONNECTING)
                with self._lock:
                    self._camera_configured = False
                    self._monitor.begin_connect(reconnect=True)
                source = self._source_factory()
                source.connect()
                with self._lock:
                    self._camera_configured = True
                    generation = self._connection_generation
                self._queue_event(
                    "LIVE_SERVICE_CAMERA_CONNECTED",
                    {"source_type": self.config.source_type, **self.config.connection_details, "batch_id": self.batch_id},
                )
                self._reconnect_event.clear()
                while not self._stop_event.is_set() and not self._reconnect_event.is_set():
                    self._publish_frame(next(source.frames(1)), generation)
            except Exception as exc:  # Camera faults must keep the service alive.
                with self._condition:
                    self._camera_configured = False
                    self._monitor.mark_read_failure()
                    # Invalidate in-flight frames in the same critical section
                    # that reports the failed connection. Buffer cleanup must
                    # not leave a window for an old frame to commit as healthy.
                    self._set_state(CameraState.DISCONNECTED, str(exc))
                with self._buffer_condition:
                    self._buffer.take()
                self._queue_event("LIVE_SERVICE_CAMERA_ERROR", {"error": str(exc)})
            finally:
                if source is not None:
                    source.disconnect()
            if not self._stop_event.is_set():
                self._reconnect_event.clear()
                self._set_state(CameraState.RECONNECTING, self._last_error)
                self._stop_event.wait(self.config.reconnect_delay_s)

    def _process(self) -> None:
        """Processing thread: owns the database and inspects the newest frame."""
        self.config.database_path.parent.mkdir(parents=True, exist_ok=True)
        # Poll fast enough that a stale frame is noticed well inside its window.
        poll_timeout_s = max(0.05, min(0.2, self.config.stale_after_s / 2))
        with SQLiteInspectionRepository(self.config.database_path) as repository:
            repository.start_batch(self.batch_id, self.config.source_name, DATA_MODE)
            while not self._stop_event.is_set():
                self._drain_events(repository)
                buffered = self._take_buffered_frame(poll_timeout_s)
                if buffered is None:
                    self._age_out()
                    continue
                try:
                    self._accept_packet(buffered[0], repository, generation=buffered[1])
                except Exception as exc:  # A bad frame must not kill inspection.
                    self._set_state(CameraState.DISCONNECTED, str(exc))
                    self._queue_event("LIVE_SERVICE_PROCESSING_ERROR", {"error": str(exc)})
            self._drain_events(repository)

    def _accept_packet(
        self,
        packet: FramePacket,
        repository: SQLiteInspectionRepository | None = None,
        *,
        generation: int | None = None,
    ) -> None:
        processing_started = time.perf_counter()
        with self._lock:
            generation = self._connection_generation if generation is None else generation
            if generation != self._connection_generation:
                return
        image = packet.image
        expected_shape = (self.config.expected_height_px, self.config.expected_width_px, 3)
        if image.shape != expected_shape or image.dtype != np.uint8:
            error = f"camera frame must be uint8 BGR {expected_shape}; received {image.shape} {image.dtype}"
            self._monitor.mark_read_failure()
            self._set_state(CameraState.DISCONNECTED, error)
            raise ValueError(error)
        if packet.source_name != self.config.source_name:
            raise ValueError("frame source does not match the selected camera configuration")
        frame_id = self._frames_received
        now = time.monotonic()
        # Service health is decided by frame age, not by "the last read returned".
        # Take the more conservative of the source view and this one so a
        # healthy-looking read cannot re-enable inspection on its own.
        with self._lock:
            if generation != self._connection_generation:
                return
            service_state = self._monitor.frame_received(now)
        effective_state = (
            service_state if packet.camera_state is CameraState.HEALTHY else packet.camera_state
        )
        packet = replace(packet, frame_id=frame_id, camera_state=effective_state)
        image = packet.image
        height, width = image.shape[:2]
        records: list[DetectionRecord] = []
        annotated = image.copy()
        skipped_for_recovery = False

        target_present = self._material_present(image) if packet.camera_state is CameraState.HEALTHY else False
        if packet.camera_state is CameraState.HEALTHY and target_present:
            annotated, records = self._processor.process(packet, self.batch_id)
        elif packet.camera_state is not CameraState.HEALTHY:
            skipped_for_recovery = True

        roi_x, roi_y, roi_width, roi_height = self.config.roi_px
        cv2.rectangle(
            annotated,
            (roi_x, roi_y),
            (roi_x + roi_width, roi_y + roi_height),
            (255, 120, 0),
            2,
        )
        if packet.camera_state is CameraState.HEALTHY and not target_present:
            cv2.putText(
                annotated,
                "WAITING FOR MATERIAL",
                (roi_x + 12, roi_y + 34),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 190, 50),
                2,
                cv2.LINE_AA,
            )

        ok, encoded = cv2.imencode(
            ".jpg",
            annotated,
            [cv2.IMWRITE_JPEG_QUALITY, self.config.jpeg_quality],
        )
        if not ok:
            raise OSError("could not encode the latest inspection frame")

        detection_rows = [record.to_dict() for record in records]
        processed_at_utc = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        processing_latency_ms = round((time.perf_counter() - processing_started) * 1000, 2)

        with self._condition:
            # A disconnect/reconnect may arrive during decode or inspection. Only
            # frames from the current connection may commit records or publish health.
            if generation != self._connection_generation:
                return
            if repository is not None:
                for record in records:
                    repository.append_detection(record)
            self._state = packet.camera_state
            self._last_error = None
            self._width = width
            self._height = height
            self._frames_received += 1
            if packet.camera_state is CameraState.HEALTHY:
                self._frames_processed += 1
            if target_present:
                self._inspection_frames += 1
            if skipped_for_recovery:
                self._recovery_frames_skipped += 1
            self._target_present = target_present
            self._last_frame_monotonic = now
            self._frame_times.append(now)
            self._latest_detection_count = len(detection_rows)
            self._detections.extend(detection_rows)
            self._jpeg = encoded.tobytes()
            self._last_frame_received_at_utc = packet.received_at_utc
            self._last_frame_processed_at_utc = processed_at_utc
            self._last_processing_latency_ms = processing_latency_ms
            self._frame_version += 1
            self._condition.notify_all()

    def _material_present(self, image: np.ndarray) -> bool:
        if not self.config.presence_gate_enabled:
            return True
        roi_x, roi_y, roi_width, roi_height = self.config.roi_px
        if roi_x + roi_width > image.shape[1] or roi_y + roi_height > image.shape[0]:
            return False
        roi = image[roi_y : roi_y + roi_height, roi_x : roi_x + roi_width]
        grey = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        centre_width = max(1, int(roi_width * self.config.target_centre_fraction))
        centre_x = (roi_width - centre_width) // 2
        centre = grey[:, centre_x : centre_x + centre_width]
        mask = np.uint8(centre < self.config.target_dark_threshold) * 255
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            np.ones((15, 5), np.uint8),
        )
        component_count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        for component in range(1, component_count):
            component_width = stats[component, cv2.CC_STAT_WIDTH]
            component_height = stats[component, cv2.CC_STAT_HEIGHT]
            width_fraction = component_width / centre_width
            height_fraction = component_height / roi_height
            if (
                self.config.target_min_row_fraction <= width_fraction <= self.config.target_max_width_fraction
                and height_fraction >= self.config.target_min_coverage
            ):
                return True
        return False

    def _fps(self) -> float:
        if len(self._frame_times) < 2:
            return 0.0
        elapsed = self._frame_times[-1] - self._frame_times[0]
        return round((len(self._frame_times) - 1) / elapsed, 2) if elapsed > 0 else 0.0

    def snapshot_payload(self) -> dict[str, Any]:
        with self._lock:
            frame_age_ms = (
                None
                if self._last_frame_monotonic is None
                else round((time.monotonic() - self._last_frame_monotonic) * 1000, 1)
            )
            summary = {
                "status": "RUNNING" if self._state is CameraState.HEALTHY and self._target_present else "WAITING_FOR_MATERIAL" if self._state is CameraState.HEALTHY else "WAITING",
                "evidence_level": DATA_MODE,
                "camera_path": self.config.camera_path,
                "source_type": self.config.source_type,
                "inspection_profile": self.config.inspection_profile,
                "parameter_status": self.config.parameter_status,
                "requested_pixel_format": self.config.pixel_format,
                "requested_fps": self.config.requested_fps,
                "requested_width_px": self.config.expected_width_px,
                "requested_height_px": self.config.expected_height_px,
                "camera_source": self.config.source_name,
                "batch_id": self.batch_id,
                "framesize_name": self.config.framesize_name,
                "camera_state": self._state.value,
                "automatic_actions_allowed": self._state is CameraState.HEALTHY and self._target_present,
                "target_present": self._target_present,
                "detection_active": self._state is CameraState.HEALTHY and self._target_present,
                "camera_configured": self._camera_configured,
                "last_error": self._last_error,
                "frames_received": self._frames_received,
                "frames_processed_when_healthy": self._frames_processed,
                "inspection_frames": self._inspection_frames,
                "recovery_frames_skipped": self._recovery_frames_skipped,
                "dropped_frames": self._buffer.dropped_frames,
                "measured_pipeline_fps": self._fps(),
                "frame_received_at_utc": self._last_frame_received_at_utc,
                "frame_processed_at_utc": self._last_frame_processed_at_utc,
                "frame_age_ms": frame_age_ms,
                "stale_after_ms": round(self.config.stale_after_s * 1000),
                "disconnect_after_ms": round(self.config.disconnect_after_s * 1000),
                "processing_latency_ms": self._last_processing_latency_ms,
                "snapshot_published_at_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "frame_width_px": self._width,
                "frame_height_px": self._height,
                "roi_px": list(self.config.roi_px),
                "recovery_frames_required": self.config.recovery_frames,
                "candidate_records": len(self._detections),
                "current_frame_candidates": self._latest_detection_count,
                "current_frame_id": max(0, self._frames_received - 1),
                "hardware_stream_verified": self._frames_received > 0,
                "rpla_defect_performance_verified": False,
                "physical_measurements_available": False,
                "uptime_s": round(time.monotonic() - self._started_at, 1),
                "interpretation": "Candidate detection runs only while the configurable material-presence gate is active; rPLA accuracy requires physical validation.",
            }
            return {
                "type": "snapshot",
                "version": self._frame_version,
                "summary": summary,
                "detections": list(self._detections),
            }

    def latest_jpeg(self) -> tuple[int, bytes | None]:
        with self._lock:
            return self._frame_version, self._jpeg

    def wait_for_jpeg(self, after_version: int, timeout_s: float = 2.0) -> tuple[int, bytes | None]:
        with self._condition:
            self._condition.wait_for(
                lambda: self._frame_version > after_version or self._stop_event.is_set(),
                timeout=timeout_s,
            )
            return self._frame_version, self._jpeg


SERVICE_CONFIG = load_service_config()
_runtime: InspectionRuntime | None = None


def get_runtime() -> InspectionRuntime:
    """Build the runtime on first use.

    Importing this module must not construct a camera runtime: tests import it
    for the config loader and the class, and a module-level instance made every
    test depend on one shared object.
    """
    global _runtime
    if _runtime is None:
        _runtime = InspectionRuntime(SERVICE_CONFIG)
    return _runtime


class DeleteEventsRequest(BaseModel):
    record_ids: list[str] = Field(min_length=1, max_length=200)


@asynccontextmanager
async def lifespan(_: FastAPI) -> Iterator[None]:
    runtime = get_runtime()
    runtime.start()
    try:
        yield
    finally:
        runtime.stop()


app = FastAPI(title="rPLA Live Inspection Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(SERVICE_CONFIG.cors_allow_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    payload = get_runtime().snapshot_payload()
    return payload["summary"]


@app.get("/api/snapshot")
def snapshot() -> dict[str, Any]:
    return get_runtime().snapshot_payload()


@app.get("/api/events")
def events(limit: int = 100) -> dict[str, Any]:
    runtime = get_runtime()
    payload = runtime.snapshot_payload()
    safe_limit = max(1, min(limit, runtime.config.event_retention))
    return {"batch_id": payload["summary"]["batch_id"], "items": payload["detections"][-safe_limit:]}


@app.post("/api/events/delete")
def delete_events(request: DeleteEventsRequest) -> dict[str, Any]:
    runtime = get_runtime()
    deleted = runtime.delete_detections(request.record_ids)
    return {"deleted": deleted, "snapshot": runtime.snapshot_payload()}


@app.get("/api/frame.jpg")
def frame() -> Response:
    _, jpeg = get_runtime().latest_jpeg()
    if jpeg is None:
        raise HTTPException(status_code=503, detail="camera frame is not available yet")
    return Response(content=jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


def _mjpeg_frames() -> Iterator[bytes]:
    runtime = get_runtime()
    version = -1
    while True:
        version, jpeg = runtime.wait_for_jpeg(version)
        if jpeg is None:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            + f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii")
            + jpeg
            + b"\r\n"
        )


@app.get("/api/stream.mjpg")
def stream() -> StreamingResponse:
    return StreamingResponse(
        _mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/control/reconnect")
def reconnect() -> dict[str, str]:
    get_runtime().request_reconnect()
    return {"status": "reconnect_requested"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    runtime = get_runtime()
    last_version = -1
    try:
        while True:
            payload = runtime.snapshot_payload()
            if payload["version"] != last_version:
                await websocket.send_json(payload)
                last_version = payload["version"]
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return
