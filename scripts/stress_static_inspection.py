"""Randomised synthetic stress test of the static geometry inspector.

Not part of the pytest suite (it takes several minutes). From the project root:
    .\\.venv\\Scripts\\python.exe scripts/stress_static_inspection.py

Good specimens (random width, taper, flare, gentle bend, noise, JPEG, angle)
must give no candidates; one or two random bulges/necks must each be found with
the right type. Every case has its own seed, so a failure printed with its
index can be replayed. Synthetic evidence only; it says nothing about real rPLA.
"""

from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT)]
from test_static_inspection import analyse, render  # noqa: E402

SHAPE = (1080, 1920)
HALF = (SHAPE[0] - 1) / 2
rng = np.random.default_rng(20261007)


def jpeg(image, quality):
    ok, data = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def base_shape():
    width = rng.uniform(160, 420)
    taper = rng.uniform(-30, 30)
    flare = rng.uniform(-15, 15)
    bend_amp = rng.uniform(0, 25)
    bend_period = rng.uniform(900, 2500)
    w = lambda v: width + taper * v / HALF + flare * (v / HALF) ** 2
    c = lambda v: bend_amp * np.sin(2 * np.pi * v / bend_period)
    return w, c, dict(width=round(width), taper=round(taper, 1), flare=round(flare, 1), bend=round(bend_amp, 1))


def finish(image):
    q = rng.choice([0, 90, 75])
    return jpeg(image, int(q)) if q else image


def run_good(n):
    global rng
    failures = []
    for i in range(n):
        rng = np.random.default_rng(i)
        w, c, info = base_shape()
        angle = rng.uniform(-30, 30)
        image = finish(render(w, centre=c, angle_deg=angle, noise=rng.uniform(2, 10), seed=i))
        o = analyse(image)
        if o.status != "valid" or o.candidates:
            failures.append((i, info, round(angle, 1), o.status, o.reason_codes,
                             [(x["defect_type"], x["peak_px"], x["run_length_px"]) for x in o.candidates]))
    return failures


def run_defect(n, pair=False):
    global rng
    failures = []
    for i in range(n):
        rng = np.random.default_rng(5000 + i + (10000 if pair else 0))
        w, c, info = base_shape()
        anomalies = []
        start = rng.uniform(0, SHAPE[0] - 400)
        for _ in range(2 if pair else 1):
            length = rng.uniform(50, 220)
            height = rng.uniform(10, 40) * rng.choice([1, -1])
            side = rng.choice(["right", "left", "both"])
            anomalies.append((start, length, height, side))
            start += length + rng.uniform(45, 120)
        if anomalies[-1][0] + anomalies[-1][1] > SHAPE[0]:
            continue

        def extra(v, which):
            total = np.zeros_like(v, dtype=float)
            for s0, length, height, side in anomalies:
                inside = (v + HALF >= s0) & (v + HALF < s0 + length)
                if which == "width":
                    total += height * inside
                elif side == "right":
                    total += height / 2 * inside
                elif side == "left":
                    total -= height / 2 * inside
            return total

        image = finish(render(lambda v: w(v) + extra(v, "width"), centre=lambda v: c(v) + extra(v, "centre"),
                              noise=rng.uniform(2, 8), seed=1000 + i))
        o = analyse(image)
        expected = ["width_bulge_candidate" if a[2] > 0 else "width_neck_candidate" for a in anomalies]
        found = [x["defect_type"] for x in sorted(o.candidates, key=lambda x: x["axial_range_px"][0])]
        if o.status != "valid" or found != expected:
            failures.append((i, info, [(round(a[0]), round(a[1]), round(float(a[2]), 1), str(a[3])) for a in anomalies],
                             o.status, o.reason_codes,
                             [(x["defect_type"], x["axial_range_px"], x["peak_px"]) for x in o.candidates]))
    return failures


if __name__ == "__main__":
    for name, result, total in (("good", run_good(100), 100), ("single", run_defect(200), 200),
                                ("pair", run_defect(200, pair=True), 200)):
        print(f"{name}: {len(result)} failures of {total}", flush=True)
        for item in result[:8]:
            print("   ", item, flush=True)
