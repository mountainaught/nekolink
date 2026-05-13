import asyncio
import time

from rich.live import Live

from .helpers import con
from .dashboard import build_dashboard


async def run_loop(ee, tail, e4):
    t_start = time.monotonic()

    if not e4.connected:
        await e4.start()

    con.print("[bold green]starting nekolink...[/bold green]")

    try:
        with Live(build_dashboard(ee, tail, t_start), refresh_per_second=10, console=con) as live:
            while True:
                ee.update_stress()
                if tail.initialized:
                    dt = time.monotonic() - t_start
                    x = ee.map(dt)
                    tail.move_to(x, 0)
                live.update(build_dashboard(ee, tail, t_start))
                await asyncio.sleep(0.100)
    except KeyboardInterrupt:
        con.print("\n[yellow]stopping...[/yellow]")
    finally:
        if tail.initialized:
            tail.cleanup()
        if e4.connected:
            await e4.end()