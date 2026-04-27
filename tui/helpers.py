"""
Shared constants, hardware checks, formatting utils.
"""

import os
import platform
import random
import asyncio
from datetime import datetime


LOGO = (
    "[bold cyan] ╔╗╔┌─┐┬┌─┌─┐┬  ┬┌┐┌┬┌─[/bold cyan]\n"
    "[bold cyan] ║║║├┤ ├┴┐│ ││  ││││├┴┐[/bold cyan]\n"
    "[bold cyan] ╝╚╝└─┘┴ ┴└─┘┴─┘┴┘└┘┴ ┴[/bold cyan]"
)

VERSION = "1.0.0"

BOOT_MODULES = [
    "emotionengine.core",
    "emotionengine.bvp_processor",
    "emotionengine.acc_processor",
    "emotionengine.vital_signs",
    "emotionengine.msptd_fast",
    "subsystems.tail_driver",
    "subsystems.e4_biometric",
    "subsystems.py_e4lib.client",
]


def ts() -> str:
    """Compact timestamp for log lines."""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def check_i2c() -> tuple[bool, str]:
    """Probe for PCA9685 on the I2C bus."""
    try:
        if os.path.exists("/dev/i2c-1"):
            return True, "PCA9685 detected @ 0x40"
        return False, "/dev/i2c-1 not found"
    except Exception as e:
        return False, str(e)


def check_bluetooth() -> tuple[bool, str]:
    """Check if a Bluetooth adapter is up."""
    try:
        r = os.popen("hciconfig 2>/dev/null").read()
        if "UP RUNNING" in r:
            return True, "hci0 UP RUNNING"
        return False, "adapter down or missing"
    except Exception:
        return False, "hciconfig unavailable"


async def restart_bluetooth(password: str) -> tuple[bool, str]:
    """Restart bluetooth service via sudo. Returns (success, message)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "-S", "systemctl", "restart", "bluetooth",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(input=f"{password}\n".encode())
        if proc.returncode == 0:
            # give it a sec to come back up
            await asyncio.sleep(2)
            return True, "bluetooth service restarted"
        else:
            return False, stderr.decode().strip() or "unknown error"
    except Exception as e:
        return False, str(e)


def get_system_ident() -> dict[str, str]:
    """System info dict for boot screen."""
    return {
        "HOST ": platform.node(),
        "ARCH ": platform.machine(),
        "KERN ": platform.release(),
        "PYRT ": platform.python_version(),
        "PID  ": str(os.getpid()),
    }


def fake_hex_line(n: int = 16) -> str:
    """Random hex bytes for boot flavor text."""
    return " ".join(f"{random.randint(0, 255):02x}" for _ in range(n))


def make_bar(val: float, max_val: float, width: int = 30) -> str:
    """ASCII progress bar with color thresholds."""
    ratio = min(max(val / max_val if max_val else 0, 0.0), 1.0)
    filled = int(ratio * width)
    if ratio < 0.3:
        c = "green"
    elif ratio < 0.7:
        c = "yellow"
    else:
        c = "red"
    return f"[{c}]{'█' * filled}{'░' * (width - filled)}[/{c}] {ratio * 100:5.1f}%"