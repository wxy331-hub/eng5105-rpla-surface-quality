#!/usr/bin/env bash
# Demonstration on the Raspberry Pi: first the STM32 lamp watchdog, step by step
# (scripts/lamp_demo.py), then live filament inspection left running in the background
# (scripts/start-rpla-pi.sh, which keeps the lamp on through scripts/lamp_watchdog.py).
# The inspection keeps the lamp and camera on while specimens are changed, and survives the
# SSH session ending; stop it with scripts/stop-demo-pi.sh. Extra arguments go to
# lamp_demo.py, e.g. --auto. Log: data/output/pi_demo.log.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python="$root/.venv/bin/python"
port="${RPLA_LAMP_PORT:-/dev/ttyACM0}"
log="$root/data/output/pi_demo.log"

if ps -eo args= | grep -q -E "[s]rc\.week8_service|[l]amp_watchdog\.py"; then
  echo "Live inspection is already running. 识别服务已在运行。"
  exit 0
fi

if [[ -e "$port" ]]; then
  "$python" -B "$root/scripts/lamp_demo.py" --port "$port" "$@"
else
  echo "No lamp controller at $port; skipping the lamp demonstration." >&2
  echo "没有找到 $port（灯光控制器），跳过灯光演示。" >&2
fi

mkdir -p "$(dirname "$log")"
setsid nohup bash "$root/scripts/start-rpla-pi.sh" > "$log" 2>&1 < /dev/null &
echo "Starting live inspection in the background ... 正在后台启动线材实时识别……"
for _ in $(seq 90); do
  if curl -s -o /dev/null --max-time 1 http://127.0.0.1:8765/api/health; then
    break
  fi
  sleep 1
done
for _ in $(seq 10); do grep -q "lamp controller NORMAL" "$log" && break; sleep 0.5; done
if grep -q "lamp controller NORMAL" "$log"; then
  echo "Live inspection is running: lamp on, camera on. 识别已常驻运行：灯常亮、摄像头常开。"
else
  echo "Inspection service started, but the lamp did not report ON; see $log" >&2
  echo "识别服务已启动，但灯没有回报点亮，请查看 $log" >&2
fi
