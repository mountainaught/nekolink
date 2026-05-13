# tui/calibration.py

import sys
import tty
import termios

from rich.panel import Panel
from rich.table import Table
from rich.console import Group

from .helpers import con


def _getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _draw(tail, step, selected, current_angles):
    cal = tail.calibration

    table = Table(show_header=True, border_style="green", title="servo positions")
    table.add_column("servo", style="green")
    table.add_column("angle", style="green", justify="right")
    table.add_column("offset", style="dim green", justify="right")
    table.add_column("scale", style="dim green", justify="right")
    table.add_column("", justify="center")

    servos = ["blue", "red", "yellow"]
    for name in servos:
        marker = " ◂" if name == selected else ""
        table.add_row(
            name,
            f"{current_angles[name]:6.1f}°",
            f"{cal['offsets'][name]:+.1f}",
            f"{cal['scales'][name]:.2f}",
            f"[bold green]{marker}[/bold green]",
        )

    x, y = tail.where()
    tip = f"[green]tip position: ({x:+.3f}, {y:+.3f})[/green]\n"

    controls = (
        f"\n[green]step size: {step}°[/green]\n\n"
        "[green]controls:[/green]\n"
        "  [dim green]tab[/dim green]        — select servo\n"
        "  [dim green]← →  (a/d)[/dim green] — adjust angle\n"
        "  [dim green]↑ ↓  (w/s)[/dim green] — adjust step size\n"
        "  [dim green]z[/dim green]           — zero selected servo\n"
        "  [dim green]o[/dim green]           — set current as origin (save offsets)\n"
        "  [dim green]r[/dim green]           — reset all to 0°\n"
        "  [dim green]x[/dim green]           — done\n"
    )

    con.clear()
    con.print(Panel(
        Group(tip, table, controls),
        title="[green]tail calibration[/green]",
        border_style="green",
    ))


def tail_calibration(tail):
    if not tail.initialized:
        con.print("[red]tail not initialized[/red]")
        return False

    servos = ["blue", "red", "yellow"]
    selected = 0
    step = 5.0
    current_angles = {"blue": 0.0, "red": 0.0, "yellow": 0.0}

    tail.move(0, 0, 0)

    _draw(tail, step, servos[selected], current_angles)

    while True:
        key = _getch()
        name = servos[selected]

        if key == '\t':
            selected = (selected + 1) % 3

        elif key == '\x1b[C' or key in ('d', 'D'):
            current_angles[name] = min(180, current_angles[name] + step)

        elif key == '\x1b[D' or key in ('a', 'A'):
            current_angles[name] = max(0, current_angles[name] - step)

        elif key == '\x1b[A' or key in ('w', 'W'):
            step = min(45, step * 2)

        elif key == '\x1b[B' or key in ('s', 'S'):
            step = max(1, step / 2)

        elif key in ('z', 'Z'):
            current_angles[name] = 0.0

        elif key in ('o', 'O'):
            offsets = {k: v for k, v in current_angles.items()}
            tail.calibrate(offsets=offsets)
            current_angles = {"blue": 0.0, "red": 0.0, "yellow": 0.0}

        elif key in ('r', 'R'):
            current_angles = {"blue": 0.0, "red": 0.0, "yellow": 0.0}

        elif key in ('x', 'X'):
            break

        tail.move(
            current_angles["blue"],
            current_angles["red"],
            current_angles["yellow"],
        )

        _draw(tail, step, servos[selected], current_angles)

    tail.move(0, 0, 0)
    return True