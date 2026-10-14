"""Check the real PA8 output: sample GPIOA->IDR bit 8 over SWD while the firmware runs.

Usage (on the Pi, with openocd already running as a server on TCL port 6666):
    python3 pwm_probe.py --port /dev/ttyACM0
Each SWD read lands at an effectively random phase of the 20 kHz PWM, so the fraction of
reads that see PA8 high estimates the duty cycle. TIM1 ARR and CCR1 are read as well.
"""
import argparse
import socket
import threading
import time

import serial

GPIOA_IDR, TIM1_ARR, TIM1_CCR1 = 0x40020010, 0x4001002C, 0x40010034


class OpenOcd:
    def __init__(self):
        self.sock = socket.create_connection(("127.0.0.1", 6666))

    def cmd(self, text):
        self.sock.sendall(text.encode() + b"\x1a")
        data = b""
        while not data.endswith(b"\x1a"):
            data += self.sock.recv(4096)
        return data[:-1].decode().strip()

    def word(self, address):
        return int(self.cmd(f"read_memory 0x{address:08x} 32 1"), 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--samples", type=int, default=2000)
    args = parser.parse_args()

    ocd = OpenOcd()
    ser = serial.Serial(args.port, 115200, timeout=0.1)
    ser.write(b"\n")
    beat = {"on": False}

    def heartbeat():
        while True:
            if beat["on"]:
                ser.write(b"HB\n")
            time.sleep(0.1)

    threading.Thread(target=heartbeat, daemon=True).start()

    def measure(label):
        arr, ccr = ocd.word(TIM1_ARR), ocd.word(TIM1_CCR1)
        start = time.monotonic()
        high = sum((ocd.word(GPIOA_IDR) >> 8) & 1 for _ in range(args.samples))
        rate = args.samples / (time.monotonic() - start)
        print(f"{label}：PA8 高电平比例 {100 * high / args.samples:.1f}%"
              f"（{args.samples} 次采样，约 {rate:.0f} 次/s）；寄存器 ARR={arr}，CCR1={ccr}，"
              f"设定占空比 {100 * ccr / (arr + 1):.1f}%", flush=True)

    beat["on"] = True
    time.sleep(0.4)
    ser.write(b"ARM\n")
    time.sleep(0.5)
    measure("NORMAL，50%")
    ser.write(b"DUTY,20\n")
    time.sleep(0.3)
    measure("NORMAL，20%")
    ser.write(b"DUTY,50\n")
    beat["on"] = False
    time.sleep(4.5)
    measure("停发心跳 4.5 s 后（应为 FAULT）")
    ser.write(b"STATUS\n")
    time.sleep(0.3)
    print("板子回报：", ser.read(400).decode(errors="replace").strip().splitlines()[-1], flush=True)


if __name__ == "__main__":
    main()
