"""Run a complete synthetic 12-view sample and write a reproducible evidence pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
from uuid import uuid4

import cv2
import numpy as np

from src.week7.workflow import ANGLES, PROJECT_ROOT, SampleWorkflow


def run(output: Path, sample_id: str = "W7-DEMO-001") -> dict:
    workflow = SampleWorkflow(output)
    sample = workflow.create_sample(sample_id)
    session_id = sample["session_id"]
    for angle in ANGLES:
        sample = workflow.capture_angle(session_id, angle)
    # Demonstrate a deliberate retake, retaining the two replaced attempts.
    workflow.capture_angle(session_id, 0, retake=True)
    sample = workflow.store.complete_sample(session_id)
    destination = output / ("export-" + session_id)
    destination.mkdir(exist_ok=False)
    (destination / "captures.csv").write_text(workflow.store.export_csv(session_id), encoding="utf-8-sig")
    result = {
        "evidence_label": "OFFLINE_SYNTHETIC_ONLY", "sample": sample,
        "health": workflow.health(), "config": workflow.config,
        "runtime": {"python": platform.python_version(), "opencv": cv2.__version__, "numpy": np.__version__},
        "validation_scope": "Generated images and simulated MCU messages; no physical camera or material validation",
    }
    (destination / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    workflow.store.close()
    return {"session_id": session_id, "completed_views": sample["completed_views"],
            "attempts": len(sample["captures"]), "status": sample["status"], "output": str(destination)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=PROJECT_ROOT / "data/output" / ("week7_demo_" + uuid4().hex[:8]))
    parser.add_argument("--sample-id", default="W7-DEMO-001")
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.sample_id), indent=2))


if __name__ == "__main__":
    main()
