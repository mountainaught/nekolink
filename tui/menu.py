import argparse
import asyncio
import time

from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.live import Live

from .helpers import (
    con, LOGO, ts,
    check_i2c, check_bluetooth, restart_bluetooth, make_bar,
)
from .boot import boot_sequence
from .run import run_loop
from .calibration import tail_calibration


def show_menu(state):
    con.clear()
    con.print(LOGO)
    con.print()

    t = "[green]✓[/green]" if state["tail"] else "[red]✗[/red]"
    e = "[green]✓[/green]" if state["ee"] else "[red]✗[/red]"
    c = "[green]✓[/green]" if state["e4"] else "[red]✗[/red]"
    tc = "[green]✓[/green]" if state["tail_cal"] else "[red]✗[/red]"
    ec = "[green]✓[/green]" if state["ee_cal"] else "[red]✗[/red]"
    con.print(f"  TAIL [{t}]  ENGINE [{e}]  E4 [{c}]  TAIL CAL [{tc}]  EE CAL [{ec}]\n")

    options = {
        "1": "Initialize Tail" + (" [dim](done)[/dim]" if state["tail"] else ""),
        "2": "Initialize Emotion Engine" + (" [dim](done)[/dim]" if state["ee"] else ""),
        "3": "Connect E4" + (" [dim](done)[/dim]" if state["e4"] else ""),
        "4": "Initialize All",
        "5": "Calibrate Tail" + (" [dim](done)[/dim]" if state["tail_cal"] else ""),
        "6": "Calibrate E4 + Emotion Engine" + (" [dim](done)[/dim]" if state["ee_cal"] else ""),
        "7": "▸ Run NekoLink",
        "8": "Exit",
    }

    for k, v in options.items():
        con.print(f"  [green][{k}][/green] {v}")

    con.print()
    return Prompt.ask("[green]select[/green]", choices=list(options.keys()))


async def menu_loop():
    parser = argparse.ArgumentParser(description="NekoLink — emotion-driven kinetic interface")
    parser.add_argument("--skip-intro", action="store_true", help="skip boot sequence")
    args = parser.parse_args()

    from emotionengine import EmotionEngine
    from subsystems.TailController import TailController
    from subsystems.E4Controller import E4Controller

    if args.skip_intro:
        i2c_ok, _ = check_i2c()
        bt_ok, _ = check_bluetooth()
        con.print("[dim green]boot skipped[/dim green]\n")
    else:
        i2c_ok, bt_ok = boot_sequence()

    tail = TailController(0, 2, 4)
    ee = None
    e4 = None
    e4_fails = 0

    state = {"tail": False, "ee": False, "e4": False, "tail_cal": False, "ee_cal": False}

    while True:
        choice = show_menu(state)

        if choice == "1" and not state["tail"]:
            if not i2c_ok:
                con.print("[red]I2C unavailable[/red]")
                time.sleep(0.5)
                continue
            con.print("[green]initializing tail...[/green]")
            ok, msg = tail.initialize()
            state["tail"] = ok
            con.print(f"[green]{msg}[/green]" if ok else f"[red]{msg}[/red]")
            time.sleep(0.5)

        elif choice == "2" and not state["ee"]:
            con.print("[green]creating emotion engine...[/green]")
            ee = EmotionEngine()
            state["ee"] = True
            con.print("[green]emotion engine ready[/green]")
            time.sleep(0.5)

        elif choice == "3" and not state["e4"]:
            if not state["ee"]:
                con.print("[red]initialize emotion engine first[/red]")
                time.sleep(0.5)
                continue
            if not bt_ok:
                if Confirm.ask("[yellow]bluetooth unavailable. restart bluetooth service?[/yellow]"):
                    passwd = Prompt.ask("[yellow]sudo password[/yellow]", password=True)
                    ok, msg = await restart_bluetooth(passwd)
                    if ok:
                        con.print(f"[green]{msg}[/green]")
                        bt_ok, _ = check_bluetooth()
                    else:
                        con.print(f"[red]{msg}[/red]")
                time.sleep(0.5)
                continue

            con.print("[green]scanning for E4...[/green]")
            e4 = E4Controller()
            ok = await e4.connect(ee.bvp_parser(), ee.eda_parser(), ee.acc_parser())
            if ok:
                state["e4"] = True
                e4_fails = 0
                con.print("[bold green]E4 connected[/bold green]")
            else:
                e4_fails += 1
                con.print(f"[red]connection failed (attempt {e4_fails})[/red]")
                if e4_fails >= 3:
                    if Confirm.ask("[yellow]3+ failures. restart bluetooth?[/yellow]"):
                        passwd = Prompt.ask("[yellow]sudo password[/yellow]", password=True)
                        ok, msg = await restart_bluetooth(passwd)
                        if ok:
                            con.print(f"[green]{msg}[/green]")
                            bt_ok, _ = check_bluetooth()
                            e4_fails = 0
                        else:
                            con.print(f"[red]{msg}[/red]")
            time.sleep(0.5)

        elif choice == "4":
            if not state["tail"] and i2c_ok:
                con.print("[green]initializing tail...[/green]")
                ok, msg = tail.initialize()
                state["tail"] = ok
                con.print(f"[green]  {msg}[/green]" if ok else f"[red]  {msg}[/red]")

            if not state["ee"]:
                con.print("[green]creating emotion engine...[/green]")
                ee = EmotionEngine()
                state["ee"] = True
                con.print("[green]  emotion engine ready[/green]")

            if not state["e4"] and state["ee"] and bt_ok:
                con.print("[green]scanning for E4...[/green]")
                e4 = E4Controller()
                ok = await e4.connect(ee.bvp_parser(), ee.eda_parser(), ee.acc_parser())
                if ok:
                    state["e4"] = True
                    e4_fails = 0
                    con.print("[bold green]  E4 connected[/bold green]")
                else:
                    e4_fails += 1
                    con.print(f"[red]  E4 failed (attempt {e4_fails})[/red]")
                    if e4_fails >= 3:
                        con.print("[yellow]  consider restarting bluetooth[/yellow]")

            if all(state.values()):
                con.print("\n[bold green]all systems initialized[/bold green]")
            else:
                skipped = [k for k, v in state.items() if not v]
                con.print(f"\n[yellow]skipped: {', '.join(skipped)}[/yellow]")
            time.sleep(0.5)

        elif choice == "5" and not state["tail_cal"]:
            if not state["tail"]:
                con.print("[red]initialize tail first[/red]")
                time.sleep(0.5)
                continue

            if tail_calibration(tail):
                state["tail_cal"] = True
                con.print("[bold green]tail calibration saved[/bold green]")
            else:
                con.print("[yellow]tail calibration cancelled[/yellow]")
            time.sleep(0.5)

        elif choice == "6" and not state["ee_cal"]:
            if not state["ee"] or not state["e4"]:
                con.print("[red]initialize emotion engine and connect E4 first[/red]")
                time.sleep(0.5)
                continue

            con.print("[green]starting E4 stream...[/green]")
            await e4.start()

            con.print("[yellow]beginning 60s emotion calibration[/yellow]")
            con.print("[dim]remain calm, avoid movement or distressing thoughts[/dim]\n")

            cal_start = time.monotonic()

            async def _cal_display():
                with Live(console=con, refresh_per_second=4) as live:
                    while not ee.is_calibrated:
                        elapsed = time.monotonic() - cal_start
                        remaining = max(0, 60 - elapsed)

                        hr = ee.current_hr
                        hrv = ee.current_hrv
                        eda = ee.current_eda

                        text = (
                            f"[green]calibrating... {remaining:4.1f}s remaining[/green]\n"
                            f"[green]{make_bar(elapsed, 60.0)}[/green]\n\n"
                            f"[dim green]♥ HR:  {f'{hr:.0f} bpm' if hr else 'waiting...'}[/dim green]\n"
                            f"[dim green]↕ HRV: {f'{hrv:.1f} ms' if hrv else 'waiting...'}[/dim green]\n"
                            f"[dim green]⚡ EDA: {f'{eda:.2f} μS' if eda else 'waiting...'}[/dim green]\n"
                            f"[dim green]● ACC: {'moving' if ee.is_moving else 'still'}"
                            f" (var: {ee.acc_variance:.6f})[/dim green]\n"
                        )
                        live.update(
                            Panel(text, title="[green]calibration[/green]", border_style="green")
                        )
                        await asyncio.sleep(0.250)

            await asyncio.gather(
                ee.calibrate(),
                _cal_display(),
            )

            state["ee_cal"] = True
            con.print("[bold green]calibration complete[/bold green]")
            time.sleep(0.5)

        elif choice == "7":
            if not all(state.values()):
                missing = [k for k, v in state.items() if not v]
                con.print(f"[red]not ready — missing: {', '.join(missing)}[/red]")
                time.sleep(0.5)
                continue

            con.print("\n[bold green]▸ launching nekolink...[/bold green]")
            time.sleep(0.5)
            await run_loop(ee, tail, e4)
            state["e4"] = False
            state["ee_cal"] = False

        elif choice == "8":
            con.print("[green]goodbye~ nyaa[/green]")
            break