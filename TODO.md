# Future Design Ideas
## Near-term Priorities

## Core Mechanics & Resources
- **Tool Generation & Degradation:** Introduce tools that enhance efficiency but degrade over time, requiring replacement or repair. (basic tools exist; decay not implemented)
- **Disaggregated Food Resources:** Expand food beyond a single type to include meat, grain, and potentially fruits, influencing different aspects of the settlement. (meat/grain split done)
- ~~**New Resource - Guts:** Hunters produce guts, a byproduct of meat production, used by Bowyers and someday for Bard instruments.~~
- ~~**Mana Quarry:** Introduce a "mana quarry" that produces crystals, a resource for magical units.~~ (renamed to general mana site)
- **Storage Caps & Overflow:** Implement storage caps for all produced goods and items tied to number of base buildings. Production buildings should store the most of their output. Houses store small extra food (overflow buffer). Warehouses (future) enable larger overflow. Indicate when production buildings are idle due to missing inputs or full storage.
- **Weaver:** Convert hemp to linen (and downstream rope/paper inputs).
- **Tailor:** Turn linen + pelts/skins into clothing.
- **Armorer:** Use linen + pelts for padded armor; skins for leather armor.

## Exploration & World Interaction
- **Fog of War Deck:** Implement a system where exploring units (e.g., rangers) have a chance to discover new tiles like quarries, rivers, or monster lairs.
- **Threat/Danger Ratings:** Introduce a dynamic threat system that increases with expansion or resource extraction, requiring adventurer units to manage.

## Progression & Specialization
- **Specialization Paths:** Define clear paths for units to become specialized (e.g., Fighter, Wizard, Thief, Cleric, Weaponsmith, Armorsmith).
- **Fighter Unlock:** Combine peasant + sword + leather armor to create a fighter. Fighters reduce threat and generate minor gold.
- **Weaponsmith & Rogues:** Weaponsmiths can produce daggers (unlocking rogues) and tools for worker efficiency (with periodic breakage).
- **Wizards:** Scribes + towers unlock wizards, who consume scrolls (from scribes) and crystals (from mana quarry) for enchantments.
- **Clerics:** Scribes + church unlock clerics, who provide a buffer against unit death or boost morale/productivity.
- **Party System & Adventures:** Allow creation of "parties" for adventures, yielding significant gold/artifacts or risking loss.

## Environmental & Narrative Elements
- **Weather Cycles:** Implement dynamic weather cycles impacting gameplay.
- **Narrative Seeds in News/Status Log:** Inject story prompts and events into the news feed.
- ~~**Persistent Status Log:** Create a continuous feed for events and news.~~ (scrolling news feed added)
- **Quirky Narrative Events:** Include humorous or character-driven events in the newsfeed (e.g., woodsman's daily routine, carpenter's best plank).
- **Fishing:** Introduce fishing as a food gathering activity.

## Design Documents
- **Tech Tree Design Document:** Map out our ideal tech tree.

## UI
- Support modular, continually expanding lists of jobs, resources, and buildings.

## Testing & Simulation
- Add a headless simulation mode (no Tk) to fast-forward ticks/seasons from a JSON state: expose a `step(ticks)` loop without scheduling, guard UI calls, and allow seeding `random` for deterministic runs. Include a small driver script to run N seasons and log key resources (e.g., flax/linen/pelts) for balancing.

## Architecture for More Jobs/Goods
- Introduce a shared worker pipeline: per-job configs define `work_time`, `start_job` (reserve inputs, return token), and `finish_job` (emit outputs); a generic loop advances progress per worker instead of bespoke per-job loops.
- Use registries for jobs/buildings (costs, unlock predicates, display labels/tooltips) to drive unlock checks, save/load, and UI row generation rather than scattered if/else blocks.
- Store crafting recipes as data (inputs/outputs, time, selection strategy) so adding new goods is mostly config, not code.
- Add resource access helpers to centralize defaulting/clamping and cut down on ad hoc `setdefault` calls.
