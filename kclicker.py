import tkinter as tk
from tkinter import messagebox

TICK_MS = 1000  # game tick in milliseconds
UI_SCALE = 1.2
FOOD_UPKEEP_PER_CAPITA = 0.25
WARMTH_UPKEEP_PER_CAPITA = 0.02
HUNTER_FOOD_YIELD = 0.475  # supports ~1.9 pop per hunter at baseline
HUNTER_PELT_YIELD = 0.05
HUNTER_GUT_YIELD = 0.02
HUNTER_FEATHER_YIELD = 0.05
HUNTER_SKIN_YIELD = 0.05
HUNTER_ARROW_USE_PER_TICK = 0.3
BOW_HUNTER_BONUS = 1.25
BOWYER_BOW_TIME = 6.0  # ticks of work to craft one bow
FARM_GRAIN_YIELD = 0.75
FARM_HEMP_YIELD = 0.25
SKIN_HEMP_UNLOCK = 5
STARVATION_PENALTY = 0.75


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
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Kingdom Clicker")
        self.root.geometry("1080x720")
        self.root.configure(bg="#1e272e")

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
            "Hemp": 0.0,
        }

        # units
        self.peasants = 0
        self.hunters = 0
        self.woodsmen = 0
        self.bowyers = 0
        self.rangers = 0

        # buildings
        self.lumber_mills = 0
        self.houses = 0
        self.farms = 0

        # misc
        self.base_pop_cap = 4
        self.log_text = "an empty clearing awaits settlers."
        self.last_food_need = 0.0
        self.last_warmth_need = 0.0
        self.lumber_buffer = 0.0  # wood waiting to be milled
        self.grain_buffer = 0.0  # seasonal grain waiting for harvest
        self.farm_growth_slots = 0  # farms eligible for this year's growth
        self.hunter_bows_equipped = 0
        self.jobs_unlocked = False
        self.farm_unlocked = False
        self.food_breakdown_unlocked = False
        self.guts_unlocked = False
        self.guts_visible = False
        self.hemp_unlocked = False
        self.bowyer_unlocked = False
        self.ranger_unlocked = False
        self.bowyer_progress = []
        self.total_meat_made = 0.0
        self.season_tick = 0
        self.season_phase = 0
        self.season_icons = ["🌱", "☀️", "🍂", "❄️"]
        self.current_season_icon = self.season_icons[0]
        self.resource_grid_cols = 5
        self.sticky_resources = set()

        # --- ui layout ---

        self._build_ui()

        # start loop
        self.update_ui()
        self.root.after(TICK_MS, self.game_tick)

    # --------- ui ---------

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
            "Hemp": "#55efc4",
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
        Tooltip(self.btn_ranger_plus, "Cost: 1 bow, 20 arrows, 1 peasant (idle)")

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

        self.log_label = tk.Label(
            news_col,
            text=self.log_text,
            font=("Helvetica", scaled(10), "italic"),
            bg="#1e272e",
            fg="#d2dae2",
            wraplength=260,
            justify="left",
        )
        self.log_label.pack(anchor="w", pady=(0, 10))

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
            + self.rangers
            + self.lumber_mills
            + self.farms
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
        self.set_log("a peasant sharpens a stick and ventures out to hunt.")

    def action_remove_hunter(self):
        if self.hunters <= 0:
            self.set_log("no hunters to reassign.")
            return
        self.hunters -= 1
        self.peasants += 1
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
        self.set_log("a peasant starts shaping staves and stringing crude bows.")

    def action_remove_bowyer(self):
        if self.bowyers <= 0:
            self.set_log("no bowyers to reassign.")
            return
        self.bowyers -= 1
        self.peasants += 1
        if self.bowyer_progress:
            self.bowyer_progress.pop()
        self.set_log("a bowyer leaves the bench and returns as a peasant.")

    def action_add_ranger(self):
        if not self.ranger_unlocked:
            self.set_log("you need bows and arrows ready before training rangers.")
            return
        if self.peasants <= 0:
            self.set_log("no idle peasants to train as rangers.")
            return
        bow_cost = 1
        arrow_cost = 20
        if self.resources["Bows"] < bow_cost or self.resources["Arrows"] < arrow_cost:
            self.set_log("you need a bow and arrows ready to outfit a ranger.")
            return
        self.resources["Bows"] -= bow_cost
        self.resources["Arrows"] -= arrow_cost
        self.peasants -= 1
        self.rangers += 1
        self.set_log("a peasant takes bow and arrows, ranging beyond the village.")

    def action_remove_ranger(self):
        if self.rangers <= 0:
            self.set_log("no rangers to recall.")
            return
        self.rangers -= 1
        self.peasants += 1
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
                excess = self.hunter_bows_equipped - self.hunters
                self.hunter_bows_equipped -= excess
                self.resources["Bows"] += excess

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

        # production: bowyers (craft bows slowly, consuming planks + guts; arrows if feathers are present)
        if len(self.bowyer_progress) < self.bowyers:
            self.bowyer_progress += [0.0] * (self.bowyers - len(self.bowyer_progress))
        elif len(self.bowyer_progress) > self.bowyers:
            self.bowyer_progress = self.bowyer_progress[: self.bowyers]

        for i in range(self.bowyers):
            self.bowyer_progress[i] += 1.0 * prod_mult
            while self.bowyer_progress[i] >= BOWYER_BOW_TIME:
                crafted = False
                if self.resources["Feathers"] >= 20 and self.resources["Planks"] >= 1:
                    self.resources["Feathers"] -= 20
                    self.resources["Planks"] -= 1
                    self.resources["Arrows"] += 20
                    crafted = True
                elif self.resources["Planks"] >= 1 and self.resources["Guts"] >= 1:
                    self.resources["Planks"] -= 1
                    self.resources["Guts"] -= 1
                    self.resources["Bows"] += 1
                    crafted = True

                if crafted:
                    self.bowyer_progress[i] -= BOWYER_BOW_TIME
                else:
                    # can't craft anything now; keep progress for later
                    break

        # update display-only food total
        self._sync_food_total()

        self.update_ui()
        self.root.after(TICK_MS, self.game_tick)

    # --------- ui update ---------

    def set_log(self, text: str):
        self.log_text = text
        self.log_label.config(text=self.log_text)

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
                    if self.hemp_unlocked:
                        hemp_gain = self.farm_growth_slots * FARM_HEMP_YIELD
                        self.resources["Hemp"] += hemp_gain
                    self.grain_buffer = 0.0
                    self.set_log(f"summer harvest brings in {int(harvest)} grain.")
        else:
            self.season_label.config(text=self.current_season_icon)

    def _get_display_resource_names(self):
        names = []
        if self.food_breakdown_unlocked:
            primary = ["Meat", "Grain", "Pelts", "Wood", "Planks"]
        else:
            primary = ["Food", "Pelts", "Wood", "Planks"]

        for name in primary:
            if name not in names:
                names.append(name)

        for name, amount in self.resources.items():
            if name in primary:
                continue
            if name == "Food" and self.food_breakdown_unlocked:
                continue
            if name in ("Meat", "Grain") and not self.food_breakdown_unlocked:
                continue
            if amount > 0:
                if name != "Food":
                    self.sticky_resources.add(name)
                names.append(name)
        for sticky in self.sticky_resources:
            if sticky not in names:
                names.append(sticky)
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
                text = f"wood: {int(total_wood)}"
            else:
                text = f"{name.lower()}: {int(self.resources.get(name, 0))}"

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
        self.ranger_value.config(text=f"{self.rangers}")

        # pop tooltip
        lines = [f"peasants {self.peasants}"]
        if self.hunters:
            lines.append(f"hunters {self.hunters}")
        if self.woodsmen:
            lines.append(f"woodsmen {self.woodsmen}")
        if self.bowyers:
            lines.append(f"bowyers {self.bowyers}")
        if self.rangers:
            lines.append(f"rangers {self.rangers}")
        if self.lumber_mills:
            lines.append(f"carpenters {self.lumber_mills}")
        if self.farms:
            lines.append(f"farmers {self.farms}")
        self.pop_tooltip.text = "\n".join(lines)

        # building counts
        self.house_value.config(text=f"{self.houses}")
        self.mill_value.config(text=f"{self.lumber_mills}")
        self.farm_value.config(text=f"{self.farms}")

        # unlock rows
        if not self.jobs_unlocked and (
            self.peasants + self.hunters + self.woodsmen + self.bowyers + self.rangers
        ) > 0:
            self.jobs_unlocked = True
        if self.jobs_unlocked:
            if not self.hunter_row.winfo_manager():
                self.hunter_row.pack(anchor="w", pady=(10, 2), fill="x")
            if not self.woods_row.winfo_manager():
                self.woods_row.pack(anchor="w", pady=2, fill="x")
            if self.bowyer_unlocked and not self.bowyer_row.winfo_manager():
                self.bowyer_row.pack(anchor="w", pady=2, fill="x")
            if self.ranger_unlocked and not self.ranger_row.winfo_manager():
                self.ranger_row.pack(anchor="w", pady=2, fill="x")

        if not self.farm_unlocked and self.resources["Planks"] >= 8:
            self.farm_unlocked = True
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

        if not self.hemp_unlocked and self.resources["Skins"] >= SKIN_HEMP_UNLOCK:
            self.hemp_unlocked = True
            self.set_log("farmers learn to ready fields for hemp during harvests.")

        # bowyer unlock gating on inputs
        if (
            not self.bowyer_unlocked
            and self.resources["Guts"] >= 3
            and self.resources["Planks"] >= 3
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

        # enable/disable buttons based on affordability
        self._update_button_states()

    def _update_button_states(self):

        # upgrades
        if self.peasants <= 0:
            self.btn_hunter_plus.config(state="disabled", bg="#84817a")
            self.btn_woodsman_plus.config(state="disabled", bg="#84817a")
            self.btn_bowyer_plus.config(state="disabled", bg="#84817a")
            self.btn_ranger_plus.config(state="disabled", bg="#84817a")
        else:
            self.btn_hunter_plus.config(state="normal", bg="#33d9b2")
            self.btn_woodsman_plus.config(state="normal", bg="#ffb142")
            if self.bowyer_unlocked:
                self.btn_bowyer_plus.config(state="normal", bg="#eccc68")
            else:
                self.btn_bowyer_plus.config(state="disabled", bg="#84817a")
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

        if self.rangers > 0:
            self.btn_ranger_minus.config(state="normal")
        else:
            self.btn_ranger_minus.config(state="disabled")

        if self.ranger_unlocked and self.peasants > 0:
            self.btn_ranger_plus.config(state="normal", bg="#70a1ff")
        else:
            self.btn_ranger_plus.config(state="disabled", bg="#84817a")

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

        # abandon buttons
        if self.lumber_mills > 0:
            self.btn_mill_minus.config(state="normal")
        else:
            self.btn_mill_minus.config(state="disabled")

        if self.farms > 0:
            self.btn_farm_minus.config(state="normal")
        else:
            self.btn_farm_minus.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = KingdomIdlePOC(root)
    root.mainloop()
