# Final summary

## Project objective

This project models a multi-agent radioactive waste mission in a hostile environment split into three zones (`z1`, `z2`, `z3`) with increasing radioactivity. The goal is to maintain system stability by collecting, transforming, and disposing waste faster than it is generated.

For this project, we made two explicit optimization goals:

1. **Speed goal**: be as fast as possible at processing waste across the full pipeline.
2. **Survival goal**: prevent robot death (`energy <= 0`) during the mission.

These two goals are treated jointly during tuning: high throughput is only valid if robot survival is preserved.

## Life-loss model (explicit)

Robots lose life through both action costs and carrying pressure:

- Action costs: `move=1`, `pick_up=1`, `transform=3`, `drop=1`.
- Additional carrying loss each tick (additive over inventory):
  - `green`: `+1.0`,
  - `yellow`: `+1.25`,
  - `red`: `+2.6`.

So carrying multiple wastes accumulates linearly. Example: `[green, yellow, red]` adds `1.0 + 1.25 + 2.6 = 4.85` life loss per tick on top of action costs.

Decontamination zones recover `+8` life per tick (capped by max life), but carrying loss still applies in the same tick. If any robot reaches `energy <= 0`, the run ends in failure.

## Explicit project rules

- **No loaded robot on decontamination**: carrying any waste blocks entry into decontamination tiles.
- **Batch transform rule**: `ACTION_TRANSFORM` converts as many valid pairs as possible in one tick (`while count >= cost`).
- **Strict success rule**: success is reached only if the waste map is empty **and** every robot inventory is empty.

## Modeling choices

- Source system: collaborative robotic waste cleaning under access and energy constraints.
- Simulation frame: discrete grid, tick-based dynamics, local perceptions, shared environment.
- Agent roles:
  - Green robot (`z1`): `2 green -> 1 yellow`.
  - Yellow robot (`z1-z2`): `2 yellow -> 1 red`.
  - Red robot (`z1-z3`): transports `red` to disposal in `z3`.

## Main design decisions and justifications

- Percepts-deliberate-do loop with local knowledge.
  - Justification: directly follows the course architecture and keeps decision logic modular.

- Path planning with A* for target navigation.
  - Justification: improves task efficiency versus random or purely greedy movement.

- Intention lock, cooldown, and hysteresis.
  - Justification: reduces oscillation and unstable action switching.

- Memory with TTL for known waste and recent-position tracking.
  - Justification: balances exploration and exploitation while avoiding stale information.

- Quantity-aware local waste memory (`known_waste.count`).
  - Justification: avoids underestimating opportunities when multiple wastes are stacked on one cell (critical for yellow pair decisions).

- Dynamic survival policy with energy reserve estimation.
  - Justification: prevents unsafe actions and lowers death risk when carrying waste.

- Decontamination-aware constraints (loaded robots avoid decontamination entry; emergency drop in survival mode).
  - Justification: preserves viability and avoids dead-end states.

- Local perception model fixed in code.
  - Justification: the global perception switch was removed; agents now always rely on local perception plus memory/messages.

- Lightweight communication protocol (`waste_found`, `need_pickup`, `load_status`).
  - Justification: enables practical coordination without heavy negotiation overhead.

- Correct handoff signaling from actual drop events.
  - Justification: `need_pickup` is now based on inventory diff after action, preventing false downstream alerts.

- Asynchronous mailbox with one-tick delay and communication metrics (`messages_sent`).
  - Justification: realistic decoupling between send/receive and measurable collaboration cost.

- Message-focus persistence with Euclidean preemption.
  - Justification: reduces frequent target switching while still allowing better nearby opportunities.

- Return retarget memory for green and yellow.
  - Justification: captures actionable nearby targets during recovery/recharge and resumes productive flow faster.

- Yellow exact energy-feasibility planning for endgame transform/drop progression.
  - Justification: replaces fixed heuristics with guaranteed-survival planning and better eastward progress.

- Green anti-loop safeguards near decontamination.
  - Justification: no-repick windows and decon hold behavior prevent repetitive pickup/drop oscillations.

- Green exhausted-zone exploration memory.
  - Justification: top/bottom zone TTL memory and row-bounded exploration reduce repeated scans of known empty halves.

- Decision trace instrumentation (`decision_reason`, `decision_target`, `why=` logs).
  - Justification: supports debugging, analysis, and reproducible tuning.

## Evaluation and outputs

The model is evaluated through repeated simulation runs with visual inspection and exported analytics.

Main outputs:
- per-tick state history in the model,
- csv reports in `reports/report_tick_*/simulation_data.csv`,
- aggregate analytics from `src/analytics.py`,
- iterative experiment notes in `reports/intelligence_log.md`.

## Current scope and limitation

The repository covers assignment step 1 and step 2 (communication-enabled agents). Step 3 uncertainty modeling is not yet implemented as a dedicated extension.

Current limitations remain:
- communication is still one-way `inform` style (no negotiation/acknowledgment),
- quantity memory from messages is opportunistic and can still become stale between refreshes,
- policy tuning remains scenario-dependent (thresholds may require calibration per map dynamics).