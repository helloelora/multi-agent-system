# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
Robot agent classes: GreenAgent, YellowAgent, RedAgent.
Each follows the percepts -> deliberate -> do loop.
Includes energy system and inter-agent communication.
"""

import random
from src.config import (
    ZONE_1_END, ZONE_2_END, GRID_COLS, GRID_ROWS,
    AGENT_MAX_CARRY, GREEN_TO_YELLOW_COST, YELLOW_TO_RED_COST,
    ENERGY_ENABLED, AGENT_MAX_ENERGY,
    ENERGY_COST_MOVE, ENERGY_COST_PICKUP, ENERGY_COST_TRANSFORM,
    ENERGY_COST_DROP,
    COMMUNICATION_ENABLED,
    HEALTH_LOW_THRESHOLD,
    HEALTH_RESUME_THRESHOLD,
    DECISION_INTENTION_HOLD_TICKS,
    DECISION_SWITCH_MARGIN,
    KNOWLEDGE_WASTE_TTL,
    STUCK_REPLAN_TICKS,
)


# -- Actions -------------------------------------------------------------------
ACTION_MOVE_UP = "move_up"
ACTION_MOVE_DOWN = "move_down"
ACTION_MOVE_LEFT = "move_left"
ACTION_MOVE_RIGHT = "move_right"
ACTION_PICK_UP = "pick_up"
ACTION_TRANSFORM = "transform"
ACTION_DROP = "drop"
ACTION_IDLE = "idle"

ALL_MOVES = [ACTION_MOVE_UP, ACTION_MOVE_DOWN, ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT]

INTENT_SURVIVE = "survive"
INTENT_DELIVER = "deliver"
INTENT_TRANSFORM = "transform"
INTENT_PICKUP = "pickup"
INTENT_SEEK_WASTE = "seek_waste"
INTENT_EXPLORE = "explore"

# Energy costs per action
_ACTION_ENERGY_COST = {
    ACTION_MOVE_UP: ENERGY_COST_MOVE,
    ACTION_MOVE_DOWN: ENERGY_COST_MOVE,
    ACTION_MOVE_LEFT: ENERGY_COST_MOVE,
    ACTION_MOVE_RIGHT: ENERGY_COST_MOVE,
    ACTION_PICK_UP: ENERGY_COST_PICKUP,
    ACTION_TRANSFORM: ENERGY_COST_TRANSFORM,
    ACTION_DROP: ENERGY_COST_DROP,
    ACTION_IDLE: 0,
}


class RobotAgent:
    """Base class for all robots."""

    robot_type = "base"
    allowed_zones = []
    target_waste = None
    transform_cost = 0
    output_waste = None

    def __init__(self, agent_id, x, y):
        self.agent_id = agent_id
        self.x = x
        self.y = y
        self.is_human = False
        self.inventory = []        # list of waste_type strings
        self.energy = AGENT_MAX_ENERGY if ENERGY_ENABLED else AGENT_MAX_ENERGY
        self.mailbox = []          # incoming messages for communication
        self.knowledge = {
            "pos": (x, y),
            "prev_pos": (x, y),
            "percepts": {},
            "inventory": [],
            "step_count": 0,
            "known_waste": {},      # (x,y) -> {"type": str, "ttl": int}
            "known_decontamination": set(),
            "last_action": None,
            "facing": "right",
            "energy": self.energy,
            "messages": [],         # messages received this tick
            "current_intention": INTENT_EXPLORE,
            "intention_target": None,
            "intention_lock": 0,
            "stuck_counter": 0,
            "explore_target": None,
            "survival_mode": False,
        }
        self.anim_frame = 0

    @property
    def pos(self):
        return (self.x, self.y)

    @pos.setter
    def pos(self, value):
        self.x, self.y = value

    def carry_count(self):
        return len(self.inventory)

    def can_carry_more(self):
        return self.carry_count() < AGENT_MAX_CARRY

    def has_energy_for(self, action):
        """Check if the robot has enough energy for the given action."""
        if not ENERGY_ENABLED:
            return True
        cost = _ACTION_ENERGY_COST.get(action, 0)
        return self.energy >= cost

    def send_message(self, model, msg_type, content):
        """Post a message to the model's message board for delivery next tick."""
        if not COMMUNICATION_ENABLED:
            return
        msg = {"from": self.agent_id, "type": msg_type, "content": content}
        model.message_board.append(msg)

    # -- Agent loop ------------------------------------------------------------

    def step_agent(self, model):
        # Deliver messages from mailbox into knowledge
        self.knowledge["messages"] = list(self.mailbox)
        self.mailbox.clear()

        percepts = model.get_percepts(self)
        self._update_knowledge(percepts)
        action = self.deliberate(self.knowledge)

        # Energy gate: if energy system is on and not enough energy, force idle
        if ENERGY_ENABLED and not self.has_energy_for(action):
            action = ACTION_IDLE

        new_percepts = model.do(self, action)

        # Energy bookkeeping
        if ENERGY_ENABLED:
            cost = _ACTION_ENERGY_COST.get(action, 0)
            self.energy = max(0, self.energy - cost)
            self.knowledge["energy"] = self.energy

        if new_percepts:
            self._update_knowledge(new_percepts)
        self.knowledge["step_count"] += 1
        self.knowledge["last_action"] = action
        self.anim_frame += 1

        # Communication: broadcast useful info after acting
        self._broadcast(model, percepts)

    def _broadcast(self, model, percepts):
        """Send messages about the environment after taking action."""
        if not COMMUNICATION_ENABLED:
            return
        pos = self.pos
        for p, contents in percepts.items():
            if contents.get("waste"):
                for wtype in contents["waste"]:
                    if wtype != self.target_waste:
                        # Found waste we can't handle — broadcast it
                        self.send_message(model, "waste_found",
                                          {"pos": p, "waste_type": wtype})
        # If we just dropped transformed waste, announce it
        last = self.knowledge.get("last_action")
        if last == ACTION_DROP and self.output_waste:
            self.send_message(model, "need_pickup",
                              {"pos": pos, "waste_type": self.output_waste})
        # If area around us has no waste, announce clear
        has_waste = any(contents.get("waste") for contents in percepts.values())
        if not has_waste:
            self.send_message(model, "area_clear", {"pos": pos})

    def _update_knowledge(self, percepts):
        prev_pos = self.knowledge.get("pos", (self.x, self.y))
        self.knowledge["pos"] = (self.x, self.y)
        self.knowledge["prev_pos"] = prev_pos
        self.knowledge["percepts"] = percepts
        self.knowledge["inventory"] = list(self.inventory)
        self.knowledge["energy"] = self.energy

        moved = (self.x, self.y) != prev_pos
        last_action = self.knowledge.get("last_action")
        if moved or last_action in (ACTION_PICK_UP, ACTION_TRANSFORM, ACTION_DROP):
            self.knowledge["stuck_counter"] = 0
        elif last_action in ALL_MOVES:
            self.knowledge["stuck_counter"] = self.knowledge.get("stuck_counter", 0) + 1

        for known_pos in list(self.knowledge["known_waste"].keys()):
            self.knowledge["known_waste"][known_pos]["ttl"] -= 1
            if self.knowledge["known_waste"][known_pos]["ttl"] <= 0:
                self.knowledge["known_waste"].pop(known_pos, None)

        # Remember waste locations from percepts
        for pos, contents in percepts.items():
            if contents.get("waste"):
                for waste_type in contents["waste"]:
                    self.knowledge["known_waste"][pos] = {
                        "type": waste_type,
                        "ttl": KNOWLEDGE_WASTE_TTL,
                    }
            else:
                self.knowledge["known_waste"].pop(pos, None)

            if contents.get("decontamination"):
                self.knowledge["known_decontamination"].add(pos)

    def deliberate(self, knowledge):
        raise NotImplementedError

    # -- Helpers for deliberate ------------------------------------------------

    def _check_messages_for_target(self, knowledge):
        """Check mailbox for waste_found or need_pickup matching our target type.
        Returns a target position or None."""
        if not COMMUNICATION_ENABLED:
            return None
        for msg in knowledge.get("messages", []):
            if msg["type"] in ("waste_found", "need_pickup"):
                if msg["content"].get("waste_type") == self.target_waste:
                    return msg["content"]["pos"]
        return None

    @staticmethod
    def _get_zone(col):
        if col < ZONE_1_END:
            return 1
        elif col < ZONE_2_END:
            return 2
        return 3

    @staticmethod
    def _can_move_to(col, row, allowed_zones):
        if col < 0 or col >= GRID_COLS or row < 0 or row >= GRID_ROWS:
            return False
        zone = RobotAgent._get_zone(col)
        return zone in allowed_zones

    @staticmethod
    def _direction_toward(from_pos, to_pos, allowed_zones):
        """Return a move action toward to_pos, respecting zone constraints."""
        fx, fy = from_pos
        tx, ty = to_pos
        options = []
        if tx > fx and RobotAgent._can_move_to(fx + 1, fy, allowed_zones):
            options.append(ACTION_MOVE_RIGHT)
        if tx < fx and RobotAgent._can_move_to(fx - 1, fy, allowed_zones):
            options.append(ACTION_MOVE_LEFT)
        if ty > fy and RobotAgent._can_move_to(fx, fy + 1, allowed_zones):
            options.append(ACTION_MOVE_DOWN)
        if ty < fy and RobotAgent._can_move_to(fx, fy - 1, allowed_zones):
            options.append(ACTION_MOVE_UP)
        if options:
            return random.choice(options)
        return ACTION_IDLE

    @staticmethod
    def _random_move(pos, allowed_zones):
        fx, fy = pos
        moves = []
        for action, (dx, dy) in [(ACTION_MOVE_RIGHT, (1, 0)),
                                  (ACTION_MOVE_LEFT, (-1, 0)),
                                  (ACTION_MOVE_DOWN, (0, 1)),
                                  (ACTION_MOVE_UP, (0, -1))]:
            if RobotAgent._can_move_to(fx + dx, fy + dy, allowed_zones):
                moves.append(action)
        return random.choice(moves) if moves else ACTION_IDLE

    @staticmethod
    def _manhattan(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _nearest_known_waste(self, knowledge, waste_type):
        pos = knowledge["pos"]
        known_waste = knowledge.get("known_waste", {})
        candidates = [
            p for p, info in known_waste.items()
            if info.get("type") == waste_type and self._can_move_to(p[0], p[1], self.allowed_zones)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda p: self._manhattan(pos, p))

    def _select_intention(self, knowledge, candidates):
        """Choose intention with commitment/hysteresis.
        candidates: list[(intent, score, target)]
        """
        if not candidates:
            return INTENT_EXPLORE, None

        current_intent = knowledge.get("current_intention", INTENT_EXPLORE)
        current_target = knowledge.get("intention_target")
        lock = knowledge.get("intention_lock", 0)

        if knowledge.get("stuck_counter", 0) >= STUCK_REPLAN_TICKS:
            lock = 0

        scored = sorted(candidates, key=lambda item: item[1], reverse=True)
        best_intent, best_score, best_target = scored[0]
        current_entry = next((entry for entry in scored if entry[0] == current_intent), None)

        if current_entry and lock > 0:
            current_score = current_entry[1]
            new_target = current_entry[2] if current_entry[2] is not None else current_target
            if current_score + DECISION_SWITCH_MARGIN >= best_score:
                knowledge["current_intention"] = current_intent
                knowledge["intention_target"] = new_target
                knowledge["intention_lock"] = max(0, lock - 1)
                return current_intent, new_target

        knowledge["current_intention"] = best_intent
        knowledge["intention_target"] = best_target
        knowledge["intention_lock"] = DECISION_INTENTION_HOLD_TICKS
        return best_intent, best_target

    def _needs_survival_mode(self, knowledge):
        """Low-health hysteresis to avoid oscillation around the threshold."""
        if not ENERGY_ENABLED:
            knowledge["survival_mode"] = False
            return False

        energy = knowledge.get("energy", AGENT_MAX_ENERGY)
        survival_mode = knowledge.get("survival_mode", False)

        if survival_mode:
            if energy >= HEALTH_RESUME_THRESHOLD:
                knowledge["survival_mode"] = False
            else:
                knowledge["survival_mode"] = True
        else:
            if energy <= HEALTH_LOW_THRESHOLD:
                knowledge["survival_mode"] = True

        return knowledge.get("survival_mode", False)

    def _explore_with_target(self, knowledge, min_col=0, max_col=None):
        """Explore with a persistent waypoint to avoid dithering/random bouncing."""
        pos = knowledge["pos"]
        if max_col is None:
            max_col = GRID_COLS - 1

        def _valid_target(target):
            if not target:
                return False
            tx, ty = target
            if tx < min_col or tx > max_col:
                return False
            return self._can_move_to(tx, ty, self.allowed_zones)

        target = knowledge.get("explore_target")
        reached = target is not None and self._manhattan(pos, target) <= 1
        if reached:
            target = None

        if not _valid_target(target):
            for _ in range(20):
                tx = random.randint(min_col, max_col)
                ty = random.randint(0, GRID_ROWS - 1)
                if self._can_move_to(tx, ty, self.allowed_zones):
                    target = (tx, ty)
                    break

        if not target:
            return self._random_move(pos, self.allowed_zones)

        knowledge["explore_target"] = target
        knowledge["facing"] = "right" if target[0] > pos[0] else "left"
        return self._direction_toward(pos, target, self.allowed_zones)

    def _decontamination_action(self, knowledge):
        """Return an action toward a decontamination zone when life is low."""
        pos = knowledge["pos"]
        known_decon = list(knowledge.get("known_decontamination", set()))

        if pos in known_decon:
            return ACTION_IDLE

        if known_decon:
            closest = min(known_decon,
                          key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]))
            knowledge["facing"] = "right" if closest[0] > pos[0] else "left"
            return RobotAgent._direction_toward(pos, closest, self.allowed_zones)

        # No known zone yet: move toward the nearest center of an accessible zone
        mid_row = GRID_ROWS // 2
        default_targets = []
        if 1 in self.allowed_zones:
            default_targets.append(((0 + (ZONE_1_END - 1)) // 2, mid_row))
        if 2 in self.allowed_zones:
            default_targets.append(((ZONE_1_END + (ZONE_2_END - 1)) // 2, mid_row))
        if 3 in self.allowed_zones:
            default_targets.append(((ZONE_2_END + (GRID_COLS - 1)) // 2, mid_row))

        if default_targets:
            target = min(default_targets,
                         key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]))
        else:
            target = (pos[0], mid_row)

        knowledge["facing"] = "right" if target[0] > pos[0] else "left"
        return RobotAgent._direction_toward(pos, target, self.allowed_zones)


class GreenAgent(RobotAgent):
    """Collects green waste in z1, transforms 2 green -> 1 yellow, transports east."""

    robot_type = "green"
    allowed_zones = [1]
    target_waste = "green"
    transform_cost = GREEN_TO_YELLOW_COST
    output_waste = "yellow"

    def deliberate(self, knowledge):
        pos = knowledge["pos"]
        inv = knowledge["inventory"]
        percepts = knowledge["percepts"]
        green_count = inv.count("green")
        border_target = (ZONE_1_END - 1, pos[1])
        msg_target = self._check_messages_for_target(knowledge)
        nearest_green = self._nearest_known_waste(knowledge, "green")
        has_green_here = pos in percepts and "green" in percepts[pos].get("waste", [])

        candidates = []
        if self._needs_survival_mode(knowledge):
            candidates.append((INTENT_SURVIVE, 200.0, None))
        else:
            if "yellow" in inv:
                candidates.append((INTENT_DELIVER, 120.0 - self._manhattan(pos, border_target), border_target))
            if green_count >= self.transform_cost:
                candidates.append((INTENT_TRANSFORM, 105.0, None))
            if has_green_here and self.can_carry_more():
                candidates.append((INTENT_PICKUP, 95.0, pos))
            if msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
                candidates.append((INTENT_SEEK_WASTE, 85.0 - self._manhattan(pos, msg_target), msg_target))
            if nearest_green:
                candidates.append((INTENT_SEEK_WASTE, 70.0 - self._manhattan(pos, nearest_green), nearest_green))
            candidates.append((INTENT_EXPLORE, 20.0, None))

        intent, target = self._select_intention(knowledge, candidates)

        if intent == INTENT_SURVIVE:
            return self._decontamination_action(knowledge)
        if intent == INTENT_DELIVER:
            if pos[0] >= ZONE_1_END - 1:
                return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
            knowledge["facing"] = "right"
            return GreenAgent._direction_toward(pos, target or border_target, self.allowed_zones)
        if intent == INTENT_TRANSFORM:
            return ACTION_TRANSFORM if self.has_energy_for(ACTION_TRANSFORM) else ACTION_IDLE
        if intent == INTENT_PICKUP:
            return ACTION_PICK_UP if self.has_energy_for(ACTION_PICK_UP) else ACTION_IDLE
        if intent == INTENT_SEEK_WASTE and target:
            knowledge["facing"] = "right" if target[0] > pos[0] else "left"
            return GreenAgent._direction_toward(pos, target, self.allowed_zones)
        return self._explore_with_target(knowledge, min_col=0, max_col=ZONE_1_END - 1)


class YellowAgent(RobotAgent):
    """Collects yellow waste in z1-z2, transforms 2 yellow -> 1 red, transports east."""

    robot_type = "yellow"
    allowed_zones = [1, 2]
    target_waste = "yellow"
    transform_cost = YELLOW_TO_RED_COST
    output_waste = "red"

    def _explore_action(self, knowledge):
        """Yellow explores z1-z2 with a patrol bias near the handoff border."""
        pos = knowledge["pos"]
        border_bias = (ZONE_1_END, pos[1])
        if abs(pos[0] - ZONE_1_END) > 5:
            return YellowAgent._direction_toward(pos, border_bias, self.allowed_zones)
        return self._explore_with_target(knowledge, min_col=0, max_col=ZONE_2_END - 1)

    def deliberate(self, knowledge):
        pos = knowledge["pos"]
        inv = knowledge["inventory"]
        percepts = knowledge["percepts"]
        yellow_count = inv.count("yellow")
        border_target = (ZONE_2_END - 1, pos[1])
        msg_target = self._check_messages_for_target(knowledge)
        nearest_yellow = self._nearest_known_waste(knowledge, "yellow")
        has_yellow_here = pos in percepts and "yellow" in percepts[pos].get("waste", [])

        candidates = []
        if self._needs_survival_mode(knowledge):
            candidates.append((INTENT_SURVIVE, 200.0, None))
        else:
            if "red" in inv:
                candidates.append((INTENT_DELIVER, 120.0 - self._manhattan(pos, border_target), border_target))
            if yellow_count >= self.transform_cost:
                candidates.append((INTENT_TRANSFORM, 105.0, None))
            if has_yellow_here and self.can_carry_more():
                candidates.append((INTENT_PICKUP, 95.0, pos))
            if msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
                candidates.append((INTENT_SEEK_WASTE, 85.0 - self._manhattan(pos, msg_target), msg_target))
            if nearest_yellow:
                candidates.append((INTENT_SEEK_WASTE, 70.0 - self._manhattan(pos, nearest_yellow), nearest_yellow))
            patrol_target = (ZONE_1_END, pos[1])
            candidates.append((INTENT_EXPLORE, 20.0 - self._manhattan(pos, patrol_target), patrol_target))

        intent, target = self._select_intention(knowledge, candidates)

        if intent == INTENT_SURVIVE:
            return self._decontamination_action(knowledge)
        if intent == INTENT_DELIVER:
            if pos[0] >= ZONE_2_END - 1:
                return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
            knowledge["facing"] = "right"
            return YellowAgent._direction_toward(pos, target or border_target, self.allowed_zones)
        if intent == INTENT_TRANSFORM:
            return ACTION_TRANSFORM if self.has_energy_for(ACTION_TRANSFORM) else ACTION_IDLE
        if intent == INTENT_PICKUP:
            return ACTION_PICK_UP if self.has_energy_for(ACTION_PICK_UP) else ACTION_IDLE
        if intent == INTENT_SEEK_WASTE and target:
            knowledge["facing"] = "right" if target[0] > pos[0] else "left"
            return YellowAgent._direction_toward(pos, target, self.allowed_zones)
        if intent == INTENT_EXPLORE:
            return self._explore_action(knowledge)
        if target:
            return YellowAgent._direction_toward(pos, target, self.allowed_zones)
        return self._explore_action(knowledge)


class RedAgent(RobotAgent):
    """Collects red waste, transports to disposal zone in z3."""

    robot_type = "red"
    allowed_zones = [1, 2, 3]
    target_waste = "red"
    transform_cost = 0
    output_waste = None

    def _explore_action(self, knowledge):
        """Red explores with a bias toward z2-z3 where red waste/disposal flow happens."""
        pos = knowledge["pos"]
        z23_mid = ((ZONE_2_END + (GRID_COLS - 1)) // 2, pos[1])
        if pos[0] < ZONE_2_END - 2:
            return RedAgent._direction_toward(pos, z23_mid, self.allowed_zones)
        return self._explore_with_target(knowledge, min_col=ZONE_1_END, max_col=GRID_COLS - 1)

    def deliberate(self, knowledge):
        pos = knowledge["pos"]
        inv = knowledge["inventory"]
        percepts = knowledge["percepts"]
        disposal_target = (GRID_COLS - 1, pos[1])
        msg_target = self._check_messages_for_target(knowledge)
        nearest_red = self._nearest_known_waste(knowledge, "red")
        has_red_here = pos in percepts and "red" in percepts[pos].get("waste", [])

        candidates = []
        if self._needs_survival_mode(knowledge):
            candidates.append((INTENT_SURVIVE, 200.0, None))
        else:
            if "red" in inv:
                candidates.append((INTENT_DELIVER, 125.0 - self._manhattan(pos, disposal_target), disposal_target))
            if has_red_here and self.can_carry_more():
                candidates.append((INTENT_PICKUP, 95.0, pos))
            if msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
                candidates.append((INTENT_SEEK_WASTE, 85.0 - self._manhattan(pos, msg_target), msg_target))
            if nearest_red:
                candidates.append((INTENT_SEEK_WASTE, 70.0 - self._manhattan(pos, nearest_red), nearest_red))
            patrol_target = (ZONE_2_END, pos[1])
            candidates.append((INTENT_EXPLORE, 20.0 - self._manhattan(pos, patrol_target), patrol_target))

        intent, target = self._select_intention(knowledge, candidates)

        if intent == INTENT_SURVIVE:
            return self._decontamination_action(knowledge)
        if intent == INTENT_DELIVER:
            if pos[0] >= GRID_COLS - 1:
                return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
            knowledge["facing"] = "right"
            return RedAgent._direction_toward(pos, target or disposal_target, self.allowed_zones)
        if intent == INTENT_PICKUP:
            return ACTION_PICK_UP if self.has_energy_for(ACTION_PICK_UP) else ACTION_IDLE
        if intent == INTENT_SEEK_WASTE and target:
            knowledge["facing"] = "right" if target[0] > pos[0] else "left"
            return RedAgent._direction_toward(pos, target, self.allowed_zones)
        if intent == INTENT_EXPLORE:
            return self._explore_action(knowledge)
        if target:
            return RedAgent._direction_toward(pos, target, self.allowed_zones)
        return self._explore_action(knowledge)


# =============================================================================
# Human-controlled agent subclasses
# =============================================================================

class HumanGreenAgent(GreenAgent):
    """Player-controlled green robot. deliberate() returns pending_action."""

    def __init__(self, agent_id, x, y):
        super().__init__(agent_id, x, y)
        self.pending_action = ACTION_IDLE
        self.is_human = True

    def deliberate(self, knowledge):
        action = self.pending_action
        self.pending_action = ACTION_IDLE
        return action


class HumanYellowAgent(YellowAgent):
    """Player-controlled yellow robot. deliberate() returns pending_action."""

    def __init__(self, agent_id, x, y):
        super().__init__(agent_id, x, y)
        self.pending_action = ACTION_IDLE
        self.is_human = True

    def deliberate(self, knowledge):
        action = self.pending_action
        self.pending_action = ACTION_IDLE
        return action


class HumanRedAgent(RedAgent):
    """Player-controlled red robot. deliberate() returns pending_action."""

    def __init__(self, agent_id, x, y):
        super().__init__(agent_id, x, y)
        self.pending_action = ACTION_IDLE
        self.is_human = True

    def deliberate(self, knowledge):
        action = self.pending_action
        self.pending_action = ACTION_IDLE
        return action


HUMAN_AGENT_CLASSES = {
    "green": HumanGreenAgent,
    "yellow": HumanYellowAgent,
    "red": HumanRedAgent,
}
