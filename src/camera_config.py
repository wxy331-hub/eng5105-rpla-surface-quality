"""Source-specific acquisition and inspection profiles for the resident service."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.inspection.factory import ALGORITHMS, STATIC_ALGORITHM
from src.inspection.geometry import GeometryParams
from src.inspection.factory import surface_components


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "live_service.json"
SOURCE_TYPES = {"esp32_mjpeg", "usb_uvc"}


@dataclass(frozen=True, slots=True)
class LiveServiceConfig:
    source_type: str
    source_name: str
    camera_ip: str | None
    camera_device: int | str | None
    camera_backend: str
    pixel_format: str | None
    requested_fps: float | None
    framesize_control_value: int | None
    framesize_name: str
    expected_width_px: int
    expected_height_px: int
    roi_px: tuple[int, int, int, int]
    inspection_profile: str
    parameter_status: str
    threshold: int
    min_area_px: float
    vision_options: dict[str, float | int]
    presence_gate_enabled: bool
    target_dark_threshold: int
    target_min_row_fraction: float
    target_min_coverage: float
    target_centre_fraction: float
    target_max_width_fraction: float
    jpeg_quality: int
    reconnect_delay_s: float
    open_timeout_ms: int
    read_timeout_ms: int
    event_retention: int
    stale_after_s: float
    disconnect_after_s: float
    recovery_frames: int
    cors_allow_origins: tuple[str, ...]
    database_path: Path
    vision_algorithm: str = "baseline_threshold"
    static_options: dict[str, Any] = field(default_factory=dict)
    surface_options: dict[str, Any] = field(default_factory=dict)
    # Raspberry Pi demonstration mode (RPLA_SPLIT_PREVIEW=1): raw frames carry
    # camera health and a reduced live preview; analysis is published separately
    # under a longer budget. See live_service.SPLIT_ANALYSIS_STALE_AFTER_S.
    split_preview: bool = False

    @property
    def stream_url(self) -> str:
        if self.source_type != "esp32_mjpeg":
            raise ValueError("USB acquisition has no network stream URL")
        return os.getenv("RPLA_STREAM_URL", f"http://{self.camera_ip}:81/stream")

    @property
    def control_base_url(self) -> str:
        if self.source_type != "esp32_mjpeg":
            raise ValueError("USB acquisition has no ESP32 control URL")
        return os.getenv("RPLA_CONTROL_URL", f"http://{self.camera_ip}").rstrip("/")

    @property
    def camera_path(self) -> str:
        return {
            "esp32_mjpeg": "PLAN_B_ESP32S3_OV3660_MJPEG",
            "usb_uvc": "PLAN_A_ALC_IMX258_USB_UVC",
        }[self.source_type]

    @property
    def connection_details(self) -> dict[str, Any]:
        if self.source_type == "esp32_mjpeg":
            return {"stream_url": self.stream_url}
        return {"device": self.camera_device, "backend": self.camera_backend,
                "requested_pixel_format": self.pixel_format, "requested_fps": self.requested_fps}


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or int(value) != float(value) or int(value) <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def load_service_config(path: Path | None = None) -> LiveServiceConfig:
    config_path = path or Path(os.getenv("RPLA_CONFIG_PATH", str(DEFAULT_CONFIG_PATH)))
    raw = json.loads(Path(config_path).read_text(encoding="utf-8"))
    source_type = os.getenv("RPLA_SOURCE_TYPE", "").strip().lower() or raw.get("default_source_type", "esp32_mjpeg")
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"unknown camera source type: {source_type}")
    if "sources" in raw:
        if source_type not in raw["sources"]:
            raise ValueError(f"camera source is not configured: {source_type}")
        source = raw["sources"][source_type]
    elif source_type == "esp32_mjpeg":
        source = raw  # Existing flat Plan B configurations remain usable.
    else:
        raise ValueError("USB acquisition requires a usb_uvc source configuration")

    inspection_name = source.get("inspection_profile", "legacy_plan_b")
    if "inspection_profiles" in raw:
        if inspection_name not in raw["inspection_profiles"]:
            raise ValueError(f"unknown inspection profile: {inspection_name}")
        inspection = raw["inspection_profiles"][inspection_name]
    else:
        inspection = raw
    profiles = source["resolution_profiles"]
    resolution = os.getenv("RPLA_RESOLUTION", "").strip().upper()
    legacy_framesize = os.getenv("RPLA_FRAMESIZE", "").strip()
    if source_type == "esp32_mjpeg" and not resolution and legacy_framesize:
        resolution = next((name for name, item in profiles.items()
                           if int(item["framesize_control_value"]) == int(legacy_framesize)), "")
        if not resolution:
            raise ValueError(f"unknown ESP32 framesize value: {legacy_framesize}")
    resolution = resolution or str(source["default_resolution"]).upper()
    if resolution not in profiles:
        raise ValueError(f"unknown resolution profile for {source_type}: {resolution}")
    profile = profiles[resolution]
    width = _positive_int(profile["width_px"], "width_px")
    height = _positive_int(profile["height_px"], "height_px")
    roi = tuple(float(value) for value in inspection["roi_normalized"])
    if len(roi) != 4 or any(not math.isfinite(value) or not 0 <= value <= 1 for value in roi):
        raise ValueError("roi_normalized must contain four finite values between zero and one")
    if roi[2] <= 0 or roi[3] <= 0 or roi[0] + roi[2] > 1 or roi[1] + roi[3] > 1:
        raise ValueError("normalized ROI must have positive size and fit inside the frame")
    roi_px = (round(roi[0] * width), round(roi[1] * height),
              max(1, round(roi[2] * width)), max(1, round(roi[3] * height)))
    if roi_px[0] + roi_px[2] > width or roi_px[1] + roi_px[3] > height:
        raise ValueError("scaled ROI lies outside the selected resolution")

    camera_ip = None
    device = None
    backend = "auto"
    pixel_format = None
    fps = None
    framesize = None
    if source_type == "esp32_mjpeg":
        camera_ip = os.getenv("RPLA_CAMERA_IP", str(source["camera_ip"])).strip()
        if not camera_ip:
            raise ValueError("ESP32 camera_ip must not be empty")
        framesize = int(profile["framesize_control_value"])
    else:
        device = os.getenv("RPLA_CAMERA_DEVICE", "").strip() or source["device"]
        backend = os.getenv("RPLA_CAMERA_BACKEND", "").strip().lower() or source.get("backend", "auto")
        if backend not in {"auto", "dshow", "msmf", "v4l2"}:
            raise ValueError(f"unknown USB camera backend: {backend}")
        pixel_format = str(profile.get("pixel_format", "MJPG")).upper()
        if pixel_format not in {"MJPG", "YUY2", "YUYV"}:
            raise ValueError(f"unsupported USB pixel format: {pixel_format}")
        if profile.get("fps") is not None:
            fps = float(profile["fps"])
            if not math.isfinite(fps) or fps <= 0:
                raise ValueError("requested fps must be positive and finite")
        # Import the adapter only for USB configuration; it validates without opening hardware.
        from src.week4.uvc import UsbUvcSource
        validated = UsbUvcSource(device, width_px=width, height_px=height,
                                 pixel_format=pixel_format, fps=fps, backend=backend)
        device = validated.device

    vision_names = ("score_base", "score_area_divisor_px", "score_ceiling", "reject_area_px",
                    "scratch_min_aspect", "contamination_min_area_px", "blur_kernel_size", "morph_kernel_size")
    vision_options = {name: inspection[name] for name in vision_names if name in inspection}
    vision_algorithm = str(inspection.get("algorithm", "baseline_threshold"))
    static_options = dict(inspection.get("static_rpla", {}))
    surface_options = dict(inspection.get("static_surface") or {})
    if vision_algorithm not in ALGORITHMS:
        raise ValueError(f"unknown vision algorithm: {vision_algorithm}")
    if vision_algorithm == STATIC_ALGORITHM:
        # Validate now so a bad profile fails at start-up, not on the first frame.
        GeometryParams.from_mapping({**static_options, "search_roi_px": roi_px})
        if surface_options:
            # Loads (and so validates) the reference too: a missing or altered
            # reference must stop start-up, not surface as a wrong grade later.
            surface_components(surface_options)
    source_name = str(source["source_name"]).strip()
    if not source_name:
        raise ValueError("source_name must not be empty")
    database_path = Path(raw["database_path"])
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path
    cors_env = os.getenv("RPLA_CORS_ORIGINS", "").strip()
    cors_origins = tuple(origin.strip() for origin in
                         (cors_env.split(",") if cors_env else raw.get("cors_allow_origins", [])) if origin.strip())
    return LiveServiceConfig(
        source_type=source_type, source_name=source_name, camera_ip=camera_ip,
        camera_device=device, camera_backend=backend, pixel_format=pixel_format, requested_fps=fps,
        framesize_control_value=framesize, framesize_name=resolution,
        expected_width_px=width, expected_height_px=height, roi_px=roi_px,
        inspection_profile=inspection_name, parameter_status=inspection.get("parameter_status", "UNVALIDATED_BASELINE"),
        threshold=int(inspection["threshold"]), min_area_px=float(inspection["min_area_px"]),
        vision_options=vision_options, presence_gate_enabled=bool(inspection["presence_gate_enabled"]),
        target_dark_threshold=int(inspection["target_dark_threshold"]),
        target_min_row_fraction=float(inspection["target_min_row_fraction"]),
        target_min_coverage=float(inspection["target_min_coverage"]),
        target_centre_fraction=float(inspection["target_centre_fraction"]),
        target_max_width_fraction=float(inspection.get("target_max_width_fraction", 0.65)),
        jpeg_quality=int(raw["jpeg_quality"]), reconnect_delay_s=float(raw["reconnect_delay_s"]),
        open_timeout_ms=int(raw["open_timeout_ms"]), read_timeout_ms=int(raw["read_timeout_ms"]),
        event_retention=_positive_int(raw["event_retention"], "event_retention"),
        stale_after_s=float(raw.get("stale_after_s", 1.0)),
        disconnect_after_s=float(raw.get("disconnect_after_s", 2.0)), recovery_frames=int(raw.get("recovery_frames", 3)),
        cors_allow_origins=cors_origins, database_path=database_path,
        vision_algorithm=vision_algorithm, static_options=static_options, surface_options=surface_options,
        split_preview=os.getenv("RPLA_SPLIT_PREVIEW", "").strip() == "1",
    )
