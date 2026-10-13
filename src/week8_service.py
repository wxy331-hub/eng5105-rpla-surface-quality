"""One resident camera serves continuous inspection and Week 8 sample capture."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from dataclasses import replace
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from src.camera_config import LiveServiceConfig, PROJECT_ROOT, load_service_config
from src.live_service import CameraCaptureError, InspectionRuntime, create_app as create_live_app
from src.week7_service import create_app as create_sample_app
from src.week8.workflow import CameraSampleWorkflow


def create_app(root: Path, *, runtime: InspectionRuntime | None = None,
               config: LiveServiceConfig | None = None, capture_timeout_s: float = 5.0,
               connect_on_start: bool = True, gui_dir: Path | None = None) -> FastAPI:
    """Compose existing REST/WS/MJPEG and sample contracts around one camera.

    gui_dir serves a built GUI (gui-prototype/dist/client) from the same origin,
    so a browser on another computer needs only this one address.
    """
    if gui_dir is not None and not (Path(gui_dir) / "index.html").is_file():
        raise FileNotFoundError(f"built GUI not found: {Path(gui_dir) / 'index.html'}")
    root = Path(root).resolve()
    if runtime is None:
        selected = config or load_service_config()
        selected = replace(selected, database_path=root / "live_inspection.db")
        runtime = InspectionRuntime(selected)
    runtime.connection_deferred = not connect_on_start
    workflow = CameraSampleWorkflow(root, runtime, capture_timeout_s=capture_timeout_s)
    app = create_sample_app(root, workflow=workflow,
                            cors_allow_origins=runtime.config.cors_allow_origins)
    app.title = "rPLA Camera Sample Capture"
    # include_router copies routes, not startup/shutdown; the single lifespan
    # below owns the one runtime and closes it exactly once.
    app.include_router(create_live_app(runtime).router)
    app.state.runtime = runtime

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if connect_on_start:
            runtime.start()
        try:
            yield
        finally:
            runtime.stop()
            workflow.store.close()

    app.router.lifespan_context = lifespan

    @app.exception_handler(CameraCaptureError)
    async def unavailable(_: Request, exc: CameraCaptureError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    if gui_dir is not None:
        # Mounted last so every API and WebSocket route above keeps precedence.
        app.mount("/", StaticFiles(directory=gui_dir, html=True), name="gui")
    return app


class ServiceServer(uvicorn.Server):
    """Ends open MJPEG and WebSocket loops when shutdown starts.

    Otherwise an open browser held Ctrl+C at "Waiting for connections to close"
    (Raspberry Pi, 2026-10-13). A short graceful-shutdown timeout would also
    cancel a capture still being analysed or written (Codex review 2026-10-13),
    so the timeout stays only as a long backstop for a stream stuck on a dead socket.
    """

    def __init__(self, config: uvicorn.Config, runtime: InspectionRuntime) -> None:
        super().__init__(config)
        self.runtime = runtime

    async def shutdown(self, sockets=None) -> None:
        self.runtime.close_streams()
        await super().shutdown(sockets=sockets)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data/output/week8_service")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--source-type", choices=("usb_uvc", "esp32_mjpeg"),
                        default=os.getenv("RPLA_SOURCE_TYPE", "usb_uvc"))
    parser.add_argument("--capture-timeout", type=float, default=5.0)
    parser.add_argument("--wait-for-camera", action="store_true",
                        help="Start the UI/API without opening a camera until Connect is pressed")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Listen address; 0.0.0.0 only for the Raspberry Pi demonstration on a trusted LAN")
    parser.add_argument("--gui-dir", type=Path, help="Serve a built GUI from this directory on the same port")
    args = parser.parse_args()
    os.environ["RPLA_SOURCE_TYPE"] = args.source_type
    app = create_app(args.output, capture_timeout_s=args.capture_timeout,
                     connect_on_start=not args.wait_for_camera, gui_dir=args.gui_dir)
    ServiceServer(uvicorn.Config(app, host=args.host, port=args.port, timeout_graceful_shutdown=30),
                  app.state.runtime).run()


if __name__ == "__main__":
    main()
