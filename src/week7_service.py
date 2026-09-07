"""Local Week 7 API. Only generated images and simulated MCU messages are used."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from src.week7.workflow import PROJECT_ROOT, SampleWorkflow
from src.week7.protocol import ProtocolError


class SampleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_id: str = Field(min_length=1, max_length=100)


class CaptureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    angle_deg: StrictInt
    lighting_mode: Literal["bright_field", "dark_field"]
    retake: StrictBool = False


def create_app(root: Path, *, workflow: SampleWorkflow | None = None) -> FastAPI:
    runtime = workflow or SampleWorkflow(root)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        runtime.store.close()

    app = FastAPI(title="rPLA Plan A Offline Sample Capture", lifespan=lifespan)
    app.state.workflow = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[f"http://{host}:{port}" for host in ("127.0.0.1", "localhost")
                       for port in (5173, 5177)],
        allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
    )

    @app.exception_handler(KeyError)
    async def missing(_: Request, exc: KeyError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    @app.exception_handler(ProtocolError)
    async def conflict(_: Request, exc: Exception):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(OSError)
    async def archive_error(_: Request, exc: OSError):
        return JSONResponse(status_code=503, content={"detail": "Evidence archive unavailable: " + str(exc)})

    @app.get("/api/week7/health")
    def health():
        return runtime.health()

    @app.get("/api/week7/samples")
    def samples():
        return {"samples": [runtime.describe_sample(sample) for sample in runtime.store.list_samples()]}

    @app.post("/api/week7/samples", status_code=201)
    def create_sample(body: SampleRequest):
        return runtime.create_sample(body.sample_id)

    @app.get("/api/week7/samples/{session_id}")
    def sample(session_id: str):
        return runtime.describe_sample(runtime.store.get_sample(session_id))

    @app.post("/api/week7/samples/{session_id}/capture")
    def capture(session_id: str, body: CaptureRequest):
        return runtime.capture_view(session_id, body.angle_deg, body.lighting_mode, retake=body.retake)

    @app.delete("/api/week7/samples/{session_id}")
    def delete_sample(session_id: str):
        result = runtime.delete_sample(session_id)
        return JSONResponse(status_code=202 if result.get("cleanup_pending") else 200, content=result)

    @app.post("/api/week7/samples/{session_id}/complete")
    def complete(session_id: str):
        return runtime.describe_sample(runtime.store.complete_sample(session_id))

    @app.get("/api/week7/samples/{session_id}/export.csv")
    def export(session_id: str):
        csv_text = runtime.store.export_csv(session_id)
        return Response(content="\ufeff" + csv_text, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="sample-captures.csv"'})

    @app.get("/api/week7/captures/{capture_id}/{kind}.png")
    def capture_image(capture_id: str, kind: str):
        if kind not in ("raw", "annotated"):
            raise KeyError("Unknown image kind")
        return FileResponse(runtime.store.image_path(capture_id, kind), media_type="image/png")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data/output/week7_service")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(create_app(args.output), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
