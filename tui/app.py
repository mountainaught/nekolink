"""
Main Textual App — shared state, CSS, screen routing.
"""

import time
from textual.app import App
from textual.binding import Binding

from emotionengine import EmotionEngine
from subsystems.TailController import TailController
from subsystems.E4Controller import E4Controller


class NekoLinkApp(App):

    TITLE = "NekoLink"
    SUB_TITLE = "emotion-driven kinetic interface"

    CSS = """
    Screen {
        background: black;
    }
    
    Rule {
        color: #00ff41;
    }

    /* ── boot screen ── */
    #boot-log {
        background: black;
        color: #00ff41;
        border: heavy #00ff41;
        margin: 1 2;
        scrollbar-color: #00ff41;
        scrollbar-background: #0a0a0a;
    }
    #boot-prompt {
        text-align: center;
        color: #00ff41;
        text-style: bold;
        margin-top: 1;
        display: none;
    }

    /* ── menu screen ── */
    #menu-container {
        align: center middle;
        width: 60;
        height: auto;
        border: heavy #00ff41;
        background: #0a0a0a;
        padding: 1 2;
    }
    #menu-container Label {
        color: #00ff41;
        text-align: center;
        width: 100%;
    }
    .menu-btn {
        width: 100%;
        margin: 0 0 1 0;
    }
    .init-done {
        opacity: 0.3;
    }
    .menu-section {
        margin: 1 0;
    }
    #menu-status {
        color: #00ff41;
        text-align: center;
        width: 100%;
        margin: 1 0;
    }
    #menu-log {
        background: black;
        color: #00ff41;
        border: round #00ff41;
        height: 8;
        margin: 1 0;
    }

    /* ── run screen ── */
    #run-container {
        layout: grid;
        grid-size: 2 3;
        grid-gutter: 1;
        margin: 1 2;
    }
    .stat-box {
        border: round #00ff41;
        background: #0a0a0a;
        padding: 1;
        color: #00ff41;
        height: auto;
    }
    #run-controls {
        dock: bottom;
        height: 3;
        align: center middle;
        background: #0a0a0a;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self):
        super().__init__()

        # devices — tail gets created immediately (no hw hit),
        # ee and e4 created during init
        self.tail = TailController(0, 2, 4)
        self.ee = None
        self.e4 = None

        # init flags
        self.tail_inited = False
        self.ee_inited = False
        self.e4_inited = False

        # hw check results (set by boot screen)
        self.i2c_ok = False
        self.bt_ok = False

        # runtime
        self.neko_running = False
        self.neko_paused = False

        # e4 retry tracking (TUI-side)
        self.e4_fail_count = 0

        # calibration tracking (TUI-side)
        self.calibration_start = None

    @property
    def all_inited(self):
        return self.tail_inited and self.ee_inited and self.e4_inited

    @property
    def calibration_elapsed(self):
        if self.calibration_start is None:
            return 0
        return time.monotonic() - self.calibration_start

    def on_mount(self):
        from .boot import BootScreen
        self.push_screen(BootScreen())

    def goto_menu(self):
        from .menu import MenuScreen
        self.switch_screen(MenuScreen())

    def goto_run(self):
        from .run import RunScreen
        self.switch_screen(RunScreen())