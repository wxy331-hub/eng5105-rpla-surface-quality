from pathlib import Path

import cv2
import pytest

from src.esp32_ov3660_stream_check import load_config, open_stream, resolve_stream_url


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "camera_esp32_ov3660.json"


def test_ov3660_config_is_valid() -> None:
    config = load_config(CONFIG_PATH)
    assert config["sensor_model"] == "OV3660"
    assert config["sensor_model_status"] == "confirmed"
    assert config["native_max_width_px"] == 2048
    assert config["native_max_height_px"] == 1536
    assert config["framesize_control_value"] == 19
    assert config["framesize_name"] == "QXGA"
    assert config["expected_width_px"] == 2048
    assert config["expected_height_px"] == 1536
    assert config["recommended_live_default"] == "SVGA"
    assert config["resolution_profiles"]["SVGA"]["framesize_control_value"] == 11


def test_placeholder_url_must_be_replaced() -> None:
    config = load_config(CONFIG_PATH)
    with pytest.raises(ValueError, match="ESP32实际视频地址"):
        resolve_stream_url(config, None)


def test_command_line_url_overrides_placeholder() -> None:
    config = load_config(CONFIG_PATH)
    url = "http://192.168.4.1:81/stream"
    assert resolve_stream_url(config, url) == url


@pytest.mark.parametrize("opened", [True, False])
def test_stream_check_supplies_configured_timeouts_to_open(monkeypatch, opened):
    calls = []

    class Capture:
        def open(self, *args):
            calls.append(args)
            return opened

        def release(self):
            calls.append("released")

    capture = Capture()
    monkeypatch.setattr(cv2, "VideoCapture", lambda: capture)
    config = {"open_timeout_ms": 1200, "read_timeout_ms": 750}
    url = "http://192.0.2.1:81/stream"
    if opened:
        assert open_stream(url, config) is capture
    else:
        with pytest.raises(ConnectionError):
            open_stream(url, config)
        assert calls[-1] == "released"
    assert calls[0] == (url, cv2.CAP_FFMPEG, [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 1200,
        cv2.CAP_PROP_READ_TIMEOUT_MSEC, 750,
    ])
