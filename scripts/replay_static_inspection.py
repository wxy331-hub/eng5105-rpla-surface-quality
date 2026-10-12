"""Replay saved images through the static-specimen inspection branch.

Usage (project root):
    .\\.venv\\Scripts\\python.exe scripts/replay_static_inspection.py IMAGE [IMAGE ...]
        [--lighting bright_field|dark_field] [--profile plan_a] [--output DIR]

Each run writes to a new directory (never over earlier results): one annotated
JPEG and one analysis JSON per image, plus summary.json. This is an offline
replay of archived pixels; it is not a live-camera or physical measurement.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.inspection.factory import surface_components  # noqa: E402
from src.inspection.geometry import GeometryParams  # noqa: E402
from src.inspection.processor import StaticRplaProcessor  # noqa: E402
from src.week3.models import CameraState, FramePacket, utc_now_iso  # noqa: E402

DATA_MODE = "OFFLINE_REPLAY_OF_ARCHIVED_IMAGE"


def profile_params(config_path: Path, profile: str, width: int, height: int) -> GeometryParams:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    inspection = raw["inspection_profiles"][profile]
    if inspection.get("algorithm") != "static_rpla_geometry":
        raise ValueError(f"profile {profile} does not select static_rpla_geometry")
    x, y, w, h = inspection["roi_normalized"]
    roi = (round(x * width), round(y * height), max(1, round(w * width)), max(1, round(h * height)))
    return GeometryParams.from_mapping({**inspection.get("static_rpla", {}), "search_roi_px": roi})


def replay(images: list[Path], output: Path, *, lighting: str, config_path: Path, profile: str) -> list[dict]:
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, path in enumerate(images):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"could not read image: {path}")
        height, width = image.shape[:2]
        surface, reference = surface_components(
            json.loads(config_path.read_text(encoding="utf-8"))["inspection_profiles"][profile].get("static_surface") or {})
        processor = StaticRplaProcessor(profile_params(config_path, profile, width, height), data_mode=DATA_MODE,
                                        surface=surface, reference=reference)
        stamp = utc_now_iso()
        packet = FramePacket("OFFLINE_REPLAY", index, stamp, stamp, CameraState.HEALTHY, image)
        result = processor.inspect(packet, output.name, lighting_mode=lighting)
        stem = f"{index:02d}_{path.stem}"
        cv2.imwrite(str(output / f"{stem}_annotated.jpg"), result.annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
        analysis = {"source_image": str(path.resolve()), "data_mode": DATA_MODE, **result.to_dict()}
        (output / f"{stem}_analysis.json").write_text(json.dumps(analysis, indent=2, allow_nan=False),
                                                      encoding="utf-8")
        rows.append({
            "image": str(path), "geometry_status": result.geometry_status,
            "reason_codes": result.reason_codes, "candidates": len(result.candidates),
            "edge_spread_px_median": result.metrics.get("edge_spread_px_median"),
            "width_px_median": result.metrics.get("width_px_median"),
            "surface_status": result.surface_status,
            "surface_metrics": None if result.surface is None else {
                k: result.surface["metrics"].get(k) for k in ("texture_mad", "longitudinal_energy", "candidate_counts")},
            "surface_comparison": None if result.surface is None else result.surface["comparison"],
            "elapsed_ms": result.elapsed_ms,
        })
    (output / "summary.json").write_text(json.dumps({
        "generated_at_utc": utc_now_iso(), "data_mode": DATA_MODE, "lighting_mode": lighting,
        "config": str(config_path), "profile": profile, "views": rows,
    }, indent=2, allow_nan=False), encoding="utf-8")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--lighting", choices=("bright_field", "dark_field"), default="bright_field")
    parser.add_argument("--profile", default="plan_a")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "live_service.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or ROOT / "data" / "output" / f"static_inspection_replay_{stamp}"
    rows = replay(args.images, output, lighting=args.lighting, config_path=args.config, profile=args.profile)
    for row in rows:
        spread = row["edge_spread_px_median"]
        print(f"{row['geometry_status']:>9}  candidates={row['candidates']}  "
              f"spread={'-' if spread is None else f'{spread:.1f}px'}  "
              f"{' '.join(row['reason_codes'])}  {row['image']}")
    print(f"results: {output}")


if __name__ == "__main__":
    main()
