"""
Screen 3 — Live NekoLink runtime.
Displays all sensor data, tail position, stress gauges.
Pause/resume, back to menu, exit.
"""

import asyncio
import time

from textual import on, work
from textual.binding import Binding
from textual.screen import Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Label, Rule, Static

from .helpers import make_bar


class RunScreen(Screen):

    BINDINGS = [
        Binding("space", "toggle_pause", "Pause/Resume", show=True),
        Binding("escape", "back", "Back to Menu", show=True),
    ]

    def __init__(self):
        super().__init__()
        self._t_start = None
        self._running = True
        self._paused = False

    def compose(self):
        yield Label(
            "[bold cyan]▸ NEKOLINK ACTIVE[/bold cyan]",
            id="run-header",
        )
        yield Rule()

        with Container(id="run-container"):
            # row 1: stress + tail
            with Static(classes="stat-box"):
                yield Label("[bold green]── STRESS ──[/bold green]")
                yield Label("", id="lbl-stress-bar")
                yield Label("", id="lbl-stress-components")

            with Static(classes="stat-box"):
                yield Label("[bold green]── TAIL ──[/bold green]")
                yield Label("", id="lbl-tail-pos")
                yield Label("", id="lbl-tail-servos")

            # row 2: biometrics + motion
            with Static(classes="stat-box"):
                yield Label("[bold green]── BIOMETRICS ──[/bold green]")
                yield Label("", id="lbl-hr")
                yield Label("", id="lbl-hrv")
                yield Label("", id="lbl-eda")
                yield Label("", id="lbl-bvp")

            with Static(classes="stat-box"):
                yield Label("[bold green]── MOTION ──[/bold green]")
                yield Label("", id="lbl-moving")
                yield Label("", id="lbl-acc-var")
                yield Label("", id="lbl-calibration")

            # row 3: waveform + runtime info
            with Static(classes="stat-box"):
                yield Label("[bold green]── WAVEFORM ──[/bold green]")
                yield Label("", id="lbl-waveform")
                yield Label("", id="lbl-map-val")

            with Static(classes="stat-box"):
                yield Label("[bold green]── RUNTIME ──[/bold green]")
                yield Label("", id="lbl-uptime")
                yield Label("", id="lbl-loop-status")
                yield Label("", id="lbl-paused")

        yield Rule()

        with Horizontal(id="run-controls"):
            yield Button("⏸ Pause", id="btn-pause", variant="warning")
            yield Button("◂ Menu", id="btn-menu")
            yield Button("✕ Exit", id="btn-exit", variant="error")

    def on_mount(self):
        self._t_start = time.monotonic()
        self.app.neko_running = True
        self.app.neko_paused = False
        self._start_loops()

    def on_unmount(self):
        self._running = False
        self.app.neko_running = False

    # ── controls ──

    def action_toggle_pause(self):
        self._paused = not self._paused
        self.app.neko_paused = self._paused
        btn = self.query_one("#btn-pause", Button)
        btn.label = "▶ Resume" if self._paused else "⏸ Pause"
        self._update_paused_label()

    def action_back(self):
        self._running = False
        self.app.neko_running = False
        self._cleanup()
        self.app.goto_menu()

    @on(Button.Pressed, "#btn-pause")
    def on_pause(self):
        self.action_toggle_pause()

    @on(Button.Pressed, "#btn-menu")
    def on_menu(self):
        self.action_back()

    @on(Button.Pressed, "#btn-exit")
    def on_exit(self):
        self._running = False
        self._cleanup()
        self.app.exit()

    # ── cleanup ──

    def _cleanup(self):
        tail = self.app.tail
        e4 = self.app.e4
        if tail and tail.initialized:
            tail.cleanup()
        if e4 and e4.connected:
            # fire and forget — we're leaving
            asyncio.create_task(e4.end())

    # ── main loops ──

    @work(exclusive=True)
    async def _start_loops(self):
        # start E4 streaming if not already
        if self.app.e4 and self.app.e4.connected:
            try:
                await self.app.e4.start()
            except RuntimeError:
                pass  # already streaming

        # run all loops concurrently
        await asyncio.gather(
            self._stress_loop(),
            self._tail_loop(),
            self._display_loop(),
        )

    async def _stress_loop(self):
        ee = self.app.ee
        while self._running:
            if not self._paused:
                ee.update_stress()
            await asyncio.sleep(0.250)

    async def _tail_loop(self):
        ee = self.app.ee
        tail = self.app.tail
        while self._running:
            if not self._paused and tail.initialized:
                dt = time.monotonic() - self._t_start
                x = ee.map(dt)
                tail.move_to(x, 0)
            await asyncio.sleep(0.100)

    async def _display_loop(self):
        """Update all labels at ~10hz."""
        while self._running:
            self._refresh_display()
            await asyncio.sleep(0.100)

    # ── display refresh ──

    def _refresh_display(self):
        ee = self.app.ee
        tail = self.app.tail

        if not ee:
            return

        # stress
        stress = ee.stress
        self._set("lbl-stress-bar", f"  combined: {make_bar(stress, 1.0)}")
        self._set("lbl-stress-components",
            f"  [dim green]eda: {ee.eda_stress:.3f}  "
            f"bvp: {ee.bvp_stress:.3f}  "
            f"hr: {ee.hr_stress:.3f}  "
            f"hrv: {ee.hrv_stress:.3f}[/dim green]"
        )

        # tail
        if tail.initialized:
            x, y = tail.where()
            self._set("lbl-tail-pos", f"  position: ({x:+.3f}, {y:+.3f})")
            angles = tail.servo_angles
            self._set("lbl-tail-servos",
                f"  [dim green]B:{angles.get('blue', 0):6.1f}° "
                f"R:{angles.get('red', 0):6.1f}° "
                f"Y:{angles.get('yellow', 0):6.1f}°[/dim green]"
            )
        else:
            self._set("lbl-tail-pos", "  [dim red]not initialized[/dim red]")
            self._set("lbl-tail-servos", "")

        # biometrics
        hr = ee.current_hr
        hrv = ee.current_hrv
        self._set("lbl-hr", f"  ♥ HR:  {hr:.0f} bpm" if hr else "  ♥ HR:  [dim]waiting...[/dim]")
        self._set("lbl-hrv", f"  ↕ HRV: {hrv:.1f} ms" if hrv else "  ↕ HRV: [dim]waiting...[/dim]")
        self._set("lbl-eda", f"  ⚡ EDA stress: {ee.eda_stress:.3f}")
        self._set("lbl-bvp", f"  〜 BVP stress: {ee.bvp_stress:.3f}")

        # motion
        moving = ee.is_moving
        indicator = "[bold yellow]● MOVING[/bold yellow]" if moving else "[dim green]○ still[/dim green]"
        self._set("lbl-moving", f"  status: {indicator}")
        self._set("lbl-acc-var", f"  variance: {ee.acc_variance:.6f}")
        cal = "✓ calibrated" if ee.is_calibrated else "✗ uncalibrated"
        self._set("lbl-calibration", f"  engine: [green]{cal}[/green]")

        # waveform
        dt = time.monotonic() - self._t_start
        map_val = ee.map(dt)
        bar = self._waveform_bar(map_val)
        self._set("lbl-waveform", f"  {bar}")
        self._set("lbl-map-val", f"  [dim green]map(t) = {map_val:+.4f}[/dim green]")

        # runtime
        elapsed = time.monotonic() - self._t_start
        mins, secs = divmod(int(elapsed), 60)
        hrs, mins = divmod(mins, 60)
        self._set("lbl-uptime", f"  uptime: {hrs:02d}:{mins:02d}:{secs:02d}")
        self._set("lbl-loop-status",
            f"  [dim green]stress @ 4hz | tail @ 10hz | display @ 10hz[/dim green]"
        )
        self._update_paused_label()

    def _update_paused_label(self):
        if self._paused:
            self._set("lbl-paused", "  [bold yellow]⏸ PAUSED[/bold yellow]")
        else:
            self._set("lbl-paused", "  [green]▶ running[/green]")

    # ── helpers ──

    def _set(self, label_id: str, text: str):
        try:
            self.query_one(f"#{label_id}", Label).update(text)
        except Exception:
            pass

    @staticmethod
    def _waveform_bar(val: float, width: int = 40) -> str:
        """
        Renders a center-origin waveform bar.
        val in -1.0 to 1.0, center of bar = 0.
        """
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

        marker = "◆"
        chars[pos] = marker

        bar_str = "".join(chars)
        return f"[green]{bar_str}[/green]"