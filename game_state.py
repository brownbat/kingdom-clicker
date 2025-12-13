import random
from typing import Dict, List, Optional

TICK_MS = 1000  # game tick in milliseconds
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
FARM_FLAX_YIELD = 1.5  # doubled flax output to support 4 farms per weaver target
SKIN_FLAX_UNLOCK = 5
RANGER_DRAW_TICKS = 10
STARVATION_PENALTY = 0.75
WEAVER_LINEN_TIME = 10.0  # slower loom pace to balance flax supply/demand
TAILOR_WORK_TIME = 11.0  # slow tailors ~10% to ease linen drain versus weaving
SMITHY_WORK_TIME = 1.0

RECIPES: Dict[str, Dict[str, Dict[str, float] | float]] = {
    "weave_linen": {"input": {"Flax": 1}, "output": {"Linen": 1}, "time": WEAVER_LINEN_TIME},
    "craft_arrows": {"input": {"Feathers": 20, "Wood": 2}, "output": {"Arrows": 20}, "time": BOWYER_BOW_TIME},
    "craft_bow": {"input": {"Wood": 3, "Guts": 1}, "output": {"Bows": 1}, "time": BOWYER_BOW_TIME},
    "smith_sword": {"input": {"Ingots": 3}, "output": {"Swords": 1}, "time": SMITHY_WORK_TIME},
    "smith_tool": {"input": {"Ingots": 1, "Wood": 1}, "output": {"Tools": 1}, "time": SMITHY_WORK_TIME},
    "smith_dagger": {"input": {"Ingots": 1}, "output": {"Daggers": 1}, "time": SMITHY_WORK_TIME},
    "tailor_clothing": {"input": {"Linen": 1}, "output": {"Clothing": 1}, "time": TAILOR_WORK_TIME},
    "tailor_cloak": {"input": {"Linen": 1, "Pelts": 1}, "output": {"Cloaks": 1}, "time": TAILOR_WORK_TIME},
    "tailor_gambeson": {"input": {"Linen": 2, "Pelts": 1}, "output": {"Gambesons": 1}, "time": TAILOR_WORK_TIME},
}


class JobProcessor:
    def __init__(self, worker_count: int = 1):
        self.worker_count = worker_count
        self.current_recipe: Optional[str] = None
        self.progress: float = 0.0
        self.reserved_inputs: Dict[str, float] = {}
        self.reserved_output: Optional[tuple[str, str, float]] = None

    def start_job(self, recipe_id: str, state: "GameState") -> bool:
        if self.current_recipe is not None:
            return False
        recipe = RECIPES.get(recipe_id)
        if not recipe:
            return False
        if not state._reserve_for_job(self, recipe_id):
            return False
        self.current_recipe = recipe_id
        self.progress = 0.0
        return True

    def tick(self, speed_mult: float = 1.0):
        if self.current_recipe is None:
            return
        self.progress += speed_mult * self.worker_count

    def complete_job(self, state: "GameState") -> Optional[str]:
        if self.current_recipe is None:
            return None
        recipe_id = self.current_recipe
        recipe = RECIPES.get(recipe_id)
        if not recipe:
            return None
        if self.progress < recipe["time"]:
            return None
        finished = state._deliver_job_output(self)
        return finished


class GameState:
    def __init__(self, initial_state: Optional[dict] = None):
        # resources
        self.resources: Dict[str, float] = {
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
        self.log_history: List[str] = [self.log_text]
        self.pending_logs: List[str] = []
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
        self.bowyer_progress: List[float] = []
        self.weaver_progress: List[float] = []
        self.tailor_progress: List[float] = []
        self.total_meat_made = 0.0
        self.season_tick = 0
        self.season_phase = 0
        self.season_icons = ["🌱", "☀️", "🍂", "❄️"]
        self.current_season_icon = self.season_icons[0]
        self.resource_grid_cols = 5
        self.sticky_resources = set()
        self.site_deck: List[str] = []
        self.deck_seeded = False
        self.deck_refreshed_at_60 = False
        self.ranger_tick_counter = 0
        self.ranger_draw_pool = 0.0
        self.ranger_swords_equipped = 0
        self.weaver_jobs: List[JobProcessor] = []
        self.tailor_jobs: List[JobProcessor] = []
        self.bowyer_jobs: List[JobProcessor] = []
        self.smithy_jobs: List[JobProcessor] = []
        self.first_linen_announced = False
        self.quarries_discovered = 0
        self.mines_discovered = 0
        self.quarries = 0
        self.mines = 0
        self.cellars = 0
        self.warehouses = 0
        self.cellars = 0
        self.warehouses = 0
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
        self.reserved_outputs: Dict[str, float] = {}
        self.reserved_cellar_slots: float = 0.0
        self.cellar_capacity: float = 0.0
        self.cellar: Dict[str, float] = {}

        # apply overrides from json state file
        self._apply_initial_state(initial_state or {})
        self._sync_food_total()
        self.process_unlocks(initial=True)

    # --------- helpers ---------

    def add_log(self, text: str):
        self.pending_logs.append(text)
        self.log_text = text
        self.log_history.append(text)
        self.log_history = self.log_history[-5:]

    def set_log(self, text: str):
        self.add_log(text)

    def consume_logs(self) -> List[str]:
        logs = list(self.pending_logs)
        self.pending_logs.clear()
        return logs

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

    def _sync_food_total(self):
        """Keep display food in sync with meat + grain."""
        self.resources["Food"] = max(
            0.0, self.resources["Meat"] + self.resources["Grain"]
        )

    def _resource_cap(self, name: str) -> Optional[float]:
        caps = {
            "Meat": lambda s: 30 + 10 * s.houses,
            "Grain": lambda s: 30 + 30 * s.farms,
            "Pelts": lambda s: 20 + 5 * s.houses,
            "Wood": lambda s: 20 + 10 * s.houses + 30 * s.lumber_mills,
            "Planks": lambda s: 20 + 40 * s.lumber_mills,
            "Arrows": lambda s: 60 + 60 * s.bowyers,
            "Bows": lambda s: 10 + 10 * s.bowyers,
            "Cloaks": lambda s: 10 * s.tailors,
            "Clothing": lambda s: 15 * s.tailors,
            "Daggers": lambda s: 10 * s.smithies,
            "Feathers": lambda s: 25 * s.houses,
            "Flax": lambda s: 30 * s.farms,
            "Gambesons": lambda s: 5 * s.tailors,
            "Guts": lambda s: 10 + 3 * s.houses,
            "Ingots": lambda s: 30 * s.smelters,
            "Linen": lambda s: 15 * s.weavers,
            "Ore": lambda s: 60 * s.mines,
            "Skins": lambda s: 20 + 10 * s.houses,
            "Stone": lambda s: 80 * s.quarries,
            "Swords": lambda s: 5 * s.smithies,
            "Tools": lambda s: 15 * s.smithies,
        }
        fn = caps.get(name)
        return float(fn(self)) if fn else None

    def _reserved_output_total(self, name: str) -> float:
        return self.reserved_outputs.get(name, 0.0)

    def _reserved_cellar_slots_total(self) -> float:
        return self.reserved_cellar_slots

    def _cellar_used(self) -> float:
        return sum(self.cellar.values())

    def _all_jobs(self) -> List[JobProcessor]:
        return self.weaver_jobs + self.tailor_jobs + self.bowyer_jobs + self.smithy_jobs

    def _clear_job_reservations(self, processor: JobProcessor):
        processor.reserved_inputs = {}
        processor.reserved_output = None

    def _rebuild_reservations(self):
        self.reserved_outputs = {}
        self.reserved_cellar_slots = 0.0
        for job in self._all_jobs():
            if job.reserved_output:
                dest_type, item, qty = job.reserved_output
                if dest_type == "normal":
                    self.reserved_outputs[item] = self.reserved_outputs.get(item, 0.0) + qty
                elif dest_type == "cellar":
                    self.reserved_cellar_slots += qty

    def _reserve_for_job(self, processor: JobProcessor, recipe_id: str) -> bool:
        recipe = RECIPES.get(recipe_id)
        if not recipe:
            return False
        # check inputs
        for res, amt in recipe["input"].items():
            if self.resources.get(res, 0.0) < amt:
                return False
        out_item = list(recipe["output"].keys())[0]
        out_amt = recipe["output"][out_item]

        cap = self._resource_cap(out_item)
        reserved_out = self._reserved_output_total(out_item)
        normal_space = (cap - self.resources.get(out_item, 0.0) - reserved_out) if cap is not None else float("inf")
        dest: Optional[tuple[str, str, float]] = None
        if normal_space >= out_amt:
            dest = ("normal", out_item, out_amt)
            self.reserved_outputs[out_item] = self.reserved_outputs.get(out_item, 0.0) + out_amt
        else:
            cellar_space = self.cellar_capacity - self._cellar_used() - self._reserved_cellar_slots_total()
            if cellar_space >= out_amt:
                dest = ("cellar", out_item, out_amt)
                self.reserved_cellar_slots += out_amt
        if dest is None:
            return False

        for res, amt in recipe["input"].items():
            self.resources[res] = self.resources.get(res, 0.0) - amt
        processor.reserved_inputs = dict(recipe["input"])
        processor.reserved_output = dest
        return True

    def _deliver_job_output(self, processor: JobProcessor) -> Optional[str]:
        recipe_id = processor.current_recipe
        if not recipe_id:
            return None
        recipe = RECIPES.get(recipe_id)
        if not recipe:
            return None
        if not processor.reserved_output:
            return None
        dest_type, out_item, out_amt = processor.reserved_output
        if dest_type == "normal":
            self.resources[out_item] = self.resources.get(out_item, 0.0) + out_amt
            self.reserved_outputs[out_item] = max(0.0, self.reserved_outputs.get(out_item, 0.0) - out_amt)
        elif dest_type == "cellar":
            self.cellar[out_item] = self.cellar.get(out_item, 0.0) + out_amt
            self.reserved_cellar_slots = max(0.0, self.reserved_cellar_slots - out_amt)
        self._clear_job_reservations(processor)
        processor.current_recipe = None
        processor.progress = 0.0
        return recipe_id

    def _cancel_job(self, processor: JobProcessor):
        # return reserved inputs
        for res, amt in processor.reserved_inputs.items():
            self.resources[res] = self.resources.get(res, 0.0) + amt
        if processor.reserved_output:
            dest_type, out_item, out_amt = processor.reserved_output
            if dest_type == "normal":
                self.reserved_outputs[out_item] = max(0.0, self.reserved_outputs.get(out_item, 0.0) - out_amt)
            elif dest_type == "cellar":
                self.reserved_cellar_slots = max(0.0, self.reserved_cellar_slots - out_amt)
        self._clear_job_reservations(processor)
        processor.current_recipe = None
        processor.progress = 0.0

    def _can_accept_output(self, recipe_id: str) -> bool:
        recipe = RECIPES.get(recipe_id)
        if not recipe:
            return False
        for res, amt in recipe["output"].items():
            cap = self._resource_cap(res)
            reserved_out = self._reserved_output_total(res)
            normal_space = (cap - self.resources.get(res, 0.0) - reserved_out) if cap is not None else float("inf")
            if normal_space < amt:
                cellar_space = self.cellar_capacity - self._cellar_used() - self._reserved_cellar_slots_total()
                if cellar_space < amt:
                    return False
        return True

    def _apply_caps(self):
        for name, val in list(self.resources.items()):
            cap = self._resource_cap(name)
            if cap is not None and val > cap:
                self.resources[name] = cap

    def _reserved_output_total(self, name: str) -> float:
        return self.reserved_outputs.get(name, 0.0)

    def _reserved_cellar_slots_total(self) -> float:
        return self.reserved_cellar_slots

    def _cellar_used(self) -> float:
        return sum(self.cellar.values())

    def _all_jobs(self) -> List[JobProcessor]:
        return self.weaver_jobs + self.tailor_jobs + self.bowyer_jobs + self.smithy_jobs

    def _clear_job_reservations(self, processor: JobProcessor):
        processor.reserved_inputs = {}
        processor.reserved_output = None

    def _rebuild_reservations(self):
        self.reserved_outputs = {}
        self.reserved_cellar_slots = 0.0
        for job in self._all_jobs():
            if job.reserved_output:
                dest_type, item, qty = job.reserved_output
                if dest_type == "normal":
                    self.reserved_outputs[item] = self.reserved_outputs.get(item, 0.0) + qty
                elif dest_type == "cellar":
                    self.reserved_cellar_slots += qty

    # --------- state serialization ---------

    def _serialize_jobs(self, jobs: List[JobProcessor]) -> List[Dict[str, float | str | int | None]]:
        return [
            {
                "current_recipe": job.current_recipe,
                "progress": job.progress,
                "worker_count": job.worker_count,
                "reserved_inputs": job.reserved_inputs,
                "reserved_output": list(job.reserved_output) if job.reserved_output else None,
            }
            for job in jobs
        ]

    def _deserialize_jobs(self, data: list) -> List[JobProcessor]:
        jobs: List[JobProcessor] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            worker_count = int(item.get("worker_count", 1) or 1)
            job = JobProcessor(worker_count=worker_count)
            if item.get("current_recipe"):
                job.current_recipe = item["current_recipe"]
            try:
                job.progress = float(item.get("progress", 0.0))
            except (TypeError, ValueError):
                job.progress = 0.0
            if isinstance(item.get("reserved_inputs"), dict):
                job.reserved_inputs = {
                    k: float(v) if isinstance(v, (int, float)) else 0.0 for k, v in item["reserved_inputs"].items()
                }
            reserved_output = item.get("reserved_output")
            if isinstance(reserved_output, list) and len(reserved_output) == 3:
                dest_type, out_item, qty = reserved_output
                try:
                    qty_val = float(qty)
                    job.reserved_output = (str(dest_type), str(out_item), qty_val)
                except (TypeError, ValueError):
                    job.reserved_output = None
            jobs.append(job)
        return jobs

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
            "cellars",
            "warehouses",
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
            self.weaver_jobs = self._deserialize_jobs(state["weaver_jobs"])
        if isinstance(state.get("tailor_jobs"), list):
            self.tailor_jobs = self._deserialize_jobs(state["tailor_jobs"])
        if isinstance(state.get("bowyer_jobs"), list):
            self.bowyer_jobs = self._deserialize_jobs(state["bowyer_jobs"])
        if isinstance(state.get("smithy_jobs"), list):
            self.smithy_jobs = self._deserialize_jobs(state["smithy_jobs"])
        if isinstance(state.get("cellar"), dict):
            self.cellar = {k: float(v) for k, v in state["cellar"].items()}
        if "cellar_capacity" in state:
            try:
                self.cellar_capacity = float(state["cellar_capacity"])
            except (TypeError, ValueError):
                self.cellar_capacity = 0.0
        else:
            self.cellar_capacity = self.cellars * 40 + self.warehouses * 260
        if isinstance(state.get("reserved_outputs"), dict):
            self.reserved_outputs = {k: float(v) for k, v in state["reserved_outputs"].items()}
        if "reserved_cellar_slots" in state:
            try:
                self.reserved_cellar_slots = float(state["reserved_cellar_slots"])
            except (TypeError, ValueError):
                pass
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
                "Gambesons": state["tailor_last_crafted"].get(
                    "Gambesons", state["tailor_last_crafted"].get("PaddedArmor", -1)
                ),
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
        self._rebuild_reservations()

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
            "bowyer_jobs": self._serialize_jobs(self.bowyer_jobs),
            "weaver_jobs": self._serialize_jobs(self.weaver_jobs),
            "tailor_jobs": self._serialize_jobs(self.tailor_jobs),
            "smithy_jobs": self._serialize_jobs(self.smithy_jobs),
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
            "cellar": self.cellar,
            "cellar_capacity": self.cellar_capacity,
            "reserved_outputs": self.reserved_outputs,
            "reserved_cellar_slots": self.reserved_cellar_slots,
        }

    def _load_state_dict(self, state: dict):
        # reset key fields to defaults before applying new state
        self.__init__(initial_state=state)

    # --------- actions ---------

    def action_recruit_peasant(self):
        if self.total_pop >= self.pop_cap:
            self.add_log("you need more housing before recruiting more peasants.")
            return
        # recruiting costs a bit of food
        if (self.resources["Meat"] + self.resources["Grain"]) < 2:
            self.add_log("not enough food to support another mouth.")
            return

        # consume from meat first, then grain
        cost = 2
        consumed_from_meat = min(cost, self.resources["Meat"])
        self.resources["Meat"] -= consumed_from_meat
        remaining_cost = cost - consumed_from_meat
        if remaining_cost > 0:
            self.resources["Grain"] -= remaining_cost

        self.peasants += 1
        self.add_log("a new peasant joins your fledgling settlement.")
        self._sync_food_total()

    def action_fire_peasant(self):
        if self.peasants <= 0:
            self.add_log("no idle peasants to send away.")
            return
        self.peasants -= 1
        self.total_pop  # trigger property for clarity
        self.add_log("a peasant departs, leaving your camp quieter.")

    def action_add_hunter(self):
        if self.peasants <= 0:
            self.add_log("no idle peasants to turn into hunters.")
            return
        self.peasants -= 1
        self.hunters += 1
        if self.resources.get("Bows", 0) > 0:
            self.add_log("a peasant strings a bow and joins the hunt.")
        else:
            self.add_log("a peasant sharpens a stick and ventures out to hunt.")

    def action_remove_hunter(self):
        if self.hunters <= 0:
            self.add_log("no hunters to reassign.")
            return
        self.hunters -= 1
        self.peasants += 1
        self.hunter_bows_equipped = min(self.hunter_bows_equipped, self.hunters)
        self.add_log("a hunter lays down their bow and returns as a peasant.")

    def action_add_woodsman(self):
        if self.peasants <= 0:
            self.add_log("no idle peasants to send into the woods.")
            return
        self.peasants -= 1
        self.woodsmen += 1
        self.add_log("a peasant grips a stone hatchet and starts felling trees.")

    def action_remove_woodsman(self):
        if self.woodsmen <= 0:
            self.add_log("no woodsmen to reassign.")
            return
        self.woodsmen -= 1
        self.peasants += 1
        self.add_log("a woodsman returns to the village as a peasant.")

    def action_add_bowyer(self):
        if not self.bowyer_unlocked:
            self.add_log("you need better materials before anyone can craft bows.")
            return
        if self.peasants <= 0:
            self.add_log("no idle peasants to put to the bowyer's bench.")
            return
        self.peasants -= 1
        self.bowyers += 1
        self.bowyer_jobs.append(JobProcessor())
        self.add_log("a peasant starts shaping staves and stringing crude bows.")

    def action_remove_bowyer(self):
        if self.bowyers <= 0:
            self.add_log("no bowyers to reassign.")
            return
        self.bowyers -= 1
        self.peasants += 1
        if self.bowyer_jobs:
            job = self.bowyer_jobs.pop()
            self._cancel_job(job)
        self.add_log("a bowyer leaves the bench and returns as a peasant.")

    def action_add_weaver(self):
        if not self.weaver_unlocked:
            self.add_log("you need some flax before anyone can try weaving.")
            return
        if self.peasants <= 0:
            self.add_log("no idle peasants to put to the loom.")
            return
        self.peasants -= 1
        self.weavers += 1
        self.weaver_jobs.append(JobProcessor())
        self.add_log("a peasant begins spinning flax into rough linen.")

    def action_remove_weaver(self):
        if self.weavers <= 0:
            self.add_log("no weavers to reassign.")
            return
        self.weavers -= 1
        self.peasants += 1
        if self.weaver_jobs:
            job = self.weaver_jobs.pop()
            self._cancel_job(job)
        self.add_log("a weaver leaves the loom and returns as a peasant.")

    def action_add_ranger(self):
        if not self.ranger_unlocked:
            self.add_log("you need bows and arrows ready before training rangers.")
            return
        if self.peasants <= 0:
            self.add_log("no idle peasants to train as rangers.")
            return
        bow_cost = 1
        arrow_cost = 10
        if self.resources["Bows"] < bow_cost or self.resources["Arrows"] < arrow_cost:
            self.add_log("you need a bow and arrows ready to outfit a ranger.")
            return
        self.resources["Bows"] -= bow_cost
        self.resources["Arrows"] -= arrow_cost
        if self.resources.get("Swords", 0) >= 1:
            self.resources["Swords"] -= 1
            self.ranger_swords_equipped += 1
        self.peasants -= 1
        self.rangers += 1
        self.add_log("a peasant takes bow and arrows, ranging beyond the village.")

    def action_remove_ranger(self):
        if self.rangers <= 0:
            self.add_log("no rangers to recall.")
            return
        self.rangers -= 1
        self.peasants += 1
        self.ranger_swords_equipped = min(self.ranger_swords_equipped, self.rangers)
        self.add_log("a ranger returns to the village as a peasant.")

    def action_build_lumber_mill(self):
        cost_wood = 20
        if self.resources["Wood"] < cost_wood:
            self.add_log("not enough wood for a lumber mill.")
            return
        if self.peasants <= 0:
            self.add_log(
                "everyone is busy (idle peasants 0). free a worker to staff the mill."
            )
            return
        self.resources["Wood"] -= cost_wood
        self.peasants -= 1
        self.lumber_mills += 1
        self.add_log("you raise a simple lumber mill. one peasant now works there.")

    def action_build_house(self):
        cost_planks = 10
        if self.resources["Planks"] < cost_planks:
            self.add_log("not enough planks to build a house.")
            return
        self.resources["Planks"] -= cost_planks
        self.houses += 1
        self.add_log("a new house is built. more peasants can be housed.")

    def action_build_farm(self):
        cost_planks = 8
        if self.resources["Planks"] < cost_planks:
            self.add_log("not enough planks to build a farm.")
            return
        if self.peasants <= 0:
            self.add_log(
                "everyone is busy (idle peasants 0). free a worker to tend the farm."
            )
            return
        self.resources["Planks"] -= cost_planks
        self.peasants -= 1
        self.farms += 1
        self.add_log("fields are tilled. a peasant now toils as a farmer.")

    def action_build_quarry(self):
        cost_planks = 4
        if self.resources["QuarrySites"] <= 0:
            self.add_log("you need a quarry site before building a quarry.")
            return
        if self.resources["Planks"] < cost_planks:
            self.add_log("not enough planks to build a quarry.")
            return
        if self.peasants <= 0:
            self.add_log("everyone is busy (idle peasants 0). free a worker for the quarry.")
            return
        self.resources["Planks"] -= cost_planks
        self.resources["QuarrySites"] -= 1
        self.peasants -= 1
        self.quarries += 1
        self.add_log("a quarry is established; stone can be cut here.")

    def action_build_mine(self):
        cost_planks = 4
        if self.resources["MineSites"] <= 0:
            self.add_log("you need an ore site before digging a mine.")
            return
        if self.resources["Planks"] < cost_planks:
            self.add_log("not enough planks to shore up a mine entrance.")
            return
        if self.peasants <= 0:
            self.add_log("everyone is busy (idle peasants 0). free a worker for the mine.")
            return
        self.resources["Planks"] -= cost_planks
        self.resources["MineSites"] -= 1
        self.peasants -= 1
        self.mines += 1
        self.add_log("a mine entrance is dug; ore extraction can begin.")

    def action_build_cellar(self):
        cost_planks = 6
        cost_meat = 5
        cost_grain = 5
        if self.resources["Planks"] < cost_planks:
            self.add_log("not enough planks to dig out a cellar.")
            return
        if (self.resources["Meat"] < cost_meat) or (self.resources["Grain"] < cost_grain):
            self.add_log("stockpile 5 meat and 5 grain before digging a cellar.")
            return
        self.resources["Planks"] -= cost_planks
        self.resources["Meat"] -= cost_meat
        self.resources["Grain"] -= cost_grain
        self.cellars += 1
        self.cellar_capacity += 40
        self.add_log("a cool cellar is dug, adding 40 storage slots.")

    def action_build_warehouse(self):
        cost_planks = 12
        cost_stone = 6
        if self.cellars <= 0:
            self.add_log("build a cellar first before raising a warehouse.")
            return
        if self.resources["Stone"] < cost_stone:
            self.add_log("not enough stone to raise a warehouse.")
            return
        if self.resources["Planks"] < cost_planks:
            self.add_log("not enough planks to frame a warehouse.")
            return
        self.resources["Stone"] -= cost_stone
        self.resources["Planks"] -= cost_planks
        self.warehouses += 1
        self.cellar_capacity += 260
        self.add_log("a warehouse goes up, adding 260 storage slots.")

    def action_abandon_cellar(self):
        if self.cellars <= 0:
            self.add_log("no cellars to fill in.")
            return
        self.cellars -= 1
        self.cellar_capacity = max(0.0, self.cellar_capacity - 40)
        # trim cellar contents if over capacity
        overflow = max(0.0, self._cellar_used() - self.cellar_capacity)
        if overflow > 0 and self.cellar:
            for item in list(self.cellar.keys()):
                if overflow <= 0:
                    break
                take = min(self.cellar[item], overflow)
                self.cellar[item] -= take
                overflow -= take
                if self.cellar[item] <= 0:
                    del self.cellar[item]
        self.add_log("a cellar is filled in, freeing the land.")

    def action_abandon_warehouse(self):
        if self.warehouses <= 0:
            self.add_log("no warehouses to dismantle.")
            return
        self.warehouses -= 1
        self.cellar_capacity = max(0.0, self.cellar_capacity - 260)
        overflow = max(0.0, self._cellar_used() - self.cellar_capacity)
        if overflow > 0 and self.cellar:
            for item in list(self.cellar.keys()):
                if overflow <= 0:
                    break
                take = min(self.cellar[item], overflow)
                self.cellar[item] -= take
                overflow -= take
                if self.cellar[item] <= 0:
                    del self.cellar[item]
        self.add_log("a warehouse is dismantled, reducing storage space.")

    def action_build_smelter(self):
        cost_planks = 2
        cost_stone = 8
        if self.resources["Stone"] < cost_stone:
            self.add_log("not enough stone to build a smelter.")
            return
        if self.resources["Planks"] < cost_planks:
            self.add_log("not enough planks to shore up the smelter.")
            return
        if self.peasants <= 0:
            self.add_log("everyone is busy (idle peasants 0). free a worker for the smelter.")
            return
        self.resources["Stone"] -= cost_stone
        self.resources["Planks"] -= cost_planks
        self.peasants -= 1
        self.smelters += 1
        self.add_log("a smelter is built; ore can now be refined into ingots.")

    def action_build_smithy(self):
        cost_planks = 10
        cost_stone = 4
        if self.resources["Stone"] < cost_stone:
            self.add_log("not enough stone to build a smithy.")
            return
        if self.resources["Planks"] < cost_planks:
            self.add_log("not enough planks to raise a smithy.")
            return
        if self.peasants <= 0:
            self.add_log("everyone is busy (idle peasants 0). free a worker for the smithy.")
            return
        self.resources["Stone"] -= cost_stone
        self.resources["Planks"] -= cost_planks
        self.peasants -= 1
        self.smithies += 1
        self.smithy_jobs.append(JobProcessor())
        self.add_log("a smithy is built; metalwork can begin.")

    def action_build_tailor(self):
        cost_planks = 6
        if not self.tailor_unlocked:
            self.add_log("you need linen in stores before a tailor will set up shop.")
            return
        if self.resources["Planks"] < cost_planks:
            self.add_log("not enough planks to build a tailor's shop.")
            return
        if self.peasants <= 0:
            self.add_log("everyone is busy (idle peasants 0). free a worker for tailoring.")
            return
        self.resources["Planks"] -= cost_planks
        self.peasants -= 1
        self.tailor_shops += 1
        self.tailors += 1
        self.tailor_jobs.append(JobProcessor())
        self.sticky_resources.update({"Clothing", "Cloaks", "Gambesons"})
        self.add_log("a tailor sets up a modest shop, ready to sew garments.")

    def action_abandon_lumber_mill(self):
        if self.lumber_mills <= 0:
            self.add_log("no lumber mills to abandon.")
            return
        self.lumber_mills -= 1
        self.peasants += 1
        self.add_log("you shutter a lumber mill. its worker returns as an idle peasant.")

    def action_abandon_farm(self):
        if self.farms <= 0:
            self.add_log("no farms to abandon.")
            return
        self.farms -= 1
        self.peasants += 1
        self.add_log("you let a farm go fallow. its worker returns as an idle peasant.")

    def action_abandon_smelter(self):
        if self.smelters <= 0:
            self.add_log("no smelters to close.")
            return
        self.smelters -= 1
        self.peasants += 1
        self.add_log("you bank a smelter's fires. its worker returns as an idle peasant.")

    def action_abandon_smithy(self):
        if self.smithies <= 0:
            self.add_log("no smithies to shutter.")
            return
        self.smithies -= 1
        self.peasants += 1
        if self.smithy_jobs:
            job = self.smithy_jobs.pop()
            self._cancel_job(job)
        self.add_log("you close a smithy. its worker returns as an idle peasant.")

    def action_abandon_tailor(self):
        if self.tailor_shops <= 0:
            self.add_log("no tailors to send away.")
            return
        self.tailor_shops -= 1
        self.tailors = max(0, self.tailor_shops)
        self.peasants += 1
        if self.tailor_jobs and len(self.tailor_jobs) > self.tailor_shops:
            to_remove = self.tailor_jobs[self.tailor_shops :]
            for job in to_remove:
                self._cancel_job(job)
            self.tailor_jobs = self.tailor_jobs[: self.tailor_shops]
        self.add_log("a tailor closes shop, returning as an idle peasant.")

    # --------- job helpers ---------

    def _smithy_pick_target(self, choice: str):
        stocks = {
            "sword": (self.resources.get("Swords", 0.0), self._resource_cap("Swords")),
            "dagger": (self.resources.get("Daggers", 0.0), self._resource_cap("Daggers")),
            "tool": (self.resources.get("Tools", 0.0), self._resource_cap("Tools")),
        }

        def has_room(item):
            val, cap = stocks[item]
            return cap is None or val < cap

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

    def _tailor_can_craft(self, target: str) -> bool:
        if target == "clothing":
            return self.resources["Linen"] >= 1
        if target == "cloak":
            return self.resources["Linen"] >= 1 and self.resources["Pelts"] >= 1
        if target == "gambeson":
            return self.resources["Linen"] >= 2 and self.resources["Pelts"] >= 1
        return False

    def _tailor_pick_target(self, choice: str):
        stocks = {
            "clothing": self.resources.get("Clothing", 0.0),
            "cloak": self.resources.get("Cloaks", 0.0),
            "gambeson": self.resources.get("Gambesons", 0.0),
        }

        def ready(item: str) -> bool:
            return self._tailor_can_craft(item)

        if choice in ("clothing", "cloak", "gambeson"):
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
                "cloak": self.tailor_last_crafted.get("Cloaks", -1),
                "gambeson": self.tailor_last_crafted.get("Gambesons", -1),
            }
            min_last = min(last_map[k] for k in candidates)
            stalest = [k for k in candidates if last_map[k] == min_last]
            return random.choice(stalest)

        return None

    def _ensure_deck(self):
        # refresh once at pop 60 by adding new cards on top of the existing deck
        if self.total_pop >= 60 and not self.deck_refreshed_at_60:
            self.site_deck += self._build_deck(high_pop=True)
            random.shuffle(self.site_deck)
            self.deck_refreshed_at_60 = True
        if not self.site_deck and not self.deck_seeded:
            self.site_deck = self._build_deck(high_pop=False)
            self.deck_seeded = True

    def _build_deck(self, high_pop: bool):
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
        self.add_log(log_map.get(card, f"rangers discover a {card}."))

    def _tick_season(self):
        prev_phase = self.season_phase
        self.season_tick += 1
        phase = (self.season_tick // 15) % 4
        first_tick = self.season_tick == 1
        phase_changed = phase != prev_phase
        if first_tick or phase_changed:
            self.season_phase = phase
            self.current_season_icon = self.season_icons[phase]
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
                    self.add_log(f"summer harvest brings in {int(harvest)} grain.")
        else:
            self.current_season_icon = self.season_icons[phase]

    def _ensure_job_slots(self, jobs: List[JobProcessor], desired: int) -> List[JobProcessor]:
        if len(jobs) < desired:
            jobs += [JobProcessor() for _ in range(desired - len(jobs))]
        elif len(jobs) > desired:
            to_remove = jobs[desired:]
            for job in to_remove:
                self._cancel_job(job)
            jobs = jobs[:desired]
        return jobs

    def process_unlocks(self, initial: bool = False):
        previous_jobs_unlocked = self.jobs_unlocked
        if not self.jobs_unlocked and self.total_pop > 0:
            self.jobs_unlocked = True
        if not self.farm_unlocked and self.houses >= 3 and self.resources["Planks"] >= 8:
            self.farm_unlocked = True
            self.add_log("with three homes built, villagers organize their first farm.")
        if (
            not self.food_breakdown_unlocked
            and self.hunters > 0
            and self.farms > 0
        ):
            self.food_breakdown_unlocked = True
            self.add_log(
                "your people distinguish meat from grain, improving resource management."
            )

        if self.guts_unlocked and self.resources["Guts"] > 0 and not self.guts_visible:
            self.guts_visible = True
            self.add_log("hunters begin separating out guts for other uses.")

        if not self.flax_unlocked and self.resources["Skins"] >= SKIN_FLAX_UNLOCK:
            self.flax_unlocked = True
            self.add_log("farmers learn to ready fields for flax during harvests.")
        if not self.weaver_unlocked and self.resources["Flax"] >= 3:
            self.weaver_unlocked = True
            self.add_log("stored flax invites experiments at a simple loom.")

        if (
            not self.bowyer_unlocked
            and self.resources["Guts"] >= 3
            and self.resources["Wood"] >= 6
        ):
            self.bowyer_unlocked = True
            self.add_log("processed wood and guts might form a useful new tool.")

        if (
            not self.ranger_unlocked
            and self.resources["Bows"] > 0
            and self.resources["Arrows"] > 0
        ):
            self.ranger_unlocked = True

        if not self.quarry_unlocked and (
            self.resources["QuarrySites"] > 0 or self.quarries > 0
        ):
            self.quarry_unlocked = True

        if not self.mine_unlocked and (self.resources["MineSites"] > 0 or self.mines > 0):
            self.mine_unlocked = True

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

        if (
            not self.smithy_unlocked
            and (self.resources["Stone"] > 0 or self.smithies > 0)
            and (self.resources["Ingots"] > 0 or self.smithies > 0)
        ):
            self.smithy_unlocked = True

        if not self.tailor_unlocked and (
            self.resources["Linen"] >= 1 or self.tailor_shops > 0
        ):
            self.tailor_unlocked = True
            self.add_log("a villager offers to tailor garments from your linen stock.")

        if self.jobs_unlocked and not previous_jobs_unlocked and initial:
            self.pending_logs = list(self.pending_logs)

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
                self.add_log("hunters begin separating out guts for other uses.")
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
                    self.add_log("smelters pour their first crude ingots.")

        # production: smithies (craft tools/weapons)
        self.smithy_jobs = self._ensure_job_slots(self.smithy_jobs, self.smithies)
        if self.smithies > 0:
            self.resources.setdefault("Tools", 0.0)
            self.resources.setdefault("Daggers", 0.0)
            self.resources.setdefault("Swords", 0.0)
            self.sticky_resources.update({"Tools", "Daggers", "Swords"})
            for processor in self.smithy_jobs:
                if processor.current_recipe is None:
                    choice = random.choice(["sword", "dagger", "tool", "lowest", "stale"])
                    target = self._smithy_pick_target(choice)
                    recipe_map = {
                        "sword": "smith_sword",
                        "dagger": "smith_dagger",
                        "tool": "smith_tool",
                    }
                    recipe_id = recipe_map.get(target or "")
                    if recipe_id and self._can_accept_output(recipe_id):
                        processor.start_job(recipe_id, self)
                processor.tick(prod_mult)
                finished = processor.complete_job(self)
                if finished:
                    output_name = list(RECIPES[finished]["output"].keys())[0]
                    self.smithy_craft_counter += 1
                    if output_name == "Swords":
                        self.smithy_last_crafted["Swords"] = self.smithy_craft_counter
                    elif output_name == "Daggers":
                        self.smithy_last_crafted["Daggers"] = self.smithy_craft_counter
                    elif output_name == "Tools":
                        self.smithy_last_crafted["Tools"] = self.smithy_craft_counter

        # production: tailors (convert linen/pelts into clothing types)
        self.tailor_jobs = self._ensure_job_slots(self.tailor_jobs, self.tailor_shops)
        if self.tailor_shops > 0:
            self.resources.setdefault("Clothing", 0.0)
            self.resources.setdefault("Cloaks", 0.0)
            self.resources.setdefault("Gambesons", 0.0)
            self.sticky_resources.update({"Clothing", "Cloaks", "Gambesons"})

            for processor in self.tailor_jobs:
                if processor.current_recipe is None:
                    choice = random.choice(["clothing", "cloak", "gambeson", "lowest", "stale"])
                    target = self._tailor_pick_target(choice)
                    recipe_map = {
                        "clothing": "tailor_clothing",
                        "cloak": "tailor_cloak",
                        "gambeson": "tailor_gambeson",
                    }
                    recipe_id = recipe_map.get(target or "")
                    if recipe_id and self._can_accept_output(recipe_id):
                        processor.start_job(recipe_id, self)

                processor.tick(prod_mult)
                finished = processor.complete_job(self)
                if finished:
                    self.tailor_craft_counter += 1
                    if finished == "tailor_clothing":
                        self.tailor_last_crafted["Clothing"] = self.tailor_craft_counter
                    elif finished == "tailor_cloak":
                        self.tailor_last_crafted["Cloaks"] = self.tailor_craft_counter
                    elif finished == "tailor_gambeson":
                        self.tailor_last_crafted["Gambesons"] = self.tailor_craft_counter

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
        self.weaver_jobs = self._ensure_job_slots(self.weaver_jobs, self.weavers)
        if self.weavers > 0:
            for processor in self.weaver_jobs:
                if (
                    processor.current_recipe is None
                    and self.resources["Flax"] >= 1
                    and self._can_accept_output("weave_linen")
                ):
                    processor.start_job("weave_linen", self)
                processor.tick(prod_mult)
                finished = processor.complete_job(self)
                if finished == "weave_linen":
                    first_linen = self.resources.get("Linen", 0) <= 1
                    self.sticky_resources.add("Linen")
                    if first_linen and not self.first_linen_announced:
                        self.first_linen_announced = True
                        self.add_log("your first linen is woven from flax fibers.")

        # production: bowyers (craft bows/arrows)
        self.bowyer_jobs = self._ensure_job_slots(self.bowyer_jobs, self.bowyers)
        if self.bowyers > 0:
            for processor in self.bowyer_jobs:
                if processor.current_recipe is None:
                    if self._can_accept_output("craft_arrows") and processor.start_job("craft_arrows", self):
                        pass
                    elif self._can_accept_output("craft_bow") and processor.start_job("craft_bow", self):
                        pass
                processor.tick(prod_mult)
                finished = processor.complete_job(self)
                if finished:
                    self.sticky_resources.update({"Bows", "Arrows"})

        # update display-only food total
        for k in list(self.resources):
            if self.resources[k] < 0:
                self.resources[k] = 0.0
        self._apply_caps()
        self._sync_food_total()
        self.process_unlocks()

    # --------- helpers for UI ---------

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
            if self.tailor_shops > 0 or any(
                self.resources.get(k, 0) > 0 for k in ("Clothing", "Cloaks", "Gambesons")
            ):
                self.sticky_resources.update({"Clothing", "Cloaks", "Gambesons"})
            if amount > 0:
                if name != "Food":
                    self.sticky_resources.add(name)
                dynamic.append(name)
        dynamic.extend(self.sticky_resources)
        dynamic = sorted(set(dynamic))
        names.extend(dynamic)
        return names
