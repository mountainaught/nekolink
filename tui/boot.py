"""
Screen 1 — NASA-log-style boot sequence.
Runs real hardware checks, offers retry on failure.
"""

import asyncio
import random

from textual import on, work
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import RichLog, Label
from textual.reactive import reactive

from .helpers import (
    ts, LOGO, VERSION, BOOT_MODULES,
    get_system_ident, fake_hex_line,
    check_i2c, check_bluetooth,
)


class BootScreen(Screen):

    BINDINGS = [
        Binding("enter", "proceed", "Continue", show=False),
    ]

    boot_done: reactive[bool] = reactive(False)

    def compose(self):
        yield RichLog(id="boot-log", markup=True, highlight=True, auto_scroll=True)
        yield Label("[blink]▸ PRESS ENTER TO CONTINUE ◂[/blink]", id="boot-prompt")

    def on_mount(self):
        self.run_boot()

    def action_proceed(self):
        if self.boot_done:
            self.app.goto_menu()

    def watch_boot_done(self, done: bool):
        if done:
            self.query_one("#boot-prompt").styles.display = "block"

    # ── boot sequence ──

    @work(exclusive=True)
    async def run_boot(self):
        log = self.query_one("#boot-log", RichLog)
        w = log.write

        await asyncio.sleep(0.3)

        # logo
        for line in LOGO.strip().split("\n"):
            w(line)
            await asyncio.sleep(0.04)

        w("[green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/green]")
        w(f"[dim green] emotion-driven kinetic interface v{VERSION}[/dim green]")
        w("[green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/green]")
        w("")
        await asyncio.sleep(0.5)

        # system ident
        w(f"[green][{ts()}] SYSTEM IDENTIFICATION[/green]")
        for k, v in get_system_ident().items():
            await asyncio.sleep(0.07)
            w(f"[dim green]  {k}: {v}[/dim green]")
        w("")
        await asyncio.sleep(0.3)

        # module loading
        w(f"[green][{ts()}] LOADING CORE MODULES[/green]")
        for mod in BOOT_MODULES:
            dots = "·" * (42 - len(mod))
            w(f"[green]  {mod} {dots} [bold green]OK[/bold green][/green]")
            await asyncio.sleep(random.uniform(0.04, 0.12))
        w("")
        await asyncio.sleep(0.25)

        # memory flavor
        w(f"[green][{ts()}] MEMORY ALLOCATION[/green]")
        for _ in range(4):
            addr = random.randint(0x7F000000, 0x7FFFFFFF)
            size = random.choice([64, 128, 256, 512])
            w(f"[dim green]  0x{addr:08X}  alloc {size}KB[/dim green]")
            await asyncio.sleep(0.04)
        w(f"[green]  heap integrity ···················· [bold green]PASS[/bold green][/green]")
        w("")
        await asyncio.sleep(0.3)

        # entropy flavor
        w(f"[green][{ts()}] SEEDING ENTROPY POOL[/green]")
        w(f"[dim green]  {fake_hex_line()}[/dim green]")
        w(f"[dim green]  {fake_hex_line()}[/dim green]")
        w(f"[green]  pool ready ························ [bold green]OK[/bold green][/green]")
        w("")
        await asyncio.sleep(0.35)

        # real hardware checks
        await self._hw_preflight(w)

        # done
        w("")
        w(f"[green][{ts()}] BOOT SEQUENCE COMPLETE[/green]")
        w("")
        self.boot_done = True

    async def _hw_preflight(self, w):
        w(f"[green][{ts()}] HARDWARE PREFLIGHT[/green]")

        # I2C check
        i2c_ok, i2c_msg = check_i2c()
        self.app.i2c_ok = i2c_ok
        if i2c_ok:
            w(f"[green]  I2C bus ·························· [bold green]{i2c_msg}[/bold green][/green]")
        else:
            w(f"[red]  I2C bus ·························· [bold red]FAIL[/bold red][/red]")
            w(f"[dim red]    {i2c_msg}[/dim red]")

        await asyncio.sleep(0.2)

        # Bluetooth check
        bt_ok, bt_msg = check_bluetooth()
        self.app.bt_ok = bt_ok
        if bt_ok:
            w(f"[green]  Bluetooth ························ [bold green]{bt_msg}[/bold green][/green]")
        else:
            w(f"[red]  Bluetooth ························ [bold red]FAIL[/bold red][/red]")
            w(f"[dim red]    {bt_msg}[/dim red]")

        await asyncio.sleep(0.2)

        # retry if either failed
        if not i2c_ok or not bt_ok:
            w("")
            w(f"[yellow]  ⚠ {self._fail_summary(i2c_ok, bt_ok)}[/yellow]")
            w(f"[yellow]  hardware issues won't block boot but will affect initialization.[/yellow]")

    @staticmethod
    def _fail_summary(i2c_ok, bt_ok):
        fails = []
        if not i2c_ok:
            fails.append("I2C")
        if not bt_ok:
            fails.append("Bluetooth")
        return f"{' and '.join(fails)} unavailable."