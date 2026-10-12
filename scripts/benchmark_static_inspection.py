"""Time the static inspection pipeline stage by stage on this machine (e.g. the Raspberry Pi 4B).

Usage (project root):
    python scripts/benchmark_static_inspection.py IMAGE [IMAGE ...] [--repeat N]
    python scripts/benchmark_static_inspection.py --camera 0 [--seconds 5]

IMAGE is an archived raw capture (PNG). The first form times, per image, what the
live service does with one 4K frame: MJPG decode (simulated by re-encoding the
image as JPEG and decoding it), geometry, surface, the whole inspection, and the
preview JPEG encode. The second form reads the camera at the configured UHD MJPG
mode through V4L2 and reports the delivered frame rate. Results are timings on
this host only; they are not a requirement-R4 capture-to-result measurement.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
from pathlib import Path
import statistics
import sys
import time

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from replay_static_inspection import profile_params  # noqa: E402
from src.inspection.factory import surface_components  # noqa: E402
from src.inspection.geometry import analyse_geometry  # noqa: E402
from src.inspection.processor import StaticRplaProcessor  # noqa: E402
from src.inspection.surface import analyse_surface  # noqa: E402
from src.week3.models import CameraState, FramePacket, utc_now_iso  # noqa: E402

CONFIG = ROOT / "config" / "live_service.json"


def timed(fn, repeat: int) -> tuple[float, object]:
    times, result = [], None
    for _ in range(repeat):
        start = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - start)
    return statistics.median(times) * 1000, result


def bench_images(paths: list[Path], repeat: int) -> None:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))["inspection_profiles"]["plan_a"]
    surface, reference = surface_components(raw.get("static_surface") or {})
    for path in paths:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(path)
        params = profile_params(CONFIG, "plan_a", image.shape[1], image.shape[0])
        ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        decode_ms, _ = timed(lambda: cv2.imdecode(jpeg, cv2.IMREAD_COLOR), repeat)
        geometry_ms, geometry = timed(lambda: analyse_geometry(image, params), repeat)
        surface_ms, _ = timed(lambda: analyse_surface(geometry.context, geometry.status, geometry.metrics, surface,
                                                      reference, "bright_field", 0), repeat)
        processor = StaticRplaProcessor(params, data_mode="BENCHMARK", surface=surface, reference=reference)
        stamp = utc_now_iso()
        packet = FramePacket("BENCHMARK", 0, stamp, stamp, CameraState.HEALTHY, image)
        inspect_ms, result = timed(lambda: processor.inspect(packet, "BENCHMARK", lighting_mode="bright_field",
                                                             angle_deg=0), repeat)
        encode_ms, _ = timed(lambda: cv2.imencode(".jpg", result.annotated, [cv2.IMWRITE_JPEG_QUALITY, 86]), repeat)
        print(f"{path.name}: {image.shape[1]}x{image.shape[0]} geometry={geometry.status} surface={result.surface_status}")
        print(f"  MJPG decode {decode_ms:7.0f} ms | geometry {geometry_ms:7.0f} ms | surface {surface_ms:7.0f} ms | "
              f"whole inspection {inspect_ms:7.0f} ms | preview JPEG {encode_ms:6.0f} ms")
        print(f"  => one live preview frame about {decode_ms + inspect_ms + encode_ms:.0f} ms "
              f"({1000 / (decode_ms + inspect_ms + encode_ms):.2f} frames/s); stale limit 1000 ms")


def bench_camera(device: str, seconds: float) -> None:
    index = int(device) if device.isdigit() else device
    capture = cv2.VideoCapture(index, cv2.CAP_V4L2) if sys.platform.startswith("linux") else cv2.VideoCapture(index)
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
    capture.set(cv2.CAP_PROP_FPS, 30)
    if not capture.isOpened():
        raise SystemExit(f"could not open camera {device}")
    frames, start, shape = 0, time.perf_counter(), None
    while time.perf_counter() - start < seconds:
        ok, frame = capture.read()
        if ok:
            frames += 1
            shape = frame.shape
    elapsed = time.perf_counter() - start
    capture.release()
    print(f"camera {device}: {frames} frames in {elapsed:.1f} s = {frames / elapsed:.2f} frames/s decoded, shape {shape}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("images", nargs="*", type=Path)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--camera")
    parser.add_argument("--seconds", type=float, default=5.0)
    args = parser.parse_args()
    print(f"host: {platform.machine()} {platform.platform()} | CPUs {os.cpu_count()} | "
          f"OpenCV {cv2.__version__} threads {cv2.getNumThreads()} | Python {platform.python_version()}")
    if args.images:
        bench_images(args.images, args.repeat)
    if args.camera is not None:
        bench_camera(args.camera, args.seconds)
    if not args.images and args.camera is None:
        parser.error("give IMAGE paths and/or --camera DEVICE")


if __name__ == "__main__":
    main()
