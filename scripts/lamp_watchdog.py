"""Heartbeat client for the STM32 lamp watchdog (NUCLEO-F446RE on the Pi's USB port).

The Nucleo keeps the 24 V lamp off unless this client sends a heartbeat every 100 ms.
Heartbeats are sent only while the inspection service answers /api/health, so the lamp
switches off when the service, this client or the Pi stops:
  - service unhealthy for 2 s: send TIMEOUT once and stop heartbeats (lamp off 3 s later);
  - client or Pi stops: heartbeats stop (lamp off about 3.5 s later);
  - service healthy again: re-arm the lamp at the configured duty.
Firmware protocol (115200 8N1, one ASCII line each): HB, TIMEOUT, ARM, DUTY,n, STATUS;
the board reports STATE,<NORMAL|SUSPECT|FAULT>,<duty>,<uptime ms>.

Standard library only (Linux termios serial), so it runs from the project venv on the Pi.
Usage: python3 scripts/lamp_watchdog.py [--port /dev/ttyACM0] [--duty 30]
"""
import argparse
import os
import signal
import threading
import time
import urllib.request

HB_PERIOD_S = 0.1
FEED_TIMEOUT_S = 2.0       # service unhealthy this long -> TIMEOUT, heartbeats stop
REARM_INTERVAL_S = 2.0     # minimum spacing between ARM attempts
HEALTH_PERIOD_S = 0.5


def decide(now, last_healthy, board_state, last_arm, timeout_sent, duty):
    """Commands for one heartbeat period; returns (commands, timeout_sent, last_arm)."""
    if now - last_healthy <= FEED_TIMEOUT_S:
        commands = ["HB"]
        if board_state in (None, "FAULT") and now - last_arm >= REARM_INTERVAL_S:
            commands += [f"DUTY,{duty}", "ARM"]
            last_arm = now
        return commands, False, last_arm
    if not timeout_sent:
        return ["TIMEOUT"], True, last_arm
    return [], True, last_arm


def parse_state(raw):
    """Fields of a complete STATE report, or None (a line cut off when the port opened is dropped)."""
    fields = raw.decode(errors="replace").strip().split(",")
    if (len(fields) >= 3 and fields[0] == "STATE" and fields[1] in ("NORMAL", "SUSPECT", "FAULT")
            and fields[2].isdigit()):
        return fields
    return None


def open_serial(port):
    import termios  # Linux only; imported here so the decision logic stays testable anywhere

    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0                                                 # iflag: raw input
    attrs[1] = 0                                                 # oflag: raw output
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL      # 8N1, no modem control
    attrs[3] = 0                                                 # lflag: no echo, no canonical mode
    attrs[4] = attrs[5] = termios.B115200
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)
    os.write(fd, b"\n")                                          # end any partial line on the board
    return fd


class Client:
    def __init__(self, port, health_url, duty):
        self.port, self.health_url, self.duty = port, health_url, duty
        self.fd = None
        self.pending = b""
        self.board_state = None
        self.last_healthy = float("-inf")
        self.stop = threading.Event()

    def log(self, text):
        now = time.time()
        print(time.strftime("%H:%M:%S", time.localtime(now)) + f".{int(now * 1000) % 1000:03d}", text, flush=True)

    def poll_health(self):
        healthy = None
        while not self.stop.is_set():
            try:
                with urllib.request.urlopen(self.health_url, timeout=1.0) as response:
                    ok = response.status == 200
            except OSError:
                ok = False
            if ok:
                self.last_healthy = time.monotonic()
            if ok != healthy:
                self.log("inspection service " + ("healthy" if ok else "not responding"))
                healthy = ok
            self.stop.wait(HEALTH_PERIOD_S)

    def send(self, commands):
        if commands:
            os.write(self.fd, "".join(c + "\n" for c in commands).encode())

    def read_reports(self):
        try:
            self.pending += os.read(self.fd, 512)
        except BlockingIOError:
            return
        while b"\n" in self.pending:
            raw, self.pending = self.pending.split(b"\n", 1)
            fields = parse_state(raw)
            if fields and fields[1] != self.board_state:
                self.board_state = fields[1]
                self.log(f"lamp controller {fields[1]}, duty {fields[2]} %")

    def run(self):
        threading.Thread(target=self.poll_health, daemon=True).start()
        last_arm, timeout_sent = float("-inf"), False
        due = time.monotonic()
        while not self.stop.is_set():
            try:
                if self.fd is None:
                    self.fd = open_serial(self.port)
                    self.board_state, self.pending = None, b""
                    self.log(f"connected to {self.port}")
                self.read_reports()
                commands, timeout_sent, last_arm = decide(time.monotonic(), self.last_healthy,
                                                          self.board_state, last_arm, timeout_sent, self.duty)
                self.send(commands)
            except OSError as error:
                if self.fd is not None:
                    self.log(f"lost {self.port}: {error}")
                    os.close(self.fd)
                    self.fd = None
                self.stop.wait(1.0)
                continue
            due += HB_PERIOD_S
            self.stop.wait(max(0.0, due - time.monotonic()))
        if self.fd is not None:
            try:
                self.send(["TIMEOUT"])        # switch the lamp off promptly rather than by silence
            finally:
                os.close(self.fd)
        self.log("stopped")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--health", default="http://127.0.0.1:8765/api/health")
    parser.add_argument("--duty", type=int, default=30, choices=range(0, 101), metavar="0-100")
    args = parser.parse_args()
    client = Client(args.port, args.health, args.duty)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: client.stop.set())
    client.run()


if __name__ == "__main__":
    main()
