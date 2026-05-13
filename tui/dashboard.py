import time

from rich.panel import Panel
from rich.layout import Layout

from .helpers import make_bar, waveform_bar


def build_dashboard(ee, tail, t_start):
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    # header
    layout["header"].update(
        Panel("[bold cyan]▸ NEKOLINK ACTIVE[/bold cyan]", style="green")
    )

    # stress + biometrics
    hr = ee.current_hr
    hrv = ee.current_hrv
    eda = ee.current_eda
    stress_text = (
        f"combined: {make_bar(ee.stress)}\n"
        f"[dim]eda: {ee.eda_stress:.3f}  bvp: {ee.bvp_stress:.3f}  "
        f"hr: {ee.hr_stress:.3f}  hrv: {ee.hrv_stress:.3f}[/dim]\n\n"
        f"♥ HR:  {f'{hr:.0f} bpm' if hr else 'waiting...'}\n"
        f"↕ HRV: {f'{hrv:.1f} ms' if hrv else 'waiting...'}\n"
        f"⚡ EDA: {f'{eda:.2f} μS' if eda else 'waiting...'} (stress: {ee.eda_stress:.3f})\n\n"
    )
    moving = "[bold yellow]● MOVING[/bold yellow]" if ee.is_moving else "[dim]○ still[/dim]"
    stress_text += f"{moving}  var: {ee.acc_variance:.6f}"
    layout["left"].update(
        Panel(stress_text, title="[green]stress & bio[/green]", border_style="green")
    )

    # tail + runtime
    dt = time.monotonic() - t_start
    map_val = ee.map(dt)

    if tail.initialized:
        x, y = tail.where()
        tail_text = f"position: ({x:+.3f}, {y:+.3f})\n"
    else:
        tail_text = "position: [dim]not initialized[/dim]\n"

    tail_text += f"map(t):   {map_val:+.4f}\n"
    tail_text += f"waveform: {waveform_bar(map_val)}\n"

    elapsed = int(dt)
    m, s = divmod(elapsed, 60)
    h, m = divmod(m, 60)
    tail_text += f"\nuptime: {h:02d}:{m:02d}:{s:02d}"

    layout["right"].update(
        Panel(tail_text, title="[green]tail & runtime[/green]", border_style="green")
    )

    # footer
    layout["footer"].update(
        Panel("[dim]ctrl+c to stop and return to menu[/dim]", style="green")
    )

    return layout