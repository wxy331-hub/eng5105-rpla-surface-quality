"""Step-by-step demonstration of the STM32 lamp watchdog, run on the Pi before the inspection service.

Each step waits for Enter (or runs on a timer with --auto) and prints the controller's own
state reports as they arrive, with the time since the step's action:
  1 power-up: lamp off until the Pi arms it      4 Pi failure: heartbeat stops -> lamp off
  2 heartbeat + ARM: lamp on at 30 %             5 Pi recovers: heartbeat + ARM -> lamp on
  3 PWM brightness 20 % -> 30 %                  6 controller hang: IWDG reset -> lamp off
The lamp is left off; scripts/lamp_watchdog.py re-arms it once the inspection service runs.
Usage: python3 scripts/lamp_demo.py [--port /dev/ttyACM0] [--auto]
"""
import argparse
import os
import sys
import threading
import time

from lamp_watchdog import open_serial, parse_state

MEANING = {"NORMAL": "lamp ON / 灯亮", "SUSPECT": "heartbeat missing, lamp kept on / 心跳中断，灯暂时保持",
           "FAULT": "lamp OFF / 灯灭"}


class Controller:
    def __init__(self, port):
        self.fd = open_serial(port)
        self.lock = threading.Lock()
        self.pending = b""
        self.heartbeat = False
        threading.Thread(target=self._beat, daemon=True).start()

    def _beat(self):
        while True:
            if self.heartbeat:
                self.send("HB")
            time.sleep(0.1)

    def send(self, command):
        with self.lock:
            os.write(self.fd, (command + "\n").encode())

    def reports(self):
        try:
            self.pending += os.read(self.fd, 512)
        except BlockingIOError:
            pass
        lines = []
        while b"\n" in self.pending:
            raw, self.pending = self.pending.split(b"\n", 1)
            lines.append(raw.decode(errors="replace").strip())
        return lines

    def watch(self, seconds, start, quiet_periodic=True):
        """Print state changes for `seconds`; times are relative to `start`."""
        last = None
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            for line in self.reports():
                fields = line.split(",")
                if parse_state(line.encode()):
                    if quiet_periodic and (fields[1], fields[2]) == last:
                        continue
                    last = (fields[1], fields[2])
                    note = MEANING.get(fields[1], "")
                    print(f"   +{time.monotonic() - start:5.2f} s  controller {fields[1]:<7} duty {fields[2]:>3} %   {note}",
                          flush=True)
                elif fields[0] == "BOOT":
                    print(f"   +{time.monotonic() - start:5.2f} s  controller restarted, cause: {fields[1]}"
                          "  （单片机已被硬件看门狗复位）", flush=True)
            time.sleep(0.02)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--auto", action="store_true", help="advance on a timer instead of Enter")
    args = parser.parse_args()
    lamp = Controller(args.port)

    def step(number, title_en, title_zh):
        if number > 1:
            if args.auto:
                time.sleep(1.0)
            else:
                input("\n   Press Enter for the next step (回车进入下一步) ...")
        print(f"\n[{number}/6] {title_en}\n      {title_zh}", flush=True)
        return time.monotonic()

    try:
        time.sleep(0.3)
        lamp.reports()
        lamp.pending = b""          # drop a report cut off when the port was opened
        t = step(1, "Power-up: the lamp stays off until the Raspberry Pi arms it",
                 "上电：树莓派发出许可前，灯保持熄灭")
        lamp.send("STATUS")
        lamp.watch(2.0, t)

        t = step(2, "The Pi sends a heartbeat every 100 ms and arms the lamp at 30 %",
                 "树莓派每 100 ms 发一次心跳，并以 30% 亮度开灯")
        lamp.heartbeat = True
        time.sleep(0.3)
        lamp.send("DUTY,30")
        lamp.send("ARM")
        lamp.watch(3.0, t)

        t = step(3, "Brightness is set by PWM duty on PA8 (20 kHz): 20 %, then back to 30 %",
                 "亮度由 PA8 的 PWM 占空比控制（20 kHz）：先调到 20%，再回到 30%")
        lamp.send("DUTY,20")
        lamp.watch(2.5, t)
        lamp.send("DUTY,30")
        lamp.watch(1.5, t)

        t = step(4, "Simulated Pi failure: the heartbeat stops; the controller switches the lamp off",
                 "模拟树莓派故障：心跳停止，控制器自动关灯")
        lamp.heartbeat = False
        lamp.watch(5.0, t)

        t = step(5, "The Pi recovers: heartbeat resumes and the lamp is re-armed",
                 "树莓派恢复：心跳恢复，重新开灯")
        lamp.heartbeat = True
        time.sleep(0.3)
        lamp.send("ARM")
        lamp.watch(3.0, t)

        t = step(6, "Controller firmware hang: its hardware watchdog (IWDG) resets it, lamp off",
                 "模拟单片机死机：硬件看门狗（IWDG）复位单片机，灯熄灭")
        lamp.send("HANG")
        lamp.watch(3.5, t)
        lamp.heartbeat = False

        print("\nLamp watchdog demonstration complete. 灯光看门狗演示结束。", flush=True)
        if not args.auto:
            input("\n   Press Enter to start live filament inspection (回车启动线材实时识别) ...")
    except KeyboardInterrupt:
        lamp.heartbeat = False
        lamp.send("TIMEOUT")
        print("\nStopped; the lamp switches off in about 3 s. 已中止，灯约 3 秒后熄灭。")
        sys.exit(130)
    finally:
        os.close(lamp.fd)


if __name__ == "__main__":
    main()
