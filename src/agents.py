# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
Robot agent classes: GreenAgent, YellowAgent, RedAgent.
Each follows the percepts -> deliberate -> do loop.
"""

import random
from src.config import (
    ZONE_1_END, ZONE_2_END, GRID_COLS, GRID_ROWS,
    AGENT_MAX_CARRY, GREEN_TO_YELLOW_COST, YELLOW_TO_RED_COST,
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
        self.knowledge = {
            "pos": (x, y),
            "percepts": {},
            "inventory": [],
            "step_count": 0,
            "known_waste": {},      # (x,y) -> waste_type
            "last_action": None,
            "facing": "right",
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

    # -- Agent loop ------------------------------------------------------------

    def step_agent(self, model):
        percepts = model.get_percepts(self)
        self._update_knowledge(percepts)
        action = self.deliberate(self.knowledge)
        new_percepts = model.do(self, action)
        if new_percepts:
            self._update_knowledge(new_percepts)
        self.knowledge["step_count"] += 1
        self.anim_frame += 1

    def _update_knowledge(self, percepts):
        self.knowledge["pos"] = (self.x, self.y)
        self.knowledge["percepts"] = percepts
        self.knowledge["inventory"] = list(self.inventory)

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

        # If we have a yellow waste, move east to drop it at zone boundary
        if "yellow" in inv:
            knowledge["facing"] = "right"
            # Drop at the eastern edge of z1 (border with z2)
            if pos[0] >= ZONE_1_END - 1:
                return ACTION_DROP
            return GreenAgent._direction_toward(pos, (ZONE_1_END - 1, pos[1]),
                                                self.allowed_zones)

        # If we have 2+ green, transform
        if green_count >= self.transform_cost:
            return ACTION_TRANSFORM

        # If there's green waste on current cell, pick it up
        if pos in percepts:
            cell = percepts[pos]
            if cell.get("waste"):
                for w in cell["waste"]:
                    if w == "green" and self.can_carry_more():
                        return ACTION_PICK_UP

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

        # If we have a red waste, move east to drop at z2 border
        if "red" in inv:
            knowledge["facing"] = "right"
            if pos[0] >= ZONE_2_END - 1:
                return ACTION_DROP
            return YellowAgent._direction_toward(pos, (ZONE_2_END - 1, pos[1]),
                                                 self.allowed_zones)

        # Transform if we have enough
        if yellow_count >= self.transform_cost:
            return ACTION_TRANSFORM

        # Pick up yellow on current cell
        if pos in percepts:
            cell = percepts[pos]
            if cell.get("waste"):
                for w in cell["waste"]:
                    if w == "yellow" and self.can_carry_more():
                        return ACTION_PICK_UP

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

        # If carrying red waste, go to disposal zone
        if "red" in inv:
            knowledge["facing"] = "right"
            disposal_col = GRID_COLS - 1
            if pos[0] >= disposal_col:
                return ACTION_DROP
            return RedAgent._direction_toward(pos, (disposal_col, pos[1]),
                                              self.allowed_zones)

        # Pick up red on current cell
        if pos in percepts:
            cell = percepts[pos]
            if cell.get("waste"):
                for w in cell["waste"]:
                    if w == "red" and self.can_carry_more():
                        return ACTION_PICK_UP

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
