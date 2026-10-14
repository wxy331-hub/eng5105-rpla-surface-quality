#!/usr/bin/env bash
# Stop the background live inspection started by scripts/demo-pi.sh: the service shuts down
# gracefully (camera released, in-flight capture finished), the lamp client sends TIMEOUT
# and exits, and the lamp switches off about 3 s later.
set -uo pipefail

service_pid() { ps -eo pid=,args= | awk '/-m src\.week8_service/ && !/awk/ {print $1; exit}'; }

pid="$(service_pid)"
if [[ -z "$pid" ]]; then
  echo "Live inspection is not running. 识别服务没有在运行。"
else
  kill -INT "$pid"
  for _ in $(seq 60); do [[ -z "$(service_pid)" ]] && break; sleep 0.5; done
  if [[ -n "$(service_pid)" ]]; then
    echo "The service did not stop within 30 s (pid $pid). 服务 30 秒内未停止。" >&2
    exit 1
  fi
  echo "Live inspection stopped; the lamp switches off in about 3 s. 识别已停止，灯约 3 秒后熄灭。"
fi
# A lamp client left without its service (e.g. after a crash) would keep sending TIMEOUT only.
pkill -f "[l]amp_watchdog\.py" 2>/dev/null || true
