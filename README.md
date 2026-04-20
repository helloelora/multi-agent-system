# Radioactive Waste Mission - Group 19

**Members:** Ali Dor, Elora Drouilhet
**Course:** MAS 2026 - Multi-Agent Systems
**Period:** 13/03/2026 - 20/04/2026

![Game overview](19_robot_mission_MAS2026/pics/game.PNG)

Agent-based simulation where three robot types cooperate to clean a radioactive
grid. Green robots work in zone 1 and transform `green -> yellow`. Yellow robots
shuttle between zone 1 and 2 and transform `yellow -> red`. Red robots carry
the final waste to the east-edge disposal column.

The mission fails if the total live waste on the grid reaches the meltdown
threshold, or if any robot runs out of life energy. It succeeds when every
spawned block has been processed through the pipeline and disposed.

---

## Requirements

```
pygame  >= 2.6.0
numpy   >= 1.24.0
matplotlib >= 3.7.0
```

Install with:

```bash
cd 19_robot_mission_MAS2026
pip install -r requirements.txt
```

Python 3.10+ recommended.

## Run

From inside `19_robot_mission_MAS2026/`:

```bash
python run.py
```

This opens the start menu. Pick a robot skin, toggle human-player mode if you
want to drive one of the three robots yourself, tune the start settings, then
press **START** (or Enter).

Optional web dashboard (JSON API + live grid):

```bash
python server.py
# open http://localhost:8080
```

## Controls (in-game)

| Key | Action |
|---|---|
| `Space` / `Esc` | Pause |
| `+` / `-` | Speed up / slow down |
| `1` / `2` / `3` | Auto / single-step / step-by-5 modes |
| `N` | Advance one step (in step mode) |
| `E` | Manually export the current analytics report |
| `R` | Restart from the start menu |
| `M` | Return to main menu |
| `Q` | Quit |

## Human-player mode

From the start menu, you can switch from "AI ONLY" to "HUMAN PLAYER" and
pick one of the three colours to control directly. The selected robot
stops deliberating autonomously and waits for your keystrokes; the other
two keep running their normal strategy and still treat you as a teammate
for the communication protocol (you broadcast `waste_found` and
`need_pickup` exactly like an AI would).

Controls while playing as a robot:

| Key | Action |
|---|---|
| Arrow keys | Move one cell |
| `Space` | Pick up waste on the current cell |
| `T` | Transform (2 greens -> 1 yellow, or 2 yellows -> 1 red) |
| `F` | Drop one item from the inventory |
| `I` | Idle (skip this tick, recover energy if on decontamination) |

A pulsing diamond and an arrow above your robot make it easy to spot on
the grid, and the bar at the bottom of the playfield shows your
inventory, life, and control reminders.

## Start-menu settings

| Setting | Range | What it does |
|---|---|---|
| Initial Green Waste | 5-50 | Number of green blocks placed at tick 0 |
| Max Radiation | 30-200 | Meltdown threshold (total live waste) |
| Spawn Interval | 30-300 | Ticks between spawn waves in zone 1 |
| Global Knowledge on/off | toggle | If on, agents read the full waste map; if off, each agent only knows what it has seen or been told |

Agent tick rate (base movement speed) is locked to the config default; use `+`
in-game to change speed live.

---

## Architecture

Three layers, one per file group:

- **`src/objects.py`** - pure data: `Waste`, `Radioactivity`, `DisposalZone`,
  `DecontaminationZone`.
- **`src/model.py`** - the world. Holds the grid, spawns, executes actions
  (`model.do(agent, action)`), ticks time, detects game-over, accumulates
  history for the charts.
- **`src/agents.py`** - the robots. Each one runs the classical
  `percepts -> deliberate -> do` loop:

  ```
  percepts = model.get_percepts(self)
  self._update_knowledge(percepts)
  action = self.deliberate(self.knowledge)
  new_percepts = model.do(self, action)
  ```

Each tick every robot sees a small local window of the grid, updates its
internal knowledge (known waste, visit counts, messages, energy, intention),
then picks one of eight actions: move up/down/left/right, pick up, transform,
drop, idle.

### Decision priority

`deliberate()` walks a fixed cascade. The first satisfied clause wins:

1. **SURVIVE** - energy below threshold: drop cargo, head to the nearest
   decontamination tile to recover.
2. **DELIVER** - if carrying the transformed output, go deliver it to the
   handoff border (or, for red robots, to the disposal column).
3. **TRANSFORM** - on-site if enough input in inventory.
4. **PICKUP** - if standing on a target-type waste and can safely carry one
   more (energy check included).
5. **SEEK** - if a known-waste position exists in the local knowledge, A*
   navigate to it.
6. **PATROL** - station near the handoff border where upstream inputs arrive.
7. **EXPLORE** - frontier-based exploration weighted by visit counts (cells
   visited less often score higher).

Intentions are committed for `DECISION_INTENTION_HOLD_TICKS` ticks to avoid
oscillation between two equally-scored options.

### Communication

Asynchronous mailbox, one-tick delay. Each agent can broadcast:

- `waste_found` - "I see waste of type T at position P"
- `waste_picked` - "I just picked up at P, you can drop that entry"
- `need_pickup` - "I dropped a target output at P, downstream come get it"
- `load_status` - periodic heartbeat with role, inventory count, intention, pos

Every agent broadcasts **all waste types it can see**, not only its own
target. So yellow walking through zone 1 reports the green wastes it spots,
and red stumbling into zone 2 reports yellow wastes. Messages are delivered
next tick and merged into the recipient's `known_waste` map. When
`GLOBAL_KNOWLEDGE` is off, this is the only way information propagates
between agents.

### Downstream-scouts-for-upstream strategy

A feature we designed deliberately: whenever a downstream robot has nothing
urgent to do, it walks into the upstream zone and scouts for the upstream
robot. It cannot pick those blocks up (wrong target type), but its
perception ticks trigger `waste_found` broadcasts that the upstream robot
consumes.

- **Red** (`_assist_green`, `agents.py:753`) - priority 7 of its cascade.
  When no red waste is known and nothing closer needs doing, red A*-routes
  to the centre of zone 1 and explores there, broadcasting any green or
  yellow waste it spots on the way and once inside.
- **Yellow** - its default patrol range (`_SEEK_MIN_COL=6` to
  `_SEEK_MAX_COL=14`) straddles the zone-1 / zone-2 border. Yellow enters
  zone 1 naturally while waiting for green's deliveries, and broadcasts the
  green wastes it passes over.

This is why, in the pickup chart above, the **green bar has "alerted"
entries at all** (5 out of 30). Those 5 pickups are green wastes that
yellow or red saw first and broadcast.

The strategy is invisible on the yellow and red bars because those bars
only count their *own* pickups of their *own* target type. Scouting
contributes to the **green bar's alerted count**, not to the scouts' bars.

**Impact on mission time.** In our experiments, missions with all three
robots scouting complete noticeably faster than the same seed run with
yellow and red sitting idle at their patrol positions. The opening phase -
where green has to locate the initial 16 blocks scattered across zone 1 -
is the bottleneck: a single green robot sweeping column by column takes
much longer than green plus two scouts feeding positions into its mailbox.
Once the pipeline is primed (first yellows arriving at the border), the
advantage narrows because yellow is busy and red takes over alone, but the
head-start on the first wave shortens total run time by a visible margin.

### Key safeguards

- **TTL on known waste** - entries decay after `KNOWLEDGE_WASTE_TTL` ticks
  unless refreshed; prevents agents from chasing ghosts.
- **Permanent memory for `need_pickup`** on *our* target type - downstream
  agents never forget a delivered waste.
- **First-seen wins** tagging (`source = self | alerted`) - we track whether
  each known block came from direct perception or from a message, which lets
  us report how often each robot acted on its own vs. on an alert.
- **UID-based pickup counting** - every `Waste` has a stable uid that survives
  pickup -> drop cycles; pickup statistics only count the first time a block
  is lifted, so drop-and-repick never inflates the numbers.

---

## Versions tested

During development we kept each major iteration in its own git branch. Three
snapshots matter for the report.

### Version 1 - random walk baseline (`game-v1`)

- Percepts-deliberate-do loop in place, but the movement policy was a plain
  `random.choice` over legal directions.
- Pickup / transform / drop happened greedily whenever the robot happened to
  land on the right cell.
- Energy and mailbox existed but no agent planned around them.
- **Observed failure mode:** robots spent most ticks oscillating between two
  cells, and the mission almost always ended in meltdown before any green
  waste reached the disposal column.

### Version 2 - A* and intention locking (`game-v2`)

Replaced the random walk with A* shortest paths and introduced a commitment
layer so the robot does not flip its intention every tick:

- `_a_star_path(start, goal)` with grid constraints (allowed zones per role).
- `intention_lock` counter + `DECISION_INTENTION_HOLD_TICKS` hysteresis.
- Target scoring uses distance, energy cost, visit history
  (`_frontier_information_gain`), and a recency penalty
  (`_recent_position_penalty`) to break ties away from cells just visited.
- `_set_decision_debug(reason, target)` logs a one-line reason per tick, which
  made runs investigable.
- **Observed improvement:** clearance rate went up by a large factor, but
  agents started dying of life loss because they still charged into zone 3
  without checking their return budget.

### Version 3 - production (`game-v2-fixes`, the version in this folder)

Kept A* and intentions from v2, removed the dead scaffolding, and added:

- **Decontamination + survival mode.** If energy drops below
  `HEALTH_LOW_THRESHOLD`, the robot drops its cargo, switches intention to
  `SURVIVE`, and A*-navigates to the nearest decon tile. It does not resume
  mission work until energy climbs back over `HEALTH_RESUME_THRESHOLD`
  (hysteresis prevents rapid mode flipping near the threshold).
- **Energy-feasibility check before committing.** `_can_complete_cycle`
  estimates the total step cost of `go -> pickup -> deliver -> return` and
  refuses the intention if the remaining energy would not cover it.
- **Loaded-robot safety.** Decontamination tiles are blocked while carrying
  radioactive cargo so the agent cannot heal while leaking.
- **UID-based pickup dedup** (see Safeguards above) added in the last week
  of development once we noticed the survival-drop-then-repick case was
  inflating statistics.
- **Sidebar bar chart** showing per-robot pickup attribution
  (self-detected vs. alerted) as a goal-oriented metric for the teacher.

### Experiment flags you can toggle

All of the following are live at runtime without editing code:

| Flag | Location | Effect |
|---|---|---|
| `GLOBAL_KNOWLEDGE` | menu toggle | False = messages are the only information channel; True = each agent reads the true waste map directly (upper bound on coordination quality) |
| `COMMUNICATION_ENABLED` | `config.py` | False = no mailbox at all; agents rely only on personal perception |
| `ENERGY_ENABLED` | `config.py` | False = infinite energy; removes the survival priority from the cascade |
| `RADIATION_SPAWN_ENABLED` | `config.py` | False = finite mission with only the initial waste |
| `DECONTAMINATION_ENABLED` | `config.py` | False = no healing tiles |

To reproduce v1 behaviour (random walk) set `COMMUNICATION_ENABLED = False`
and swap the agents' `deliberate` to `random.choice(ALL_MOVES)` - we kept the
branch alive on the repository for reference.

---

## Results

With the default settings (16 initial green blocks, threshold 80, spawn
interval 90) and communication + energy + decontamination all enabled:

> Note: the initial count must be even. Each pair of greens transforms into
> one yellow, so an odd count leaves one green that can never be disposed
> and the success condition (`total_waste == 0`) is unreachable.

- **Clearance.** Mission usually completes around tick 2000-2500; we observed
  full clearance in roughly 80% of runs. The remaining 20% fail by meltdown
  during the yellow bottleneck around tick 500 when zone-2 spawns kick in.
- **Waste levels over time** (green / yellow / red counts live on the grid):

  ![Waste count](19_robot_mission_MAS2026/pics/waste-count.PNG)

  The sawtooth comes from the spawn-then-clear cycle: green waves trigger
  yellow conversion which triggers red transport, each wave drawn lower as
  the pipeline catches up.

- **Robot life (energy) over time**, one curve per robot type:

  ![Life by robot type](19_robot_mission_MAS2026/pics/life.PNG)

  The periodic V-shape is the survival-mode hysteresis: each robot drains
  while working, cuts back to its decon tile, refills, returns. The red
  dashed line is `HEALTH_LOW_THRESHOLD`.

- **Pickup attribution.** The sidebar bar chart separates, per robot,
  pickups of blocks the robot discovered itself (filled bar) from blocks
  it learned about through a message (outlined bar):

  ![Pickups per robot](19_robot_mission_MAS2026/pics/pickups.PNG)

  In this run: `G0` (green) picks up mostly blocks it finds itself (25 vs.
  5) because zone 1 is small enough to sweep. `Y1` (yellow) is almost
  entirely message-driven (1 vs. 13): it waits at the zone-1 border for
  green to broadcast `need_pickup` after each delivery. `R2` (red) is 100%
  alerted (0 vs. 6): it never sees yellow waste before yellow itself posts
  a `need_pickup`. This is the shape we wanted from the communication
  protocol - downstream agents should react to upstream deliveries, not
  wander into zones they have no business scanning.

- **Ablations we ran:**
  - `COMMUNICATION_ENABLED=False` drops clearance to ~40% and shifts all
    pickup bars to fully self-detected (no alerts possible).
  - `GLOBAL_KNOWLEDGE=True` pushes clearance past 95% but makes the
    communication protocol trivially redundant.
  - `DECONTAMINATION_ENABLED=False` caps energy at starting value; agents
    die around tick 1500 without ever making it back across the grid.

### Analytics

At game end, `run.py` auto-exports to `reports/report_tick_<N>/`:

- `simulation_data.csv` - tick-by-tick counts and energy
- `waste_over_time.png`
- `total_vs_threshold.png`
- `disposal_rate.png`
- `agent_energy.png`

The same export is available mid-run via the `E` key.

### Tick-level log

While playing, every tick is appended to `output/run<NNN>/log.txt` with per-
robot position, inventory, intention reason, target, and current knowledge.
These logs were the main tool we used to debug v2 -> v3.

---

## Project layout

```
19_robot_mission_MAS2026/
|- run.py              # main entry, pygame loop, key handling
|- server.py           # optional HTTP dashboard (localhost:8080)
|- requirements.txt
|- assets/             # generated sprites and tiles
|- src/
|   |- config.py       # all tunable parameters
|   |- objects.py      # Waste, Radioactivity, zones
|   |- model.py        # world logic: grid, actions, game over
|   |- agents.py       # GreenAgent, YellowAgent, RedAgent + base class
|   |- renderer.py     # pygame renderer, HUD, scrollable sidebar
|   |- sprites.py      # programmatic pixel-art robot designs
|   |- sounds.py       # procedural sound effects
|   |- analytics.py    # report export (CSV + matplotlib charts)
|   |- menu.py         # start menu and pause overlay
|- README.md           # this file
```

---

## Known limitations

- Agent count is fixed at one per color. Multi-robot-per-color was wired up
  in v1 but retired when we introduced role-specific intention locking; we
  did not backport the generalization.
- Red robot has no transform step, so its `pipeline_stats` uses `disposals`
  instead of `deliveries`.
- The web dashboard renders a simplified grid only and does not expose the
  sidebar metrics.
