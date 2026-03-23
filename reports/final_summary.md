# Final summary

## Project objective

This project models a multi-agent radioactive waste mission in a hostile environment split into three zones (`z1`, `z2`, `z3`) with increasing radioactivity. The goal is to maintain system stability by collecting, transforming, and disposing waste faster than it is generated.

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

- Dynamic survival policy with energy reserve estimation.
  - Justification: prevents unsafe actions and lowers death risk when carrying waste.

- Decontamination-aware constraints (loaded robots avoid decontamination entry; emergency drop in survival mode).
  - Justification: preserves viability and avoids dead-end states.

- Lightweight communication protocol (`waste_found`, `need_pickup`, `area_clear`, `load_status`).
  - Justification: enables practical coordination without heavy negotiation overhead.

- Asynchronous mailbox with one-tick delay and communication metrics (`messages_sent`).
  - Justification: realistic decoupling between send/receive and measurable collaboration cost.

- Yellow exact energy-feasibility planning for endgame transform/drop progression.
  - Justification: replaces fixed heuristics with guaranteed-survival planning and better eastward progress.

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

## Conclusion

The implemented system is a constrained, explainable multi-agent pipeline with explicit coordination, survival safeguards, and measurable behavior. The main contribution is not only functional collaboration between roles, but also robust decision engineering to keep the mission viable under increasing pressure.
