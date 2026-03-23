# Lightweight AUML protocol for step 2

## Objective

This protocol adds explicit information sharing between robot roles to improve handoff quality, reduce unsafe decisions, and stabilize target commitment.

## Agent roles

- `GreenAgent`: collects `green`, performs `2 green -> 1 yellow`, and prepares upstream handoff.
- `YellowAgent`: collects `yellow`, performs `2 yellow -> 1 red`, and relays to downstream disposal.
- `RedAgent`: collects `red` and disposes it in `z3`.

## Message set

All messages are modeled as lightweight `inform`-style signals sent through the internal mailbox.

- `waste_found`
  - meaning: announces detected waste of a given type and position.
  - delivery: sent to the role that can process the waste type.
  - fields: `{ pos, waste_type, count }`.

- `need_pickup`
  - meaning: announces that dropped waste is available for the downstream role.
  - delivery: sent to the role that can process the dropped type.
  - fields: `{ pos, waste_type }`.
  - guard: emitted only for actual dropped waste types computed from inventory diff (prevents false handoff alerts).

- `load_status`
  - meaning: reports current downstream availability and workload state.
  - fields: `{ role, target_waste, available, is_active, last_action, pos }`.
  - `available` uses locally known quantities (`count`) plus carried target items.

## Delivery model

Communication is asynchronous with one-tick delayed delivery:
- messages emitted at tick `t` are readable at tick `t+1`,
- each agent processes its mailbox during the next deliberation cycle,
- no direct synchronous negotiation is used.

## Implemented coordination patterns

Current coordination patterns include:

- Recovery-aware upstream pause:
  - when green receives yellow `load_status` indicating sufficient downstream availability,
  - and green is not carrying waste,
  - green can prioritize recharge before resuming collection.

- Persistent message focus:
  - robots keep a `message_focus_target` across ticks,
  - switching occurs only when a new message-derived target is strictly Euclidean-closer.

- Return retarget caching:
  - during survival/recharge return, green and yellow can memorize nearby relevant waste,
  - after recovery they may prioritize this cached retarget before broad exploration.

- Quantity-aware yellow pair logic:
  - yellow wait-for-pair reasoning uses quantity-aware known counts,
  - stacked yellow waste on the same cell is treated as a valid pair opportunity.

These rules reduce unsafe pickups, lower oscillations, and improve handoff continuity.

## Scope and limits

This protocol is intentionally lightweight:
- no contract-net bidding,
- no multi-round negotiation,
- no reliability layer beyond mailbox delivery.

The design remains sufficient for the assignment objective of adding practical communication to agent decision-making.
