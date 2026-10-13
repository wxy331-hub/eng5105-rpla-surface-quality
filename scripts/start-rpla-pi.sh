#!/usr/bin/env bash
# Raspberry Pi 4B demonstration: one service owns the USB camera, inspects in
# split preview mode and serves the built GUI, so a browser on another computer
# in the same trusted LAN opens http://<pi-address>:8765/.
#
# Before the first run, build the GUI on the development computer with
#   VITE_INSPECTION_MODE=service VITE_SERVICE_SAME_ORIGIN=1 pnpm run build
# and copy gui-prototype/dist/client to the same path on the Pi.
# Stop with Ctrl+C; the service then closes the camera.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python="$root/.venv/bin/python"
gui="$root/gui-prototype/dist/client"
[[ -x "$python" ]] || { echo "Missing $python; create the venv and install requirements.txt" >&2; exit 1; }
[[ -f "$gui/index.html" ]] || { echo "Missing $gui/index.html; copy the built GUI first" >&2; exit 1; }

export RPLA_SOURCE_TYPE=usb_uvc
export RPLA_CONFIG_PATH="$root/config/live_service.json"
export RPLA_CAMERA_DEVICE="${RPLA_CAMERA_DEVICE:-/dev/video0}"
export RPLA_CAMERA_BACKEND=v4l2
export RPLA_RESOLUTION=UHD
export RPLA_SPLIT_PREVIEW=1

cd "$root"
echo "Open http://$(hostname -I | awk '{print $1}'):8765/ from a computer on this network."
exec "$python" -B -m src.week8_service --host 0.0.0.0 --port 8765 \
  --gui-dir "$gui" --output "$root/data/output/pi_demo"
