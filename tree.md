# Kingdom Clicker – Draft Tech Tree (Requires/Produces)

## Jobs
- peasant: requires housing; produces can be recruited into other jobs (baseline labor).
- hunter: requires peasant; produces meat/food, pelts, guts (if we track); upkeep food/warmth.
- woodsman: requires peasant; produces wood.
- farmer: requires peasant, farm; produces food/hemp (see hemp chain).
- fighter: requires peasant, weapon (sword), armor (any); produces threat reduction (tbd), gold, counts toward parties.
- ranger: requires peasant, weapon (bow), armor (leather); produces threat reduction, scouting draws (finite/expandable deck).
- miner: requires peasant, quarry (stone site discovered); produces stone.
- ore miner: requires peasant, mine (ore site discovered); produces ore.
- carpenter: requires peasant, workshop; produces boosted plank output/tools prep.
- blacksmith: requires peasant, forge/smelter; produces weapons/armor/tools.
- scribe: requires peasant, paper (or linen + ink), tower/study; produces research/mana seeds; promotes to wizard/cleric.
- wizard: requires scribe, mana/enchantments; produces enchantments/boosts, threat control.
- cleric: requires scribe, faith resource; produces healing/morale.

## Buildings
- house: requires planks; produces +2 pop cap.
- lumber mill: requires wood, peasant; consumes wood; produces planks (3 wood → 1 plank via buffer).
- farm: requires planks, peasant; produces food/hemp.
- workshop: requires planks/stone; unlocks tools/carpenter.
- quarry: requires discovered stone site, tools?; produces stone when staffed.
- mine: requires discovered ore site (via ranger), tools; produces ore.
- forge/smelter: requires stone/ore, fuel; produces ingots/weapons/armor.
- smokehouse/barn (optional): requires wood/stone; produces preserved food/buffer if decay exists.
- market/trade post (optional): requires planks/stone; produces resource exchanges/gold.
- paper mill: requires hemp/linen/wood pulp, water; produces paper.
- tower/study: requires stone/planks/paper; houses scribes; produces research/mana seed.
- mage tower: requires tower + mana + enchantments; houses wizards.
- chapel/temple: requires stone/wood, faith input; houses clerics.

## Equipment / Resources
- weapon (sword): requires ingots/wood; used by fighters; upgraded via enchantments (no decay).
- weapon (bow): requires wood/strings; used by rangers.
- armor (leather): requires pelts/leather; used by rangers/fighters.
- armor (metal): requires ingots; used by fighters.
- tools: requires wood + stone/ingots; boosts production; decay over time.
- hemp: grown on farms; processed into fiber.
- linen: processed hemp; used for clothing, rope, paper.
- rope: from hemp/linen; prerequisite for some builds (mines, bridges, wells).
- paper: from hemp/linen pulp (paper mill); consumed by scribes.
- mana: produced by wizards/structures; consumed by enchantments.
- enchantments: produced by wizards; upgrade weapons/armor/tools; swords upgraded via enchantments instead of decay.
- stone: from quarries (discovered sites); used in advanced buildings.
- ore/ingots: from mines (discovered via ranger) → smelter; used for weapons/armor/tools.

## Unlock Cues
- Jobs panel: peasant available at start; hunter/woodsman appear after first peasant recruited.
- Farm row: appears once 8 planks are ever held.
- Quarry unlock: after a discovered stone site from scouting deck; then buildable, then miner job active.
- Mine unlock: after a discovered ore site from scouting deck via ranger; then buildable, then ore extraction.
- Hemp/paper chain: hemp unlocked via farm upgrade or deck discovery; paper mill after hemp/linen present; tower after paper; scribes unlock in tower; wizard/cleric after scribe + mana/faith.
- Scouting deck: ranger ticks draw from finite/expandable deck; finds forests/clearings/stone sites/ore sites; deck size grows with pop/structures to pace discoveries (prevents infinite mines).

## Clarifications Needed
- Do we track separate meat vs. generic food, or keep food unified?
- Should guts/leather be explicit resources?
- Are stone/ore/metals in scope, or should we stay wood/planks/pelts/food only?
- How should threat/scouting resolve mechanically (per tick vs. events)?
- Do we want equipment durability or one-time costs?
