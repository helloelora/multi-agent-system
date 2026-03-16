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
    ENERGY_COST_DROP, ENERGY_RECHARGE_IDLE,
    COMMUNICATION_ENABLED,
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
        self.inventory = []        # list of waste_type strings
        self.energy = AGENT_MAX_ENERGY if ENERGY_ENABLED else AGENT_MAX_ENERGY
        self.mailbox = []          # incoming messages for communication
        self.knowledge = {
            "pos": (x, y),
            "percepts": {},
            "inventory": [],
            "step_count": 0,
            "known_waste": {},      # (x,y) -> waste_type
            "last_action": None,
            "facing": "right",
            "energy": self.energy,
            "messages": [],         # messages received this tick
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
            if action == ACTION_IDLE:
                self.energy = min(AGENT_MAX_ENERGY,
                                  self.energy + ENERGY_RECHARGE_IDLE)
            else:
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
        self.knowledge["pos"] = (self.x, self.y)
        self.knowledge["percepts"] = percepts
        self.knowledge["inventory"] = list(self.inventory)
        self.knowledge["energy"] = self.energy

        # Remember waste locations from percepts
        for pos, contents in percepts.items():
            if contents.get("waste"):
                for w in contents["waste"]:
                    self.knowledge["known_waste"][pos] = w
            else:
                self.knowledge["known_waste"].pop(pos, None)

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

        # Energy check: if low energy, idle to recharge
        if ENERGY_ENABLED and knowledge.get("energy", 100) < ENERGY_COST_TRANSFORM:
            # Only idle if we can't do anything useful
            if knowledge.get("energy", 100) < ENERGY_COST_MOVE:
                return ACTION_IDLE

        # If we have a yellow waste, move east to drop it at zone boundary
        if "yellow" in inv:
            knowledge["facing"] = "right"
            # Drop at the eastern edge of z1 (border with z2)
            if pos[0] >= ZONE_1_END - 1:
                if not self.has_energy_for(ACTION_DROP):
                    return ACTION_IDLE
                return ACTION_DROP
            if not self.has_energy_for(ACTION_MOVE_RIGHT):
                return ACTION_IDLE
            return GreenAgent._direction_toward(pos, (ZONE_1_END - 1, pos[1]),
                                                self.allowed_zones)

        # If we have 2+ green, transform
        if green_count >= self.transform_cost:
            if not self.has_energy_for(ACTION_TRANSFORM):
                return ACTION_IDLE
            return ACTION_TRANSFORM

        # If there's green waste on current cell, pick it up
        if pos in percepts:
            cell = percepts[pos]
            if cell.get("waste"):
                for w in cell["waste"]:
                    if w == "green" and self.can_carry_more():
                        if not self.has_energy_for(ACTION_PICK_UP):
                            return ACTION_IDLE
                        return ACTION_PICK_UP

        # Check messages for waste tips
        msg_target = self._check_messages_for_target(knowledge)
        if msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
            knowledge["facing"] = "right" if msg_target[0] > pos[0] else "left"
            return GreenAgent._direction_toward(pos, msg_target, self.allowed_zones)

        # Look for known green waste nearby
        known = knowledge["known_waste"]
        green_positions = [p for p, w in known.items() if w == "green"]
        if green_positions:
            closest = min(green_positions,
                          key=lambda p: abs(p[0]-pos[0]) + abs(p[1]-pos[1]))
            knowledge["facing"] = "right" if closest[0] > pos[0] else "left"
            return GreenAgent._direction_toward(pos, closest, self.allowed_zones)

        # Wander
        return GreenAgent._random_move(pos, self.allowed_zones)


class YellowAgent(RobotAgent):
    """Collects yellow waste in z1-z2, transforms 2 yellow -> 1 red, transports east."""

    robot_type = "yellow"
    allowed_zones = [1, 2]
    target_waste = "yellow"
    transform_cost = YELLOW_TO_RED_COST
    output_waste = "red"

    def deliberate(self, knowledge):
        pos = knowledge["pos"]
        inv = knowledge["inventory"]
        percepts = knowledge["percepts"]
        yellow_count = inv.count("yellow")

        # Energy check
        if ENERGY_ENABLED and knowledge.get("energy", 100) < ENERGY_COST_MOVE:
            return ACTION_IDLE

        # If we have a red waste, move east to drop at z2 border
        if "red" in inv:
            knowledge["facing"] = "right"
            if pos[0] >= ZONE_2_END - 1:
                if not self.has_energy_for(ACTION_DROP):
                    return ACTION_IDLE
                return ACTION_DROP
            return YellowAgent._direction_toward(pos, (ZONE_2_END - 1, pos[1]),
                                                 self.allowed_zones)

        # Transform if we have enough
        if yellow_count >= self.transform_cost:
            if not self.has_energy_for(ACTION_TRANSFORM):
                return ACTION_IDLE
            return ACTION_TRANSFORM

        # Pick up yellow on current cell
        if pos in percepts:
            cell = percepts[pos]
            if cell.get("waste"):
                for w in cell["waste"]:
                    if w == "yellow" and self.can_carry_more():
                        if not self.has_energy_for(ACTION_PICK_UP):
                            return ACTION_IDLE
                        return ACTION_PICK_UP

        # Check messages for waste tips
        msg_target = self._check_messages_for_target(knowledge)
        if msg_target:
            knowledge["facing"] = "right" if msg_target[0] > pos[0] else "left"
            return YellowAgent._direction_toward(pos, msg_target, self.allowed_zones)

        # Seek known yellow waste
        known = knowledge["known_waste"]
        yellow_positions = [p for p, w in known.items() if w == "yellow"]
        if yellow_positions:
            closest = min(yellow_positions,
                          key=lambda p: abs(p[0]-pos[0]) + abs(p[1]-pos[1]))
            knowledge["facing"] = "right" if closest[0] > pos[0] else "left"
            return YellowAgent._direction_toward(pos, closest, self.allowed_zones)

        # Patrol near z1/z2 border to pick up dropped waste
        border_x = ZONE_1_END
        if abs(pos[0] - border_x) > 3:
            return YellowAgent._direction_toward(pos, (border_x, pos[1]),
                                                 self.allowed_zones)

        return YellowAgent._random_move(pos, self.allowed_zones)


class RedAgent(RobotAgent):
    """Collects red waste, transports to disposal zone in z3."""

    robot_type = "red"
    allowed_zones = [1, 2, 3]
    target_waste = "red"
    transform_cost = 0
    output_waste = None

    def deliberate(self, knowledge):
        pos = knowledge["pos"]
        inv = knowledge["inventory"]
        percepts = knowledge["percepts"]

        # Energy check
        if ENERGY_ENABLED and knowledge.get("energy", 100) < ENERGY_COST_MOVE:
            return ACTION_IDLE

        # If carrying red waste, go to disposal zone
        if "red" in inv:
            knowledge["facing"] = "right"
            disposal_col = GRID_COLS - 1
            if pos[0] >= disposal_col:
                if not self.has_energy_for(ACTION_DROP):
                    return ACTION_IDLE
                return ACTION_DROP
            return RedAgent._direction_toward(pos, (disposal_col, pos[1]),
                                              self.allowed_zones)

        # Pick up red on current cell
        if pos in percepts:
            cell = percepts[pos]
            if cell.get("waste"):
                for w in cell["waste"]:
                    if w == "red" and self.can_carry_more():
                        if not self.has_energy_for(ACTION_PICK_UP):
                            return ACTION_IDLE
                        return ACTION_PICK_UP

        # Check messages for waste tips
        msg_target = self._check_messages_for_target(knowledge)
        if msg_target:
            knowledge["facing"] = "right" if msg_target[0] > pos[0] else "left"
            return RedAgent._direction_toward(pos, msg_target, self.allowed_zones)

        # Seek known red waste
        known = knowledge["known_waste"]
        red_positions = [p for p, w in known.items() if w == "red"]
        if red_positions:
            closest = min(red_positions,
                          key=lambda p: abs(p[0]-pos[0]) + abs(p[1]-pos[1]))
            knowledge["facing"] = "right" if closest[0] > pos[0] else "left"
            return RedAgent._direction_toward(pos, closest, self.allowed_zones)

        # Patrol near z2/z3 border
        border_x = ZONE_2_END
        if abs(pos[0] - border_x) > 3:
            return RedAgent._direction_toward(pos, (border_x, pos[1]),
                                              self.allowed_zones)

        return RedAgent._random_move(pos, self.allowed_zones)
