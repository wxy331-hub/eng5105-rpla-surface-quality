"""Exercise real HTTP routing without adding a test-client dependency."""

from contextlib import contextmanager
import json
import socket
import sqlite3
from threading import Thread
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import uvicorn

from src.week7_service import create_app
from src.week7.workflow import SampleWorkflow
from src.week7.store import SampleStore


@contextmanager
def local_server(root, config_path):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    workflow = SampleWorkflow(root, config_path=config_path)
    server = uvicorn.Server(uvicorn.Config(create_app(root, workflow=workflow), log_level="error"))
    thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Local test API failed to start")
            time.sleep(0.02)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        assert not thread.is_alive()


def request(base, path, body=None, *, method=None):
    req = Request(base + path, data=None if body is None else json.dumps(body).encode(),
                  headers={} if body is None else {"Content-Type": "application/json"}, method=method)
    try:
        response = urlopen(req, timeout=10)
    except HTTPError as error:
        response = error
    with response:
        content = response.read()
        if "application/json" in response.headers.get("Content-Type", ""):
            content = json.loads(content)
        return response.status, content


def test_http_capture_export_images_and_validation(tmp_path, sample_capture_config):
    with local_server(tmp_path, sample_capture_config) as base:
        assert request(base, "/api/week7/health")[1]["physical_outputs_allowed"] is False
        status, sample = request(base, "/api/week7/samples", {"sample_id": "HTTP-SAMPLE"})
        assert status == 201
        assert sample["capture_configuration"]["image_size_px"] == [640, 360]
        assert sample["capture_compatible"] is True
        path = "/api/week7/samples/" + sample["session_id"]
        assert request(base, path + "/complete", {})[0] == 409
        assert request(base, path + "/capture", {"angle_deg": "60", "lighting_mode": "bright_field"})[0] == 422
        assert request(base, path + "/capture", {"angle_deg": True, "lighting_mode": "bright_field"})[0] == 422
        assert request(base, path + "/capture", {"angle_deg": 60, "lighting_mode": "bright_field", "retake": "false"})[0] == 422
        assert request(base, path + "/capture", {"angle_deg": 60})[0] == 422
        assert request(base, path + "/capture", {"angle_deg": 60, "lighting_mode": "both"})[0] == 422
        assert request(base, path)[1]["captures"] == []
        for angle in (0, 60, 120, 180, 240, 300):
            for light_index, light in enumerate(("bright_field", "dark_field")):
                status, sample = request(base, path + "/capture", {"angle_deg": angle, "lighting_mode": light})
                assert status == 200, sample
                assert sample["completed_views"] == angle // 30 + light_index + 1
                assert sample["captures"][-1]["lighting_mode"] == light
        assert request(base, path + "/capture", {"angle_deg": 0, "lighting_mode": "bright_field"})[0] == 409
        assert request(base, path + "/complete", {})[1]["status"] == "completed"
        capture = sample["current_views"][0]
        status, png = request(base, f"/api/week7/captures/{capture['capture_id']}/raw.png")
        assert status == 200 and png.startswith(b"\x89PNG")
        assert request(base, "/api/week7/captures/unknown/raw.png")[0] == 404
        assert request(base, path + "/export.csv")[1].startswith(b"\xef\xbb\xbf")
        assert request(base, "/api/week7/samples")[1]["samples"][0]["sample_id"] == "HTTP-SAMPLE"
        # A selected-session deletion removes images/history and leaves neighbours.
        _, neighbour = request(base, "/api/week7/samples", {"sample_id": "KEEP"})
        status, deleted = request(base, path, method="DELETE")
        assert status == 200, deleted
        assert deleted["deleted_session_id"] == sample["session_id"]
        assert deleted["deleted_capture_count"] == 12
        assert deleted["deleted_image_count"] == 24
        assert not deleted.get("cleanup_pending")
        assert request(base, path)[0] == 404
        assert request(base, f"/api/week7/captures/{capture['capture_id']}/raw.png")[0] == 404
        assert request(base, path + "/export.csv")[0] == 404
        assert request(base, "/api/week7/samples")[1]["samples"][0]["session_id"] == neighbour["session_id"]


def test_pending_file_cleanup_remains_discoverable_and_retryable(tmp_path, sample_capture_config, monkeypatch):
    with local_server(tmp_path, sample_capture_config) as base:
        _, sample = request(base, "/api/week7/samples", {"sample_id": "CLEANUP-RETRY"})
        path = "/api/week7/samples/" + sample["session_id"]
        assert request(base, path + "/capture", {"angle_deg": 0, "lighting_mode": "dark_field"})[0] == 200
        def file_locked(self, directory):
            raise PermissionError("Test image temporarily in use")
        with monkeypatch.context() as patch:
            patch.setattr(SampleStore, "_purge_sample_deletion", file_locked)
            status, result = request(base, path, method="DELETE")
            assert status == 202 and result["cleanup_pending"]
            assert result["pending_image_count"] == 2
            assert request(base, path)[0] == 404
            health = request(base, "/api/week7/health")[1]
            assert health["camera"] == {"status": "not_integrated", "connected": None, "capture_available": False}
            assert health["pending_deletions"][0]["deleted_session_id"] == sample["session_id"]
        status, result = request(base, path, method="DELETE")
        assert status == 200 and not result["cleanup_pending"]
        assert result["deleted_image_count"] == 2
        assert request(base, "/api/week7/health")[1]["pending_deletions"] == []


def test_database_unavailable_returns_structured_503(tmp_path, sample_capture_config, monkeypatch):
    with local_server(tmp_path, sample_capture_config) as base:
        def unavailable(_):
            raise sqlite3.OperationalError("test database unavailable")
        monkeypatch.setattr(SampleStore, "list_samples", unavailable)
        status, result = request(base, "/api/week7/samples")
        assert status == 503
        assert "test database unavailable" in result["detail"]
