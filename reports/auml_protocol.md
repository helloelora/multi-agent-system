# Lightweight auml protocol for step 2

## Objective

This protocol adds explicit information sharing between robot roles to improve handoff quality and reduce idle or conflicting movements.

## Agent roles

- `GreenAgent`: collects `green`, performs `2 green -> 1 yellow`, and prepares upstream handoff.
- `YellowAgent`: collects `yellow`, performs `2 yellow -> 1 red`, and relays to downstream disposal.
- `RedAgent`: collects `red` and disposes it in `z3`.

## Message set

All messages are currently modeled as `inform`-style signals sent through the internal mailbox.

- `waste_found`
  - meaning: announces detected waste of a given type and position.
  - typical fields: `{ kind, pos, sender_role }`.

- `need_pickup`
  - meaning: announces that transformed waste is now available for the downstream role.
  - typical fields: `{ kind, pos, sender_role }`.

- `load_status`
  - meaning: reports current downstream availability and workload state.
  - typical fields: `{ role, target_waste, available, is_active, last_action, pos }`.

- `area_clear`
  - meaning: announces that no waste is currently perceived in the sender local neighborhood.
  - typical fields: `{ pos, sender_role }`.

## Delivery model

Communication is asynchronous with one-tick delayed delivery:
- messages emitted at tick `t` are readable at tick `t+1`,
- each agent processes its mailbox during the next deliberation cycle,
- no direct synchronous negotiation is used.

## Implemented coordination pattern

One active rule is a recovery-aware upstream pause:
- when a green robot receives a yellow `load_status` indicating sufficient downstream availability,
- and green is not carrying waste,
- green can prioritize recharge in decontamination before resuming collection.

This rule reduces unsafe pickups during low-energy phases and improves pipeline continuity.

## Scope and limits

This protocol is intentionally lightweight:
- no contract-net bidding,
- no multi-round negotiation,
- no reliability layer beyond mailbox delivery.

The design remains sufficient for the assignment objective of adding practical communication to agent decision-making.
