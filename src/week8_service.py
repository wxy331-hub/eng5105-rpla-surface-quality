"""One resident camera serves continuous inspection and Week 8 sample capture."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from dataclasses import replace
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.camera_config import LiveServiceConfig, PROJECT_ROOT, load_service_config
from src.live_service import CameraCaptureError, InspectionRuntime, create_app as create_live_app
from src.week7_service import create_app as create_sample_app
from src.week8.workflow import CameraSampleWorkflow


def create_app(root: Path, *, runtime: InspectionRuntime | None = None,
               config: LiveServiceConfig | None = None, capture_timeout_s: float = 5.0,
               connect_on_start: bool = True) -> FastAPI:
    """Compose existing REST/WS/MJPEG and sample contracts around one camera."""
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

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data/output/week8_service")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--source-type", choices=("usb_uvc", "esp32_mjpeg"),
                        default=os.getenv("RPLA_SOURCE_TYPE", "usb_uvc"))
    parser.add_argument("--capture-timeout", type=float, default=5.0)
    parser.add_argument("--wait-for-camera", action="store_true",
                        help="Start the UI/API without opening a camera until Connect is pressed")
    args = parser.parse_args()
    os.environ["RPLA_SOURCE_TYPE"] = args.source_type
    import uvicorn
    uvicorn.run(create_app(args.output, capture_timeout_s=args.capture_timeout,
                           connect_on_start=not args.wait_for_camera),
                host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
