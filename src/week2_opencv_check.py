"""Week 2 OpenCV environment check for the ENG5105 vision project."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

import cv2
import numpy as np


def create_synthetic_filament(width: int = 640, height: int = 360) -> np.ndarray:
    """Create a repeatable test image with a filament-like strip and defects."""
    image = np.full((height, width, 3), 235, dtype=np.uint8)
    centre_y = height // 2

    cv2.rectangle(image, (30, centre_y - 38), (width - 30, centre_y + 38), (95, 95, 95), -1)
    cv2.circle(image, (width // 3, centre_y), 13, (225, 225, 225), -1)
    cv2.line(
        image,
        (2 * width // 3 - 25, centre_y - 25),
        (2 * width // 3 + 25, centre_y + 25),
        (230, 230, 230),
        6,
    )
    return image


def analyse_image(image: np.ndarray) -> tuple[np.ndarray, dict[str, int | str]]:
    """Run a simple, explainable OpenCV baseline and return an annotated image."""
    if image is None or image.size == 0:
        raise ValueError("Input image is empty.")

    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(grey, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    annotated = image.copy()
    significant = [contour for contour in contours if cv2.contourArea(contour) >= 20]
    cv2.drawContours(annotated, significant, -1, (0, 0, 255), 2)

    result: dict[str, int | str] = {
        "python_version": platform.python_version(),
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
        "image_width_px": int(image.shape[1]),
        "image_height_px": int(image.shape[0]),
        "significant_contours": len(significant),
        "status": "PASS",
    }
    return annotated, result


def load_or_create_image(input_path: Path | None) -> np.ndarray:
    """Load a user image, or create a synthetic image when none is supplied."""
    if input_path is None:
        return create_synthetic_filament()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input image does not exist: {input_path}")

    image = cv2.imread(str(input_path))
    if image is None:
        raise ValueError(f"OpenCV could not decode the image: {input_path}")
    return image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Python/OpenCV and process one local or synthetic image."
    )
    parser.add_argument("--input", type=Path, help="Optional JPEG or PNG input image.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/week2_opencv_check.jpg"),
        help="Annotated image output path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        image = load_or_create_image(args.input)
        annotated, result = analyse_image(image)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.output), annotated):
            raise OSError(f"Could not write output image: {args.output}")
        result["output_path"] = str(args.output.resolve())
        print(json.dumps(result, indent=2))
        return 0
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
