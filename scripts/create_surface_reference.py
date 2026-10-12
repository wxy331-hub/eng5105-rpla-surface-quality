"""Create a good-sample surface reference from archived raw images (bench demo starting point).

Usage (project root):
    .\\.venv\\Scripts\\python.exe scripts/create_surface_reference.py --reference-id REF-GOOD01-0DEG IMAGE [IMAGE ...]

The first image defines the reference; any further images of the same good
sample (same set-up) are compared with it and recorded as a repeatability check.
The file is written to data/references/static_rpla_surface/<reference_id>.json
and an existing reference is never overwritten. Point the plan_a profile's
static_surface.reference_path at the new file and restart the service.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.inspection.processor import StaticRplaProcessor  # noqa: E402
from src.inspection.surface import (  # noqa: E402
    REFERENCE_SCHEMA_VERSION,
    SURFACE_ALGORITHM_VERSION,
    SurfaceParams,
    validate_reference_metrics,
)
from src.week3.models import CameraState, FramePacket, utc_now_iso  # noqa: E402
from replay_static_inspection import profile_params  # noqa: E402

REFERENCE_DIR = ROOT / "data" / "references" / "static_rpla_surface"


def analyse(path: Path, config_path: Path, profile: str) -> dict:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"could not read image: {path}")
    raw = json.loads(config_path.read_text(encoding="utf-8"))["inspection_profiles"][profile]
    # The reference is measured without any reference of its own.
    surface = SurfaceParams.from_mapping({**raw.get("static_surface", {}), "reference_path": None})
    geometry = profile_params(config_path, profile, image.shape[1], image.shape[0])
    stamp = utc_now_iso()
    result = StaticRplaProcessor(geometry, data_mode="REFERENCE_CREATION", surface=surface).inspect(
        FramePacket("REFERENCE", 0, stamp, stamp, CameraState.HEALTHY, image), "REFERENCE",
        lighting_mode="bright_field")
    payload = result.to_dict()
    if payload["geometry_status"] != "valid" or payload["surface"]["status"] != "valid":
        raise SystemExit(f"{path}: not usable as a reference: {payload['reason_codes']}")
    return {"path": path, "payload": payload, "surface_params": surface}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--reference-id", required=True)
    parser.add_argument("--capture-id")
    parser.add_argument("--angle", type=int, default=0, choices=(0, 60, 120, 180, 240, 300))
    parser.add_argument("--profile", default="plan_a")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "live_service.json")
    args = parser.parse_args()
    if not args.reference_id.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("reference id may contain letters, digits, '-' and '_' only")
    target = REFERENCE_DIR / f"{args.reference_id}.json"
    if target.exists():
        raise SystemExit(f"{target} already exists; references are never overwritten")

    runs = [analyse(path, args.config, args.profile) for path in args.images]
    first = runs[0]["payload"]
    surface, geometry = first["surface"]["metrics"], first["metrics"]
    metrics = {"texture_mad": surface["texture_mad"], "longitudinal_energy": surface["longitudinal_energy"],
               "brightness_median": surface["brightness_median"], "edge_spread_px": surface["edge_spread_px"],
               "width_px": geometry["width_px_median"]}
    try:
        # The loader's rule, applied before anything is written.
        validate_reference_metrics(metrics)
    except ValueError as error:
        raise SystemExit(f"{runs[0]['path']}: not usable as a reference: {error}")

    def ratio(value: float, base: float) -> float | None:
        return round(value / base, 3) if base > 0 else None

    repeat = []
    for run in runs[1:]:
        other = run["payload"]["surface"]["metrics"]
        repeat.append({"image": str(run["path"]),
                       "texture_ratio": ratio(other["texture_mad"], surface["texture_mad"]),
                       "streak_ratio": ratio(other["longitudinal_energy"], surface["longitudinal_energy"])})
    source_path = runs[0]["path"]
    reference = {
        "schema_version": REFERENCE_SCHEMA_VERSION,
        "reference_id": args.reference_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "algorithm_version": SURFACE_ALGORITHM_VERSION,
        "operator_label": "good_reference",
        "evidence_scope": "BENCH_DEMO_STARTING_POINT",
        "min_feature_px": runs[0]["surface_params"].min_feature_px,
        "metrics": metrics,
        "source": {"image": str(source_path.resolve()), "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                   "capture_id": args.capture_id, "angle_deg": args.angle, "lighting_mode": "bright_field"},
        "repeatability": {"status": "checked" if repeat else "unchecked", "frames": repeat},
        "bright_structures": first["surface"]["metrics"].get("bright_structures", []),
        "geometry_parameters": first["parameters"],
        "surface_parameters": first["surface"]["parameters"],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "x", encoding="utf-8") as handle:  # "x": fail rather than overwrite
        json.dump(reference, handle, indent=2, allow_nan=False)
    print(json.dumps({"reference": str(target), "metrics": reference["metrics"], "repeatability": repeat}, indent=2))
    if reference["bright_structures"]:
        print("WARNING: the reference image itself has long bright structures (possible glare). Under the same "
              "lighting every compared view may have its grade suspended; consider moving the light and recreating.")
    print(f'set inspection_profiles.{args.profile}.static_surface.reference_path to '
          f'"{target.relative_to(ROOT).as_posix()}" and restart the service')


if __name__ == "__main__":
    main()
