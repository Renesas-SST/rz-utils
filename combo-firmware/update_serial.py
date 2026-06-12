#!/usr/bin/env python3
"""
Update uEnv.txt + fix overlay-data.service on both SD cards via serial.

Uploads a fix script (base64-encoded via heredoc), executes it on the board.

Usage:
  python3 update_serial.py                              # /dev/ttyUSB2 default
  python3 update_serial.py --port /dev/ttyUSB0          # custom port
  python3 update_serial.py --port /dev/ttyUSB2 --baud 115200
"""

import argparse
import base64
import time
import sys

try:
    import serial
except ImportError:
    print("Install pyserial: pip install pyserial")
    sys.exit(1)

FIX_SCRIPT = r"""#!/bin/sh
FIX_SERVICE() {
  local f="$1/etc/systemd/system/overlay-data.service"
  [ -f "$f" ] || return 0
  if grep -q 'mount -L DATA' "$f"; then
    sed -i 's|ExecStart=/bin/mount -L DATA /data|ExecStart=/bin/sh -c '"'"'ROOT_DEV=$(findmnt -n -o SOURCE /); mount "${ROOT_DEV%p*}p14" /data'"'"'|' "$f"
    echo "  Fixed: $f"
  else
    echo "  OK (already fixed): $f"
  fi
}

echo "=== 1/3 Update uEnv.txt on FAT partitions ==="
for dev in mmcblk0 mmcblk1; do
  [ -b "/dev/${dev}p1" ] || continue
  mount "/dev/${dev}p1" /mnt 2>/dev/null || continue
  cat > /mnt/uEnv.txt << 'EOF'
# Refer to readme.txt for more information on setting up U-Boot Env
prodsdboot=run mmc_do_boot

# Quick boot by label -- run <name> at U-Boot prompt
core-image-minimal=setenv root_part 5; boot
core-image-bsp=setenv root_part 6; boot
core-image-weston=setenv root_part 7; boot
renesas-core-image-cli=setenv root_part 8; boot
renesas-core-image-weston=setenv root_part 9; boot
renesas-quickboot-cli=setenv root_part 10; boot
renesas-quickboot-wayland=setenv root_part 11; boot
ubuntu-core-image=setenv root_part 12; boot
ubuntu-lxde-image=setenv root_part 13; boot

mmc_args=if test -z "${root_part}"; then setenv root_part 5; fi; setenv bootargs ro rootwait earlycon root=/dev/mmcblk${mmcdev}p${root_part}

# root_part map:  5=minimal  6=bsp  7=weston  8=cli  9=core-weston  10=quickboot-cli  11=quickboot-wayland  12=ubuntu-core  13=ubuntu-lxde
# Manual: setenv root_part N; boot
EOF
  sync
  umount /mnt
  echo "  /dev/${dev}p1: uEnv.txt updated"
done

echo "=== 2/3 Fix overlay-data.service on all rootfs ==="
for dev in mmcblk0 mmcblk1; do
  for part in 5 6 7 8 9 10 11 12 13; do
    [ -b "/dev/${dev}p${part}" ] || continue
    mount "/dev/${dev}p${part}" /mnt 2>/dev/null || continue
    FIX_SERVICE /mnt
    umount /mnt
  done
done

echo "=== 3/3 Fix current root overlay ==="
FIX_SERVICE /

echo "=== Serial update complete ==="
echo "You can now use: run core-image-minimal (or any image name) at U-Boot prompt"
"""


class SerialClient:
    def __init__(self, port: str, baud: int = 115200, timeout: float = 10):
        self.ser = serial.Serial(port, baud, timeout=timeout)
        self.ser.reset_input_buffer()
        self.buf = ""

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def read_until_marker(self, marker: str, timeout: float = 30) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if marker in self.buf:
                idx = self.buf.index(marker) + len(marker)
                data = self.buf[:idx]
                self.buf = self.buf[idx:]
                return data
            try:
                chunk = self.ser.read(1024)
                if chunk:
                    self.buf += chunk.decode(errors="replace")
                    sys.stdout.write(chunk.decode(errors="replace"))
                    sys.stdout.flush()
            except serial.SerialException:
                time.sleep(0.1)
        raise TimeoutError(f"Timeout ({timeout}s) waiting for: {marker}")

    def send(self, text: str):
        self.ser.write(text.encode())

    def cmd(self, command: str, marker: str = "# ", timeout: float = 60) -> str:
        self.send(command + "\n")
        return self.read_until_marker(marker, timeout=timeout)

    def login(self):
        self.send("\n")
        time.sleep(1)
        self.buf += self.ser.read(self.ser.in_waiting or 1024).decode(errors="replace")
        if "login:" in self.buf.lower():
            self.buf = ""
            self.cmd("root", "Password:")
            self.cmd("", "# ", timeout=10)
        elif "Password:" in self.buf:
            self.buf = ""
            self.cmd("", "# ", timeout=10)
        elif "# " in self.buf:
            self.buf = ""
        else:
            self.cmd("root", "# ", timeout=15)

    def upload_script(self, script: str):
        b64 = base64.b64encode(script.encode()).decode()
        self.cmd("cat > /tmp/fix.b64 << 'B64EOF'")
        self.send(b64 + "\n")
        self.send("B64EOF\n")
        time.sleep(0.5)
        self.cmd("base64 -d /tmp/fix.b64 > /tmp/fix.sh", "# ", timeout=10)
        self.cmd("chmod +x /tmp/fix.sh", "# ", timeout=5)

    def run_script(self):
        self.send("/tmp/fix.sh\n")
        return self.read_until_marker("Serial update complete", timeout=600)


def main():
    parser = argparse.ArgumentParser(description="Update SD cards via serial")
    parser.add_argument("--port", default="/dev/ttyUSB2")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    board = SerialClient(args.port, args.baud)
    try:
        print(f"Connecting to {args.port} @ {args.baud}...")
        board.login()
        print("\n=== Logged in ===")

        print("Uploading fix script...")
        board.upload_script(FIX_SCRIPT)
        print("Running fix script (this may take a few minutes)...")
        board.run_script()
        print("\n=== Done ===")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        board.close()


if __name__ == "__main__":
    main()
