"""Host-side test of the NUCLEO-F446RE lamp watchdog; the PC stands in for the Raspberry Pi.

Usage: python3 hb_test.py --port /dev/ttyACM0   (needs pyserial; stop scripts/lamp_watchdog.py first)
Every scenario checks the firmware's own STATE reports (commanded duty, not a light
measurement); the lamp itself is observed by eye. The board is left in FAULT (lamp off).
"""
import argparse
import os
import threading
import time

import serial

HB_PERIOD = 0.1


class Board:
    def __init__(self, port):
        self.port = port
        self.ser = serial.Serial(port, 115200, timeout=0.05)
        self.ser.write(b"\n")          # terminate any partial line left in the board's buffer
        self.t0 = time.monotonic()
        self.lines = []
        self.lock = threading.Lock()
        self.tx_lock = threading.Lock()
        self.heartbeat = False
        self.running = True
        self.paused = False             # receiver stays off the port while it is being closed
        os.makedirs("logs", exist_ok=True)
        self.log = open(time.strftime("logs/test_%Y%m%d_%H%M%S.txt"), "w", encoding="utf-8")
        threading.Thread(target=self._receive, daemon=True).start()
        threading.Thread(target=self._beat, daemon=True).start()

    def now(self):
        return time.monotonic() - self.t0

    def _receive(self):
        pending = b""
        while self.running:
            try:
                data = b"" if self.paused or not self.ser.is_open else self.ser.read(256)
            except (serial.SerialException, OSError, TypeError):
                data = b""
            if not data:
                time.sleep(0.01)
                continue
            pending += data
            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                text = raw.decode(errors="replace").strip()
                if text:
                    t = self.now()
                    with self.lock:
                        self.lines.append((t, text))
                    self.log.write(f"{t:8.3f}  <- {text}\n")

    def _beat(self):
        due = time.monotonic()
        while self.running:
            if self.heartbeat:
                self.send("HB", quiet=True)
            due += HB_PERIOD
            time.sleep(max(0.0, due - time.monotonic()))

    def send(self, command, quiet=False):
        with self.tx_lock:
            if self.ser.is_open:
                self.ser.write((command + "\n").encode())
        if not quiet:
            self.log.write(f"{self.now():8.3f}  -> {command}\n")

    def wait_for(self, prefix, since, timeout):
        """Time of the first line starting with `prefix` received after `since`, or None."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self.lock:
                for t, text in self.lines:
                    if t >= since and text.startswith(prefix):
                        return t
            time.sleep(0.01)
        return None

    def seen(self, prefix, since, until=None):
        with self.lock:
            return any(t >= since and (until is None or t <= until) and text.startswith(prefix)
                       for t, text in self.lines)

    def state(self):
        """State and duty from the first report received after this request (None if none)."""
        t = self.now()
        self.send("STATUS")
        if self.wait_for("STATE,", t, 1.5) is None:
            return None
        with self.lock:
            for when, text in self.lines:
                if when >= t and text.startswith("STATE,"):
                    return text.split(",")[1:3]
        return None


def arm(board):
    board.heartbeat = True
    time.sleep(0.4)
    t = board.now()
    board.send("ARM")
    return board.wait_for("STATE,NORMAL,", t, 1.0) is not None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM4")
    args = parser.parse_args()
    board = Board(args.port)
    results = []

    def record(name, ok, detail):
        results.append((name, ok, detail))
        print(f"{'通过' if ok else '失败'}  {name}：{detail}", flush=True)

    # Start from a known state: no heartbeat, wait out any SUSPECT grace, expect FAULT.
    board.heartbeat = False
    time.sleep(4.0)
    st = board.state()
    record("起始状态为 FAULT、占空比 0", st == ["FAULT", "0"], f"读到 {st}")

    # 1. ARM is refused without a fresh heartbeat.
    t = board.now()
    board.send("ARM")
    refused = board.wait_for("ERR,ARM", t, 1.0) is not None
    record("没有心跳时 ARM 被拒绝", refused and not board.seen("STATE,NORMAL", t), "收到 ERR,ARM" if refused else "未收到拒绝")

    # 2. Heartbeat + ARM -> NORMAL at 50 %, held for 3 s without SUSPECT.
    t = board.now()
    ok = arm(board)
    time.sleep(3.0)
    st = board.state()
    record("有心跳时 ARM 后亮灯 50%", ok and st == ["NORMAL", "50"] and not board.seen("STATE,SUSPECT", t),
           f"保持 3 s 后读到 {st}")

    # 3. Heartbeat stops (Pi hang): SUSPECT after ~0.5 s, lamp off ~3 s later.
    t_stop = board.now()
    board.heartbeat = False
    t_s = board.wait_for("STATE,SUSPECT", t_stop, 2.0)
    t_f = board.wait_for("STATE,FAULT,0", t_stop, 6.0)
    ok = t_s is not None and t_f is not None and 0.4 <= t_s - t_stop <= 0.8 and 3.3 <= t_f - t_stop <= 3.9
    record("心跳中断后关灯（模拟树莓派死机）", ok,
           f"停发心跳后 {t_s - t_stop:.2f} s 进入 SUSPECT，{t_f - t_stop:.2f} s 关灯" if t_s and t_f else "未按时进入 FAULT")

    # 4. Heartbeat returns: the lamp stays off until an explicit ARM.
    board.heartbeat = True
    t = board.now()
    time.sleep(1.5)
    stayed_off = not board.seen("STATE,NORMAL", t)
    ok = arm(board)
    record("心跳恢复后不自动亮灯，ARM 才重新开启", stayed_off and ok,
           "心跳恢复 1.5 s 内保持关灯，ARM 后亮灯" if stayed_off and ok else f"保持关灯={stayed_off}，ARM 成功={ok}")

    # 5. Host reports its own timeout: SUSPECT at once, lamp off 3 s later.
    t = board.now()
    board.heartbeat = False
    board.send("TIMEOUT")
    t_s = board.wait_for("STATE,SUSPECT", t, 1.0)
    t_f = board.wait_for("STATE,FAULT,0", t, 5.0)
    ok = t_s is not None and t_f is not None and t_s - t <= 0.2 and 2.9 <= t_f - t <= 3.4
    record("树莓派主动报超时后关灯", ok,
           f"发 TIMEOUT 后 {t_s - t:.2f} s 进入 SUSPECT，{t_f - t:.2f} s 关灯" if t_s and t_f else "未按时进入 FAULT")

    # 6. A short stall inside the grace period recovers without switching the lamp off.
    arm(board)
    t = board.now()
    board.heartbeat = False
    time.sleep(1.2)
    board.heartbeat = True
    t_back = board.now()
    t_n = board.wait_for("STATE,NORMAL", t_back, 2.0)
    ok = t_n is not None and board.seen("STATE,SUSPECT", t) and not board.seen("STATE,FAULT", t)
    record("短暂卡顿（1.2 s）在宽限期内恢复，灯不灭", ok,
           f"心跳恢复后 {t_n - t_back:.2f} s 回到 NORMAL，期间未关灯" if ok else "未按预期恢复")

    # 7. Brightness commands.
    t = board.now()
    board.send("DUTY,20")
    dimmed = board.wait_for("STATE,NORMAL,20", t, 1.0) is not None
    t = board.now()
    board.send("DUTY,150")
    rejected = board.wait_for("ERR,DUTY", t, 1.0) is not None
    t = board.now()
    board.send("DUTY,50")
    restored = board.wait_for("STATE,NORMAL,50", t, 1.0) is not None
    record("调光命令（20% → 50%，150% 被拒绝）", dimmed and rejected and restored,
           f"调到 20%={dimmed}，拒绝 150%={rejected}，回到 50%={restored}")

    # 8. Firmware hang: the independent watchdog resets the MCU, which restarts in FAULT.
    t = board.now()
    board.send("HANG")
    t_h = board.wait_for("HANGING", t, 1.0)
    t_b = board.wait_for("BOOT,IWDG", t, 4.0)
    t_f = board.wait_for("STATE,FAULT,0", t, 5.0)
    ok = t_h is not None and t_b is not None and t_f is not None and 0.5 <= t_b - t <= 2.5
    record("单片机死机后由硬件看门狗复位并关灯", ok,
           f"死机后 {t_b - t:.2f} s 复位（BOOT,IWDG），复位后为 FAULT" if ok else "未观察到看门狗复位")

    # 9. Host program exits (serial port closed): the board on its own switches the lamp off.
    arm(board)
    board.heartbeat = False
    board.paused = True
    time.sleep(0.2)
    board.ser.close()
    time.sleep(4.5)
    board.ser.open()
    board.ser.write(b"\n")
    board.paused = False
    st = board.state()
    record("上位机程序退出、串口关闭后自行关灯", st == ["FAULT", "0"], f"串口关闭 4.5 s 后重连读到 {st}")

    board.heartbeat = False
    time.sleep(4.0)
    final = board.state()
    board.running = False
    time.sleep(0.2)
    board.log.close()
    passed = sum(ok for _, ok, _ in results)
    print(f"\n共 {len(results)} 项，通过 {passed} 项；结束时板子状态 {final}。")


if __name__ == "__main__":
    main()
