"""
Screen 2 — Main menu. Manual init, parameters, launch.
"""

import asyncio

from textual import on, work
from textual.screen import Screen
from textual.containers import Container, Vertical
from textual.widgets import Button, Label, RichLog, Rule

from .helpers import ts, LOGO

from emotionengine import EmotionEngine
from subsystems.E4Controller import E4Controller


class MenuScreen(Screen):

    def compose(self):
        with Container(id="menu-container"):
            yield Label(LOGO)
            yield Rule()

            # status bar
            yield Label("", id="menu-status")

            # init section
            yield Label("[bold green]── INITIALIZATION ──[/bold green]", classes="menu-section")
            yield Button("Initialize Tail (I2C/PCA9685)", id="btn-init-tail", classes="menu-btn")
            yield Button("Initialize Emotion Engine", id="btn-init-ee", classes="menu-btn")
            yield Button("Connect E4 Wristband (BLE)", id="btn-init-e4", classes="menu-btn")
            yield Button("Initialize All", id="btn-init-all", classes="menu-btn", variant="success")

            yield Rule()

            # actions
            yield Label("[bold green]── ACTIONS ──[/bold green]", classes="menu-section")
            yield Button("▸ Run NekoLink", id="btn-run", classes="menu-btn", variant="success")
            yield Button("Device Stats", id="btn-stats", classes="menu-btn")
            yield Button("Exit", id="btn-exit", classes="menu-btn", variant="error")

            yield Rule()

            # log output for init feedback
            yield RichLog(id="menu-log", markup=True, auto_scroll=True)

    def on_mount(self):
        self._refresh_buttons()
        self._update_status()

    # ── status ──

    def _update_status(self):
        tail = "✓" if self.app.tail_inited else "✗"
        ee = "✓" if self.app.ee_inited else "✗"
        e4 = "✓" if self.app.e4_inited else "✗"

        status = f"[green]TAIL [{tail}]  EE [{ee}]  E4 [{e4}][/green]"
        self.query_one("#menu-status", Label).update(status)

    def _refresh_buttons(self):
        self._gray_if_done("btn-init-tail", self.app.tail_inited)
        self._gray_if_done("btn-init-ee", self.app.ee_inited)
        self._gray_if_done("btn-init-e4", self.app.e4_inited)
        self._gray_if_done("btn-init-all", self.app.all_inited)

        # e4 depends on ee
        e4_btn = self.query_one("#btn-init-e4", Button)
        if not self.app.ee_inited and not self.app.e4_inited:
            e4_btn.disabled = True
            e4_btn.label = "Connect E4 (needs Emotion Engine first)"
        elif self.app.e4_inited:
            e4_btn.label = "Connect E4 Wristband (BLE)"

        # i2c / bt warnings
        tail_btn = self.query_one("#btn-init-tail", Button)
        if not self.app.i2c_ok and not self.app.tail_inited:
            tail_btn.disabled = True
            tail_btn.label = "Initialize Tail (I2C unavailable)"

        e4_btn = self.query_one("#btn-init-e4", Button)
        if not self.app.bt_ok and not self.app.e4_inited:
            e4_btn.disabled = True
            e4_btn.label = "Connect E4 (Bluetooth unavailable)"

    def _gray_if_done(self, btn_id, done):
        btn = self.query_one(f"#{btn_id}", Button)
        if done:
            btn.add_class("init-done")
            btn.disabled = True
        else:
            btn.remove_class("init-done")
            btn.disabled = False

    def _log(self, msg):
        self.query_one("#menu-log", RichLog).write(f"[green][{ts()}][/green] {msg}")

    # ── button handlers ──

    @on(Button.Pressed, "#btn-init-tail")
    def on_init_tail(self):
        self._do_init_tail()

    @on(Button.Pressed, "#btn-init-ee")
    def on_init_ee(self):
        self._do_init_ee()

    @on(Button.Pressed, "#btn-init-e4")
    def on_init_e4(self):
        self._do_init_e4()

    @on(Button.Pressed, "#btn-init-all")
    def on_init_all(self):
        self._do_init_all()

    @on(Button.Pressed, "#btn-run")
    def on_run(self):
        self._do_run()

    @on(Button.Pressed, "#btn-stats")
    def on_stats(self):
        self._log("[yellow]stats view not implemented yet[/yellow]")

    @on(Button.Pressed, "#btn-exit")
    def on_exit(self):
        self.app.exit()

    # ── init workers ──

    @work(exclusive=True)
    async def _do_init_tail(self):
        self._log("initializing tail controller...")
        ok, msg = self.app.tail.initialize()
        if ok:
            self.app.tail_inited = True
            self._log(f"[bold green]tail: {msg}[/bold green]")
        else:
            self._log(f"[bold red]tail failed: {msg}[/bold red]")
        self._refresh_buttons()
        self._update_status()

    @work(exclusive=True)
    async def _do_init_ee(self):
        self._log("creating emotion engine...")
        self.app.ee = EmotionEngine()
        self.app.ee_inited = True
        self._log("[bold green]emotion engine ready[/bold green]")
        self._refresh_buttons()
        self._update_status()

    @work(exclusive=True)
    async def _do_init_e4(self):
        if not self.app.ee_inited:
            self._log("[red]emotion engine must be initialized first[/red]")
            return

        self._log("scanning for E4 wristband...")
        self.app.e4 = E4Controller()
        ee = self.app.ee
        ok = await self.app.e4.connect(
            ee.bvp_parser(), ee.eda_parser(), ee.acc_parser()
        )

        if ok:
            self.app.e4_inited = True
            self.app.e4_fail_count = 0
            self._log("[bold green]E4 connected and streams registered[/bold green]")
        else:
            self.app.e4_fail_count += 1
            self._log(f"[bold red]E4 connection failed (attempt {self.app.e4_fail_count})[/bold red]")

            if self.app.e4_fail_count >= 3:
                self._log("[yellow]3+ failures — consider restarting bluetooth[/yellow]")
                self._log("[yellow]run: sudo systemctl restart bluetooth[/yellow]")
                # TODO: add bluetooth restart button/prompt here

        self._refresh_buttons()
        self._update_status()

    @work(exclusive=True)
    async def _do_init_all(self):
        if not self.app.tail_inited:
            await self._do_init_tail.__wrapped__(self)
        if not self.app.ee_inited:
            await self._do_init_ee.__wrapped__(self)
        if not self.app.e4_inited:
            await self._do_init_e4.__wrapped__(self)
        self._log("[green]initialization sequence complete[/green]")

    # ── run ──

    @work(exclusive=True)
    async def _do_run(self):
        if not self.app.all_inited:
            self._log("[yellow]running auto-init first...[/yellow]")
            await self._do_init_all.__wrapped__(self)

        if not self.app.all_inited:
            self._log("[red]init failed, cannot start[/red]")
            return

        if not self.app.ee.is_calibrated:
            self._log("[yellow]starting 60s emotion calibration...[/yellow]")
            self._log("[dim]remain calm, avoid movement or distressing thoughts[/dim]")
            self.app.calibration_start = __import__("time").monotonic()
            await self.app.e4.start()
            await self.app.ee.calibrate()
            self._log("[bold green]calibration complete[/bold green]")

        self._log("[bold green]launching nekolink...[/bold green]")
        await asyncio.sleep(0.5)
        self.app.goto_run()