from pathlib import Path

import pytest

from src.esp32_ov3660_stream_check import load_config, resolve_stream_url


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
