# Radioactive waste mission

## Project context

This project implements an agent-based simulation of robots cleaning dangerous waste in a hostile environment with increasing radioactivity from west to east. It follows the assignment described in `../project.md` and focuses on step 1 (autonomous behavior) and step 2 (communication between agents).

## Source system and simulation frame

The source system is a waste-cleaning mission where specialized robots must coordinate under movement and energy constraints.

The simulation frame is a discrete grid world with:
- three zones (`z1`, `z2`, `z3`) of low, medium, and high radioactivity,
- three waste states (`green`, `yellow`, `red`),
- increasing waste generation pressure,
- a failure condition when total waste crosses a threshold.

The simulator executes one tick at a time and logs system-level indicators (waste inventory, disposal, survival, communication).

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
- Knowledge and memory: local `known_waste` memory with TTL expiration, visited-cell counters, and recent-position windows.
- Decision stability: intention lock, switch cooldown, and hysteresis to reduce oscillations.
- Dynamic survival policy: role-aware energy reserve estimation based on path cost and return-to-decontamination needs.
- Safety constraints: loaded robots avoid entering decontamination tiles and use emergency drop behavior in survival-critical states.
- Communication timing: one-tick asynchronous mailbox delivery with cumulative `messages_sent` tracking in model history.
- Communication payload enrichment: `load_status` includes workload, activity state, last action, and sender position.
- Role-specific viability exceptions: green can prioritize `pickup -> transform` in edge cases where local transform feasibility is immediate.
- Yellow endgame planning: exact energy-feasibility planning for farthest-east transform/drop progression before forced return.
- Debug traceability: per-step decision reason and target are stored and displayed in the UI (`why=` style diagnostics).

## Evaluation approach

The project is evaluated through repeated simulation runs with visual inspection and exported metrics.

Generated outputs include:
- per-tick history,
- csv reports in `reports/report_tick_*/simulation_data.csv`,
- aggregate plots produced by `src/analytics.py`.

The iterative tuning history is preserved in `reports/intelligence_log.md` as append-only experiment notes.

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
