# Radioactive waste mission

## Project context

This project implements an agent-based simulation of robots cleaning dangerous waste in a hostile environment with increasing radioactivity from west to east. It follows the assignment described in `../project.md` and focuses on step 1 (autonomous behavior) and step 2 (communication between agents).

## Chosen optimization goals (project-specific)

At the beginning of this project, we explicitly selected two practical goals for tuning and evaluation:

1. **Be as fast as possible**: maximize waste-processing throughput (collect, transform, dispose) and reduce backlog quickly.
2. **Keep robots alive**: avoid robot death from life depletion; survival is treated as a hard mission constraint.

## Source system and simulation frame

The source system is a waste-cleaning mission where specialized robots must coordinate under movement and energy constraints.

The simulation frame is a discrete grid world with:
- three zones (`z1`, `z2`, `z3`) of low, medium, and high radioactivity,
- three waste states (`green`, `yellow`, `red`),
- increasing waste generation pressure,
- a failure condition when total waste crosses a threshold.

The simulator executes one tick at a time and logs system-level indicators (waste inventory, disposal, survival, communication).

## Life-loss mechanics (how robots lose life)

Robot life is represented by the `energy` variable and is updated every tick.

- **Base action costs**: each action consumes life (`move=1`, `pick_up=1`, `transform=3`, `drop=1`).
- **Carrying penalty per tick**: while carrying waste, robots lose additional life every tick:
  - carrying one `green`: `+1.0` life loss/tick,
  - carrying one `yellow`: `+1.25` life loss/tick,
  - carrying one `red`: `+2.6` life loss/tick.
- **Accumulation rule**: penalties are additive across all carried items.
  - Example: inventory `[green, yellow, yellow]` causes an extra loss of `1.0 + 1.25 + 1.25 = 3.5` per tick.
- **Decontamination recovery**: if a robot is in a decontamination zone, it recovers `+8` per tick (capped at max life), then carrying loss is applied.
- **Failure condition**: if any robot reaches `energy <= 0`, the mission fails.

## Explicit safety/mission rules chosen in this project

- **No loaded robot on decontamination**: a robot carrying any waste cannot enter a decontamination tile.
- **Batch transform semantics**: `ACTION_TRANSFORM` converts as many valid pairs as possible in one tick (`while count >= cost`), not only one pair.
- **Strict success condition**: mission success is declared only when both conditions are true at the same time:
  - the on-map waste storage is empty,
  - all robot inventories are empty.

## Environment and agents

Environment properties in this model are partially observable, dynamic, discrete, and shared by multiple autonomous agents.

Robot roles are:
- Green robot: can move only in `z1`, picks `green`, transforms `2 green -> 1 yellow`.
- Yellow robot: can move in `z1-z2`, picks `yellow`, transforms `2 yellow -> 1 red`.
- Red robot: can move in `z1-z3`, picks `red`, disposes it in the eastern disposal zone.

Each robot follows a `percepts -> deliberate -> do` loop with local knowledge, memory, and energy-aware decisions.

## Decision model summary

The implementation combines:
- role-specific intentions and action priorities,
- shortest-path movement (A*),
- survival constraints (decontamination and low-energy safeguards),
- asynchronous communication through a one-tick mailbox.

Communication messages currently include:
- `waste_found`,
- `need_pickup`,
- `load_status`.

The protocol details are documented in `reports/auml_protocol.md`.

## Implemented design choices

Beyond the baseline assignment requirements, the current code implements the following design choices:
- Knowledge and memory: local `known_waste` memory with TTL expiration, visited-cell counters, recent-position windows, and per-cell waste quantity (`count`) tracking.
- Decision stability: intention lock, switch cooldown, and hysteresis to reduce oscillations.
- Dynamic survival policy: role-aware energy reserve estimation based on path cost and return-to-decontamination needs.
- Safety constraints: loaded robots avoid entering decontamination tiles and use emergency drop behavior in survival-critical states.
- Batch transform execution: one transform action can process multiple pairs in the same tick (`while count >= cost`).
- Communication timing: one-tick asynchronous mailbox delivery with cumulative `messages_sent` tracking in model history.
- Communication payload enrichment: `load_status` includes workload, activity state, last action, and sender position; `waste_found` carries quantity (`count`) and `need_pickup` is emitted only for actual dropped types.
- Role-specific viability exceptions: green can prioritize `pickup -> transform` in edge cases where local transform feasibility is immediate.
- Yellow endgame planning: exact energy-feasibility planning for farthest-east transform/drop progression before forced return.
- Message-driven target persistence: robots keep message focus targets and switch only if a newly received target is Euclidean-closer.
- Return retarget policy: green and yellow can cache and pursue return-side retargets captured while recharging/recovering.
- Green anti-loop policy: post-drop no-repick guards plus decontamination hold behavior reduce pickup/drop ping-pong loops.
- Green exploration memory: top/bottom exhausted-zone memory with TTL and row-bounded exploration prevents repetitive empty-half rescans.
- Yellow pair logic robustness: yellow pair-wait behavior now uses quantity-aware local counts, avoiding deadlocks when two yellow wastes are stacked on one cell.
- Debug traceability: per-step decision reason and target are stored in decision logs (`why=` style diagnostics).

## Recent updates (2026-03)

- Communication semantics were corrected so downstream pickup requests match the true post-action inventory diff, preventing false yellow-to-red handoff signals.
- Global-runtime count leakage was removed from yellow/red decision paths in favor of locally observed and communicated information.
- Local perception is enforced: agents always use local `3x3` perception plus memory; global perception switch has been removed from the code.

## Evaluation approach

The project is evaluated through repeated simulation runs with visual inspection and exported metrics.

Generated outputs include:
- per-tick history,
- csv reports in `reports/report_tick_*/simulation_data.csv`,
- aggregate plots produced by `src/analytics.py`.

The iterative tuning history is consolidated in `reports/intelligence_log.md`.

## Repository structure

```
multi-agent-system/
  run.py
  server.py
  requirements.txt
  src/
    agents.py
    model.py
    objects.py
    analytics.py
    config.py
    renderer.py
    sprites.py
  reports/
    auml_protocol.md
    intelligence_log.md
    report_tick_*/simulation_data.csv
```

## Setup and execution

Requirements:
- Python `3.9+`
- packages listed in `requirements.txt`

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the simulation:

```bash
python run.py
```

> ⚠️ **Warning**: Human player mode is not implemented yet.

Keyboard controls:
- `Space`: pause or resume
- `R`: restart
- `+` or `-`: change speed
- `Q`: quit

## Main configuration points

Most parameters are centralized in `src/config.py`, including:
- map size and zone boundaries,
- number of robots per role,
- waste generation rates and threshold,
- energy costs, recharge values, and safety margins,
- communication and coordination toggles.

## Current scope and limitations

This repository covers the mandatory simulation core and communication extension for step 2.

Uncertainty modeling from step 3 is not yet included as a dedicated module.
