"""检查配备OV3660的ESP32S3 Sense所提供的MJPEG网络视频。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import cv2

try:
    from src.week2_opencv_check import analyse_image
except ModuleNotFoundError:
    from week2_opencv_check import analyse_image


def load_config(path: Path) -> dict[str, Any]:
    """读取并验证ESP32相机配置。"""
    with path.open("r", encoding="utf-8") as config_file:
        config: dict[str, Any] = json.load(config_file)

    required = {
        "source_name",
        "sensor_model",
        "sensor_model_status",
        "stream_url",
        "test_duration_s",
    }
    missing = sorted(required.difference(config))
    if missing:
        raise ValueError(f"配置缺少字段: {', '.join(missing)}")
    if config["sensor_model"] != "OV3660":
        raise ValueError("当前第二周实物配置必须使用已确认的OV3660。")
    if config["sensor_model_status"] != "confirmed":
        raise ValueError("OV3660型号必须标记为已确认。")
    return config


def resolve_stream_url(config: dict[str, Any], override: str | None) -> str:
    """优先使用命令行URL，并拒绝尚未替换的占位地址。"""
    stream_url = override or str(config["stream_url"])
    if "<ESP32_IP>" in stream_url:
        raise ValueError("请使用--url填写ESP32实际视频地址，或修改配置文件中的ESP32_IP。")
    if not stream_url.startswith(("http://", "https://")):
        raise ValueError("视频地址必须以http://或https://开头。")
    return stream_url


def open_stream(stream_url: str, config: dict[str, Any]) -> cv2.VideoCapture:
    """打开MJPEG视频，并尽量应用OpenCV后端支持的超时参数。"""
    capture = cv2.VideoCapture()
    capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(config.get("open_timeout_ms", 5000)))
    capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(config.get("read_timeout_ms", 3000)))
    if not capture.open(stream_url):
        capture.release()
        raise ConnectionError(f"无法打开ESP32视频流: {stream_url}")
    return capture


def run_stream_test(
    stream_url: str,
    config: dict[str, Any],
    output_path: Path,
    duration_s: float,
) -> dict[str, Any]:
    """读取一段实时视频，统计实际帧率并保存最后一帧的标注结果。"""
    capture = open_stream(stream_url, config)
    started = time.perf_counter()
    frame_count = 0
    last_frame = None

    try:
        while time.perf_counter() - started < duration_s:
            ok, frame = capture.read()
            if not ok or frame is None:
                raise ConnectionError("视频流已连接，但读取帧失败。")
            frame_count += 1
            last_frame = frame
    finally:
        capture.release()

    elapsed_s = time.perf_counter() - started
    if last_frame is None or frame_count == 0:
        raise ConnectionError("测试期间没有收到有效视频帧。")

    annotated, analysis = analyse_image(last_frame)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), annotated):
        raise OSError(f"无法保存输出图片: {output_path}")

    return {
        "status": "PASS",
        "camera_source": config["source_name"],
        "sensor_model": config["sensor_model"],
        "sensor_model_status": config["sensor_model_status"],
        "stream_url": stream_url,
        "frames_received": frame_count,
        "elapsed_s": round(elapsed_s, 3),
        "measured_fps": round(frame_count / elapsed_s, 2),
        "frame_width_px": int(last_frame.shape[1]),
        "frame_height_px": int(last_frame.shape[0]),
        "significant_contours_last_frame": analysis["significant_contours"],
        "output_path": str(output_path.resolve()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="测试ESP32S3 OV3660 MJPEG视频流。")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/camera_esp32_ov3660.json"),
        help="相机配置文件。",
    )
    parser.add_argument("--url", help="ESP32视频地址，例如http://192.168.1.50:81/stream。")
    parser.add_argument("--duration", type=float, help="测试时长（秒）。")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/esp32_ov3660_last_frame.jpg"),
        help="最后一帧的标注结果。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        stream_url = resolve_stream_url(config, args.url)
        duration_s = args.duration or float(config["test_duration_s"])
        if duration_s <= 0:
            raise ValueError("测试时长必须大于0秒。")
        result = run_stream_test(stream_url, config, args.output, duration_s)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ConnectionError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
