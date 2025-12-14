import argparse
import json
import re
import threading
import urllib.request
from typing import Callable, Optional

try:
    from importlib import metadata as importlib_metadata
except ImportError:  # pragma: no cover - Python <3.8 shim
    import importlib_metadata  # type: ignore

from game_state import TICK_MS, GameState

UI_SCALE = 1.2
UPDATE_HINT = ""  # static hint (if desired)
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/brownbat/kingdom-clicker/master/pyproject.toml"
__version__ = "0.1.1a3"


def get_version() -> str:
    """Resolve installed package version; fall back to local constant."""
    try:
        return importlib_metadata.version("kingdom-clicker")
    except Exception:
        return __version__

try:  # UI dependencies are optional for headless simulation
    import tkinter as tk
    from tkinter import filedialog, messagebox
except Exception:  # pragma: no cover - headless fallback
    tk = None
    filedialog = None
    messagebox = None


def scaled(size: int) -> int:
    """Scale font sizes for readability."""
    return max(1, int(round(size * UI_SCALE)))


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.configure(bg="#333")
        label = tk.Label(
            self.tip,
            text=self.text,
            justify="left",
            bg="#333",
            fg="#f1f2f6",
            relief="solid",
            borderwidth=1,
            font=("Helvetica", scaled(10)),
            padx=6,
            pady=3,
        )
        label.pack(ipadx=1)
        self.tip.wm_geometry(f"+{x}+{y}")

    def hide(self, _event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class GameApp:
    def __init__(self, root: "tk.Tk", initial_state: Optional[dict] = None):
        self.root = root
        self.root.title(f"Kingdom Clicker v{get_version()}")
        self.root.geometry("1080x720")
        self.root.configure(bg="#1e272e")
        self._build_menu()
        self.update_label = None

        # core simulation state
        self.state = GameState(initial_state=initial_state or {})

        # --- ui layout ---

        self._build_ui()
        self._render_news()

        # start loop
        self.update_ui()
        self.root.after(TICK_MS, self._loop_tick)
        self._start_update_check()

    def __getattribute__(self, name):
        if name.startswith("action_"):
            state = object.__getattribute__(self, "state")
            return getattr(state, name)
        return object.__getattribute__(self, name)

    def __getattr__(self, name):
        if name != "state" and hasattr(self.state, name):
            return getattr(self.state, name)
        raise AttributeError(f"{type(self).__name__} has no attribute {name}")

    def _bind_action(self, fn: Callable[[], None]):
        def wrapper():
            fn()
            self.update_ui()

        return wrapper

    def _loop_tick(self):
        self.state.game_tick()
        self.update_ui()
        self.root.after(TICK_MS, self._loop_tick)

    def _apply_initial_state(self, state: dict):
        self.state._apply_initial_state(state)

    def _export_state(self) -> dict:
        return self.state._export_state()

    def _load_state_dict(self, state: dict):
        self.state._load_state_dict(state)
        self._render_news()

    # smithy helpers
    def _smithy_pick_target(self, choice: str):
        return self.state._smithy_pick_target(choice)

    def _smithy_craft(self, target: str):
        return self.state._smithy_craft(target)

    # --------- ui ---------
    # tailor helpers
    def _tailor_can_craft(self, target: str) -> bool:
        return self.state._tailor_can_craft(target)

    def _tailor_pick_target(self, choice: str):
        return self.state._tailor_pick_target(choice)

    def _tailor_craft(self, target: str):
        return self.state._tailor_craft(target)

    def _tailor_finish(self, target: str):
        return self.state._tailor_finish(target)

    def _sync_food_total(self):
        return self.state._sync_food_total()

    def _build_ui(self):
        # header
        header = tk.Frame(self.root, bg="#485460", pady=8)
        header.pack(fill="x")
        tk.Label(
            header,
            text="🏰 Kingdom Clicker",
            font=("Helvetica", scaled(20), "bold"),
            bg="#485460",
            fg="#ffd32a",
        ).pack()
        tk.Label(
            header,
            text=f"v{get_version()}",
            font=("Helvetica", scaled(11)),
            bg="#485460",
            fg="#d2dae2",
        ).pack()
        # optional update notice (filled when check completes)
        self.update_label = tk.Label(
            header,
            text=UPDATE_HINT,
            font=("Helvetica", scaled(10)),
            bg="#485460",
            fg="#d2dae2",
        )
        if UPDATE_HINT:
            self.update_label.pack()

        # resource bar
        res_frame = tk.Frame(self.root, bg="#1e272e", pady=10)
        res_frame.pack(fill="x")
        self.res_frame = res_frame

        self.res_labels = {}
        self.res_colors = {
            "Food": "#0be881",
            "Meat": "#ff6b6b",
            "Grain": "#f5cd79",
            "Pelts": "#d2dae2",
            "Wood": "#ffb142",
            "Planks": "#ffa801",
            "Bows": "#ffd86b",
            "Feathers": "#f7f1e3",
            "Skins": "#c9a16b",
            "Arrows": "#dcdde1",
            "Flax": "#55efc4",
            "Linen": "#9aecdb",
            "Clothing": "#95afc0",
            "Cloaks": "#82ccdd",
            "Gambesons": "#aaa69d",
            "QuarrySites": "#ced6e0",
            "MineSites": "#ced6e0",
            "Stone": "#a4b0be",
            "Ore": "#a5b1c2",
            "Ingots": "#ffd32a",
            "Tools": "#d2dae2",
            "Daggers": "#c44569",
            "Swords": "#ff5252",
            "Leather": "#c7a17a",
        }
        self.res_grid = tk.Frame(res_frame, bg="#1e272e")
        self.res_grid.pack(fill="x")
        for i in range(self.resource_grid_cols):
            self.res_grid.columnconfigure(i, weight=1)

        # population as resource-style row
        pop_frame = tk.Frame(self.root, bg="#1e272e")
        pop_frame.pack(fill="x", pady=(0, 6))
        self.pop_label = tk.Label(
            pop_frame,
            text="pop: 0/0",
            font=("Courier", scaled(14), "bold"),
            bg="#1e272e",
            fg="#0be881",
            anchor="w",
        )
        self.pop_label.pack(anchor="w", padx=10)
        self.pop_tooltip = Tooltip(self.pop_label, "")

        # population + forces
        status_frame = tk.Frame(self.root, bg="#1e272e")
        status_frame.pack(fill="x", pady=(0, 5))

        self.force_label = tk.Label(
            status_frame,
            text="",
            font=("Helvetica", scaled(12)),
            bg="#1e272e",
            fg="#ff5e57",
        )
        self.force_label.pack(side="right", padx=10)

        # main content area inside a scrollable canvas
        content_wrap = tk.Frame(self.root, bg="#1e272e")
        content_wrap.pack(fill="both", expand=True, padx=10, pady=5)
        canvas = tk.Canvas(content_wrap, bg="#1e272e", highlightthickness=0)
        scrollbar = tk.Scrollbar(content_wrap, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        content = tk.Frame(canvas, bg="#1e272e")
        content_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def _on_frame_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            needs_scroll = canvas.bbox("all")[3] > canvas.winfo_height()
            scrollbar.pack_forget()
            if needs_scroll:
                scrollbar.pack(side="right", fill="y")

        def _on_canvas_configure(event):
            canvas.itemconfig(content_id, width=event.width)
            needs_scroll = canvas.bbox("all")[3] > event.height
            scrollbar.pack_forget()
            if needs_scroll:
                scrollbar.pack(side="right", fill="y")

        content.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        # mouse wheel scrolling (Windows/Mac delta; Linux button 4/5)
        def _on_mousewheel(event):
            if canvas.bbox("all")[3] <= canvas.winfo_height():
                return
            if event.num == 4:  # Linux scroll up
                delta = -1
            elif event.num == 5:  # Linux scroll down
                delta = 1
            else:
                delta = -1 * int(event.delta / 120) if event.delta else 0
            if delta:
                canvas.yview_scroll(delta, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

        for i in range(3):
            content.columnconfigure(i, weight=1)

        assign_col = tk.Frame(content, bg="#1e272e")
        assign_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        build_col = tk.Frame(content, bg="#1e272e")
        build_col.grid(row=0, column=1, sticky="nsew", padx=(0, 10))

        news_col = tk.Frame(content, bg="#1e272e")
        news_col.grid(row=0, column=2, sticky="nsew")

        tk.Label(
            assign_col,
            text="Recruit",
            font=("Helvetica", scaled(14), "bold"),
            bg="#1e272e",
            fg="#ffffff",
        ).pack(anchor="w", pady=(0, 4))

        # peasant row (hire/fire)
        peasant_row = tk.Frame(assign_col, bg="#1e272e")
        peasant_row.pack(anchor="w", pady=2, fill="x")
        self.peasant_label = tk.Label(
            peasant_row,
            text="peasant",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.peasant_label.pack(side="left")
        self.btn_peasant_minus = tk.Button(
            peasant_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_fire_peasant),
        )
        self.btn_peasant_minus.pack(side="left", padx=(4, 2))
        self.peasant_value = tk.Label(
            peasant_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.peasant_value.pack(side="left")
        self.btn_peasant_plus = tk.Button(
            peasant_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#706fd3",
            fg="#ffffff",
            command=self._bind_action(self.state.action_recruit_peasant),
        )
        self.btn_peasant_plus.pack(side="left", padx=2)

        # hunter row
        hunter_row = tk.Frame(assign_col, bg="#1e272e")
        self.hunter_row = hunter_row
        self.hunter_label = tk.Label(
            hunter_row,
            text="hunter",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.hunter_label.pack(side="left")
        self.btn_hunter_minus = tk.Button(
            hunter_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_hunter),
        )
        self.btn_hunter_minus.pack(side="left", padx=(4, 2))
        self.hunter_value = tk.Label(
            hunter_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.hunter_value.pack(side="left")
        self.btn_hunter_plus = tk.Button(
            hunter_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#33d9b2",
            fg="#000000",
            command=self._bind_action(self.state.action_add_hunter),
        )
        self.btn_hunter_plus.pack(side="left", padx=2)

        # woodsman row
        woods_row = tk.Frame(assign_col, bg="#1e272e")
        self.woods_row = woods_row
        self.woodsman_label = tk.Label(
            woods_row,
            text="woodsman",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.woodsman_label.pack(side="left")
        self.btn_woodsman_minus = tk.Button(
            woods_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_woodsman),
        )
        self.btn_woodsman_minus.pack(side="left", padx=(4, 2))
        self.woodsman_value = tk.Label(
            woods_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.woodsman_value.pack(side="left")
        self.btn_woodsman_plus = tk.Button(
            woods_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#ffb142",
            fg="#000000",
            command=self._bind_action(self.state.action_add_woodsman),
        )
        self.btn_woodsman_plus.pack(side="left", padx=2)

        # bowyer row (starts locked)
        bowyer_row = tk.Frame(assign_col, bg="#1e272e")
        self.bowyer_row = bowyer_row
        self.bowyer_label = tk.Label(
            bowyer_row,
            text="bowyer",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.bowyer_label.pack(side="left")
        self.btn_bowyer_minus = tk.Button(
            bowyer_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_bowyer),
        )
        self.btn_bowyer_minus.pack(side="left", padx=(4, 2))
        self.bowyer_value = tk.Label(
            bowyer_row,
            text="0/0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.bowyer_value.pack(side="left")
        self.btn_bowyer_plus = tk.Button(
            bowyer_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#eccc68",
            fg="#000000",
            command=self._bind_action(self.state.action_add_bowyer),
        )
        self.btn_bowyer_plus.pack(side="left", padx=2)

        # weaver row (starts locked)
        weaver_row = tk.Frame(assign_col, bg="#1e272e")
        self.weaver_row = weaver_row
        self.weaver_label = tk.Label(
            weaver_row,
            text="weaver",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.weaver_label.pack(side="left")
        self.btn_weaver_minus = tk.Button(
            weaver_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_weaver),
        )
        self.btn_weaver_minus.pack(side="left", padx=(4, 2))
        self.weaver_value = tk.Label(
            weaver_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.weaver_value.pack(side="left")
        self.btn_weaver_plus = tk.Button(
            weaver_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#34ace0",
            fg="#000000",
            command=self._bind_action(self.state.action_add_weaver),
        )
        self.btn_weaver_plus.pack(side="left", padx=2)
        Tooltip(self.btn_weaver_plus, "Cost: 1 peasant. Spins flax into linen.")

        # sawyer row
        sawyer_row = tk.Frame(assign_col, bg="#1e272e")
        self.sawyer_row = sawyer_row
        self.sawyer_label = tk.Label(
            sawyer_row,
            text="sawyer",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.sawyer_label.pack(side="left")
        self.btn_sawyer_minus = tk.Button(
            sawyer_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_sawyer),
        )
        self.btn_sawyer_minus.pack(side="left", padx=(4, 2))
        self.sawyer_value = tk.Label(
            sawyer_row,
            text="0/0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.sawyer_value.pack(side="left")
        self.btn_sawyer_plus = tk.Button(
            sawyer_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#ffa801",
            fg="#000000",
            command=self._bind_action(self.state.action_add_sawyer),
        )
        self.btn_sawyer_plus.pack(side="left", padx=2)
        Tooltip(self.btn_sawyer_plus, "Assigns a peasant as sawyer (2 slots per mill).")

        # farmer row
        farmer_row = tk.Frame(assign_col, bg="#1e272e")
        self.farmer_row = farmer_row
        self.farmer_label = tk.Label(
            farmer_row,
            text="farmer",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.farmer_label.pack(side="left")
        self.btn_farmer_minus = tk.Button(
            farmer_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_farmer),
        )
        self.btn_farmer_minus.pack(side="left", padx=(4, 2))
        self.farmer_value = tk.Label(
            farmer_row,
            text="0/0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.farmer_value.pack(side="left")
        self.btn_farmer_plus = tk.Button(
            farmer_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#f5cd79",
            fg="#000000",
            command=self._bind_action(self.state.action_add_farmer),
        )
        self.btn_farmer_plus.pack(side="left", padx=2)
        Tooltip(self.btn_farmer_plus, "Assigns a peasant as farmer (3 slots per farm).")

        # ranger row (starts locked)
        ranger_row = tk.Frame(assign_col, bg="#1e272e")
        self.ranger_row = ranger_row
        self.ranger_label = tk.Label(
            ranger_row,
            text="ranger",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.ranger_label.pack(side="left")
        self.btn_ranger_minus = tk.Button(
            ranger_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_ranger),
        )
        self.btn_ranger_minus.pack(side="left", padx=(4, 2))
        self.ranger_value = tk.Label(
            ranger_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.ranger_value.pack(side="left")
        self.btn_ranger_plus = tk.Button(
            ranger_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#70a1ff",
            fg="#000000",
            command=self._bind_action(self.state.action_add_ranger),
        )
        self.btn_ranger_plus.pack(side="left", padx=2)
        Tooltip(self.btn_ranger_plus, "Cost: 1 bow, 10 arrows, 1 peasant (idle)")

        # stonemason row
        stonemason_row = tk.Frame(assign_col, bg="#1e272e")
        self.stonemason_row = stonemason_row
        self.stonemason_label = tk.Label(
            stonemason_row,
            text="stonemason",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.stonemason_label.pack(side="left")
        self.btn_stonemason_minus = tk.Button(
            stonemason_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_stonemason),
        )
        self.btn_stonemason_minus.pack(side="left", padx=(4, 2))
        self.stonemason_value = tk.Label(
            stonemason_row,
            text="0/0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.stonemason_value.pack(side="left")
        self.btn_stonemason_plus = tk.Button(
            stonemason_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#d1ccc0",
            fg="#000000",
            command=self._bind_action(self.state.action_add_stonemason),
        )
        self.btn_stonemason_plus.pack(side="left", padx=2)
        Tooltip(self.btn_stonemason_plus, "Assigns a stonemason (quarry slots).")

        # miner row
        miner_row = tk.Frame(assign_col, bg="#1e272e")
        self.miner_row = miner_row
        self.miner_label = tk.Label(
            miner_row,
            text="miner",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.miner_label.pack(side="left")
        self.btn_miner_minus = tk.Button(
            miner_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_miner),
        )
        self.btn_miner_minus.pack(side="left", padx=(4, 2))
        self.miner_value = tk.Label(
            miner_row,
            text="0/0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.miner_value.pack(side="left")
        self.btn_miner_plus = tk.Button(
            miner_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#ced6e0",
            fg="#000000",
            command=self._bind_action(self.state.action_add_miner),
        )
        self.btn_miner_plus.pack(side="left", padx=2)
        Tooltip(self.btn_miner_plus, "Assigns a miner (15 slots per mine).")

        # smelter worker row
        smelter_worker_row = tk.Frame(assign_col, bg="#1e272e")
        self.smelter_worker_row = smelter_worker_row
        self.smelter_worker_label = tk.Label(
            smelter_worker_row,
            text="smelter",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.smelter_worker_label.pack(side="left")
        self.btn_smelter_worker_minus = tk.Button(
            smelter_worker_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_smelter_worker),
        )
        self.btn_smelter_worker_minus.pack(side="left", padx=(4, 2))
        self.smelter_worker_value = tk.Label(
            smelter_worker_row,
            text="0/0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.smelter_worker_value.pack(side="left")
        self.btn_smelter_worker_plus = tk.Button(
            smelter_worker_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#ffd32a",
            fg="#000000",
            command=self._bind_action(self.state.action_add_smelter_worker),
        )
        self.btn_smelter_worker_plus.pack(side="left", padx=2)
        Tooltip(self.btn_smelter_worker_plus, "Assigns a smelter (per furnace).")

        # blacksmith row
        blacksmith_row = tk.Frame(assign_col, bg="#1e272e")
        self.blacksmith_row = blacksmith_row
        self.blacksmith_label = tk.Label(
            blacksmith_row,
            text="blacksmith",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.blacksmith_label.pack(side="left")
        self.btn_blacksmith_minus = tk.Button(
            blacksmith_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_blacksmith),
        )
        self.btn_blacksmith_minus.pack(side="left", padx=(4, 2))
        self.blacksmith_value = tk.Label(
            blacksmith_row,
            text="0/0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.blacksmith_value.pack(side="left")
        self.btn_blacksmith_plus = tk.Button(
            blacksmith_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#ffa502",
            fg="#000000",
            command=self._bind_action(self.state.action_add_blacksmith),
        )
        self.btn_blacksmith_plus.pack(side="left", padx=2)
        Tooltip(self.btn_blacksmith_plus, "Assigns a blacksmith (per smithy).")

        # tailor worker row
        tailor_worker_row = tk.Frame(assign_col, bg="#1e272e")
        self.tailor_worker_row = tailor_worker_row
        self.tailor_worker_label = tk.Label(
            tailor_worker_row,
            text="tailor",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.tailor_worker_label.pack(side="left")
        self.btn_tailor_worker_minus = tk.Button(
            tailor_worker_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_tailor_worker),
        )
        self.btn_tailor_worker_minus.pack(side="left", padx=(4, 2))
        self.tailor_worker_value = tk.Label(
            tailor_worker_row,
            text="0/0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.tailor_worker_value.pack(side="left")
        self.btn_tailor_worker_plus = tk.Button(
            tailor_worker_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#95afc0",
            fg="#000000",
            command=self._bind_action(self.state.action_add_tailor_worker),
        )
        self.btn_tailor_worker_plus.pack(side="left", padx=2)
        Tooltip(self.btn_tailor_worker_plus, "Assigns a tailor (1 slot per workshop).")

        # tanner row
        tanner_row = tk.Frame(assign_col, bg="#1e272e")
        self.tanner_row = tanner_row
        self.tanner_label = tk.Label(
            tanner_row,
            text="tanner",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.tanner_label.pack(side="left")
        self.btn_tanner_minus = tk.Button(
            tanner_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_remove_tanner),
        )
        self.btn_tanner_minus.pack(side="left", padx=(4, 2))
        self.tanner_value = tk.Label(
            tanner_row,
            text="0/0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=5,
            anchor="center",
        )
        self.tanner_value.pack(side="left")
        self.btn_tanner_plus = tk.Button(
            tanner_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#a4b0be",
            fg="#000000",
            command=self._bind_action(self.state.action_add_tanner),
        )
        self.btn_tanner_plus.pack(side="left", padx=2)
        Tooltip(self.btn_tanner_plus, "Assigns a tanner (per tannery).")

        # buildings
        buildings_frame = tk.Frame(build_col, bg="#1e272e")
        buildings_frame.pack(fill="x", pady=(0, 5))

        tk.Label(
            buildings_frame,
            text="Build",
            font=("Helvetica", scaled(14), "bold"),
            bg="#1e272e",
            fg="#ffffff",
        ).pack(anchor="w")

        # house row (no unbuild)
        house_row = tk.Frame(buildings_frame, bg="#1e272e")
        house_row.pack(anchor="w", pady=2, fill="x")
        self.house_label = tk.Label(
            house_row,
            text="house",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.house_label.pack(side="left")
        self.btn_house_minus = tk.Button(
            house_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            state="disabled",
            bg="#84817a",
            fg="#ffffff",
        )
        self.btn_house_minus.pack(side="left", padx=(4, 2))
        self.house_value = tk.Label(
            house_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.house_value.pack(side="left")
        self.btn_house_plus = tk.Button(
            house_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#f7d794",
            fg="#000000",
            command=self._bind_action(self.state.action_build_house),
        )
        self.btn_house_plus.pack(side="left", padx=2)
        Tooltip(self.btn_house_plus, "Cost: 10 planks")

        # lumber mill row
        mill_row = tk.Frame(buildings_frame, bg="#1e272e")
        mill_row.pack(anchor="w", pady=2, fill="x")
        self.mill_label = tk.Label(
            mill_row,
            text="lumber mill",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.mill_label.pack(side="left")
        self.btn_mill_minus = tk.Button(
            mill_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_abandon_lumber_mill),
        )
        self.btn_mill_minus.pack(side="left", padx=(4, 2))
        self.mill_value = tk.Label(
            mill_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.mill_value.pack(side="left")
        self.btn_mill_plus = tk.Button(
            mill_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#2ecc71",
            fg="#000000",
            command=self._bind_action(self.state.action_build_lumber_mill),
        )
        self.btn_mill_plus.pack(side="left", padx=2)
        Tooltip(self.btn_mill_plus, "Cost: 20 wood. Provides 2 sawyer slots.")

        # bowyer shop row
        bowyer_shop_row = tk.Frame(buildings_frame, bg="#1e272e")
        self.bowyer_shop_row = bowyer_shop_row
        self.bowyer_shop_label = tk.Label(
            bowyer_shop_row,
            text="bowyer shop",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.bowyer_shop_label.pack(side="left")
        self.btn_bowyer_shop_minus = tk.Button(
            bowyer_shop_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            state="disabled",
            command=self._bind_action(self.state.action_abandon_bowyer_shop),
        )
        self.btn_bowyer_shop_minus.pack(side="left", padx=(4, 2))
        self.bowyer_shop_value = tk.Label(
            bowyer_shop_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.bowyer_shop_value.pack(side="left")
        self.btn_bowyer_shop_plus = tk.Button(
            bowyer_shop_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#84817a",
            fg="#000000",
            state="disabled",
            command=self._bind_action(self.state.action_build_bowyer_shop),
        )
        self.btn_bowyer_shop_plus.pack(side="left", padx=2)
        Tooltip(self.btn_bowyer_shop_plus, "Cost: 6 planks. Provides 2 bowyer slots.")

        # farm row
        farm_row = tk.Frame(buildings_frame, bg="#1e272e")
        # start hidden; packed when unlocked
        self.farm_row = farm_row
        self.farm_label = tk.Label(
            farm_row,
            text="farm",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.farm_label.pack(side="left")
        self.btn_farm_minus = tk.Button(
            farm_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_abandon_farm),
        )
        self.btn_farm_minus.pack(side="left", padx=(4, 2))
        self.farm_value = tk.Label(
            farm_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.farm_value.pack(side="left")
        self.btn_farm_plus = tk.Button(
            farm_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#f5cd79",
            fg="#000000",
            command=self._bind_action(self.state.action_build_farm),
        )
        self.btn_farm_plus.pack(side="left", padx=2)
        Tooltip(self.btn_farm_plus, "Cost: 8 planks. Provides 3 farmer slots.")

        # quarry row
        quarry_row = tk.Frame(buildings_frame, bg="#1e272e")
        self.quarry_row = quarry_row
        self.quarry_label = tk.Label(
            quarry_row,
            text="quarry",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.quarry_label.pack(side="left")
        self.btn_quarry_minus = tk.Button(
            quarry_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            state="disabled",
        )
        self.btn_quarry_minus.pack(side="left", padx=(4, 2))
        self.quarry_value = tk.Label(
            quarry_row,
            text="0/0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.quarry_value.pack(side="left")
        self.btn_quarry_plus = tk.Button(
            quarry_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#84817a",
            fg="#000000",
            state="disabled",
            command=self._bind_action(self.state.action_build_quarry),
        )
        self.btn_quarry_plus.pack(side="left", padx=2)
        Tooltip(self.btn_quarry_plus, "Cost: 4 planks. Requires quarry site; enables stonemasons.")

        # mine row
        mine_row = tk.Frame(buildings_frame, bg="#1e272e")
        self.mine_row = mine_row
        self.mine_label = tk.Label(
            mine_row,
            text="mine",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.mine_label.pack(side="left")
        self.btn_mine_minus = tk.Button(
            mine_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            state="disabled",
        )
        self.btn_mine_minus.pack(side="left", padx=(4, 2))
        self.mine_value = tk.Label(
            mine_row,
            text="0/0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.mine_value.pack(side="left")
        self.btn_mine_plus = tk.Button(
            mine_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#84817a",
            fg="#000000",
            state="disabled",
            command=self._bind_action(self.state.action_build_mine),
        )
        self.btn_mine_plus.pack(side="left", padx=2)
        Tooltip(self.btn_mine_plus, "Cost: 4 planks. Requires ore site; enables miners.")

        # furnace row
        smelter_row = tk.Frame(buildings_frame, bg="#1e272e")
        self.smelter_row = smelter_row
        self.smelter_label = tk.Label(
            smelter_row,
            text="furnace",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.smelter_label.pack(side="left")
        self.btn_smelter_minus = tk.Button(
            smelter_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            state="disabled",
            command=self._bind_action(self.state.action_abandon_smelter),
        )
        self.btn_smelter_minus.pack(side="left", padx=(4, 2))
        self.smelter_value = tk.Label(
            smelter_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.smelter_value.pack(side="left")
        self.btn_smelter_plus = tk.Button(
            smelter_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#84817a",
            fg="#000000",
            state="disabled",
            command=self._bind_action(self.state.action_build_smelter),
        )
        self.btn_smelter_plus.pack(side="left", padx=2)
        Tooltip(self.btn_smelter_plus, "Cost: 2 planks, 8 stone. Builds a furnace for smelters.")

        # cellar row (storage)
        cellar_row = tk.Frame(buildings_frame, bg="#1e272e")
        self.cellar_row = cellar_row
        self.cellar_label = tk.Label(
            cellar_row,
            text="cellar",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.cellar_label.pack(side="left")
        self.btn_cellar_minus = tk.Button(
            cellar_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_abandon_cellar),
        )
        self.btn_cellar_minus.pack(side="left", padx=(4, 2))
        self.cellar_value = tk.Label(
            cellar_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.cellar_value.pack(side="left")
        self.btn_cellar_plus = tk.Button(
            cellar_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#84817a",
            fg="#000000",
            state="disabled",
            command=self._bind_action(self.state.action_build_cellar),
        )
        self.btn_cellar_plus.pack(side="left", padx=2)
        Tooltip(
            self.btn_cellar_plus,
            "Cost: 6 planks, 5 meat, 5 grain. Adds 40 storage slots.",
        )

        # warehouse row (storage)
        warehouse_row = tk.Frame(buildings_frame, bg="#1e272e")
        self.warehouse_row = warehouse_row
        self.warehouse_label = tk.Label(
            warehouse_row,
            text="warehouse",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.warehouse_label.pack(side="left")
        self.btn_warehouse_minus = tk.Button(
            warehouse_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            command=self._bind_action(self.state.action_abandon_warehouse),
        )
        self.btn_warehouse_minus.pack(side="left", padx=(4, 2))
        self.warehouse_value = tk.Label(
            warehouse_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.warehouse_value.pack(side="left")
        self.btn_warehouse_plus = tk.Button(
            warehouse_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#84817a",
            fg="#000000",
            state="disabled",
            command=self._bind_action(self.state.action_build_warehouse),
        )
        self.btn_warehouse_plus.pack(side="left", padx=2)
        Tooltip(
            self.btn_warehouse_plus,
            "Cost: 6 stone, 12 planks. Requires a cellar. Adds 260 storage slots.",
        )

        # smithy row
        smithy_row = tk.Frame(buildings_frame, bg="#1e272e")
        self.smithy_row = smithy_row
        self.smithy_label = tk.Label(
            smithy_row,
            text="smithy",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.smithy_label.pack(side="left")
        self.btn_smithy_minus = tk.Button(
            smithy_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            state="disabled",
            command=self._bind_action(self.state.action_abandon_smithy),
        )
        self.btn_smithy_minus.pack(side="left", padx=(4, 2))
        self.smithy_value = tk.Label(
            smithy_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.smithy_value.pack(side="left")
        self.btn_smithy_plus = tk.Button(
            smithy_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#84817a",
            fg="#000000",
            state="disabled",
            command=self._bind_action(self.state.action_build_smithy),
        )
        self.btn_smithy_plus.pack(side="left", padx=2)
        Tooltip(self.btn_smithy_plus, "Cost: 10 planks, 4 stone. Enables blacksmiths.")

        # tailor row
        tailor_row = tk.Frame(buildings_frame, bg="#1e272e")
        self.tailor_row = tailor_row
        self.tailor_label = tk.Label(
            tailor_row,
            text="textile workshop",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.tailor_label.pack(side="left")
        self.btn_tailor_minus = tk.Button(
            tailor_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            state="disabled",
            command=self._bind_action(self.state.action_abandon_tailor),
        )
        self.btn_tailor_minus.pack(side="left", padx=(4, 2))
        self.tailor_value = tk.Label(
            tailor_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.tailor_value.pack(side="left")
        self.btn_tailor_plus = tk.Button(
            tailor_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#84817a",
            fg="#000000",
            state="disabled",
            command=self._bind_action(self.state.action_build_tailor),
        )
        self.btn_tailor_plus.pack(side="left", padx=2)
        Tooltip(
            self.btn_tailor_plus,
            "Cost: 6 planks. Crafts clothing from linen.",
        )

        # tannery row
        tannery_row = tk.Frame(buildings_frame, bg="#1e272e")
        self.tannery_row = tannery_row
        self.tannery_label = tk.Label(
            tannery_row,
            text="tannery",
            font=("Helvetica", scaled(11)),
            bg="#1e272e",
            fg="#ffffff",
            width=14,
            anchor="w",
        )
        self.tannery_label.pack(side="left")
        self.btn_tannery_minus = tk.Button(
            tannery_row,
            text="-",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#57606f",
            fg="#ffffff",
            state="disabled",
            command=self._bind_action(self.state.action_abandon_tannery),
        )
        self.btn_tannery_minus.pack(side="left", padx=(4, 2))
        self.tannery_value = tk.Label(
            tannery_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
            anchor="center",
        )
        self.tannery_value.pack(side="left")
        self.btn_tannery_plus = tk.Button(
            tannery_row,
            text="+",
            font=("Helvetica", scaled(10), "bold"),
            width=2,
            bg="#84817a",
            fg="#000000",
            state="disabled",
            command=self._bind_action(self.state.action_build_tannery),
        )
        self.btn_tannery_plus.pack(side="left", padx=2)
        Tooltip(self.btn_tannery_plus, "Cost: 8 wood, 4 planks. Requires a found spring.")

        # news log column
        news_header = tk.Frame(news_col, bg="#1e272e")
        news_header.pack(fill="x", pady=(0, 4))
        tk.Label(
            news_header,
            text="news from the village",
            font=("Helvetica", scaled(13), "bold"),
            bg="#1e272e",
            fg="#ffffff",
        ).pack(side="left", anchor="w")
        self.season_label = tk.Label(
            news_header,
            text=self.current_season_icon,
            font=("Helvetica", scaled(14)),
            bg="#1e272e",
            fg="#ffffff",
        )
        self.season_label.pack(side="right", anchor="e")

        self.news_labels = []
        for _ in range(5):
            lbl = tk.Label(
                news_col,
                text="",
                font=("Helvetica", scaled(10), "italic"),
                bg="#1e272e",
                fg="#d2dae2",
                wraplength=260,
                justify="left",
            )
            lbl.pack(anchor="w", pady=(0, 2))
            self.news_labels.append(lbl)
        self._render_news()

    # --------- helpers ---------

    @property
    def pop_cap(self) -> int:
        return self.base_pop_cap + self.houses * 2

    @property
    def total_pop(self) -> int:
        # peasants + workers in roles + staffed buildings
        return (
            self.peasants
            + self.hunters
            + self.woodsmen
            + self.bowyers
            + self.weavers
            + self.rangers
            + self.lumber_mills
            + self.farms
            + self.tailor_shops
            + self.quarries
            + self.mines
            + self.smelters
            + self.smithies
        )

    # --------- actions ---------

    def action_recruit_peasant(self):
        if self.total_pop >= self.pop_cap:
            self.set_log("you need more housing before recruiting more peasants.")
            return
        # recruiting costs a bit of food
        if (self.resources["Meat"] + self.resources["Grain"]) < 2:
            self.set_log("not enough food to support another mouth.")
            return

        # consume from meat first, then grain
        cost = 2
        consumed_from_meat = min(cost, self.resources["Meat"])
        self.resources["Meat"] -= consumed_from_meat
        remaining_cost = cost - consumed_from_meat
        if remaining_cost > 0:
            self.resources["Grain"] -= remaining_cost
        
        self.peasants += 1
        self.set_log("a new peasant joins your fledgling settlement.")
        self._sync_food_total()

    def action_fire_peasant(self):
        if self.peasants <= 0:
            self.set_log("no idle peasants to send away.")
            return
        self.peasants -= 1
        self.total_pop  # trigger property for clarity
        self.set_log("a peasant departs, leaving your camp quieter.")

    def action_add_hunter(self):
        if self.peasants <= 0:
            self.set_log("no idle peasants to turn into hunters.")
            return
        self.peasants -= 1
        self.hunters += 1
        if self.resources.get("Bows", 0) > 0:
            self.set_log("a peasant strings a bow and joins the hunt.")
        else:
            self.set_log("a peasant sharpens a stick and ventures out to hunt.")

    def action_remove_hunter(self):
        if self.hunters <= 0:
            self.set_log("no hunters to reassign.")
            return
        self.hunters -= 1
        self.peasants += 1
        self.hunter_bows_equipped = min(self.hunter_bows_equipped, self.hunters)
        self.set_log("a hunter lays down their bow and returns as a peasant.")

    def action_add_woodsman(self):
        if self.peasants <= 0:
            self.set_log("no idle peasants to send into the woods.")
            return
        self.peasants -= 1
        self.woodsmen += 1
        self.set_log("a peasant grips a stone hatchet and starts felling trees.")

    def action_remove_woodsman(self):
        if self.woodsmen <= 0:
            self.set_log("no woodsmen to reassign.")
            return
        self.woodsmen -= 1
        self.peasants += 1
        self.set_log("a woodsman returns to the village as a peasant.")

    def action_add_bowyer(self):
        if not self.bowyer_unlocked:
            self.set_log("you need better materials before anyone can craft bows.")
            return
        if self.peasants <= 0:
            self.set_log("no idle peasants to put to the bowyer's bench.")
            return
        self.peasants -= 1
        self.bowyers += 1
        self.bowyer_progress.append(0.0)
        self.bowyer_jobs.append(None)
        self.set_log("a peasant starts shaping staves and stringing crude bows.")

    def action_remove_bowyer(self):
        if self.bowyers <= 0:
            self.set_log("no bowyers to reassign.")
            return
        self.bowyers -= 1
        self.peasants += 1
        if self.bowyer_progress:
            self.bowyer_progress.pop()
        if self.bowyer_jobs:
            self.bowyer_jobs.pop()
        self.set_log("a bowyer leaves the bench and returns as a peasant.")

    def action_add_weaver(self):
        if not self.weaver_unlocked:
            self.set_log("you need some flax before anyone can try weaving.")
            return
        if self.peasants <= 0:
            self.set_log("no idle peasants to put to the loom.")
            return
        self.peasants -= 1
        self.weavers += 1
        self.weaver_progress.append(0.0)
        self.weaver_jobs.append(None)
        self.set_log("a peasant begins spinning flax into rough linen.")

    def action_remove_weaver(self):
        if self.weavers <= 0:
            self.set_log("no weavers to reassign.")
            return
        self.weavers -= 1
        self.peasants += 1
        if self.weaver_progress:
            self.weaver_progress.pop()
        if self.weaver_jobs:
            self.weaver_jobs.pop()
        self.set_log("a weaver leaves the loom and returns as a peasant.")

    def action_add_ranger(self):
        if not self.ranger_unlocked:
            self.set_log("you need bows and arrows ready before training rangers.")
            return
        if self.peasants <= 0:
            self.set_log("no idle peasants to train as rangers.")
            return
        bow_cost = 1
        arrow_cost = 10
        if self.resources["Bows"] < bow_cost or self.resources["Arrows"] < arrow_cost:
            self.set_log("you need a bow and arrows ready to outfit a ranger.")
            return
        self.resources["Bows"] -= bow_cost
        self.resources["Arrows"] -= arrow_cost
        if self.resources.get("Swords", 0) >= 1:
            self.resources["Swords"] -= 1
            self.ranger_swords_equipped += 1
        self.peasants -= 1
        self.rangers += 1
        self.set_log("a peasant takes bow and arrows, ranging beyond the village.")

    def action_remove_ranger(self):
        if self.rangers <= 0:
            self.set_log("no rangers to recall.")
            return
        self.rangers -= 1
        self.peasants += 1
        self.ranger_swords_equipped = min(self.ranger_swords_equipped, self.rangers)
        self.set_log("a ranger returns to the village as a peasant.")

    def action_build_lumber_mill(self):
        cost_wood = 20
        if self.resources["Wood"] < cost_wood:
            self.set_log("not enough wood for a lumber mill.")
            return
        if self.peasants <= 0:
            self.set_log(
                "everyone is busy (idle peasants 0). free a worker to staff the mill."
            )
            return
        self.resources["Wood"] -= cost_wood
        self.peasants -= 1
        self.lumber_mills += 1
        self.set_log("you raise a simple lumber mill. one peasant now works there.")

    def action_build_house(self):
        cost_planks = 10
        if self.resources["Planks"] < cost_planks:
            self.set_log("not enough planks to build a house.")
            return
        self.resources["Planks"] -= cost_planks
        self.houses += 1
        self.set_log("a new house is built. more peasants can be housed.")

    def action_build_farm(self):
        cost_planks = 8
        if self.resources["Planks"] < cost_planks:
            self.set_log("not enough planks to build a farm.")
            return
        if self.peasants <= 0:
            self.set_log(
                "everyone is busy (idle peasants 0). free a worker to tend the farm."
            )
            return
        self.resources["Planks"] -= cost_planks
        self.peasants -= 1
        self.farms += 1
        self.set_log("fields are tilled. a peasant now toils as a farmer.")

    def action_build_quarry(self):
        cost_planks = 4
        if self.resources["QuarrySites"] <= 0:
            self.set_log("you need a quarry site before building a quarry.")
            return
        if self.resources["Planks"] < cost_planks:
            self.set_log("not enough planks to build a quarry.")
            return
        if self.peasants <= 0:
            self.set_log("everyone is busy (idle peasants 0). free a worker for the quarry.")
            return
        self.resources["Planks"] -= cost_planks
        self.resources["QuarrySites"] -= 1
        self.peasants -= 1
        self.quarries += 1
        self.set_log("a quarry is established; stone can be cut here.")

    def action_build_mine(self):
        cost_planks = 4
        if self.resources["MineSites"] <= 0:
            self.set_log("you need an ore site before digging a mine.")
            return
        if self.resources["Planks"] < cost_planks:
            self.set_log("not enough planks to shore up a mine entrance.")
            return
        if self.peasants <= 0:
            self.set_log("everyone is busy (idle peasants 0). free a worker for the mine.")
            return
        self.resources["Planks"] -= cost_planks
        self.resources["MineSites"] -= 1
        self.peasants -= 1
        self.mines += 1
        self.set_log("a mine entrance is dug; ore extraction can begin.")

    def action_build_smelter(self):
        cost_planks = 2
        cost_stone = 8
        if self.resources["Stone"] < cost_stone:
            self.set_log("not enough stone to build a smelter.")
            return
        if self.resources["Planks"] < cost_planks:
            self.set_log("not enough planks to shore up the smelter.")
            return
        if self.peasants <= 0:
            self.set_log("everyone is busy (idle peasants 0). free a worker for the smelter.")
            return
        self.resources["Stone"] -= cost_stone
        self.resources["Planks"] -= cost_planks
        self.peasants -= 1
        self.smelters += 1
        self.set_log("a smelter is built; ore can now be refined into ingots.")

    def action_build_smithy(self):
        cost_planks = 10
        cost_stone = 4
        if self.resources["Stone"] < cost_stone:
            self.set_log("not enough stone to build a smithy.")
            return
        if self.resources["Planks"] < cost_planks:
            self.set_log("not enough planks to raise a smithy.")
            return
        if self.peasants <= 0:
            self.set_log("everyone is busy (idle peasants 0). free a worker for the smithy.")
            return
        self.resources["Stone"] -= cost_stone
        self.resources["Planks"] -= cost_planks
        self.peasants -= 1
        self.smithies += 1
        self.set_log("a smithy is built; metalwork can begin.")

    def action_build_tailor(self):
        cost_planks = 6
        if not self.tailor_unlocked:
            self.set_log("you need linen in stores before a tailor will set up shop.")
            return
        if self.resources["Planks"] < cost_planks:
            self.set_log("not enough planks to build a tailor's shop.")
            return
        if self.peasants <= 0:
            self.set_log("everyone is busy (idle peasants 0). free a worker for tailoring.")
            return
        self.resources["Planks"] -= cost_planks
        self.peasants -= 1
        self.tailor_shops += 1
        self.tailors += 1
        self.tailor_jobs.append(None)
        self.sticky_resources.update({"Clothing", "Cloaks", "Gambesons"})
        self.set_log("a tailor sets up a modest shop, ready to sew garments.")

    def action_abandon_lumber_mill(self):
        if self.lumber_mills <= 0:
            self.set_log("no lumber mills to abandon.")
            return
        self.lumber_mills -= 1
        self.peasants += 1
        self.set_log("you shutter a lumber mill. its worker returns as an idle peasant.")

    def action_abandon_farm(self):
        if self.farms <= 0:
            self.set_log("no farms to abandon.")
            return
        self.farms -= 1
        self.peasants += 1
        self.set_log("you let a farm go fallow. its worker returns as an idle peasant.")

    def action_abandon_smelter(self):
        if self.smelters <= 0:
            self.set_log("no smelters to close.")
            return
        self.smelters -= 1
        self.peasants += 1
        self.set_log("you bank a smelter's fires. its worker returns as an idle peasant.")

    def action_abandon_smithy(self):
        if self.smithies <= 0:
            self.set_log("no smithies to shutter.")
            return
        self.smithies -= 1
        self.peasants += 1
        self.set_log("you close a smithy. its worker returns as an idle peasant.")

    def action_abandon_tailor(self):
        if self.tailor_shops <= 0:
            self.set_log("no tailors to send away.")
            return
        self.tailor_shops -= 1
        self.tailors = max(0, self.tailor_shops)
        self.peasants += 1
        if self.tailor_progress:
            self.tailor_progress = self.tailor_progress[: self.tailor_shops]
        if self.tailor_jobs:
            self.tailor_jobs = self.tailor_jobs[: self.tailor_shops]
        self.set_log("a tailor closes shop, returning as an idle peasant.")

    # --------- simulation ---------

    def game_tick(self):
        self.state.game_tick()
        self.update_ui()

    # --------- ui update ---------

    def set_log(self, text: str):
        self.state.set_log(text)
        self._render_news()

    def _render_news(self):
        if self.state.pending_logs:
            self.state.consume_logs()
        ordered = list(reversed(self.state.log_history))
        for idx, lbl in enumerate(self.news_labels):
            if idx < len(ordered):
                lbl.config(text=ordered[idx])
            else:
                lbl.config(text="")

    def _menu_save(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save game state",
        )
        if not path:
            return
        state = self._export_state()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as exc:
            messagebox.showerror("Save failed", f"Could not save state:\n{exc}")

    def _menu_load(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load game state",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as exc:
            messagebox.showerror("Load failed", f"Could not load state:\n{exc}")
            return
        self._load_state_dict(state)
        self.update_ui()

    # --------- menu actions ---------

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save...", command=self._menu_save)
        file_menu.add_command(label="Load...", command=self._menu_load)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

    def _tick_season(self):
        self.state._tick_season()
        if hasattr(self, "season_label"):
            self.season_label.config(text=self.state.current_season_icon)

    def _build_deck(self, high_pop: bool):
        return self.state._build_deck(high_pop)

    def _ensure_deck(self):
        return self.state._ensure_deck()

    def _draw_ranger_card(self):
        self.state._draw_ranger_card()

    def _get_display_resource_names(self):
        return self.state._get_display_resource_names()

    # --------- update checking ---------
    def _start_update_check(self):
        if not self.update_label:
            return

        def worker():
            remote = self._fetch_remote_version()
            current = get_version()
            if remote and remote != current:
                whl = f"kingdom_clicker-{remote}-py3-none-any.whl"
                url = f"https://github.com/brownbat/kingdom-clicker/raw/master/dist/{whl}"
                msg = f"Update available: v{current} → v{remote}. Run: pipx install --force {url}"
                self.root.after(0, lambda: self._set_update_text(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _set_update_text(self, text: str):
        if self.update_label and text:
            self.update_label.config(text=text)
            if not self.update_label.winfo_manager():
                self.update_label.pack()

    def _fetch_remote_version(self) -> Optional[str]:
        try:
            with urllib.request.urlopen(UPDATE_CHECK_URL, timeout=3) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r'version\s*=\s*"([^"]+)"', data)
            if m:
                return m.group(1).strip()
        except Exception:
            return None
        return None

    def update_ui(self):
        s = self.state
        s._sync_food_total()
        for k in s.resources:
            if s.resources[k] < 0:
                s.resources[k] = 0.0

        self.season_label.config(text=s.current_season_icon)
        self._render_news()

        display_resources = s._get_display_resource_names()

        # hide labels no longer displayed
        for name, lbl in list(self.res_labels.items()):
            if name not in display_resources and lbl.winfo_manager():
                lbl.grid_forget()

        # render visible resources in a grid (wrap after N columns)
        display_name_map = {
            "Cloaks": "cloaks",
            "Gambesons": "gambeson",
        }

        for idx, name in enumerate(display_resources):
            lbl = self.res_labels.get(name)
            if not lbl:
                lbl = tk.Label(
                    self.res_grid,
                    text="",
                    font=("Courier", scaled(14), "bold"),
                    bg="#1e272e",
                    fg=self.res_colors.get(name, "#ffffff"),
                    width=16,
                    anchor="w",
                )
                self.res_labels[name] = lbl

            if name == "Wood":
                total_wood = self.resources["Wood"] + self.lumber_buffer
                base_name = "wood"
                value = int(total_wood)
            else:
                base_name = display_name_map.get(name, name.lower())
                value = int(self.resources.get(name, 0))
            text = f"{base_name}: {value}"

            lbl.config(text=text, fg=self.res_colors.get(name, "#ffffff"))
            row = idx // self.resource_grid_cols
            col = idx % self.resource_grid_cols
            lbl.grid(row=row, column=col, padx=5, pady=2, sticky="w")

        # population
        self.pop_label.config(text=f"pop: {s.total_pop}/{s.pop_cap}")

        # forces indicator
        warnings = []
        if (s.resources["Meat"] + s.resources["Grain"]) <= 0:
            warnings.append("hungry")
        if s.resources["Pelts"] <= 0:
            warnings.append("cold")

        if warnings:
            self.force_label.config(text=" | ".join(warnings))
        else:
            self.force_label.config(text="")

        # assignment labels under buttons
        self.peasant_value.config(text=f"{s.peasants}")
        self.hunter_value.config(text=f"{s.hunters}")
        self.woodsman_value.config(text=f"{s.woodsmen}")
        self.bowyer_value.config(text=f"{s.bowyers}/{s._job_capacity('bowyer') or 0}")
        self.weaver_value.config(text=f"{s.weavers}/{s._job_capacity('weaver') or 0}")
        self.ranger_value.config(text=f"{s.rangers}")
        self.sawyer_value.config(text=f"{s.sawyers}/{s._job_capacity('sawyer') or 0}")
        self.farmer_value.config(text=f"{s.farmers}/{s._job_capacity('farmer') or 0}")
        self.stonemason_value.config(text=f"{s.stonemasons}/{s._job_capacity('stonemason') or 0}")
        self.miner_value.config(text=f"{s.miners}/{s._job_capacity('miner') or 0}")
        self.smelter_worker_value.config(text=f"{s.smelter_workers}/{s._job_capacity('smelter') or 0}")
        self.blacksmith_value.config(text=f"{s.blacksmiths}/{s._job_capacity('blacksmith') or 0}")
        self.tailor_worker_value.config(text=f"{s.tailors}/{s._job_capacity('tailor') or 0}")
        self.tanner_value.config(text=f"{s.tanners}/{s._job_capacity('tanner') or 0}")
        # building counts
        total_quarry_sites = int(s.quarries + s.resources["QuarrySites"])
        total_mine_sites = int(s.mines + s.resources["MineSites"])
        self.quarry_value.config(text=f"{s.quarries}/{total_quarry_sites}")
        self.mine_value.config(text=f"{s.mines}/{total_mine_sites}")

        # pop tooltip
        lines = [f"peasants {s.peasants}"]
        if s.hunters:
            lines.append(f"hunters {s.hunters}")
        if s.woodsmen:
            lines.append(f"woodsmen {s.woodsmen}")
        if s.bowyers:
            lines.append(f"bowyers {s.bowyers}")
        if s.weavers:
            lines.append(f"weavers {s.weavers}")
        if s.sawyers:
            lines.append(f"sawyers {s.sawyers}")
        if s.farmers:
            lines.append(f"farmers {s.farmers}")
        if s.rangers:
            lines.append(f"rangers {s.rangers}")
        if s.stonemasons:
            lines.append(f"stonemasons {s.stonemasons}")
        if s.miners:
            lines.append(f"miners {s.miners}")
        if s.smelter_workers:
            lines.append(f"smelters {s.smelter_workers}")
        if s.blacksmiths:
            lines.append(f"blacksmiths {s.blacksmiths}")
        if s.tailors:
            lines.append(f"tailors {s.tailors}")
        if s.tanners:
            lines.append(f"tanners {s.tanners}")
        self.pop_tooltip.text = "\n".join(lines)

        # building counts
        self.house_value.config(text=f"{s.houses}")
        self.mill_value.config(text=f"{s.lumber_mills}")
        self.farm_value.config(text=f"{s.farms}")
        if hasattr(self, "bowyer_shop_value"):
            self.bowyer_shop_value.config(text=f"{s.bowyer_shops}")
        self.smelter_value.config(text=f"{s.smelters}")
        self.smithy_value.config(text=f"{s.smithies}")
        self.tailor_value.config(text=f"{s.tailor_shops}")
        self.cellar_value.config(text=f"{s.cellars}")
        if hasattr(self, "tannery_value"):
            self.tannery_value.config(text=f"{s.tanneries}")
        self.warehouse_value.config(text=f"{s.warehouses}")

        # unlock rows
        if s.jobs_unlocked:
            if not self.hunter_row.winfo_manager():
                self.hunter_row.pack(anchor="w", pady=(10, 2), fill="x")
            if not self.woods_row.winfo_manager():
                self.woods_row.pack(anchor="w", pady=2, fill="x")
            if s.bowyer_unlocked and s.bowyer_shops > 0 and not self.bowyer_row.winfo_manager():
                self.bowyer_row.pack(anchor="w", pady=2, fill="x")
            if s.weaver_unlocked and not self.weaver_row.winfo_manager():
                self.weaver_row.pack(anchor="w", pady=2, fill="x")
            if s.lumber_mills > 0 and not self.sawyer_row.winfo_manager():
                self.sawyer_row.pack(anchor="w", pady=2, fill="x")
            if s.farms > 0 and not self.farmer_row.winfo_manager():
                self.farmer_row.pack(anchor="w", pady=2, fill="x")
            if s.ranger_unlocked and not self.ranger_row.winfo_manager():
                self.ranger_row.pack(anchor="w", pady=2, fill="x")
            if s.bowyer_unlocked and s.bowyer_shops > 0 and not self.bowyer_row.winfo_manager():
                self.bowyer_row.pack(anchor="w", pady=2, fill="x")
            if s.quarry_unlocked and s.quarries > 0 and not self.stonemason_row.winfo_manager():
                self.stonemason_row.pack(anchor="w", pady=2, fill="x")
            if s.mine_unlocked and s.mines > 0 and not self.miner_row.winfo_manager():
                self.miner_row.pack(anchor="w", pady=2, fill="x")
            if s.quarry_unlocked and not self.quarry_row.winfo_manager():
                self.quarry_row.pack(anchor="w", pady=2, fill="x")
            if s.mine_unlocked and not self.mine_row.winfo_manager():
                self.mine_row.pack(anchor="w", pady=2, fill="x")
            if s.smelter_unlocked and not self.smelter_row.winfo_manager():
                self.smelter_row.pack(anchor="w", pady=2, fill="x")
            if s.smelter_unlocked and s.smelters > 0 and not self.smelter_worker_row.winfo_manager():
                self.smelter_worker_row.pack(anchor="w", pady=2, fill="x")
            if s.smithy_unlocked and not self.smithy_row.winfo_manager():
                self.smithy_row.pack(anchor="w", pady=2, fill="x")
            if s.smithy_unlocked and s.smithies > 0 and not self.blacksmith_row.winfo_manager():
                self.blacksmith_row.pack(anchor="w", pady=2, fill="x")
            if s.tailor_unlocked and s.tailor_shops > 0 and not self.tailor_worker_row.winfo_manager():
                self.tailor_worker_row.pack(anchor="w", pady=2, fill="x")
            if s.tannery_unlocked and s.tanneries > 0 and not self.tanner_row.winfo_manager():
                self.tanner_row.pack(anchor="w", pady=2, fill="x")

        if s.farm_unlocked and not self.farm_row.winfo_manager():
            self.farm_row.pack(anchor="w", pady=2, fill="x")
        if s.bowyer_unlocked and not self.bowyer_shop_row.winfo_manager():
            self.bowyer_shop_row.pack(anchor="w", pady=2, fill="x")

        # ensure crafting rows show once unlocked
        if s.jobs_unlocked and s.weaver_unlocked and not self.weaver_row.winfo_manager():
            self.weaver_row.pack(anchor="w", pady=2, fill="x")
        if s.jobs_unlocked and s.bowyer_unlocked and s.bowyer_shops > 0 and not self.bowyer_row.winfo_manager():
            self.bowyer_row.pack(anchor="w", pady=2, fill="x")
        if s.jobs_unlocked and s.ranger_unlocked and not self.ranger_row.winfo_manager():
            self.ranger_row.pack(anchor="w", pady=2, fill="x")
        if s.jobs_unlocked and s.tailor_unlocked and s.tailor_shops > 0 and not self.tailor_worker_row.winfo_manager():
            self.tailor_worker_row.pack(anchor="w", pady=2, fill="x")
        if s.jobs_unlocked and s.quarry_unlocked and not self.quarry_row.winfo_manager():
            self.quarry_row.pack(anchor="w", pady=2, fill="x")
        if s.jobs_unlocked and s.mine_unlocked and not self.mine_row.winfo_manager():
            self.mine_row.pack(anchor="w", pady=2, fill="x")
        if s.jobs_unlocked and s.smelter_unlocked and not self.smelter_row.winfo_manager():
            self.smelter_row.pack(anchor="w", pady=2, fill="x")
        if s.jobs_unlocked and s.smelter_unlocked and s.smelters > 0 and not self.smelter_worker_row.winfo_manager():
            self.smelter_worker_row.pack(anchor="w", pady=2, fill="x")
        if s.jobs_unlocked and s.smithy_unlocked and not self.smithy_row.winfo_manager():
            self.smithy_row.pack(anchor="w", pady=2, fill="x")
        if s.jobs_unlocked and s.smithy_unlocked and s.smithies > 0 and not self.blacksmith_row.winfo_manager():
            self.blacksmith_row.pack(anchor="w", pady=2, fill="x")
        if (s.cellar_unlocked) or s.cellars > 0:
            if not self.cellar_row.winfo_manager():
                self.cellar_row.pack(anchor="w", pady=2, fill="x")
        if (
            (s.cellars > 0 and s.resources["Stone"] >= 6 and s.resources["Planks"] >= 12)
            or s.warehouses > 0
        ):
            if not self.warehouse_row.winfo_manager():
                self.warehouse_row.pack(anchor="w", pady=2, fill="x")
        if s.tannery_unlocked and not self.tannery_row.winfo_manager():
            self.tannery_row.pack(anchor="w", pady=2, fill="x")

        # enable/disable buttons based on affordability
        self._update_button_states()

    def _update_button_states(self):
        s = self.state

        # upgrades
        if s.peasants <= 0:
            self.btn_hunter_plus.config(state="disabled", bg="#84817a")
            self.btn_woodsman_plus.config(state="disabled", bg="#84817a")
            self.btn_bowyer_plus.config(state="disabled", bg="#84817a")
            self.btn_ranger_plus.config(state="disabled", bg="#84817a")
        else:
            self.btn_hunter_plus.config(state="normal", bg="#33d9b2")
            self.btn_woodsman_plus.config(state="normal", bg="#ffb142")
            if s.bowyer_unlocked:
                self.btn_bowyer_plus.config(state="normal", bg="#eccc68")
            else:
                self.btn_bowyer_plus.config(state="disabled", bg="#84817a")
            # ranger enable handled later when unlocked flag is set

        if s.hunters > 0:
            self.btn_hunter_minus.config(state="normal")
        else:
            self.btn_hunter_minus.config(state="disabled")

        if s.woodsmen > 0:
            self.btn_woodsman_minus.config(state="normal")
        else:
            self.btn_woodsman_minus.config(state="disabled")

        if s.bowyers > 0:
            self.btn_bowyer_minus.config(state="normal")
        else:
            self.btn_bowyer_minus.config(state="disabled")

        if s.weavers > 0:
            self.btn_weaver_minus.config(state="normal")
        else:
            self.btn_weaver_minus.config(state="disabled")

        if s.rangers > 0:
            self.btn_ranger_minus.config(state="normal")
        else:
            self.btn_ranger_minus.config(state="disabled")

        # building-gated jobs
        cap_sawyer = s._job_capacity("sawyer") or 0
        cap_farmer = s._job_capacity("farmer") or 0
        cap_stone = s._job_capacity("stonemason") or 0
        cap_miner = s._job_capacity("miner") or 0
        cap_bowyer = s._job_capacity("bowyer") or 0
        cap_weaver = s._job_capacity("weaver") or 0
        cap_smelter = s._job_capacity("smelter") or 0
        cap_blacksmith = s._job_capacity("blacksmith") or 0
        cap_tailor = s._job_capacity("tailor") or 0
        cap_tanner = s._job_capacity("tanner") or 0

        def _enable_job(plus_btn, condition, color):
            if condition:
                plus_btn.config(state="normal", bg=color)
            else:
                plus_btn.config(state="disabled", bg="#84817a")

        _enable_job(self.btn_sawyer_plus, s.peasants > 0 and s.lumber_mills > 0 and s.sawyers < cap_sawyer, "#ffa801")
        _enable_job(self.btn_farmer_plus, s.peasants > 0 and s.farms > 0 and s.farmers < cap_farmer, "#f5cd79")
        _enable_job(self.btn_stonemason_plus, s.peasants > 0 and s.quarries > 0 and s.stonemasons < cap_stone, "#d1ccc0")
        _enable_job(self.btn_miner_plus, s.peasants > 0 and s.mines > 0 and s.miners < cap_miner, "#ced6e0")
        _enable_job(self.btn_bowyer_plus, s.peasants > 0 and s.bowyer_shops > 0 and s.bowyers < cap_bowyer, "#eccc68")
        _enable_job(self.btn_weaver_plus, s.peasants > 0 and s.tailor_shops > 0 and s.weavers < cap_weaver, "#34ace0")
        _enable_job(self.btn_smelter_worker_plus, s.peasants > 0 and s.smelters > 0 and s.smelter_workers < cap_smelter, "#ffd32a")
        _enable_job(self.btn_blacksmith_plus, s.peasants > 0 and s.smithies > 0 and s.blacksmiths < cap_blacksmith, "#ffa502")
        _enable_job(self.btn_tailor_worker_plus, s.peasants > 0 and s.tailor_shops > 0 and s.tailors < cap_tailor, "#95afc0")
        _enable_job(self.btn_tanner_plus, s.peasants > 0 and s.tanneries > 0 and s.tanners < cap_tanner, "#a4b0be")

        for btn, count in [
            (self.btn_sawyer_minus, s.sawyers),
            (self.btn_farmer_minus, s.farmers),
            (self.btn_stonemason_minus, s.stonemasons),
            (self.btn_miner_minus, s.miners),
            (self.btn_smelter_worker_minus, s.smelter_workers),
            (self.btn_blacksmith_minus, s.blacksmiths),
            (self.btn_tailor_worker_minus, s.tailors),
            (self.btn_tanner_minus, s.tanners),
        ]:
            btn.config(state="normal" if count > 0 else "disabled")

        ranger_ready = (
            s.ranger_unlocked
            and s.peasants > 0
            and s.resources["Bows"] >= 1
            and s.resources["Arrows"] >= 10
        )
        if ranger_ready:
            self.btn_ranger_plus.config(state="normal", bg="#70a1ff")
        else:
            self.btn_ranger_plus.config(state="disabled", bg="#84817a")

        # quarries/mines
        if (
            s.quarry_unlocked
            and s.resources["QuarrySites"] >= 1
            and s.resources["Planks"] >= 4
        ):
            self.btn_quarry_plus.config(state="normal", bg="#d1ccc0")
        else:
            self.btn_quarry_plus.config(state="disabled", bg="#84817a")

        if (
            s.mine_unlocked
            and s.resources["MineSites"] >= 1
            and s.resources["Planks"] >= 4
        ):
            self.btn_mine_plus.config(state="normal", bg="#d1ccc0")
        else:
            self.btn_mine_plus.config(state="disabled", bg="#84817a")

        # recruit
        recruitable = (
            s.total_pop < s.pop_cap
            and (s.resources["Meat"] + s.resources["Grain"]) >= 2
        )
        if recruitable:
            self.btn_peasant_plus.config(state="normal", bg="#706fd3")
        else:
            self.btn_peasant_plus.config(state="disabled", bg="#84817a")

        if s.peasants > 0:
            self.btn_peasant_minus.config(state="normal")
        else:
            self.btn_peasant_minus.config(state="disabled")

        # buildings
        if s.resources["Wood"] >= 20:
            self.btn_mill_plus.config(state="normal", bg="#2ecc71")
        else:
            self.btn_mill_plus.config(state="disabled", bg="#84817a")

        if s.resources["Planks"] >= 10:
            self.btn_house_plus.config(state="normal", bg="#f7d794")
        else:
            self.btn_house_plus.config(state="disabled", bg="#84817a")

        if s.resources["Planks"] >= 8:
            self.btn_farm_plus.config(state="normal", bg="#f5cd79")
        else:
            self.btn_farm_plus.config(state="disabled", bg="#84817a")

        if s.bowyer_unlocked and s.resources["Planks"] >= 6:
            self.btn_bowyer_shop_plus.config(state="normal", bg="#eccc68")
        else:
            self.btn_bowyer_shop_plus.config(state="disabled", bg="#84817a")

        if (
            s.smelter_unlocked
            and s.resources["Stone"] >= 8
            and s.resources["Planks"] >= 2
        ):
            self.btn_smelter_plus.config(state="normal", bg="#ffd32a")
        else:
            self.btn_smelter_plus.config(state="disabled", bg="#84817a")

        if (
            s.smithy_unlocked
            and s.resources["Stone"] >= 4
            and s.resources["Planks"] >= 10
        ):
            self.btn_smithy_plus.config(state="normal", bg="#ffa502")
        else:
            self.btn_smithy_plus.config(state="disabled", bg="#84817a")

        if s.flax_unlocked and s.resources["Planks"] >= 6:
            self.btn_tailor_plus.config(state="normal", bg="#95afc0")
        else:
            self.btn_tailor_plus.config(state="disabled", bg="#84817a")

        if s.tannery_unlocked and s.resources["Wood"] >= 8 and s.resources["Planks"] >= 4:
            self.btn_tannery_plus.config(state="normal", bg="#a4b0be")
        else:
            self.btn_tannery_plus.config(state="disabled", bg="#84817a")

        # storage buildings
        if s.cellar_unlocked:
            self.btn_cellar_plus.config(state="normal", bg="#95afc0")
        else:
            self.btn_cellar_plus.config(state="disabled", bg="#84817a")

        if (
            s.cellars > 0
            and s.resources["Stone"] >= 6
            and s.resources["Planks"] >= 12
        ):
            self.btn_warehouse_plus.config(state="normal", bg="#95afc0")
        else:
            self.btn_warehouse_plus.config(state="disabled", bg="#84817a")

        # abandon buttons
        if s.lumber_mills > 0:
            self.btn_mill_minus.config(state="normal")
        else:
            self.btn_mill_minus.config(state="disabled")

        if s.bowyer_shops > 0:
            self.btn_bowyer_shop_minus.config(state="normal")
        else:
            self.btn_bowyer_shop_minus.config(state="disabled")

        if s.farms > 0:
            self.btn_farm_minus.config(state="normal")
        else:
            self.btn_farm_minus.config(state="disabled")

        if s.smelters > 0:
            self.btn_smelter_minus.config(state="normal")
        else:
            self.btn_smelter_minus.config(state="disabled")

        if s.smithies > 0:
            self.btn_smithy_minus.config(state="normal")
        else:
            self.btn_smithy_minus.config(state="disabled")

        if s.tailor_shops > 0:
            self.btn_tailor_minus.config(state="normal")
        else:
            self.btn_tailor_minus.config(state="disabled")

        if s.cellars > 0:
            self.btn_cellar_minus.config(state="normal")
        else:
            self.btn_cellar_minus.config(state="disabled")

        if s.warehouses > 0:
            self.btn_warehouse_minus.config(state="normal")
        else:
            self.btn_warehouse_minus.config(state="disabled")

        if s.tanneries > 0:
            self.btn_tannery_minus.config(state="normal")
        else:
            self.btn_tannery_minus.config(state="disabled")


def main():
    parser = argparse.ArgumentParser(description="Run Kingdom Clicker.")
    parser.add_argument(
        "--state",
        type=str,
        help="Path to JSON file with starting state overrides.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the simulation without launching the UI (defaults to 100 ticks).",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit.",
    )
    parser.add_argument(
        "--sim-ticks",
        type=int,
        default=None,
        help="Number of ticks to advance in headless mode.",
    )
    args = parser.parse_args()

    initial_state = {}
    if args.state:
        try:
            with open(args.state, "r", encoding="utf-8") as f:
                initial_state = json.load(f)
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"Failed to load state file '{args.state}': {exc}")
            initial_state = {}

    if args.version:
        print(get_version())
        raise SystemExit(0)

    headless_ticks = args.sim_ticks if args.sim_ticks is not None else (100 if args.headless else None)
    if headless_ticks is not None:
        state = GameState(initial_state=initial_state)
        for _ in range(max(0, headless_ticks)):
            state.game_tick()
        print("Final resources:")
        for name in sorted(state.resources):
            print(f"{name}: {int(state.resources[name])}")
    else:
        if tk is None:
            raise SystemExit("Tkinter is required to launch the UI.")
        root = tk.Tk()
        app = GameApp(root, initial_state=initial_state)
        root.mainloop()


if __name__ == "__main__":
    main()
