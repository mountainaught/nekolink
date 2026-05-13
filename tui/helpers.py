import os
import asyncio
from datetime import datetime
from rich.console import Console

con = Console()

LOGO = (
    r"[bold cyan]             _         _ _       _    [/bold cyan]" "\n"
    r"[bold cyan]            | |       | (_)     | |   [/bold cyan]" "\n"
    r"[bold cyan]  _ __   ___| | _____ | |_ _ __ | | __[/bold cyan]" "\n"
    r"[bold cyan] | '_ \ / _ \ |/ / _ \| | | '_ \| |/ /[/bold cyan]" "\n"
    r"[bold cyan] | | | |  __/   < (_) | | | | | |   < [/bold cyan]" "\n"
    r"[bold cyan] |_| |_|\___|_|\_\___/|_|_|_| |_|_|\_\ [/bold cyan]"
)

VERSION = "1.0.0"


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def check_i2c():
    try:
        if os.path.exists("/dev/i2c-1"):
            return True, "PCA9685 detected @ 0x40"
        return False, "/dev/i2c-1 not found"
    except Exception as e:
        return False, str(e)


def check_bluetooth():
    try:
        r = os.popen("hciconfig 2>/dev/null").read()
        if "UP RUNNING" in r:
            return True, "hci0 UP RUNNING"
        return False, "adapter down or missing"
    except Exception:
        return False, "hciconfig unavailable"


async def restart_bluetooth(password: str):
    try:
        proc = await asyncio.create_subprocess_exec(
            "sudo", "-S", "systemctl", "restart", "bluetooth",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(input=f"{password}\n".encode())
        if proc.returncode == 0:
            await asyncio.sleep(2)
            return True, "bluetooth service restarted"
        else:
            return False, stderr.decode().strip() or "unknown error"
    except Exception as e:
        return False, str(e)


def make_bar(val, max_val=1.0, width=30):
    ratio = min(max(val / max_val if max_val else 0, 0.0), 1.0)
    filled = int(ratio * width)
    if ratio < 0.3:
        c = "green"
    elif ratio < 0.7:
        c = "yellow"
    else:
        c = "red"
    return f"[{c}]{'█' * filled}{'░' * (width - filled)}[/{c}] {ratio * 100:5.1f}%"


def waveform_bar(val, width=36):
    mid = width // 2
    pos = int((val + 1.0) / 2.0 * width)
    pos = max(0, min(width - 1, pos))
    chars = list("─" * width)
    chars[mid] = "┼"
    if pos < mid:
        for i in range(pos, mid):
            chars[i] = "█"
    elif pos > mid:
        for i in range(mid + 1, pos + 1):
            chars[i] = "█"
    chars[pos] = "◆"
    return "".join(chars)