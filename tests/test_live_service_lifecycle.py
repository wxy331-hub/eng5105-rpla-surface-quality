"""Exercise idle-client disconnect and shutdown through real HTTP/WebSockets."""

from contextlib import contextmanager
from dataclasses import replace
import json
import socket
import threading
import time
from urllib.request import urlopen

import pytest
import uvicorn
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from src.camera_config import load_service_config
from src.live_service import InspectionRuntime
from src.week8_service import create_app


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("RPLA_SOURCE_TYPE", "usb_uvc")
    for key in ("RPLA_CONFIG_PATH", "RPLA_RESOLUTION", "RPLA_CAMERA_DEVICE"):
        monkeypatch.delenv(key, raising=False)
    config = replace(load_service_config(), database_path=tmp_path / "live.db")
    selected = InspectionRuntime(config, source_factory=lambda: pytest.fail("No camera should be opened"))
    yield selected
    selected.stop(timeout_s=0.2)


@contextmanager
def idle_server(root, runtime):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{sock.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(
        create_app(root, runtime=runtime, connect_on_start=False), log_level="error",
    ))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 3
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    try:
        yield base, server
    finally:
        server.should_exit = True
        thread.join(timeout=1.5)
        stopped_gracefully = not thread.is_alive()
        if not stopped_gracefully:
            # Failure cleanup must not strand an old implementation's worker.
            runtime.stop(timeout_s=0.2)
            server.force_exit = True
            thread.join(timeout=3)
        sock.close()
        assert stopped_gracefully, "Idle client task prevented bounded graceful server shutdown"


def test_idle_websocket_sends_heartbeat_without_changing_frame_version(runtime, tmp_path):
    with idle_server(tmp_path / "heartbeat", runtime) as (base, _):
        with connect(base.replace("http:", "ws:") + "/ws") as client:
            first = json.loads(client.recv(timeout=1))
            second = json.loads(client.recv(timeout=1.6))
            assert first["version"] == second["version"] == 0
            assert first["summary"]["camera_state"] == second["summary"]["camera_state"] == "DISCONNECTED"
            assert first["summary"]["snapshot_published_at_utc"] != second["summary"]["snapshot_published_at_utc"]


def test_closed_idle_websocket_does_not_hold_server_shutdown(runtime, tmp_path):
    with idle_server(tmp_path / "ws-close", runtime) as (base, _):
        with connect(base.replace("http:", "ws:") + "/ws") as client:
            assert json.loads(client.recv(timeout=1))["version"] == 0


def test_mjpeg_client_closed_while_camera_has_no_frames_does_not_hold_shutdown(runtime, tmp_path):
    with idle_server(tmp_path / "mjpeg-close", runtime) as (base, _):
        with urlopen(base + "/api/stream.mjpg", timeout=2) as response:
            assert response.headers["Content-Type"].startswith("multipart/x-mixed-replace")


def test_runtime_stop_closes_idle_websocket(runtime, tmp_path):
    with idle_server(tmp_path / "runtime-stop", runtime) as (base, _):
        with connect(base.replace("http:", "ws:") + "/ws") as client:
            client.recv(timeout=1)
            runtime.stop(timeout_s=0.2)
            with pytest.raises(ConnectionClosed):
                client.recv(timeout=1)
