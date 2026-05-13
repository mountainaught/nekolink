import glob
import os
import platform
import random
import time

from .helpers import con, LOGO, VERSION, ts, check_i2c, check_bluetooth


def boot_sequence():
    con.clear()
    con.print(LOGO)
    con.print("[green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/green]")
    con.print(f"[dim green] emotion-driven kinetic interface v{VERSION}[/dim green]")
    con.print("[green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/green]\n")
    time.sleep(0.5)

    # system ident
    con.print(f"[green][{ts()}] SYSTEM IDENTIFICATION[/green]")
    for k, v in {
        "HOST": platform.node(),
        "ARCH": platform.machine(),
        "KERN": platform.release(),
        "PYRT": platform.python_version(),
        "PID": str(os.getpid()),
    }.items():
        con.print(f"[dim green]  {k:5s}: {v}[/dim green]")
        time.sleep(0.07)
    con.print()
    time.sleep(0.3)

    # modules
    con.print(f"[green][{ts()}] LOADING CORE MODULES[/green]")
    for mod in [
        "emotionengine.core", "emotionengine.bvp_processor",
        "emotionengine.acc_processor", "emotionengine.vital_signs",
        "emotionengine.msptd_fast", "subsystems.tail_driver",
        "subsystems.e4_biometric", "subsystems.py_e4lib.client",
    ]:
        dots = "·" * (42 - len(mod))
        con.print(f"[green]  {mod} {dots} [bold green]OK[/bold green][/green]")
        time.sleep(random.uniform(0.04, 0.12))
    con.print()
    time.sleep(0.3)

    # hardware preflight
    con.print(f"[green][{ts()}] HARDWARE PREFLIGHT[/green]")

    i2c_ok, i2c_msg = check_i2c()
    if i2c_ok:
        con.print(f"[green]  I2C bus ·························· [bold green]{i2c_msg}[/bold green][/green]")
    else:
        con.print(f"[red]  I2C bus ·························· [bold red]FAIL: {i2c_msg}[/bold red][/red]")
    time.sleep(0.2)

    bt_ok, bt_msg = check_bluetooth()
    if bt_ok:
        con.print(f"[green]  Bluetooth ························ [bold green]{bt_msg}[/bold green][/green]")
    else:
        con.print(f"[red]  Bluetooth ························ [bold red]FAIL: {bt_msg}[/bold red][/red]")
    time.sleep(0.2)

    con.print()
    con.print(f"[green][{ts()}] BOOT SEQUENCE COMPLETE[/green]")
    time.sleep(0.5)

    # code flash
    con.print(f"\n[green][{ts()}] COMPILING RUNTIME ENVIRONMENT[/green]")
    time.sleep(0.3)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    py_files = sorted(glob.glob(os.path.join(project_root, "**/*.py"), recursive=True))

    for filepath in py_files:
        relpath = os.path.relpath(filepath, project_root)
        con.print(f"[green]  ── {relpath} ──[/green]")
        time.sleep(0.05)

        try:
            with open(filepath, "r") as f:
                lines = f.readlines()
        except Exception:
            continue

        step = max(1, len(lines) // 20)
        for i in range(0, len(lines), step):
            line = lines[i].rstrip()
            if not line:
                continue
            line = line.replace("[", "\\[")
            con.print(f"[dim green]{line}[/dim green]")
            time.sleep(0.008)

    con.print(f"\n[green][{ts()}] COMPILED {len(py_files)} MODULES[/green]")
    time.sleep(0.3)
    con.print(f"[green][{ts()}] LINKING...[/green]")
    time.sleep(0.2)
    con.print(f"[green][{ts()}] [bold green]READY[/bold green][/green]")
    time.sleep(0.5)

    return i2c_ok, bt_ok