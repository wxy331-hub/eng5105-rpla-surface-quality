"""Explicit small synthetic configurations for fast workflow and HTTP tests."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_capture_config(tmp_path):
    config_path = Path(__file__).resolve().parents[1] / "config/week7_offline.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.update(image_size_px=[640, 360], roi_px=[28, 144, 584, 72])
    path = tmp_path / "small-synthetic-config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path
