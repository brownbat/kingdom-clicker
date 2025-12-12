import argparse
import json
import random
import tkinter as tk
from tkinter import filedialog, messagebox

TICK_MS = 1000  # game tick in milliseconds
UI_SCALE = 1.2
FOOD_UPKEEP_PER_CAPITA = 0.25
WARMTH_UPKEEP_PER_CAPITA = 0.02
HUNTER_FOOD_YIELD = 0.475  # supports ~1.9 pop per hunter at baseline
HUNTER_PELT_YIELD = 0.05
HUNTER_GUT_YIELD = 0.02
HUNTER_FEATHER_YIELD = 0.1
HUNTER_SKIN_YIELD = 0.05
BOW_HUNTER_BONUS = 1.25
HUNTER_ARROW_USE_PER_TICK = 0.08
BOWYER_BOW_TIME = 6.0  # ticks of work to craft one bow
FARM_GRAIN_YIELD = 0.6  # reduced slightly to offset more flax
SMITHY_SWORD_CAP = 5
SMITHY_DAGGER_CAP = 10
SMITHY_TOOL_CAP = 15
FARM_FLAX_YIELD = 1.5  # doubled flax output to support 4 farms per weaver target
SKIN_FLAX_UNLOCK = 5
RANGER_DRAW_TICKS = 10
STARVATION_PENALTY = 0.75
WEAVER_LINEN_TIME = 10.0  # slower loom pace to balance flax supply/demand
TAILOR_WORK_TIME = 10.0  # slow tailors to ease linen drain versus weaving


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


class KingdomIdlePOC:
    def __init__(self, root: tk.Tk, initial_state: dict | None = None):
        self.root = root
        self.root.title("Kingdom Clicker")
        self.root.geometry("1080x720")
        self.root.configure(bg="#1e272e")
        self._build_menu()

        # --- game state ---

        # resources
        self.resources = {
            "Food": 20.0,  # for display only
            "Meat": 20.0,
            "Grain": 0.0,
            "Pelts": 5.0,
            "Wood": 0.0,
            "Planks": 0.0,
            "Guts": 0.0,
            "Bows": 0.0,
            "Feathers": 0.0,
            "Skins": 0.0,
            "Arrows": 0.0,
            "Flax": 0.0,
            "Linen": 0.0,
            "Clothing": 0.0,
            "Cloaks": 0.0,
            "Gambesons": 0.0,
            "QuarrySites": 0.0,
            "MineSites": 0.0,
            "Stone": 0.0,
            "Ore": 0.0,
            "Ingots": 0.0,
            "Tools": 0.0,
            "Daggers": 0.0,
            "Swords": 0.0,
        }

        # units
        self.peasants = 0
        self.hunters = 0
        self.woodsmen = 0
        self.bowyers = 0
        self.weavers = 0
        self.rangers = 0
        self.tailors = 0

        # buildings
        self.lumber_mills = 0
        self.houses = 2
        self.base_pop_cap = 0
        self.farms = 0
        self.smelters = 0
        self.smithies = 0
        self.tailor_shops = 0

        # misc
        self.log_text = "an empty clearing awaits settlers."
        self.log_history = [self.log_text]
        self.last_food_need = 0.0
        self.last_warmth_need = 0.0
        self.lumber_buffer = 0.0  # wood waiting to be milled
        self.grain_buffer = 0.0  # seasonal grain waiting for harvest
        self.smelter_buffer = 0.0  # ore waiting to be smelted
        self.farm_growth_slots = 0  # farms eligible for this year's growth
        self.hunter_bows_equipped = 0
        self.jobs_unlocked = False
        self.farm_unlocked = False
        self.food_breakdown_unlocked = False
        self.guts_unlocked = False
        self.guts_visible = False
        self.flax_unlocked = False
        self.bowyer_unlocked = False
        self.weaver_unlocked = False
        self.tailor_unlocked = False
        self.ranger_unlocked = False
        self.bowyer_progress = []
        self.weaver_progress = []
        self.tailor_progress = []
        self.total_meat_made = 0.0
        self.season_tick = 0
        self.season_phase = 0
        self.season_icons = ["🌱", "☀️", "🍂", "❄️"]
        self.current_season_icon = self.season_icons[0]
        self.resource_grid_cols = 5
        self.sticky_resources = set()
        self.site_deck = []
        self.deck_seeded = False
        self.deck_refreshed_at_60 = False
        self.ranger_tick_counter = 0
        self.ranger_draw_pool = 0.0
        self.ranger_swords_equipped = 0
        self.weaver_jobs = []
        self.tailor_jobs = []
        self.bowyer_jobs = []
        self.first_linen_announced = False
        self.quarries_discovered = 0
        self.mines_discovered = 0
        self.quarries = 0
        self.mines = 0
        self.quarry_unlocked = False
        self.mine_unlocked = False
        self.smelter_unlocked = False
        self.smithy_unlocked = False
        self.smithy_last_crafted = {"Swords": -1, "Daggers": -1, "Tools": -1}
        self.smithy_craft_counter = 0
        self.tailor_last_crafted = {
            "Clothing": -1,
            "Cloaks": -1,
            "Gambesons": -1,
        }
        self.tailor_craft_counter = 0

        # apply overrides from json state file
        self._apply_initial_state(initial_state or {})

        # --- ui layout ---

        self._build_ui()
        self._render_news()

        # start loop
        self.update_ui()
        self.root.after(TICK_MS, self.game_tick)

    def _apply_initial_state(self, state: dict):
        """Override starting values from a JSON blob for quick testing setups."""
        resources = state.get("resources")
        if isinstance(resources, dict):
            merged = dict(self.resources)  # start from current defaults
            for k, v in resources.items():
                try:
                    merged[k] = float(v)
                except (TypeError, ValueError):
                    merged[k] = 0.0
            self.resources = merged

        int_fields = [
            "peasants",
            "hunters",
            "woodsmen",
            "bowyers",
            "weavers",
            "rangers",
            "tailors",
            "ranger_swords_equipped",
            "lumber_mills",
            "houses",
            "farms",
            "smelters",
            "smithies",
            "tailor_shops",
            "quarries",
            "mines",
            "base_pop_cap",
            "farm_growth_slots",
            "hunter_bows_equipped",
            "season_tick",
            "season_phase",
            "quarries_discovered",
            "mines_discovered",
            "smithy_craft_counter",
            "tailor_craft_counter",
        ]
        for field in int_fields:
            if field in state:
                try:
                    setattr(self, field, int(state[field]))
                except (TypeError, ValueError):
                    continue

        float_fields = ["lumber_buffer", "grain_buffer", "smelter_buffer", "ranger_draw_pool"]
        for field in float_fields:
            if field in state:
                try:
                    setattr(self, field, float(state[field]))
                except (TypeError, ValueError):
                    continue

        # keep staffed tailors aligned to their shops
        self.tailors = self.tailor_shops

        bool_fields = [
            "deck_refreshed_at_60",
            "jobs_unlocked",
            "farm_unlocked",
            "food_breakdown_unlocked",
            "guts_unlocked",
            "guts_visible",
            "flax_unlocked",
            "bowyer_unlocked",
            "weaver_unlocked",
            "tailor_unlocked",
            "ranger_unlocked",
            "quarry_unlocked",
            "mine_unlocked",
            "smelter_unlocked",
            "smithy_unlocked",
            "deck_seeded",
            "first_linen_announced",
        ]
        for field in bool_fields:
            if field in state:
                setattr(self, field, bool(state[field]))

        if self.tailor_unlocked:
            self.sticky_resources.update({"Clothing", "Cloaks", "Gambesons"})

        if isinstance(state.get("site_deck"), list):
            # shallow copy to avoid mutating user-provided list
            self.site_deck = list(state["site_deck"])

        if isinstance(state.get("log_text"), str):
            self.log_text = state["log_text"]
        if isinstance(state.get("log_history"), list) and state["log_history"]:
            self.log_history = list(state["log_history"])[-5:]
            self.log_text = self.log_history[-1]

        if isinstance(state.get("bowyer_progress"), list):
            self.bowyer_progress = list(state["bowyer_progress"])
        if isinstance(state.get("weaver_progress"), list):
            self.weaver_progress = list(state["weaver_progress"])
        if isinstance(state.get("tailor_progress"), list):
            self.tailor_progress = list(state["tailor_progress"])
        if isinstance(state.get("weaver_jobs"), list):
            self.weaver_jobs = list(state["weaver_jobs"])
        if isinstance(state.get("tailor_jobs"), list):
            self.tailor_jobs = list(state["tailor_jobs"])
        if isinstance(state.get("bowyer_jobs"), list):
            self.bowyer_jobs = list(state["bowyer_jobs"])
        if isinstance(state.get("sticky_resources"), list):
            self.sticky_resources = set(state["sticky_resources"])
        if isinstance(state.get("smithy_last_crafted"), dict):
            self.smithy_last_crafted = {
                "Swords": state["smithy_last_crafted"].get("Swords", -1),
                "Daggers": state["smithy_last_crafted"].get("Daggers", -1),
                "Tools": state["smithy_last_crafted"].get("Tools", -1),
            }
        if isinstance(state.get("tailor_last_crafted"), dict):
            self.tailor_last_crafted = {
                "Clothing": state["tailor_last_crafted"].get("Clothing", -1),
                "Cloaks": state["tailor_last_crafted"].get("Cloaks", -1),
                "Gambesons": state["tailor_last_crafted"].get("Gambesons", state["tailor_last_crafted"].get("PaddedArmor", -1)),
            }
        if self.tailor_unlocked or self.tailor_shops > 0:
            self.sticky_resources.update({"Clothing", "Cloaks", "Gambesons"})

        if "total_meat_made" in state:
            try:
                self.total_meat_made = float(state["total_meat_made"])
            except (TypeError, ValueError):
                pass

        self.current_season_icon = self.season_icons[self.season_phase % len(self.season_icons)]
        self._sync_food_total()

    def _export_state(self) -> dict:
        return {
            "resources": self.resources,
            "peasants": self.peasants,
            "hunters": self.hunters,
            "woodsmen": self.woodsmen,
            "bowyers": self.bowyers,
            "weavers": self.weavers,
            "tailors": self.tailors,
            "rangers": self.rangers,
            "ranger_swords_equipped": self.ranger_swords_equipped,
            "lumber_mills": self.lumber_mills,
            "houses": self.houses,
            "farms": self.farms,
            "smelters": self.smelters,
            "smithies": self.smithies,
            "tailor_shops": self.tailor_shops,
            "quarries": self.quarries,
            "mines": self.mines,
            "base_pop_cap": self.base_pop_cap,
            "farm_growth_slots": self.farm_growth_slots,
            "lumber_buffer": self.lumber_buffer,
            "grain_buffer": self.grain_buffer,
            "smelter_buffer": self.smelter_buffer,
            "hunter_bows_equipped": self.hunter_bows_equipped,
            "bowyer_progress": self.bowyer_progress,
            "weaver_progress": self.weaver_progress,
            "tailor_progress": self.tailor_progress,
            "bowyer_jobs": self.bowyer_jobs,
            "weaver_jobs": self.weaver_jobs,
            "tailor_jobs": self.tailor_jobs,
            "total_meat_made": self.total_meat_made,
            "season_tick": self.season_tick,
            "season_phase": self.season_phase,
            "log_text": self.log_text,
            "log_history": self.log_history,
            "sticky_resources": list(self.sticky_resources),
            "site_deck": self.site_deck,
            "deck_seeded": self.deck_seeded,
            "deck_refreshed_at_60": self.deck_refreshed_at_60,
            "ranger_tick_counter": self.ranger_tick_counter,
            "ranger_draw_pool": self.ranger_draw_pool,
            "jobs_unlocked": self.jobs_unlocked,
            "farm_unlocked": self.farm_unlocked,
            "food_breakdown_unlocked": self.food_breakdown_unlocked,
            "guts_unlocked": self.guts_unlocked,
            "guts_visible": self.guts_visible,
            "flax_unlocked": self.flax_unlocked,
            "bowyer_unlocked": self.bowyer_unlocked,
            "weaver_unlocked": self.weaver_unlocked,
            "tailor_unlocked": self.tailor_unlocked,
            "ranger_unlocked": self.ranger_unlocked,
            "quarry_unlocked": self.quarry_unlocked,
            "mine_unlocked": self.mine_unlocked,
            "smelter_unlocked": self.smelter_unlocked,
            "smithy_unlocked": self.smithy_unlocked,
            "quarries_discovered": self.quarries_discovered,
            "mines_discovered": self.mines_discovered,
            "smithy_last_crafted": self.smithy_last_crafted,
            "smithy_craft_counter": self.smithy_craft_counter,
            "tailor_last_crafted": self.tailor_last_crafted,
            "tailor_craft_counter": self.tailor_craft_counter,
            "first_linen_announced": self.first_linen_announced,
        }

    def _load_state_dict(self, state: dict):
        # reset key fields to defaults before applying new state
        self.resources = {
            "Food": 20.0,
            "Meat": 20.0,
            "Grain": 0.0,
            "Pelts": 5.0,
            "Wood": 0.0,
            "Planks": 0.0,
            "Guts": 0.0,
            "Bows": 0.0,
            "Feathers": 0.0,
            "Skins": 0.0,
            "Arrows": 0.0,
            "Flax": 0.0,
            "Linen": 0.0,
            "Clothing": 0.0,
            "Cloaks": 0.0,
            "Gambesons": 0.0,
            "QuarrySites": 0.0,
            "MineSites": 0.0,
            "Stone": 0.0,
            "Ore": 0.0,
            "Ingots": 0.0,
            "Tools": 0.0,
            "Daggers": 0.0,
            "Swords": 0.0,
        }
        self.peasants = 0
        self.hunters = 0
        self.woodsmen = 0
        self.bowyers = 0
        self.weavers = 0
        self.tailors = 0
        self.rangers = 0
        self.ranger_swords_equipped = 0
        self.lumber_mills = 0
        self.houses = 2
        self.base_pop_cap = 0
        self.farms = 0
        self.smelters = 0
        self.smithies = 0
        self.tailor_shops = 0
        self.log_text = "an empty clearing awaits settlers."
        self.log_history = [self.log_text]
        self.last_food_need = 0.0
        self.last_warmth_need = 0.0
        self.lumber_buffer = 0.0
        self.grain_buffer = 0.0
        self.smelter_buffer = 0.0
        self.farm_growth_slots = 0
        self.hunter_bows_equipped = 0
        self.jobs_unlocked = False
        self.farm_unlocked = False
        self.food_breakdown_unlocked = False
        self.guts_unlocked = False
        self.guts_visible = False
        self.flax_unlocked = False
        self.bowyer_unlocked = False
        self.weaver_unlocked = False
        self.tailor_unlocked = False
        self.ranger_unlocked = False
        self.bowyer_progress = []
        self.weaver_progress = []
        self.tailor_progress = []
        self.tailor_last_crafted = {
            "Clothing": -1,
            "Cloaks": -1,
            "Gambesons": -1,
        }
        self.tailor_craft_counter = 0
        self.total_meat_made = 0.0
        self.season_tick = 0
        self.season_phase = 0
        self.current_season_icon = self.season_icons[0]
        self.sticky_resources = set()
        self.site_deck = []
        self.deck_seeded = False
        self.deck_refreshed_at_60 = False
        self.ranger_tick_counter = 0
        self.ranger_draw_pool = 0.0
        self.weaver_jobs = []
        self.tailor_jobs = []
        self.bowyer_jobs = []
        self.quarries = 0
        self.mines = 0
        self.quarry_unlocked = False
        self.mine_unlocked = False
        self.smelter_unlocked = False
        self.smithy_unlocked = False
        self.smithy_last_crafted = {"Swords": -1, "Daggers": -1, "Tools": -1}
        self.smithy_craft_counter = 0
        self.tailor_last_crafted = {
            "Clothing": -1,
            "Cloaks": -1,
            "Gambesons": -1,
        }
        self.tailor_craft_counter = 0
        self.quarries_discovered = 0
        self.mines_discovered = 0
        self.first_linen_announced = False

        self._apply_initial_state(state)
        self._render_news()

    # smithy helpers
    def _smithy_pick_target(self, choice: str):
        stocks = {
            "sword": (self.resources.get("Swords", 0.0), SMITHY_SWORD_CAP),
            "dagger": (self.resources.get("Daggers", 0.0), SMITHY_DAGGER_CAP),
            "tool": (self.resources.get("Tools", 0.0), SMITHY_TOOL_CAP),
        }

        def has_room(item):
            val, cap = stocks[item]
            return val < cap

        if choice in ("sword", "dagger", "tool"):
            return choice if has_room(choice) else None

        if choice == "lowest":
            candidates = [k for k in stocks if has_room(k)]
            if not candidates:
                return None
            min_val = min(stocks[k][0] for k in candidates)
            lowest = [k for k in candidates if stocks[k][0] == min_val]
            return random.choice(lowest)

        if choice == "stale":
            candidates = [k for k in stocks if has_room(k)]
            if not candidates:
                return None
            last_map = {
                "sword": self.smithy_last_crafted.get("Swords", -1),
                "dagger": self.smithy_last_crafted.get("Daggers", -1),
                "tool": self.smithy_last_crafted.get("Tools", -1),
            }
            min_last = min(last_map[k] for k in candidates)
            stalest = [k for k in candidates if last_map[k] == min_last]
            return random.choice(stalest)

        return None

    def _smithy_craft(self, target: str):
        if target == "sword":
            if self.resources["Ingots"] >= 3 and self.resources["Swords"] < SMITHY_SWORD_CAP:
                self.resources["Ingots"] -= 3
                self.resources["Swords"] += 1
                self.smithy_craft_counter += 1
                self.smithy_last_crafted["Swords"] = self.smithy_craft_counter
        elif target == "tool":
            if (
                self.resources["Ingots"] >= 1
                and self.resources["Wood"] >= 1
                and self.resources["Tools"] < SMITHY_TOOL_CAP
            ):
                self.resources["Ingots"] -= 1
                self.resources["Wood"] -= 1
                self.resources["Tools"] += 1
                self.smithy_craft_counter += 1
                self.smithy_last_crafted["Tools"] = self.smithy_craft_counter
        elif target == "dagger":
            if self.resources["Ingots"] >= 1 and self.resources["Daggers"] < SMITHY_DAGGER_CAP:
                self.resources["Ingots"] -= 1
                self.resources["Daggers"] += 1
                self.smithy_craft_counter += 1
            self.smithy_last_crafted["Daggers"] = self.smithy_craft_counter

    # --------- ui ---------
    # tailor helpers
    def _tailor_can_craft(self, target: str) -> bool:
        if target == "clothing":
            return self.resources["Linen"] >= 1
        if target == "winter":
            return self.resources["Linen"] >= 1 and self.resources["Pelts"] >= 1
        if target == "armor":
            return self.resources["Linen"] >= 2 and self.resources["Pelts"] >= 1
        return False

    def _tailor_pick_target(self, choice: str):
        stocks = {
            "clothing": self.resources.get("Clothing", 0.0),
            "winter": self.resources.get("Cloaks", 0.0),
            "armor": self.resources.get("Gambesons", 0.0),
        }

        def ready(item: str) -> bool:
            return self._tailor_can_craft(item)

        if choice in ("clothing", "winter", "armor"):
            return choice if ready(choice) else None

        if choice == "lowest":
            candidates = [k for k in stocks if ready(k)]
            if not candidates:
                return None
            min_val = min(stocks[k] for k in candidates)
            lowest = [k for k in candidates if stocks[k] == min_val]
            return random.choice(lowest)

        if choice == "stale":
            candidates = [k for k in stocks if ready(k)]
            if not candidates:
                return None
            last_map = {
                "clothing": self.tailor_last_crafted.get("Clothing", -1),
                "winter": self.tailor_last_crafted.get("Cloaks", -1),
                "armor": self.tailor_last_crafted.get("Gambesons", -1),
            }
            min_last = min(last_map[k] for k in candidates)
            stalest = [k for k in candidates if last_map[k] == min_last]
            return random.choice(stalest)

        return None

    def _tailor_craft(self, target: str):
        if target == "clothing" and self.resources["Linen"] >= 1:
            self.resources["Linen"] -= 1
            self.resources["Clothing"] += 1
            self.tailor_craft_counter += 1
            self.tailor_last_crafted["Clothing"] = self.tailor_craft_counter
            return True
        if target == "winter" and self.resources["Linen"] >= 1 and self.resources["Pelts"] >= 1:
            self.resources["Linen"] -= 1
            self.resources["Pelts"] -= 1
            self.resources["Cloaks"] += 1
            self.tailor_craft_counter += 1
            self.tailor_last_crafted["Cloaks"] = self.tailor_craft_counter
            return True
        if target == "armor" and self.resources["Linen"] >= 2 and self.resources["Pelts"] >= 1:
            self.resources["Linen"] -= 2
            self.resources["Pelts"] -= 1
            self.resources["Gambesons"] += 1
            self.tailor_craft_counter += 1
            self.tailor_last_crafted["Gambesons"] = self.tailor_craft_counter
            return True
        return False

    def _tailor_finish(self, target: str):
        """Deliver output for a garment when inputs were already reserved."""
        if target == "clothing":
            self.resources["Clothing"] += 1
            self.tailor_craft_counter += 1
            self.tailor_last_crafted["Clothing"] = self.tailor_craft_counter
            return True
        if target == "winter":
            self.resources["Cloaks"] += 1
            self.tailor_craft_counter += 1
            self.tailor_last_crafted["Cloaks"] = self.tailor_craft_counter
            return True
        if target == "armor":
            self.resources["Gambesons"] += 1
            self.tailor_craft_counter += 1
            self.tailor_last_crafted["Gambesons"] = self.tailor_craft_counter
            return True
        return False

    def _sync_food_total(self):
        """Keep display food in sync with meat + grain."""
        self.resources["Food"] = max(
            0.0, self.resources["Meat"] + self.resources["Grain"]
        )

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

        # main content row (three columns, even widths)
        content = tk.Frame(self.root, bg="#1e272e")
        content.pack(fill="both", expand=True, padx=10, pady=5)
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
            command=self.action_fire_peasant,
        )
        self.btn_peasant_minus.pack(side="left", padx=(4, 2))
        self.peasant_value = tk.Label(
            peasant_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
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
            command=self.action_recruit_peasant,
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
            command=self.action_remove_hunter,
        )
        self.btn_hunter_minus.pack(side="left", padx=(4, 2))
        self.hunter_value = tk.Label(
            hunter_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
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
            command=self.action_add_hunter,
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
            command=self.action_remove_woodsman,
        )
        self.btn_woodsman_minus.pack(side="left", padx=(4, 2))
        self.woodsman_value = tk.Label(
            woods_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
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
            command=self.action_add_woodsman,
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
            command=self.action_remove_bowyer,
        )
        self.btn_bowyer_minus.pack(side="left", padx=(4, 2))
        self.bowyer_value = tk.Label(
            bowyer_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
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
            command=self.action_add_bowyer,
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
            command=self.action_remove_weaver,
        )
        self.btn_weaver_minus.pack(side="left", padx=(4, 2))
        self.weaver_value = tk.Label(
            weaver_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
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
            command=self.action_add_weaver,
        )
        self.btn_weaver_plus.pack(side="left", padx=2)
        Tooltip(self.btn_weaver_plus, "Cost: 1 peasant. Spins flax into linen.")

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
            command=self.action_remove_ranger,
        )
        self.btn_ranger_minus.pack(side="left", padx=(4, 2))
        self.ranger_value = tk.Label(
            ranger_row,
            text="0",
            font=("Helvetica", scaled(11), "bold"),
            bg="#1e272e",
            fg="#ffffff",
            width=3,
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
            command=self.action_add_ranger,
        )
        self.btn_ranger_plus.pack(side="left", padx=2)
        Tooltip(self.btn_ranger_plus, "Cost: 1 bow, 10 arrows, 1 peasant (idle)")

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
            command=self.action_build_house,
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
            command=self.action_abandon_lumber_mill,
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
            command=self.action_build_lumber_mill,
        )
        self.btn_mill_plus.pack(side="left", padx=2)
        Tooltip(self.btn_mill_plus, "Cost: 20 wood, 1 peasant (staffed)")

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
            command=self.action_abandon_farm,
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
            command=self.action_build_farm,
        )
        self.btn_farm_plus.pack(side="left", padx=2)
        Tooltip(self.btn_farm_plus, "Cost: 8 planks, 1 peasant (staffed)")

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
            command=self.action_build_quarry,
        )
        self.btn_quarry_plus.pack(side="left", padx=2)
        Tooltip(self.btn_quarry_plus, "Cost: 4 planks, 1 peasant, requires quarry site")

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
            command=self.action_build_mine,
        )
        self.btn_mine_plus.pack(side="left", padx=2)
        Tooltip(self.btn_mine_plus, "Cost: 4 planks, 1 peasant, requires ore site")

        # smelter row
        smelter_row = tk.Frame(buildings_frame, bg="#1e272e")
        self.smelter_row = smelter_row
        self.smelter_label = tk.Label(
            smelter_row,
            text="smelter",
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
            command=self.action_abandon_smelter,
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
            command=self.action_build_smelter,
        )
        self.btn_smelter_plus.pack(side="left", padx=2)
        Tooltip(
            self.btn_smelter_plus,
            "Cost: 2 planks, 8 stone, 1 peasant (staffed)",
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
            command=self.action_abandon_smithy,
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
            command=self.action_build_smithy,
        )
        self.btn_smithy_plus.pack(side="left", padx=2)
        Tooltip(
            self.btn_smithy_plus,
            "Cost: 10 planks, 4 stone, 1 peasant (staffed)",
        )

        # tailor row
        tailor_row = tk.Frame(buildings_frame, bg="#1e272e")
        self.tailor_row = tailor_row
        self.tailor_label = tk.Label(
            tailor_row,
            text="tailor",
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
            command=self.action_abandon_tailor,
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
            command=self.action_build_tailor,
        )
        self.btn_tailor_plus.pack(side="left", padx=2)
        Tooltip(
            self.btn_tailor_plus,
            "Cost: 6 planks, 1 peasant (staffed). Crafts clothing from linen.",
        )

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
        # one game tick: handle consumption, production, penalties.
        self._tick_season()
        pop = self.total_pop

        hunger_mult = 1.0
        cold_mult = 1.0

        # consumption: hunger
        food_need = pop * FOOD_UPKEEP_PER_CAPITA
        self.last_food_need = food_need
        total_food = self.resources["Meat"] + self.resources["Grain"]
        if total_food >= food_need:
            # consume from meat first, then grain
            consumed_from_meat = min(food_need, self.resources["Meat"])
            self.resources["Meat"] -= consumed_from_meat
            remaining_need = food_need - consumed_from_meat
            if remaining_need > 0:
                self.resources["Grain"] -= remaining_need
        else:
            self.resources["Meat"] = 0.0
            self.resources["Grain"] = 0.0
            hunger_mult = STARVATION_PENALTY  # production slowed by hunger

        # consumption: exposure (pelts as proxy for warmth)
        warmth_need = pop * WARMTH_UPKEEP_PER_CAPITA
        self.last_warmth_need = warmth_need
        if self.resources["Pelts"] >= warmth_need:
            self.resources["Pelts"] -= warmth_need
        else:
            self.resources["Pelts"] = 0.0
            cold_mult = STARVATION_PENALTY  # production slowed by cold

        prod_mult = hunger_mult * cold_mult

        # production: hunters
        if self.hunters > 0:
            # keep equipped bows in sync with hunter count
            if self.hunter_bows_equipped > self.hunters:
                self.hunter_bows_equipped = self.hunters

            # equip hunters with bows if available
            while (
                self.hunter_bows_equipped < self.hunters
                and self.resources["Bows"] >= 1
            ):
                self.resources["Bows"] -= 1
                self.hunter_bows_equipped += 1

            arrows_needed = self.hunter_bows_equipped * HUNTER_ARROW_USE_PER_TICK
            arrows_spent = min(arrows_needed, self.resources["Arrows"])
            self.resources["Arrows"] -= arrows_spent
            arrow_utilization = (arrows_spent / arrows_needed) if arrows_needed > 0 else 0

            bow_bonus = BOW_HUNTER_BONUS if self.hunter_bows_equipped > 0 else 1.0
            bow_bonus = 1.0 + (bow_bonus - 1.0) * arrow_utilization

            meat_gain = self.hunters * HUNTER_FOOD_YIELD * prod_mult * bow_bonus
            self.resources["Meat"] += meat_gain
            self.total_meat_made += meat_gain
            if not self.guts_unlocked and self.total_meat_made >= 80:
                self.guts_unlocked = True
                self.resources["Guts"] = max(self.resources["Guts"], 1.0)
                self.set_log("hunters begin separating out guts for other uses.")
            if self.guts_unlocked:
                self.resources["Guts"] += (
                    self.hunters * HUNTER_GUT_YIELD * prod_mult * bow_bonus
                )
            self.resources["Pelts"] += (
                self.hunters * HUNTER_PELT_YIELD * prod_mult * bow_bonus
            )
            if self.hunter_bows_equipped > 0:
                self.resources["Feathers"] += (
                    self.hunters * HUNTER_FEATHER_YIELD * prod_mult * bow_bonus
                )
                self.resources["Skins"] += (
                    self.hunters * HUNTER_SKIN_YIELD * prod_mult * bow_bonus
                )

        # production: woodsmen
        if self.woodsmen > 0:
            self.resources["Wood"] += self.woodsmen * 1.0 * prod_mult

        # production: farms
        if self.farms > 0 and self.season_phase in (2, 3, 0):  # autumn/winter/spring growth
            active_farms = min(self.farms, self.farm_growth_slots)
            if active_farms > 0:
                self.grain_buffer += active_farms * FARM_GRAIN_YIELD * prod_mult

        # production: quarries (stone) and mines (ore)
        if self.quarries > 0:
            self.resources.setdefault("Stone", 0.0)
            self.sticky_resources.add("Stone")
            self.resources["Stone"] += self.quarries * 1.2 * prod_mult
        if self.mines > 0:
            self.resources.setdefault("Ore", 0.0)
            self.sticky_resources.add("Ore")
            self.resources["Ore"] += self.mines * 0.8 * prod_mult

        # production: smelters (convert ore -> ingots)
        if self.smelters > 0:
            self.resources.setdefault("Ingots", 0.0)
            self.sticky_resources.add("Ingots")
            max_convert = self.smelters * 1.2  # ore per tick
            convertible_ore = min(max_convert * prod_mult, self.resources["Ore"])
            self.resources["Ore"] -= convertible_ore
            self.smelter_buffer += convertible_ore
            ingots_possible = int(self.smelter_buffer // 2)
            if ingots_possible > 0:
                self.smelter_buffer -= ingots_possible * 2
                first_ingots = self.resources["Ingots"] <= 0
                self.resources["Ingots"] += ingots_possible
                if first_ingots:
                    self.set_log("smelters pour their first crude ingots.")

        # production: smithies (craft tools/weapons)
        if self.smithies > 0:
            self.resources.setdefault("Tools", 0.0)
            self.resources.setdefault("Daggers", 0.0)
            self.resources.setdefault("Swords", 0.0)
            self.sticky_resources.update({"Tools", "Daggers", "Swords"})
            for _ in range(self.smithies):
                choice = random.choice(["sword", "dagger", "tool", "lowest", "stale"])
                target = self._smithy_pick_target(choice)
                if target:
                    self._smithy_craft(target)

        # production: tailors (convert linen/pelts into clothing types)
        if self.tailor_shops > 0:
            self.resources.setdefault("Clothing", 0.0)
            self.resources.setdefault("Cloaks", 0.0)
            self.resources.setdefault("Gambesons", 0.0)
            self.sticky_resources.update({"Clothing", "Cloaks", "Gambesons"})

            if len(self.tailor_progress) < self.tailor_shops:
                self.tailor_progress += [0.0] * (self.tailor_shops - len(self.tailor_progress))
            elif len(self.tailor_progress) > self.tailor_shops:
                self.tailor_progress = self.tailor_progress[: self.tailor_shops]
            if len(self.tailor_jobs) < self.tailor_shops:
                self.tailor_jobs += [None] * (self.tailor_shops - len(self.tailor_jobs))
            elif len(self.tailor_jobs) > self.tailor_shops:
                self.tailor_jobs = self.tailor_jobs[: self.tailor_shops]

            for i in range(self.tailor_shops):
                if self.tailor_jobs[i] is None:
                    choice = random.choice(["clothing", "winter", "armor", "lowest", "stale"])
                    target = self._tailor_pick_target(choice)
                    if target:
                        # reserve inputs at start of work
                        if target == "clothing":
                            self.resources["Linen"] -= 1
                        elif target == "winter":
                            self.resources["Linen"] -= 1
                            self.resources["Pelts"] -= 1
                        elif target == "armor":
                            self.resources["Linen"] -= 2
                            self.resources["Pelts"] -= 1
                        self.tailor_jobs[i] = target
                        self.tailor_progress[i] = 0.0
                    else:
                        continue

                self.tailor_progress[i] += 1.0 * prod_mult
                if self.tailor_progress[i] >= TAILOR_WORK_TIME:
                    finished = self._tailor_finish(self.tailor_jobs[i])
                    if finished:
                        self.tailor_progress[i] = 0.0
                        self.tailor_jobs[i] = None

        # ranger gear upkeep
        if self.rangers > 0:
            if self.ranger_swords_equipped > self.rangers:
                self.ranger_swords_equipped = self.rangers
            while self.ranger_swords_equipped < self.rangers and self.resources.get("Swords", 0) >= 1:
                self.resources["Swords"] -= 1
                self.ranger_swords_equipped += 1

        # ranger exploration deck (each ranger contributes a draw share)
        if self.rangers > 0:
            self.ranger_draw_pool += self.rangers / RANGER_DRAW_TICKS
            while self.ranger_draw_pool >= 1.0:
                self.ranger_draw_pool -= 1.0
                self._draw_ranger_card()

        # production: lumber mills (convert wood -> planks)
        if self.lumber_mills > 0:
            max_convert = self.lumber_mills * 1.5  # wood per tick
            convertible_wood = min(max_convert * prod_mult, self.resources["Wood"])
            self.resources["Wood"] -= convertible_wood
            self.lumber_buffer += convertible_wood

            planks_possible = int(self.lumber_buffer // 3)
            if planks_possible > 0:
                self.lumber_buffer -= planks_possible * 3
                self.resources["Planks"] += planks_possible * prod_mult

        # production: weavers (convert flax -> linen)
        if len(self.weaver_progress) < self.weavers:
            self.weaver_progress += [0.0] * (self.weavers - len(self.weaver_progress))
        elif len(self.weaver_progress) > self.weavers:
            self.weaver_progress = self.weaver_progress[: self.weavers]
        if len(self.weaver_jobs) < self.weavers:
            self.weaver_jobs += [None] * (self.weavers - len(self.weaver_jobs))
        elif len(self.weaver_jobs) > self.weavers:
            self.weaver_jobs = self.weaver_jobs[: self.weavers]

        for i in range(self.weavers):
            if self.weaver_jobs[i] is None:
                if self.resources["Flax"] >= 1:
                    self.resources["Flax"] -= 1
                    self.weaver_jobs[i] = "linen"
                    self.weaver_progress[i] = 0.0
                else:
                    continue

            self.weaver_progress[i] += 1.0 * prod_mult
            if self.weaver_progress[i] >= WEAVER_LINEN_TIME:
                first_linen = self.resources.get("Linen", 0) <= 0
                self.resources["Linen"] += 1
                self.sticky_resources.add("Linen")
                self.weaver_progress[i] = 0.0
                self.weaver_jobs[i] = None
                if first_linen and not self.first_linen_announced:
                    self.first_linen_announced = True
                    self.set_log("your first linen is woven from flax fibers.")

        # production: bowyers (craft bows slowly, consuming planks + guts; arrows if feathers are present)
        if len(self.bowyer_progress) < self.bowyers:
            self.bowyer_progress += [0.0] * (self.bowyers - len(self.bowyer_progress))
        elif len(self.bowyer_progress) > self.bowyers:
            self.bowyer_progress = self.bowyer_progress[: self.bowyers]
        if len(self.bowyer_jobs) < self.bowyers:
            self.bowyer_jobs += [None] * (self.bowyers - len(self.bowyer_jobs))
        elif len(self.bowyer_jobs) > self.bowyers:
            self.bowyer_jobs = self.bowyer_jobs[: self.bowyers]

        for i in range(self.bowyers):
            if self.bowyer_jobs[i] is None:
                if self.resources["Feathers"] >= 20 and self.resources["Wood"] >= 2:
                    self.resources["Feathers"] -= 20
                    self.resources["Wood"] -= 2
                    self.bowyer_jobs[i] = "arrows"
                    self.bowyer_progress[i] = 0.0
                elif self.resources["Wood"] >= 3 and self.resources["Guts"] >= 1:
                    self.resources["Wood"] -= 3
                    self.resources["Guts"] -= 1
                    self.bowyer_jobs[i] = "bow"
                    self.bowyer_progress[i] = 0.0
                else:
                    continue

            self.bowyer_progress[i] += 1.0 * prod_mult
            if self.bowyer_progress[i] >= BOWYER_BOW_TIME:
                if self.bowyer_jobs[i] == "arrows":
                    self.resources["Arrows"] += 20
                elif self.bowyer_jobs[i] == "bow":
                    self.resources["Bows"] += 1
                self.bowyer_progress[i] = 0.0
                self.bowyer_jobs[i] = None

        # update display-only food total
        self._sync_food_total()

        self.update_ui()
        self.root.after(TICK_MS, self.game_tick)

    # --------- ui update ---------

    def set_log(self, text: str):
        self.log_text = text
        self.log_history.append(text)
        self.log_history = self.log_history[-5:]
        self._render_news()

    def _render_news(self):
        ordered = list(reversed(self.log_history))
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
        prev_phase = self.season_phase
        self.season_tick += 1
        phase = (self.season_tick // 15) % 4
        first_tick = self.season_tick == 1
        phase_changed = phase != prev_phase
        if first_tick or phase_changed:
            self.season_phase = phase
            self.current_season_icon = self.season_icons[phase]
            self.season_label.config(text=self.current_season_icon)
            if phase == 2:  # autumn planting (reset/lock slots)
                self.grain_buffer = 0.0
                self.farm_growth_slots = self.farms
            if phase == 1:  # summer harvest
                harvest = self.grain_buffer
                if harvest > 0:
                    self.resources["Grain"] += harvest
                    if self.flax_unlocked:
                        flax_gain = self.farm_growth_slots * FARM_FLAX_YIELD
                        self.resources["Flax"] += flax_gain
                    self.grain_buffer = 0.0
                    self.set_log(f"summer harvest brings in {int(harvest)} grain.")
        else:
            self.season_label.config(text=self.current_season_icon)

    def _build_deck(self, high_pop: bool):
        import random

        if high_pop:
            deck = []
            deck.append(random.choice(["quarry", "mine"]))  # 50/50 site
            deck.append("mana_site")
            deck.append("kobold_village")
            deck += ["forest"] * 3 + ["clearing"] * 2 + ["spring"] * 2
        else:
            deck = []
            deck += ["forest"] * 5
            deck += ["clearing"] * 3
            deck += ["spring"] * 2
            deck += ["quarry", "mine", "wolf_den"]
        random.shuffle(deck)
        return deck

    def _ensure_deck(self):
        # refresh once at pop 60 by adding new cards on top of the existing deck
        if self.total_pop >= 60 and not self.deck_refreshed_at_60:
            self.site_deck += self._build_deck(high_pop=True)
            random.shuffle(self.site_deck)
            self.deck_refreshed_at_60 = True
        if not self.site_deck and not self.deck_seeded:
            self.site_deck = self._build_deck(high_pop=False)
            self.deck_seeded = True

    def _draw_ranger_card(self):
        self._ensure_deck()
        if not self.site_deck:
            return

        card = random.choice(self.site_deck)
        self.site_deck.remove(card)
        if card != "nothing":
            self.site_deck.append("nothing")  # replace pulled cards with filler
        if card == "quarry":
            self.resources["QuarrySites"] += 1
            self.quarry_unlocked = True
            self.quarries_discovered += 1
        if card == "mine":
            self.resources["MineSites"] += 1
            self.mine_unlocked = True
            self.mines_discovered += 1
        log_map = {
            "forest": "rangers chart a dense forest.",
            "clearing": "rangers find a quiet clearing.",
            "spring": "rangers mark a fresh spring.",
            "quarry": "rangers discover a stone outcrop fit for a quarry.",
            "mine": "rangers locate a vein of ore worth mining.",
            "mana_site": "rangers map a faint ley line and crystal outcrop.",
            "kobold_village": "rangers spot a wary kobold village watching from afar.",
            "nothing": "rangers range far but find nothing new.",
            "grove": "rangers map a sacred grove.",
            "ruin": "rangers spot old ruins worth exploring.",
            "wolf_den": "rangers report a wolf den nearby—could be trouble if left alone.",
        }
        self.set_log(log_map.get(card, f"rangers discover a {card}."))

    def _get_display_resource_names(self):
        names = []
        if self.food_breakdown_unlocked:
            primary = ["Meat", "Grain", "Pelts", "Wood", "Planks"]
        else:
            primary = ["Food", "Pelts", "Wood", "Planks"]

        for name in primary:
            if name not in names:
                names.append(name)

        dynamic = []
        for name, amount in self.resources.items():
            if name in primary:
                continue
            if name == "Food" and self.food_breakdown_unlocked:
                continue
            if name in ("Meat", "Grain") and not self.food_breakdown_unlocked:
                continue
            if name in ("QuarrySites", "MineSites"):
                continue
            if self.tailor_unlocked or self.tailor_shops > 0:
                self.sticky_resources.update({"Clothing", "Cloaks", "Gambesons"})
            if amount > 0:
                if name != "Food":
                    self.sticky_resources.add(name)
                dynamic.append(name)
        dynamic.extend(self.sticky_resources)
        dynamic = sorted(set(dynamic))
        names.extend(dynamic)
        return names

    def update_ui(self):
        # clamp resources to non-negative, round for display
        self._sync_food_total()
        for k in self.resources:
            if self.resources[k] < 0:
                self.resources[k] = 0.0

        display_resources = self._get_display_resource_names()

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
        self.pop_label.config(text=f"pop: {self.total_pop}/{self.pop_cap}")

        # forces indicator
        warnings = []
        if (self.resources["Meat"] + self.resources["Grain"]) <= 0:
            warnings.append("hungry")
        if self.resources["Pelts"] <= 0:
            warnings.append("cold")

        if warnings:
            self.force_label.config(text=" | ".join(warnings))
        else:
            self.force_label.config(text="")

        # assignment labels under buttons
        self.peasant_value.config(text=f"{self.peasants}")
        self.hunter_value.config(text=f"{self.hunters}")
        self.woodsman_value.config(text=f"{self.woodsmen}")
        self.bowyer_value.config(text=f"{self.bowyers}")
        self.weaver_value.config(text=f"{self.weavers}")
        self.ranger_value.config(text=f"{self.rangers}")
        self.tailor_value.config(text=f"{self.tailor_shops}")
        # building counts
        total_quarry_sites = int(self.quarries + self.resources["QuarrySites"])
        total_mine_sites = int(self.mines + self.resources["MineSites"])
        self.quarry_value.config(text=f"{self.quarries}/{total_quarry_sites}")
        self.mine_value.config(text=f"{self.mines}/{total_mine_sites}")

        # pop tooltip
        lines = [f"peasants {self.peasants}"]
        if self.hunters:
            lines.append(f"hunters {self.hunters}")
        if self.woodsmen:
            lines.append(f"woodsmen {self.woodsmen}")
        if self.bowyers:
            lines.append(f"bowyers {self.bowyers}")
        if self.weavers:
            lines.append(f"weavers {self.weavers}")
        if self.rangers:
            lines.append(f"rangers {self.rangers}")
        if self.lumber_mills:
            lines.append(f"carpenters {self.lumber_mills}")
        if self.farms:
            lines.append(f"farmers {self.farms}")
        if self.smelters:
            lines.append(f"smelters {self.smelters}")
        if self.smithies:
            lines.append(f"smiths {self.smithies}")
        if self.tailor_shops:
            lines.append(f"tailors {self.tailor_shops}")
        self.pop_tooltip.text = "\n".join(lines)

        # building counts
        self.house_value.config(text=f"{self.houses}")
        self.mill_value.config(text=f"{self.lumber_mills}")
        self.farm_value.config(text=f"{self.farms}")
        self.smelter_value.config(text=f"{self.smelters}")
        self.smithy_value.config(text=f"{self.smithies}")

        # unlock rows
        if not self.jobs_unlocked and (
            self.peasants
            + self.hunters
            + self.woodsmen
            + self.bowyers
            + self.weavers
            + self.tailor_shops
            + self.rangers
        ) > 0:
            self.jobs_unlocked = True
        if self.jobs_unlocked:
            if not self.hunter_row.winfo_manager():
                self.hunter_row.pack(anchor="w", pady=(10, 2), fill="x")
            if not self.woods_row.winfo_manager():
                self.woods_row.pack(anchor="w", pady=2, fill="x")
            if self.bowyer_unlocked and not self.bowyer_row.winfo_manager():
                self.bowyer_row.pack(anchor="w", pady=2, fill="x")
            if self.weaver_unlocked and not self.weaver_row.winfo_manager():
                self.weaver_row.pack(anchor="w", pady=2, fill="x")
            if self.ranger_unlocked and not self.ranger_row.winfo_manager():
                self.ranger_row.pack(anchor="w", pady=2, fill="x")
            if self.quarry_unlocked and not self.quarry_row.winfo_manager():
                self.quarry_row.pack(anchor="w", pady=2, fill="x")
            if self.mine_unlocked and not self.mine_row.winfo_manager():
                self.mine_row.pack(anchor="w", pady=2, fill="x")
            if self.smelter_unlocked and not self.smelter_row.winfo_manager():
                self.smelter_row.pack(anchor="w", pady=2, fill="x")
            if self.smithy_unlocked and not self.smithy_row.winfo_manager():
                self.smithy_row.pack(anchor="w", pady=2, fill="x")
            if self.tailor_unlocked and not self.tailor_row.winfo_manager():
                self.tailor_row.pack(anchor="w", pady=2, fill="x")

        if not self.farm_unlocked and self.houses >= 3 and self.resources["Planks"] >= 8:
            self.farm_unlocked = True
            self.set_log("with three homes built, villagers organize their first farm.")
        if self.farm_unlocked and not self.farm_row.winfo_manager():
            self.farm_row.pack(anchor="w", pady=2, fill="x")

        # food breakdown
        if not self.food_breakdown_unlocked and self.hunters > 0 and self.farms > 0:
            self.food_breakdown_unlocked = True
            self.set_log(
                "your people distinguish meat from grain, improving resource management."
            )

        # guts discovery tooltip/log once visible
        if self.guts_unlocked and self.resources["Guts"] > 0 and not self.guts_visible:
            self.guts_visible = True
            self.set_log("hunters begin separating out guts for other uses.")

        if not self.flax_unlocked and self.resources["Skins"] >= SKIN_FLAX_UNLOCK:
            self.flax_unlocked = True
            self.set_log("farmers learn to ready fields for flax during harvests.")
        if not self.weaver_unlocked and self.resources["Flax"] >= 3:
            self.weaver_unlocked = True
            self.set_log("stored flax invites experiments at a simple loom.")
            if self.jobs_unlocked and not self.weaver_row.winfo_manager():
                self.weaver_row.pack(anchor="w", pady=2, fill="x")

        # bowyer unlock gating on inputs
        if (
            not self.bowyer_unlocked
            and self.resources["Guts"] >= 3
            and self.resources["Wood"] >= 6
        ):
            self.bowyer_unlocked = True
            self.set_log("processed wood and guts might form a useful new tool.")
            if self.jobs_unlocked and not self.bowyer_row.winfo_manager():
                self.bowyer_row.pack(anchor="w", pady=2, fill="x")

        if (
            not self.ranger_unlocked
            and self.resources["Bows"] > 0
            and self.resources["Arrows"] > 0
        ):
            self.ranger_unlocked = True
            if self.jobs_unlocked and not self.ranger_row.winfo_manager():
                self.ranger_row.pack(anchor="w", pady=2, fill="x")

        if not self.quarry_unlocked and (
            self.resources["QuarrySites"] > 0 or self.quarries > 0
        ):
            self.quarry_unlocked = True
            if self.jobs_unlocked and not self.quarry_row.winfo_manager():
                self.quarry_row.pack(anchor="w", pady=2, fill="x")

        if not self.mine_unlocked and (self.resources["MineSites"] > 0 or self.mines > 0):
            self.mine_unlocked = True
            if self.jobs_unlocked and not self.mine_row.winfo_manager():
                self.mine_row.pack(anchor="w", pady=2, fill="x")

        if (
            not self.smelter_unlocked
            and (
                self.smelters > 0
                or (
                    self.quarry_unlocked
                    and self.resources["Stone"] >= 8
                    and self.resources["Ore"] >= 1
                )
            )
        ):
            self.smelter_unlocked = True
            if self.jobs_unlocked and not self.smelter_row.winfo_manager():
                self.smelter_row.pack(anchor="w", pady=2, fill="x")

        if (
            not self.smithy_unlocked
            and (self.resources["Stone"] > 0 or self.smithies > 0)
            and (self.resources["Ingots"] > 0 or self.smithies > 0)
        ):
            self.smithy_unlocked = True
            if self.jobs_unlocked and not self.smithy_row.winfo_manager():
                self.smithy_row.pack(anchor="w", pady=2, fill="x")
        if not self.tailor_unlocked and (
            self.resources["Linen"] >= 1 or self.tailor_shops > 0
        ):
            self.tailor_unlocked = True
            self.set_log("a villager offers to tailor garments from your linen stock.")
            self.sticky_resources.update({"Clothing", "Cloaks", "Gambesons"})
            if self.jobs_unlocked and not self.tailor_row.winfo_manager():
                self.tailor_row.pack(anchor="w", pady=2, fill="x")

        # enable/disable buttons based on affordability
        self._update_button_states()

    def _update_button_states(self):

        # upgrades
        if self.peasants <= 0:
            self.btn_hunter_plus.config(state="disabled", bg="#84817a")
            self.btn_woodsman_plus.config(state="disabled", bg="#84817a")
            self.btn_bowyer_plus.config(state="disabled", bg="#84817a")
            self.btn_weaver_plus.config(state="disabled", bg="#84817a")
            self.btn_tailor_plus.config(state="disabled", bg="#84817a")
            self.btn_ranger_plus.config(state="disabled", bg="#84817a")
        else:
            self.btn_hunter_plus.config(state="normal", bg="#33d9b2")
            self.btn_woodsman_plus.config(state="normal", bg="#ffb142")
            if self.bowyer_unlocked:
                self.btn_bowyer_plus.config(state="normal", bg="#eccc68")
            else:
                self.btn_bowyer_plus.config(state="disabled", bg="#84817a")
            if self.weaver_unlocked:
                self.btn_weaver_plus.config(state="normal", bg="#34ace0")
            else:
                self.btn_weaver_plus.config(state="disabled", bg="#84817a")
            if self.tailor_unlocked:
                self.btn_tailor_plus.config(state="normal", bg="#95afc0")
            else:
                self.btn_tailor_plus.config(state="disabled", bg="#84817a")
            # ranger enable handled later when unlocked flag is set

        if self.hunters > 0:
            self.btn_hunter_minus.config(state="normal")
        else:
            self.btn_hunter_minus.config(state="disabled")

        if self.woodsmen > 0:
            self.btn_woodsman_minus.config(state="normal")
        else:
            self.btn_woodsman_minus.config(state="disabled")

        if self.bowyers > 0:
            self.btn_bowyer_minus.config(state="normal")
        else:
            self.btn_bowyer_minus.config(state="disabled")

        if self.weavers > 0:
            self.btn_weaver_minus.config(state="normal")
        else:
            self.btn_weaver_minus.config(state="disabled")

        if self.rangers > 0:
            self.btn_ranger_minus.config(state="normal")
        else:
            self.btn_ranger_minus.config(state="disabled")

        ranger_ready = (
            self.ranger_unlocked
            and self.peasants > 0
            and self.resources["Bows"] >= 1
            and self.resources["Arrows"] >= 10
        )
        if ranger_ready:
            self.btn_ranger_plus.config(state="normal", bg="#70a1ff")
        else:
            self.btn_ranger_plus.config(state="disabled", bg="#84817a")

        # quarries/mines
        if (
            self.quarry_unlocked
            and self.resources["QuarrySites"] >= 1
            and self.resources["Planks"] >= 4
            and self.peasants > 0
        ):
            self.btn_quarry_plus.config(state="normal", bg="#d1ccc0")
        else:
            self.btn_quarry_plus.config(state="disabled", bg="#84817a")

        if (
            self.mine_unlocked
            and self.resources["MineSites"] >= 1
            and self.resources["Planks"] >= 4
            and self.peasants > 0
        ):
            self.btn_mine_plus.config(state="normal", bg="#d1ccc0")
        else:
            self.btn_mine_plus.config(state="disabled", bg="#84817a")

        # recruit
        recruitable = (
            self.total_pop < self.pop_cap
            and (self.resources["Meat"] + self.resources["Grain"]) >= 2
        )
        if recruitable:
            self.btn_peasant_plus.config(state="normal", bg="#706fd3")
        else:
            self.btn_peasant_plus.config(state="disabled", bg="#84817a")

        if self.peasants > 0:
            self.btn_peasant_minus.config(state="normal")
        else:
            self.btn_peasant_minus.config(state="disabled")

        # buildings
        if self.resources["Wood"] >= 20 and self.peasants > 0:
            self.btn_mill_plus.config(state="normal", bg="#2ecc71")
        else:
            self.btn_mill_plus.config(state="disabled", bg="#84817a")

        if self.resources["Planks"] >= 10:
            self.btn_house_plus.config(state="normal", bg="#f7d794")
        else:
            self.btn_house_plus.config(state="disabled", bg="#84817a")

        if self.resources["Planks"] >= 8 and self.peasants > 0:
            self.btn_farm_plus.config(state="normal", bg="#f5cd79")
        else:
            self.btn_farm_plus.config(state="disabled", bg="#84817a")

        if (
            self.smelter_unlocked
            and self.resources["Stone"] >= 8
            and self.resources["Planks"] >= 2
            and self.peasants > 0
        ):
            self.btn_smelter_plus.config(state="normal", bg="#ffd32a")
        else:
            self.btn_smelter_plus.config(state="disabled", bg="#84817a")

        if (
            self.smithy_unlocked
            and self.resources["Stone"] >= 4
            and self.resources["Planks"] >= 10
            and self.peasants > 0
        ):
            self.btn_smithy_plus.config(state="normal", bg="#ffa502")
        else:
            self.btn_smithy_plus.config(state="disabled", bg="#84817a")

        if (
            self.tailor_unlocked
            and self.resources["Planks"] >= 6
            and self.peasants > 0
        ):
            self.btn_tailor_plus.config(state="normal", bg="#95afc0")
        else:
            self.btn_tailor_plus.config(state="disabled", bg="#84817a")

        # abandon buttons
        if self.lumber_mills > 0:
            self.btn_mill_minus.config(state="normal")
        else:
            self.btn_mill_minus.config(state="disabled")

        if self.farms > 0:
            self.btn_farm_minus.config(state="normal")
        else:
            self.btn_farm_minus.config(state="disabled")

        if self.smelters > 0:
            self.btn_smelter_minus.config(state="normal")
        else:
            self.btn_smelter_minus.config(state="disabled")

        if self.smithies > 0:
            self.btn_smithy_minus.config(state="normal")
        else:
            self.btn_smithy_minus.config(state="disabled")

        if self.tailor_shops > 0:
            self.btn_tailor_minus.config(state="normal")
        else:
            self.btn_tailor_minus.config(state="disabled")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Kingdom Clicker.")
    parser.add_argument(
        "--state",
        type=str,
        help="Path to JSON file with starting state overrides.",
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

    root = tk.Tk()
    app = KingdomIdlePOC(root, initial_state=initial_state)
    root.mainloop()
