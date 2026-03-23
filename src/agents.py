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
import heapq
from collections import Counter
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
    INTENTION_SWITCH_COOLDOWN_TICKS,
    RECENT_POS_WINDOW,
    RECENT_POS_PENALTY,
    FRONTIER_INFO_GAIN_WEIGHT,
    TARGET_ENERGY_RISK_WEIGHT,
    YELLOW_SEEK_BASE_SCORE,
    YELLOW_MESSAGE_SEEK_BASE_SCORE,
    GREEN_PICKUP_RISK_MARGIN,
    GREEN_PICKUP_RISK_PENALTY,
    HEALTH_LOSS_CARRY_GREEN,
    HEALTH_LOSS_CARRY_YELLOW,
    HEALTH_LOSS_CARRY_RED,
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
INTENT_RECHARGE = "recharge"

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
            "known_waste": {},      # (x,y) -> {"type": str, "ttl": int, "count": int}
            "known_decontamination": set(),
            "last_action": None,
            "facing": "right",
            "energy": self.energy,
            "messages": [],         # messages received this tick
            "current_intention": INTENT_EXPLORE,
            "intention_target": None,
            "intention_lock": 0,
            "intent_cooldown": 0,
            "stuck_counter": 0,
            "seek_idle_counter": 0,
            "explore_target": None,
            "survival_mode": False,
            "path_goal": None,
            "path_plan": [],
            "pickup_cooldown": 0,
            "recent_positions": [(x, y)],
            "visited_count": {(x, y): 0 for x in range(GRID_COLS) for y in range(GRID_ROWS)},
            "decision_reason": "",
            "decision_target": None,
            "nav_next": None,
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

    def send_message(self, model, msg_type, content, to_role=None, to_agent_id=None):
        """Queue a directed message for next-tick delivery."""
        if not COMMUNICATION_ENABLED:
            return
        msg = {
            "from": self.agent_id,
            "from_type": self.robot_type,
            "type": msg_type,
            "content": content,
            "to_role": to_role,
            "to_agent_id": to_agent_id,
        }
        model.post_message(msg)

    @staticmethod
    def _recipient_role_for_waste(waste_type):
        if waste_type == "yellow":
            return "yellow"
        if waste_type == "red":
            return "red"
        if waste_type == "green":
            return "green"
        return None

    # -- Agent loop ------------------------------------------------------------

    def step_agent(self, model):
        # Deliver messages from mailbox into knowledge
        self.knowledge["messages"] = list(self.mailbox)
        self.mailbox.clear()
        if "initial_waste_counts" not in self.knowledge:
            self.knowledge["initial_waste_counts"] = dict(model.get_waste_counts())

        percepts = model.get_percepts(self)
        self._update_knowledge(percepts)
        action = self.deliberate(self.knowledge)

        # Energy gate: if energy system is on and not enough energy, force idle
        if ENERGY_ENABLED and not self.has_energy_for(action):
            action = ACTION_IDLE

        inventory_before_action = list(self.inventory)
        new_percepts = model.do(self, action)
        dropped_waste_types = []
        if (
            action == ACTION_DROP
            and not (self.robot_type == "red" and self.pos in model.disposal_zones)
        ):
            before_counts = Counter(inventory_before_action)
            after_counts = Counter(self.inventory)
            for wtype, count_before in before_counts.items():
                if count_before > after_counts.get(wtype, 0):
                    dropped_waste_types.append(wtype)

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
        self._broadcast(model, percepts, dropped_waste_types=dropped_waste_types)

    def _broadcast(self, model, percepts, dropped_waste_types=None):
        """Send messages about the environment after taking action."""
        if not COMMUNICATION_ENABLED:
            return
        pos = self.pos
        for p, contents in percepts.items():
            if contents.get("waste"):
                waste_counts = Counter(contents["waste"])
                for wtype, wcount in waste_counts.items():
                    if wtype != self.target_waste:
                        # Found waste we cannot process: notify the relevant role only.
                        recipient_role = self._recipient_role_for_waste(wtype)
                        self.send_message(model, "waste_found",
                                          {"pos": p, "waste_type": wtype, "count": int(wcount)},
                                          to_role=recipient_role)
        # If we just dropped waste, announce only actual dropped types that this
        # role cannot process itself (prevents false yellow->red handoffs).
        if dropped_waste_types:
            for wtype in sorted(set(dropped_waste_types)):
                if wtype == self.target_waste:
                    continue
                recipient_role = self._recipient_role_for_waste(wtype)
                self.send_message(model, "need_pickup",
                                  {"pos": pos, "waste_type": wtype},
                                  to_role=recipient_role)

        # AUML-like INFORM: share local task load to help upstream robots decide to rest.
        if self.robot_type in ("yellow", "red"):
            known_target = sum(
                max(1, int(info.get("count", 1)))
                for info in self.knowledge.get("known_waste", {}).values()
                if info.get("type") == self.target_waste
            )
            carrying_target = self.inventory.count(self.target_waste)
            last_action = self.knowledge.get("last_action")
            is_active = bool(self.inventory) or (last_action not in (None, ACTION_IDLE))
            self.send_message(
                model,
                "load_status",
                {
                    "performative": "inform",
                    "role": self.robot_type,
                    "target_waste": self.target_waste,
                    "available": known_target + carrying_target,
                    "is_active": is_active,
                    "last_action": last_action,
                    "pos": pos,
                },
                to_role=("green" if self.robot_type == "yellow" else "yellow"),
            )

    def _update_knowledge(self, percepts):
        prev_pos = self.knowledge.get("pos", (self.x, self.y))
        self.knowledge["pos"] = (self.x, self.y)
        self.knowledge["prev_pos"] = prev_pos
        self.knowledge["percepts"] = percepts
        self.knowledge["inventory"] = list(self.inventory)
        self.knowledge["energy"] = self.energy
        visited = self.knowledge.setdefault("visited_count", {})
        visited[(self.x, self.y)] = visited.get((self.x, self.y), 0) + 1

        recent_positions = self.knowledge.setdefault("recent_positions", [])
        recent_positions.append((self.x, self.y))
        max_recent = max(2, int(RECENT_POS_WINDOW))
        if len(recent_positions) > max_recent:
            del recent_positions[:-max_recent]

        moved = (self.x, self.y) != prev_pos
        last_action = self.knowledge.get("last_action")
        if moved or last_action in (ACTION_PICK_UP, ACTION_TRANSFORM, ACTION_DROP):
            self.knowledge["stuck_counter"] = 0
        elif last_action in ALL_MOVES:
            self.knowledge["stuck_counter"] = self.knowledge.get("stuck_counter", 0) + 1

        current_intent = self.knowledge.get("current_intention")
        if current_intent == INTENT_SEEK_WASTE and last_action == ACTION_IDLE:
            self.knowledge["seek_idle_counter"] = self.knowledge.get("seek_idle_counter", 0) + 1
        elif moved or last_action in (ACTION_PICK_UP, ACTION_TRANSFORM, ACTION_DROP):
            self.knowledge["seek_idle_counter"] = 0

        cooldown = self.knowledge.get("pickup_cooldown", 0)
        if cooldown > 0:
            self.knowledge["pickup_cooldown"] = cooldown - 1

        intent_cooldown = self.knowledge.get("intent_cooldown", 0)
        if intent_cooldown > 0:
            self.knowledge["intent_cooldown"] = intent_cooldown - 1

        avoid_ttl = self.knowledge.get("yellow_avoid_ttl", 0)
        if avoid_ttl > 0:
            self.knowledge["yellow_avoid_ttl"] = avoid_ttl - 1
        elif self.knowledge.get("yellow_avoid_pos") is not None:
            self.knowledge["yellow_avoid_pos"] = None

        for known_pos in list(self.knowledge["known_waste"].keys()):
            self.knowledge["known_waste"][known_pos]["ttl"] -= 1
            if self.knowledge["known_waste"][known_pos]["ttl"] <= 0:
                self.knowledge["known_waste"].pop(known_pos, None)

        # Remember waste locations from percepts
        for pos, contents in percepts.items():
            if contents.get("waste"):
                waste_counts = Counter(contents["waste"])
                for waste_type, waste_count in waste_counts.items():
                    self.knowledge["known_waste"][pos] = {
                        "type": waste_type,
                        "ttl": KNOWLEDGE_WASTE_TTL,
                        "count": int(waste_count),
                    }
            else:
                self.knowledge["known_waste"].pop(pos, None)

            if contents.get("decontamination"):
                self.knowledge["known_decontamination"].add(pos)

    def deliberate(self, knowledge):
        raise NotImplementedError

    def _set_decision_debug(self, knowledge, reason, target=None):
        knowledge["decision_reason"] = reason
        knowledge["decision_target"] = target

    # -- Helpers for deliberate ------------------------------------------------

    def _check_messages_for_target(self, knowledge):
        """Check mailbox for waste_found or need_pickup matching our target type.
        Returns a target position or None."""
        if not COMMUNICATION_ENABLED:
            return None
        pos_self = knowledge.get("pos", self.pos)
        known = knowledge.setdefault("known_waste", {})
        current_focus = knowledge.get("message_focus_target")
        if isinstance(current_focus, (list, tuple)) and len(current_focus) == 2:
            current_focus = (int(current_focus[0]), int(current_focus[1]))
        else:
            current_focus = None

        if current_focus is not None:
            focus_info = known.get(current_focus)
            if (focus_info is None
                    or focus_info.get("type") != self.target_waste
                    or not self._can_move_to(current_focus[0], current_focus[1], self.allowed_zones)):
                current_focus = None

        matched_targets = []
        for msg in knowledge.get("messages", []):
            if msg["type"] in ("waste_found", "need_pickup"):
                if msg["content"].get("waste_type") == self.target_waste:
                    pos = msg["content"].get("pos")
                    if not isinstance(pos, (list, tuple)) or len(pos) != 2:
                        continue
                    pos = (int(pos[0]), int(pos[1]))
                    existing_info = known.get(pos, {})
                    existing_count = 0
                    if existing_info.get("type") == self.target_waste:
                        existing_count = max(1, int(existing_info.get("count", 1)))
                    raw_msg_count = msg["content"].get("count", 1)
                    try:
                        msg_count = max(1, int(raw_msg_count))
                    except (TypeError, ValueError):
                        msg_count = 1
                    known[pos] = {
                        "type": self.target_waste,
                        "ttl": KNOWLEDGE_WASTE_TTL,
                        "count": max(existing_count, msg_count),
                    }
                    if self._can_move_to(pos[0], pos[1], self.allowed_zones):
                        matched_targets.append(pos)

        if not matched_targets:
            if current_focus is not None:
                knowledge["message_focus_target"] = current_focus
                return current_focus
            knowledge["message_focus_target"] = None
            return None

        best_new = min(matched_targets, key=lambda p: self._euclidean(pos_self, p))
        if current_focus is None:
            chosen = best_new
        else:
            d_current = self._euclidean(pos_self, current_focus)
            d_new = self._euclidean(pos_self, best_new)
            chosen = best_new if d_new < d_current else current_focus

        knowledge["message_focus_target"] = chosen
        return chosen

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
    def _neighbors(pos, allowed_zones, blocked_positions=None):
        x, y = pos
        out = []
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if blocked_positions and (nx, ny) in blocked_positions:
                continue
            if RobotAgent._can_move_to(nx, ny, allowed_zones):
                out.append((nx, ny))
        return out

    @staticmethod
    def _action_from_step(current, nxt):
        cx, cy = current
        nx, ny = nxt
        dx, dy = nx - cx, ny - cy
        if (dx, dy) == (1, 0):
            return ACTION_MOVE_RIGHT
        if (dx, dy) == (-1, 0):
            return ACTION_MOVE_LEFT
        if (dx, dy) == (0, 1):
            return ACTION_MOVE_DOWN
        if (dx, dy) == (0, -1):
            return ACTION_MOVE_UP
        return ACTION_IDLE

    def _a_star_path(self, start, goal, allowed_zones, blocked_positions=None):
        if start == goal:
            return [start]

        open_heap = []
        heapq.heappush(open_heap, (self._manhattan(start, goal), 0, start))
        came_from = {}
        g_score = {start: 0}
        closed = set()

        while open_heap:
            _, g, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            if current == goal:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path

            closed.add(current)

            for neighbor in self._neighbors(current, allowed_zones, blocked_positions=blocked_positions):
                tentative_g = g + 1
                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self._manhattan(neighbor, goal)
                    heapq.heappush(open_heap, (f, tentative_g, neighbor))

        return None

    def _navigate_to_target(self, knowledge, target):
        pos = knowledge["pos"]
        if not target or target == pos:
            knowledge["nav_next"] = None
            if target == pos:
                knowledge.get("known_waste", {}).pop(target, None)
                knowledge["path_goal"] = None
                knowledge["path_plan"] = []
            return ACTION_IDLE

        path_goal = knowledge.get("path_goal")
        path_plan = knowledge.get("path_plan", [])

        blocked_positions = None
        if knowledge.get("inventory"):
            blocked_positions = set(knowledge.get("known_decontamination", set()))
            mid_row = GRID_ROWS // 2
            if 1 in self.allowed_zones:
                blocked_positions.add(((0 + (ZONE_1_END - 1)) // 2, mid_row))
            if 2 in self.allowed_zones:
                blocked_positions.add(((ZONE_1_END + (ZONE_2_END - 1)) // 2, mid_row))
            if 3 in self.allowed_zones:
                blocked_positions.add(((ZONE_2_END + (GRID_COLS - 1)) // 2, mid_row))

        reuse_plan = (
            path_goal == target and
            len(path_plan) >= 2 and
            path_plan[0] == pos and
            not any(blocked_positions and step in blocked_positions for step in path_plan[1:])
        )

        if not reuse_plan:
            new_plan = self._a_star_path(
                pos,
                target,
                self.allowed_zones,
                blocked_positions=blocked_positions,
            )
            if not new_plan or len(new_plan) < 2:
                if blocked_positions:
                    valid_neighbors = [
                        cell for cell in self._neighbors(pos, self.allowed_zones, blocked_positions=blocked_positions)
                    ]
                    if valid_neighbors:
                        nxt = min(valid_neighbors, key=lambda cell: self._manhattan(cell, target))
                        return self._action_from_step(pos, nxt)
                return self._direction_toward(pos, target, self.allowed_zones)
            knowledge["path_goal"] = target
            knowledge["path_plan"] = new_plan

        plan = knowledge.get("path_plan", [])
        if len(plan) < 2:
            knowledge["nav_next"] = None
            return ACTION_IDLE

        nxt = plan[1]
        knowledge["nav_next"] = nxt
        action = self._action_from_step(pos, nxt)
        knowledge["path_plan"] = plan[1:]
        return action

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

    @staticmethod
    def _euclidean(a, b):
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        return (dx * dx + dy * dy) ** 0.5

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

    def _has_known_waste_type(self, knowledge, waste_type):
        known_waste = knowledge.get("known_waste", {})
        return any(
            info.get("type") == waste_type and self._can_move_to(p[0], p[1], self.allowed_zones)
            for p, info in known_waste.items()
        )

    def _adjacent_staging_cell(self, knowledge, target):
        """Pick an accessible cell adjacent to target for standby positioning."""
        if not target:
            return None
        candidates = [
            (target[0] + 1, target[1]),
            (target[0] - 1, target[1]),
            (target[0], target[1] + 1),
            (target[0], target[1] - 1),
        ]
        valid = [p for p in candidates if self._can_move_to(p[0], p[1], self.allowed_zones)]
        if not valid:
            return None
        pos = knowledge.get("pos", self.pos)
        return min(valid, key=lambda p: self._manhattan(pos, p))

    def _recent_position_penalty(self, knowledge, cell):
        recent_positions = knowledge.get("recent_positions", [])
        if not recent_positions:
            return 0.0
        penalty = 0.0
        total = len(recent_positions)
        for index, pos in enumerate(recent_positions):
            if pos == cell:
                recency = (index + 1) / total
                penalty += RECENT_POS_PENALTY * recency
        return penalty

    def _frontier_information_gain(self, knowledge, cell):
        visited = knowledge.get("visited_count", {})
        gain = 0.0
        cx, cy = cell
        local_cells = [(cx, cy), (cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]
        for nx, ny in local_cells:
            if not self._can_move_to(nx, ny, self.allowed_zones):
                continue
            visits = visited.get((nx, ny), 0)
            gain += 1.0 / (1.0 + visits)
        return FRONTIER_INFO_GAIN_WEIGHT * gain

    def _energy_risk_penalty(self, knowledge, target, reserve_target=None):
        if not ENERGY_ENABLED or target is None:
            return 0.0
        pos = knowledge.get("pos", self.pos)
        energy = knowledge.get("energy", AGENT_MAX_ENERGY)
        inv = knowledge.get("inventory", [])
        steps = self._estimate_steps(knowledge, pos, target, inventory_override=inv)
        if reserve_target is not None:
            steps += self._estimate_steps(knowledge, target, reserve_target, inventory_override=inv)

        required = self._estimate_required_energy(knowledge, steps, inventory_override=inv)
        margin = energy - required
        safe_margin = HEALTH_LOW_THRESHOLD + 8
        if margin >= safe_margin:
            return 0.0
        return TARGET_ENERGY_RISK_WEIGHT * (safe_margin - margin)

    def _select_intention(self, knowledge, candidates):
        """Choose intention with commitment/hysteresis.
        candidates: list[(intent, score, target)]
        """
        if not candidates:
            return INTENT_EXPLORE, None

        current_intent = knowledge.get("current_intention", INTENT_EXPLORE)
        current_target = knowledge.get("intention_target")
        lock = knowledge.get("intention_lock", 0)
        intent_cooldown = knowledge.get("intent_cooldown", 0)

        if knowledge.get("stuck_counter", 0) >= STUCK_REPLAN_TICKS:
            lock = 0

        scored = sorted(candidates, key=lambda item: item[1], reverse=True)
        best_intent, best_score, best_target = scored[0]
        current_entry = next((entry for entry in scored if entry[0] == current_intent), None)

        if knowledge.get("seek_idle_counter", 0) >= 2:
            lock = 0

        if intent_cooldown > 0:
            lock = max(lock, 1)

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
        if best_intent != current_intent:
            knowledge["intent_cooldown"] = INTENTION_SWITCH_COOLDOWN_TICKS
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

    @staticmethod
    def _carry_loss_for_inventory(inv_list):
        carry_loss = 0
        for waste_type in inv_list:
            if waste_type == "green":
                carry_loss += HEALTH_LOSS_CARRY_GREEN
            elif waste_type == "yellow":
                carry_loss += HEALTH_LOSS_CARRY_YELLOW
            elif waste_type == "red":
                carry_loss += HEALTH_LOSS_CARRY_RED
        return carry_loss

    def _decon_blocked_positions(self, knowledge, inventory_override=None):
        inv = knowledge.get("inventory", []) if inventory_override is None else inventory_override
        if not inv:
            return None

        blocked_positions = set(knowledge.get("known_decontamination", set()))
        mid_row = GRID_ROWS // 2
        if 1 in self.allowed_zones:
            blocked_positions.add(((0 + (ZONE_1_END - 1)) // 2, mid_row))
        if 2 in self.allowed_zones:
            blocked_positions.add(((ZONE_1_END + (ZONE_2_END - 1)) // 2, mid_row))
        if 3 in self.allowed_zones:
            blocked_positions.add(((ZONE_2_END + (GRID_COLS - 1)) // 2, mid_row))
        return blocked_positions

    def _estimate_steps(self, knowledge, start, goal, inventory_override=None):
        if start == goal:
            return 0

        blocked_positions = self._decon_blocked_positions(knowledge, inventory_override=inventory_override)
        path = self._a_star_path(start, goal, self.allowed_zones, blocked_positions=blocked_positions)
        if path and len(path) >= 2:
            return len(path) - 1
        return self._manhattan(start, goal)

    def _estimate_required_energy(self, knowledge, steps, inventory_override=None, action_cost=0):
        inv = knowledge.get("inventory", []) if inventory_override is None else inventory_override
        carry_loss = self._carry_loss_for_inventory(inv)
        move_cost = ENERGY_COST_MOVE + carry_loss
        return steps * move_cost + action_cost

    def _needs_survival_mode_dynamic(self, knowledge, reserve_steps=0, role_prefix="agent"):
        """Task-aware survival hysteresis using estimated required reserve steps."""
        if not ENERGY_ENABLED:
            knowledge["survival_mode"] = False
            return False

        energy = knowledge.get("energy", AGENT_MAX_ENERGY)
        survival_mode = knowledge.get("survival_mode", False)
        inv = knowledge.get("inventory", [])
        carry_loss = self._carry_loss_for_inventory(inv)

        enter_raw = HEALTH_LOW_THRESHOLD + 2 + reserve_steps * (ENERGY_COST_MOVE + carry_loss)
        enter_threshold = min(AGENT_MAX_ENERGY - 8, enter_raw)
        exit_threshold = min(AGENT_MAX_ENERGY, enter_threshold + 10)

        knowledge[f"{role_prefix}_survival_enter"] = round(enter_threshold, 2)
        knowledge[f"{role_prefix}_survival_exit"] = round(exit_threshold, 2)
        knowledge[f"{role_prefix}_reserve_steps"] = int(max(0, reserve_steps))

        if survival_mode:
            if energy >= exit_threshold:
                knowledge["survival_mode"] = False
            else:
                knowledge["survival_mode"] = True
        else:
            if energy <= enter_threshold:
                knowledge["survival_mode"] = True

        return knowledge.get("survival_mode", False)

    def _needs_survival_mode_dynamic_for_target(self, knowledge, primary_target, decon_target, role_prefix="agent"):
        pos = knowledge.get("pos", self.pos)
        inv = list(knowledge.get("inventory", []))
        steps_to_primary = self._estimate_steps(knowledge, pos, primary_target, inventory_override=inv)
        steps_primary_to_decon = self._estimate_steps(knowledge, primary_target, decon_target, inventory_override=inv)
        reserve_steps = steps_to_primary + steps_primary_to_decon
        return self._needs_survival_mode_dynamic(knowledge, reserve_steps=reserve_steps, role_prefix=role_prefix)

    def _explore_with_target(self, knowledge, min_col=0, max_col=None, min_row=0, max_row=None):
        """Explore with memory: prefer less-visited reachable cells, then A* to waypoint."""
        pos = knowledge["pos"]
        if max_col is None:
            max_col = GRID_COLS - 1
        if max_row is None:
            max_row = GRID_ROWS - 1

        def _valid_target(target):
            if not target:
                return False
            tx, ty = target
            if tx < min_col or tx > max_col:
                return False
            if ty < min_row or ty > max_row:
                return False
            return self._can_move_to(tx, ty, self.allowed_zones)

        target = knowledge.get("explore_target")
        reached = target is not None and self._manhattan(pos, target) <= 1
        if reached:
            target = None

        if not _valid_target(target):
            visited = knowledge.get("visited_count", {})
            candidates = []
            for tx in range(min_col, max_col + 1):
                for ty in range(min_row, max_row + 1):
                    if self._can_move_to(tx, ty, self.allowed_zones):
                        dist_score = self._manhattan(pos, (tx, ty))
                        if dist_score == 0:
                            continue
                        visit_score = visited.get((tx, ty), 0)
                        info_gain = self._frontier_information_gain(knowledge, (tx, ty))
                        recent_penalty = self._recent_position_penalty(knowledge, (tx, ty))
                        energy_penalty = self._energy_risk_penalty(knowledge, (tx, ty))
                        total_score = info_gain - (0.8 * dist_score) - (1.2 * visit_score) - recent_penalty - energy_penalty
                        candidates.append((total_score, dist_score, (tx, ty)))

            if candidates:
                candidates.sort(key=lambda item: item[0], reverse=True)
                best_score = candidates[0][0]
                top_band = [item for item in candidates if item[0] >= (best_score - 0.75)]
                if top_band:
                    target = random.choice(top_band)[2]

        if not target:
            return self._random_move(pos, self.allowed_zones)

        knowledge["explore_target"] = target
        knowledge["facing"] = "right" if target[0] > pos[0] else "left"
        return self._navigate_to_target(knowledge, target)

    def _decontamination_action(self, knowledge):
        """Return an action toward a decontamination zone when life is low."""
        pos = knowledge["pos"]
        known_decon = list(knowledge.get("known_decontamination", set()))

        # Global decontamination rule: if carrying waste, drop before stepping
        # onto a decontamination cell (or immediately if already on it).
        if knowledge.get("inventory"):
            if pos in known_decon:
                knowledge["force_drop_all"] = True
                knowledge["pickup_cooldown"] = max(knowledge.get("pickup_cooldown", 0), 16)
                if self.robot_type == "yellow" and "yellow" in knowledge.get("inventory", []):
                    knowledge["yellow_avoid_pos"] = pos
                    knowledge["yellow_avoid_ttl"] = max(int(knowledge.get("yellow_avoid_ttl", 0)), 30)
                return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
            if known_decon:
                closest = min(
                    known_decon,
                    key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]),
                )
                if self._manhattan(pos, closest) == 1:
                    knowledge["force_drop_all"] = True
                    knowledge["pickup_cooldown"] = max(knowledge.get("pickup_cooldown", 0), 16)
                    if self.robot_type == "yellow" and "yellow" in knowledge.get("inventory", []):
                        knowledge["yellow_avoid_pos"] = pos
                        knowledge["yellow_avoid_ttl"] = max(int(knowledge.get("yellow_avoid_ttl", 0)), 30)
                    return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE

        if pos in known_decon:
            return ACTION_IDLE

        if known_decon:
            closest = min(known_decon,
                          key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]))
            knowledge["facing"] = "right" if closest[0] > pos[0] else "left"
            return self._navigate_to_target(knowledge, closest)

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
        return self._navigate_to_target(knowledge, target)


class GreenAgent(RobotAgent):
    """Collects green waste in z1, transforms 2 green -> 1 yellow, transports east."""

    robot_type = "green"
    allowed_zones = [1]
    target_waste = "green"
    transform_cost = GREEN_TO_YELLOW_COST
    output_waste = "yellow"

    @staticmethod
    def _carry_loss_for_inventory(inv_list):
        carry_loss = 0
        for waste_type in inv_list:
            if waste_type == "green":
                carry_loss += HEALTH_LOSS_CARRY_GREEN
            elif waste_type == "yellow":
                carry_loss += HEALTH_LOSS_CARRY_YELLOW
            elif waste_type == "red":
                carry_loss += HEALTH_LOSS_CARRY_RED
        return carry_loss

    def _can_deliver_and_return_safe(self, knowledge, border_target):
        """Return (can_deliver, projected_margin).

        Estimate if green can:
        1) reach border and drop yellow,
        2) reach zone-1 decontamination cell before critical energy.
        """
        if not ENERGY_ENABLED:
            return True, AGENT_MAX_ENERGY

        pos = knowledge.get("pos", self.pos)
        energy = knowledge.get("energy", AGENT_MAX_ENERGY)
        inv = list(knowledge.get("inventory", []))

        if "yellow" not in inv:
            return True, energy

        decon_target = ((0 + (ZONE_1_END - 1)) // 2, GRID_ROWS // 2)
        dist_to_border = self._manhattan(pos, border_target)
        dist_border_to_decon = self._manhattan(border_target, decon_target)

        carry_loss_before_drop = self._carry_loss_for_inventory(inv)
        inv_after_drop = [w for w in inv if w != "yellow"]
        carry_loss_after_drop = self._carry_loss_for_inventory(inv_after_drop)

        cost_to_border = dist_to_border * (ENERGY_COST_MOVE + carry_loss_before_drop)
        cost_drop = ENERGY_COST_DROP + carry_loss_after_drop
        cost_to_decon = dist_border_to_decon * (ENERGY_COST_MOVE + carry_loss_after_drop)
        projected_energy = energy - (cost_to_border + cost_drop + cost_to_decon)

        # Dynamic safety buffer: longer trips require a slightly higher reserve.
        dynamic_buffer = 2 + max(0, (dist_to_border + dist_border_to_decon) // 6)
        margin = projected_energy - (HEALTH_LOW_THRESHOLD + dynamic_buffer)
        return margin >= 0, margin

    def _green_explore_row_bounds(self, knowledge):
        mid_row = GRID_ROWS // 2
        top_exhausted = int(knowledge.get("green_top_exhausted_ttl", 0)) > 0
        bottom_exhausted = int(knowledge.get("green_bottom_exhausted_ttl", 0)) > 0
        if top_exhausted and not bottom_exhausted:
            return mid_row + 1, GRID_ROWS - 1
        if bottom_exhausted and not top_exhausted:
            return 0, mid_row
        return 0, GRID_ROWS - 1

    def _green_explore_action(self, knowledge):
        min_row, max_row = self._green_explore_row_bounds(knowledge)
        return self._explore_with_target(
            knowledge,
            min_col=0,
            max_col=ZONE_1_END - 1,
            min_row=min_row,
            max_row=max_row,
        )

    def _update_green_empty_zone_memory(self, knowledge, percepts):
        mid_row = GRID_ROWS // 2
        top_ttl = max(0, int(knowledge.get("green_top_exhausted_ttl", 0)) - 1)
        bottom_ttl = max(0, int(knowledge.get("green_bottom_exhausted_ttl", 0)) - 1)
        top_no_ticks = int(knowledge.get("green_top_no_waste_ticks", 0))
        bottom_no_ticks = int(knowledge.get("green_bottom_no_waste_ticks", 0))

        seen_green_positions = []
        for seen_pos, contents in percepts.items():
            if "green" in contents.get("waste", []):
                if self._can_move_to(seen_pos[0], seen_pos[1], self.allowed_zones):
                    seen_green_positions.append(seen_pos)

        seen_top = any(point[1] <= mid_row for point in seen_green_positions)
        seen_bottom = any(point[1] > mid_row for point in seen_green_positions)

        known_green_points = [
            point for point, info in knowledge.get("known_waste", {}).items()
            if info.get("type") == "green" and self._can_move_to(point[0], point[1], self.allowed_zones)
        ]
        known_top = any(point[1] <= mid_row for point in known_green_points)
        known_bottom = any(point[1] > mid_row for point in known_green_points)

        if seen_top or known_top:
            top_no_ticks = 0
            top_ttl = 0
        if seen_bottom or known_bottom:
            bottom_no_ticks = 0
            bottom_ttl = 0

        pos = knowledge.get("pos", self.pos)
        current_is_top = pos[1] <= mid_row
        if not knowledge.get("inventory") and not seen_green_positions:
            if current_is_top and not known_top:
                top_no_ticks += 1
            if (not current_is_top) and not known_bottom:
                bottom_no_ticks += 1

        no_waste_threshold = 12
        exhausted_ttl = 48
        if top_no_ticks >= no_waste_threshold and not known_top:
            top_ttl = max(top_ttl, exhausted_ttl)
            top_no_ticks = 0
        if bottom_no_ticks >= no_waste_threshold and not known_bottom:
            bottom_ttl = max(bottom_ttl, exhausted_ttl)
            bottom_no_ticks = 0

        knowledge["green_top_exhausted_ttl"] = top_ttl
        knowledge["green_bottom_exhausted_ttl"] = bottom_ttl
        knowledge["green_top_no_waste_ticks"] = top_no_ticks
        knowledge["green_bottom_no_waste_ticks"] = bottom_no_ticks

    def _forage_action(self, knowledge):
        """Fast local forage in z1: prefer nearby, less-visited cells."""
        pos = knowledge["pos"]
        nearest_green = self._nearest_known_waste(knowledge, "green")
        if nearest_green:
            knowledge["green_forage_target"] = None
            return self._navigate_to_target(knowledge, nearest_green)

        visited = knowledge.get("visited_count", {})

        current_target = knowledge.get("green_forage_target")
        if current_target and current_target != pos:
            if self._can_move_to(current_target[0], current_target[1], self.allowed_zones):
                return self._navigate_to_target(knowledge, current_target)
            knowledge["green_forage_target"] = None

        min_row, max_row = self._green_explore_row_bounds(knowledge)
        candidates = []
        for tx in range(0, ZONE_1_END):
            for ty in range(min_row, max_row + 1):
                if not self._can_move_to(tx, ty, self.allowed_zones):
                    continue
                dist = self._manhattan(pos, (tx, ty))
                if dist == 0:
                    continue
                visit_count = visited.get((tx, ty), 0)
                info_gain = self._frontier_information_gain(knowledge, (tx, ty))
                recent_penalty = self._recent_position_penalty(knowledge, (tx, ty))
                energy_penalty = self._energy_risk_penalty(knowledge, (tx, ty))
                score = info_gain - (1.0 * dist) - (1.5 * visit_count) - recent_penalty - energy_penalty
                candidates.append((score, dist, (tx, ty)))

        if not candidates:
            return self._green_explore_action(knowledge)

        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score = candidates[0][0]
        best_band = [item[2] for item in candidates if item[0] >= (best_score - 0.6)]
        target = random.choice(best_band) if best_band else candidates[0][2]
        knowledge["green_forage_target"] = target
        return self._navigate_to_target(knowledge, target)

    def deliberate(self, knowledge):
        pos = knowledge["pos"]
        inv = knowledge["inventory"]
        percepts = knowledge["percepts"]
        energy = knowledge.get("energy", AGENT_MAX_ENERGY)
        green_count = inv.count("green")
        green_relay_mode = bool(knowledge.get("green_relay_mode", False))
        if green_count == 0 or green_count >= self.transform_cost or "yellow" in inv:
            green_relay_mode = False
        knowledge["green_relay_mode"] = green_relay_mode
        border_target = (ZONE_1_END - 1, pos[1])
        msg_target = self._check_messages_for_target(knowledge)
        nearest_green = self._nearest_known_waste(knowledge, "green")
        green_unsafe_avoid_pos = knowledge.get("green_unsafe_avoid_pos")
        green_unsafe_avoid_ttl = int(knowledge.get("green_unsafe_avoid_ttl", 0))
        if green_unsafe_avoid_ttl > 0:
            green_unsafe_avoid_ttl -= 1
        knowledge["green_unsafe_avoid_ttl"] = green_unsafe_avoid_ttl
        if green_unsafe_avoid_ttl <= 0:
            knowledge["green_unsafe_avoid_pos"] = None
            green_unsafe_avoid_pos = None

        green_no_repick_pos = knowledge.get("green_no_repick_pos")
        green_no_repick_ttl = int(knowledge.get("green_no_repick_ttl", 0))
        if green_no_repick_ttl > 0:
            green_no_repick_ttl -= 1
        knowledge["green_no_repick_ttl"] = green_no_repick_ttl
        if green_no_repick_ttl <= 0:
            knowledge["green_no_repick_pos"] = None
            green_no_repick_pos = None

        if green_unsafe_avoid_pos is not None:
            green_unsafe_avoid_pos = tuple(green_unsafe_avoid_pos)

        def _green_known_points_excluding_unsafe():
            points = []
            for point, info in knowledge.get("known_waste", {}).items():
                if info.get("type") != "green":
                    continue
                if not self._can_move_to(point[0], point[1], self.allowed_zones):
                    continue
                if green_unsafe_avoid_ttl > 0 and green_unsafe_avoid_pos is not None and point == green_unsafe_avoid_pos:
                    continue
                points.append(point)
            return points

        known_green_points = _green_known_points_excluding_unsafe()
        if nearest_green is None and known_green_points:
            nearest_green = min(known_green_points, key=lambda point: self._manhattan(pos, point))

        if (green_unsafe_avoid_ttl > 0
                and green_unsafe_avoid_pos is not None
                and nearest_green == green_unsafe_avoid_pos):
            alt_points = _green_known_points_excluding_unsafe()
            nearest_green = min(alt_points, key=lambda point: self._manhattan(pos, point)) if alt_points else None
        known_green_count = len(known_green_points)
        self._update_green_empty_zone_memory(knowledge, percepts)
        has_green_here = pos in percepts and "green" in percepts[pos].get("waste", [])
        near_survival = energy <= (HEALTH_LOW_THRESHOLD + GREEN_PICKUP_RISK_MARGIN)
        carrying_partial = 0 < green_count < self.transform_cost
        can_deliver_safe, deliver_margin = self._can_deliver_and_return_safe(knowledge, border_target)
        knowledge["green_delivery_margin"] = round(deliver_margin, 2)
        knowledge["green_can_deliver_safe"] = bool(can_deliver_safe)

        decon_target = ((0 + (ZONE_1_END - 1)) // 2, GRID_ROWS // 2)
        return_retarget = knowledge.get("green_return_retarget")
        if isinstance(return_retarget, (list, tuple)) and len(return_retarget) == 2:
            return_retarget = (int(return_retarget[0]), int(return_retarget[1]))
        else:
            return_retarget = None

        if return_retarget is not None:
            retarget_info = knowledge.get("known_waste", {}).get(return_retarget)
            if (retarget_info is None
                    or retarget_info.get("type") != "green"
                    or not self._can_move_to(return_retarget[0], return_retarget[1], self.allowed_zones)):
                return_retarget = None

        knowledge["green_return_retarget"] = return_retarget
        if "yellow" in inv:
            primary_target = border_target
        elif green_count >= self.transform_cost:
            primary_target = pos
        elif return_retarget is not None:
            primary_target = return_retarget
        elif msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
            primary_target = msg_target
        elif nearest_green:
            primary_target = nearest_green
        else:
            primary_target = (ZONE_1_END - 1, GRID_ROWS // 2)

        in_survival = self._needs_survival_mode_dynamic_for_target(
            knowledge,
            primary_target=primary_target,
            decon_target=decon_target,
            role_prefix="green",
        )

        # If forced to return for recharge while empty, memorize any nearby green
        # and keep the one closest to decontamination as next target after recovery.
        if in_survival and "yellow" not in inv and green_count == 0:
            nearby_green_candidates = []
            for seen_pos, contents in percepts.items():
                if "green" in contents.get("waste", []):
                    if self._can_move_to(seen_pos[0], seen_pos[1], self.allowed_zones):
                        nearby_green_candidates.append(seen_pos)
                        knowledge.setdefault("known_waste", {})[seen_pos] = {
                            "type": "green",
                            "ttl": KNOWLEDGE_WASTE_TTL,
                        }
            if nearby_green_candidates:
                best_return_retarget = min(
                    nearby_green_candidates,
                    key=lambda point: self._manhattan(point, decon_target),
                )
                knowledge["green_return_retarget"] = best_return_retarget

        # Once carrying again, clear return-retarget memory.
        if "yellow" in inv or green_count > 0:
            knowledge["green_return_retarget"] = None

        dist_to_border = self._manhattan(pos, border_target)
        dist_to_decon = self._manhattan(pos, decon_target)
        carry_loss_now = self._carry_loss_for_inventory(inv)
        dynamic_recharge_enter = HEALTH_LOW_THRESHOLD + 2 + dist_to_decon * (ENERGY_COST_MOVE + carry_loss_now)
        dynamic_recharge_exit = dynamic_recharge_enter + 20
        knowledge["green_recharge_enter"] = round(dynamic_recharge_enter, 2)
        knowledge["green_recharge_exit"] = round(dynamic_recharge_exit, 2)
        on_decon = bool(pos in percepts and percepts[pos].get("decontamination", False))
        green_recover_mode = bool(knowledge.get("green_recover_mode", False))
        recover_exit_threshold = max(dynamic_recharge_exit, HEALTH_LOW_THRESHOLD + 24)
        if "yellow" in inv or green_count > 0:
            green_recover_mode = False
        elif green_recover_mode:
            if energy >= recover_exit_threshold:
                green_recover_mode = False
        elif in_survival and energy <= dynamic_recharge_exit:
            green_recover_mode = True
        knowledge["green_recover_mode"] = green_recover_mode
        pickup_blocked_recent_drop = (
            green_no_repick_ttl > 0
            and green_no_repick_pos is not None
            and tuple(green_no_repick_pos) == pos
        )

        # During recent-drop cooldown, prefer staying on recharge zone instead of
        # local ping-pong around the dropped cell.
        if (not in_survival
                and "yellow" not in inv
                and green_count == 0
                and green_no_repick_ttl > 0
                and green_no_repick_pos is not None):
            if on_decon:
                self._set_decision_debug(knowledge, "hold_decon_recent_drop_guard", target=decon_target)
                return ACTION_IDLE
            self._set_decision_debug(knowledge, "move_decon_recent_drop_guard", target=decon_target)
            return self._decontamination_action(knowledge)

        inv_after_yellow_drop = [w for w in inv if w != "yellow"]
        carry_loss_after_drop = self._carry_loss_for_inventory(inv_after_yellow_drop)
        cost_to_border_and_drop = (
            dist_to_border * (ENERGY_COST_MOVE + carry_loss_now)
            + ENERGY_COST_DROP
            + carry_loss_after_drop
        )
        energy_after_border_drop = energy - cost_to_border_and_drop
        in_border_corridor = decon_target[0] <= pos[0] <= (ZONE_1_END - 1)
        near_border_deliver_ok = (
            "yellow" in inv
            and in_border_corridor
            and dist_to_border <= max(2, dist_to_decon)
            and energy_after_border_drop >= max(8, HEALTH_LOW_THRESHOLD - 8)
        )
        knowledge["green_near_border_deliver_ok"] = bool(near_border_deliver_ok)

        partial_mode = knowledge.get("green_partial_mode", "forage")
        partial_recharge_mode = False
        if carrying_partial:
            if partial_mode == "recharge":
                if energy >= dynamic_recharge_exit:
                    partial_mode = "forage"
            else:
                if energy <= dynamic_recharge_enter:
                    partial_mode = "recharge"

            partial_recharge_mode = partial_mode == "recharge"
            knowledge["green_partial_mode"] = partial_mode
            knowledge["green_partial_recharge_mode"] = partial_recharge_mode

            if partial_recharge_mode and on_decon and energy < dynamic_recharge_exit:
                self._set_decision_debug(knowledge, "recharge_hold_decon")
                return ACTION_IDLE
        else:
            knowledge["green_partial_mode"] = "forage"
            knowledge["green_partial_recharge_mode"] = False
        downstream_yellow_busy = any(
            msg.get("type") == "load_status"
            and msg.get("content", {}).get("role") == "yellow"
            and msg.get("content", {}).get("available", 0) >= 2
            for msg in knowledge.get("messages", [])
        )
        downstream_yellow_waiting = any(
            msg.get("type") == "load_status"
            and msg.get("content", {}).get("role") == "yellow"
            and msg.get("content", {}).get("available", 0) == 0
            for msg in knowledge.get("messages", [])
        )
        yellow_waiting_positions = []
        for msg in knowledge.get("messages", []):
            if msg.get("type") != "load_status":
                continue
            content = msg.get("content", {})
            if content.get("role") != "yellow":
                continue
            if content.get("available", 0) != 0:
                continue
            msg_pos = content.get("pos")
            if isinstance(msg_pos, (list, tuple)) and len(msg_pos) == 2:
                yellow_waiting_positions.append((int(msg_pos[0]), int(msg_pos[1])))
        downstream_yellow_waiting_near = any(
            self._manhattan(pos, yellow_pos) <= 3
            for yellow_pos in yellow_waiting_positions
        )
        knowledge["green_yellow_waiting_near"] = bool(downstream_yellow_waiting_near)
        observed_yellow_total = max(
            (
                int(msg.get("content", {}).get("available", 0))
                for msg in knowledge.get("messages", [])
                if msg.get("type") == "load_status"
                and msg.get("content", {}).get("role") == "yellow"
            ),
            default=0,
        )
        knowledge["green_observed_yellow_total"] = int(observed_yellow_total)

        if observed_yellow_total <= 1:
            knowledge["green_busy_hold_ticks"] = 0

        if (not in_survival
                and not inv
                and downstream_yellow_busy
                and observed_yellow_total >= 2
                and known_green_count == 0
                and on_decon
                and energy >= (AGENT_MAX_ENERGY - 2)):
            hold_ticks = int(knowledge.get("green_busy_hold_ticks", 0)) + 1
            knowledge["green_busy_hold_ticks"] = hold_ticks
            if hold_ticks > 6:
                knowledge["green_busy_hold_ticks"] = 0
                self._set_decision_debug(knowledge, "busy_hold_timeout_resume")
                return self._forage_action(knowledge)
            self._set_decision_debug(knowledge, "busy_hold_decon")
            return ACTION_IDLE
        knowledge["green_busy_hold_ticks"] = 0

        if (not in_survival
                and not inv
                and not has_green_here
                and msg_target is None
                and nearest_green is None
                and int(knowledge.get("step_count", 0)) < 16):
            opening_probe_target = (max(0, ZONE_1_END - 2), GRID_ROWS // 2)
            self._set_decision_debug(knowledge, "local_opening_probe", target=opening_probe_target)
            return self._navigate_to_target(knowledge, opening_probe_target)

        green_pickup_plan_safe = True
        green_pickup_margin_to_decon = -999.0
        green_pickup_margin_after_pick = -999.0
        green_pickup_relay_viable = False
        green_pickup_transform_viable = False
        if (not in_survival
                and has_green_here
                and self.can_carry_more()):
            inv_after_pick = list(inv) + ["green"]
            carry_loss_after_pick = self._carry_loss_for_inventory(inv_after_pick)
            steps_pick_to_decon = self._estimate_steps(
                knowledge,
                pos,
                decon_target,
                inventory_override=inv_after_pick,
            )
            required_pick_to_decon = (
                ENERGY_COST_PICKUP
                + self._estimate_required_energy(
                    knowledge,
                    steps_pick_to_decon,
                    inventory_override=inv_after_pick,
                )
            )
            green_pickup_margin_to_decon = energy - required_pick_to_decon
            projected_after_pick = energy - (ENERGY_COST_PICKUP + carry_loss_after_pick)
            recharge_floor_after_pick = (
                HEALTH_LOW_THRESHOLD
                + 4
                + dist_to_decon * (ENERGY_COST_MOVE + carry_loss_after_pick)
            )
            green_pickup_margin_after_pick = projected_after_pick - recharge_floor_after_pick
            green_pickup_plan_safe = (
                green_pickup_margin_to_decon >= 2
                and green_pickup_margin_after_pick >= 2
            )
            green_pickup_relay_viable = (
                green_pickup_margin_to_decon >= 4
                and green_pickup_margin_after_pick >= -2
            )
            if green_count == (self.transform_cost - 1):
                inv_after_transform = list(inv_after_pick)
                for _ in range(self.transform_cost):
                    if "green" in inv_after_transform:
                        inv_after_transform.remove("green")
                inv_after_transform.append("yellow")
                steps_transform_to_decon = self._estimate_steps(
                    knowledge,
                    pos,
                    decon_target,
                    inventory_override=inv_after_transform,
                )
                required_pick_transform_to_decon = (
                    ENERGY_COST_PICKUP
                    + ENERGY_COST_TRANSFORM
                    + self._estimate_required_energy(
                        knowledge,
                        steps_transform_to_decon,
                        inventory_override=inv_after_transform,
                    )
                )
                green_pickup_transform_viable = energy >= (required_pick_transform_to_decon + 2)
        knowledge["green_pickup_plan_safe"] = bool(green_pickup_plan_safe)
        knowledge["green_pickup_margin_to_decon"] = round(float(green_pickup_margin_to_decon), 2)
        knowledge["green_pickup_margin_after_pick"] = round(float(green_pickup_margin_after_pick), 2)
        knowledge["green_pickup_relay_viable"] = bool(green_pickup_relay_viable)
        knowledge["green_pickup_transform_viable"] = bool(green_pickup_transform_viable)

        if (green_recover_mode
                and not in_survival
                and "yellow" not in inv
                and green_count == 0):
            if on_decon and energy < recover_exit_threshold:
                self._set_decision_debug(knowledge, "recover_hold_decon")
                return ACTION_IDLE
            self._set_decision_debug(knowledge, "recover_move_decon", target=decon_target)
            return self._decontamination_action(knowledge)

        # Survival guard with transformed output: prefer progressing east first,
        # and only drop when critically unsafe.
        if in_survival and "yellow" in inv:
            if pos[0] >= ZONE_1_END - 1 and self.has_energy_for(ACTION_DROP):
                self._set_decision_debug(knowledge, "survival_relay_drop_on_border", target=border_target)
                return ACTION_DROP

            can_step_right = (
                self._can_move_to(pos[0] + 1, pos[1], self.allowed_zones)
                and self.has_energy_for(ACTION_MOVE_RIGHT)
            )
            carry_loss_now = self._carry_loss_for_inventory(inv)
            projected_after_step = energy - (ENERGY_COST_MOVE + carry_loss_now)
            steps_next_to_border = self._manhattan((min(ZONE_1_END - 1, pos[0] + 1), pos[1]), border_target)
            required_after_step = self._estimate_required_energy(
                knowledge,
                steps_next_to_border,
                inventory_override=inv,
            ) + ENERGY_COST_DROP
            can_progress_before_drop = (
                can_step_right
                and projected_after_step >= max(ENERGY_COST_DROP + 2, required_after_step)
            )

            if near_border_deliver_ok or can_progress_before_drop:
                self._set_decision_debug(knowledge, "survival_relay_yellow_right", target=border_target)
                return self._navigate_to_target(knowledge, border_target)

            if self.has_energy_for(ACTION_DROP):
                self._set_decision_debug(knowledge, "survival_drop_output")
                return ACTION_DROP

        if (not in_survival
                and "yellow" in inv
                and downstream_yellow_waiting
                and (known_green_count >= 2 or downstream_yellow_waiting_near)
                and self.has_energy_for(ACTION_DROP)):
            self._set_decision_debug(knowledge, "relay_drop_for_yellow")
            return ACTION_DROP

        if (in_survival
                and "yellow" not in inv
                and green_count > 0
                ):
            if (green_count >= self.transform_cost
                    and self.has_energy_for(ACTION_TRANSFORM)
                    and (downstream_yellow_waiting or downstream_yellow_waiting_near)):
                self._set_decision_debug(knowledge, "survival_transform_for_yellow_sync")
                return ACTION_TRANSFORM

            if on_decon:
                self._set_decision_debug(knowledge, "survival_hold_green_on_decon", target=decon_target)
                return ACTION_IDLE

            steps_to_decon_with_green = self._estimate_steps(
                knowledge,
                pos,
                decon_target,
                inventory_override=inv,
            )
            required_to_decon_with_green = self._estimate_required_energy(
                knowledge,
                steps_to_decon_with_green,
                inventory_override=inv,
            )
            can_recover_with_green = energy >= (required_to_decon_with_green + 1)

            if can_recover_with_green:
                self._set_decision_debug(knowledge, "survival_recover_green_to_decon", target=decon_target)
                recover_action = self._decontamination_action(knowledge)
                if recover_action == ACTION_DROP:
                    knowledge["green_no_repick_pos"] = pos
                    knowledge["green_no_repick_ttl"] = max(int(knowledge.get("green_no_repick_ttl", 0)), 18)
                    knowledge["green_unsafe_avoid_pos"] = pos
                    knowledge["green_unsafe_avoid_ttl"] = max(int(knowledge.get("green_unsafe_avoid_ttl", 0)), 18)
                return recover_action

            if self.has_energy_for(ACTION_DROP):
                knowledge["green_no_repick_pos"] = pos
                knowledge["green_no_repick_ttl"] = 14 if dist_to_decon >= 8 else 18
                knowledge["green_unsafe_avoid_pos"] = pos
                knowledge["green_unsafe_avoid_ttl"] = max(int(knowledge.get("green_unsafe_avoid_ttl", 0)), 18)
                self._set_decision_debug(knowledge, "survival_drop_green_buffer")
                return ACTION_DROP

        if (not in_survival
                and pickup_blocked_recent_drop
                and has_green_here
                and green_count == 0):
            self._set_decision_debug(knowledge, "skip_repick_recent_survival_drop", target=decon_target)
            return self._decontamination_action(knowledge)

        if (not in_survival
            and "yellow" not in inv
            and has_green_here
            and self.can_carry_more()
            and not pickup_blocked_recent_drop
            and not green_pickup_plan_safe):
            if (green_count == 0
                    and self.has_energy_for(ACTION_PICK_UP)
                    and green_pickup_relay_viable
                    and downstream_yellow_waiting_near):
                knowledge["green_relay_mode"] = True
                self._set_decision_debug(knowledge, "pickup_for_relay_unsafe_green", target=decon_target)
                return ACTION_PICK_UP
            if (green_count == (self.transform_cost - 1)
                    and self.has_energy_for(ACTION_PICK_UP)
                    and green_pickup_transform_viable):
                knowledge["green_relay_mode"] = False
                self._set_decision_debug(knowledge, "pickup_for_transform_viable", target=pos)
                return ACTION_PICK_UP
            unsafe_target = nearest_green if nearest_green is not None else pos
            knowledge["green_unsafe_avoid_pos"] = unsafe_target
            knowledge["green_unsafe_avoid_ttl"] = max(int(knowledge.get("green_unsafe_avoid_ttl", 0)), 24)
            self._set_decision_debug(knowledge, "defer_pickup_unsafe_green_plan", target=decon_target)
            return self._decontamination_action(knowledge)

        if (not in_survival
            and "yellow" not in inv
            and has_green_here
            and self.can_carry_more()
            and not pickup_blocked_recent_drop
            and green_pickup_plan_safe
            and self.has_energy_for(ACTION_PICK_UP)):
            knowledge["green_relay_mode"] = False
            self._set_decision_debug(knowledge, "pickup_on_cell", target=pos)
            return ACTION_PICK_UP

        if (not in_survival
                and "yellow" not in inv
                and green_count == 1
                and knowledge.get("green_relay_mode", False)):
            self._set_decision_debug(knowledge, "carry_one_green_relay", target=decon_target)
            return self._decontamination_action(knowledge)

        if (not in_survival
                and green_count >= self.transform_cost
                and self.has_energy_for(ACTION_TRANSFORM)):
            self._set_decision_debug(knowledge, "transform_batch_priority")
            return ACTION_TRANSFORM

        candidates = []
        if in_survival:
            candidates.append((INTENT_SURVIVE, 200.0, None))
        else:
            if downstream_yellow_busy and not inv and energy <= (AGENT_MAX_ENERGY - 5):
                candidates.append((INTENT_RECHARGE, 130.0, None))
            if partial_recharge_mode:
                candidates.append((INTENT_RECHARGE, 160.0, None))
            if "yellow" in inv:
                if can_deliver_safe or near_border_deliver_ok:
                    candidates.append((INTENT_DELIVER, 126.0 - self._manhattan(pos, border_target), border_target))
                else:
                    candidates.append((INTENT_RECHARGE, 185.0, None))
                    if self._manhattan(pos, border_target) <= 1:
                        candidates.append((INTENT_DELIVER, 119.0, border_target))
            if green_count >= self.transform_cost:
                candidates.append((INTENT_TRANSFORM, 105.0, None))
            if has_green_here and self.can_carry_more() and not pickup_blocked_recent_drop:
                pickup_score = 95.0 - (GREEN_PICKUP_RISK_PENALTY if near_survival else 0.0)
                candidates.append((INTENT_PICKUP, pickup_score, pos))
            if msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
                base = 118.0 if carrying_partial else 85.0
                risk_penalty = self._energy_risk_penalty(knowledge, msg_target, reserve_target=decon_target)
                candidates.append((INTENT_SEEK_WASTE, base - self._manhattan(pos, msg_target) - risk_penalty, msg_target))
            if nearest_green:
                base = 110.0 if carrying_partial else 70.0
                risk_penalty = self._energy_risk_penalty(knowledge, nearest_green, reserve_target=decon_target)
                candidates.append((INTENT_SEEK_WASTE, base - self._manhattan(pos, nearest_green) - risk_penalty, nearest_green))
            explore_score = 34.0 if carrying_partial else 20.0
            candidates.append((INTENT_EXPLORE, explore_score, None))

        intent, target = self._select_intention(knowledge, candidates)
        self._set_decision_debug(knowledge, f"intent={intent}", target=target)

        if intent == INTENT_SURVIVE:
            return self._decontamination_action(knowledge)
        if intent == INTENT_RECHARGE:
            return self._decontamination_action(knowledge)
        if intent == INTENT_DELIVER:
            if pos[0] >= ZONE_1_END - 1:
                return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
            knowledge["facing"] = "right"
            return self._navigate_to_target(knowledge, target or border_target)
        if intent == INTENT_TRANSFORM:
            return ACTION_TRANSFORM if self.has_energy_for(ACTION_TRANSFORM) else ACTION_IDLE
        if intent == INTENT_PICKUP:
            return ACTION_PICK_UP if self.has_energy_for(ACTION_PICK_UP) else ACTION_IDLE
        if intent == INTENT_SEEK_WASTE and target:
            if target == pos:
                knowledge.get("known_waste", {}).pop(target, None)
                knowledge["intention_lock"] = 0
                return self._forage_action(knowledge) if carrying_partial else self._green_explore_action(knowledge)
            knowledge["facing"] = "right" if target[0] > pos[0] else "left"
            return self._navigate_to_target(knowledge, target)
        if carrying_partial:
            return self._forage_action(knowledge)
        knowledge["green_forage_target"] = None
        return self._green_explore_action(knowledge)


class YellowAgent(RobotAgent):
    """Collects yellow waste in z1-z2, transforms 2 yellow -> 1 red, transports east."""

    robot_type = "yellow"
    allowed_zones = [1, 2]
    target_waste = "yellow"
    transform_cost = YELLOW_TO_RED_COST
    output_waste = "red"

    def _forage_second_yellow(self, knowledge):
        """When carrying one yellow, sweep near z1/z2 handoff to find the second quickly."""
        pos = knowledge["pos"]
        min_col = max(0, ZONE_1_END - 2)
        max_col = min(GRID_COLS - 1, ZONE_1_END + 1)
        return self._explore_with_target(knowledge, min_col=min_col, max_col=max_col)

    def _explore_action(self, knowledge):
        """Yellow explores z1-z2 with a patrol bias near the handoff border."""
        pos = knowledge["pos"]
        corridor_anchor = (ZONE_1_END, GRID_ROWS // 2)
        if pos[0] < ZONE_1_END - 2:
            return self._navigate_to_target(knowledge, corridor_anchor)
        return self._explore_with_target(knowledge, min_col=max(0, ZONE_1_END - 2), max_col=ZONE_2_END - 1)

    def deliberate(self, knowledge):
        pos = knowledge["pos"]
        inv = knowledge["inventory"]
        percepts = knowledge["percepts"]
        energy = knowledge.get("energy", AGENT_MAX_ENERGY)
        idle_recharge_threshold = 90
        carry_recover_enter = 58
        carry_recover_exit = 72
        yellow_count = inv.count("yellow")
        yellow_idle_mode = knowledge.get("yellow_idle_mode", "stage")
        yellow_lone_ready = bool(knowledge.get("yellow_lone_ready", False))
        yellow_carry_mode = knowledge.get("yellow_carry_mode", "push")
        wait_pair_idle_ticks = int(knowledge.get("yellow_wait_pair_idle_ticks", 0))
        wait_pair_cooldown = int(knowledge.get("yellow_wait_pair_cooldown", 0))
        wait_pair_fallback_mode = bool(knowledge.get("yellow_wait_pair_fallback_mode", False))
        wait_pair_fallback_ticks = int(knowledge.get("yellow_wait_pair_fallback_ticks", 0))
        wait_pair_fallback_strategy = knowledge.get("yellow_wait_pair_fallback_strategy")
        if wait_pair_fallback_strategy not in ("standby", "scout"):
            wait_pair_fallback_strategy = None
        if wait_pair_cooldown > 0:
            wait_pair_cooldown -= 1
        knowledge["yellow_wait_pair_cooldown"] = wait_pair_cooldown
        if wait_pair_fallback_mode:
            if wait_pair_fallback_ticks > 0:
                wait_pair_fallback_ticks -= 1
            else:
                wait_pair_fallback_mode = False
                wait_pair_fallback_strategy = None
        knowledge["yellow_wait_pair_fallback_mode"] = wait_pair_fallback_mode
        knowledge["yellow_wait_pair_fallback_ticks"] = wait_pair_fallback_ticks
        knowledge["yellow_wait_pair_fallback_strategy"] = wait_pair_fallback_strategy
        carrying_partial = 0 < yellow_count < self.transform_cost
        border_target = (ZONE_2_END - 1, pos[1])
        msg_target = self._check_messages_for_target(knowledge)
        avoid_pos = knowledge.get("yellow_avoid_pos")
        avoid_ttl = int(knowledge.get("yellow_avoid_ttl", 0))
        no_repick_pos = knowledge.get("yellow_no_repick_pos")
        no_repick_ttl = int(knowledge.get("yellow_no_repick_ttl", 0))
        if no_repick_ttl > 0:
            no_repick_ttl -= 1
        knowledge["yellow_no_repick_ttl"] = no_repick_ttl
        if no_repick_ttl <= 0:
            knowledge["yellow_no_repick_pos"] = None
            no_repick_pos = None
        elif no_repick_pos is not None:
            no_repick_pos = tuple(no_repick_pos)
        avoid_active = avoid_ttl > 0 and avoid_pos is not None
        first_pick_pos = knowledge.get("yellow_first_pick_pos")
        commit_cooldown = int(knowledge.get("yellow_commit_cooldown", 0))
        if commit_cooldown > 0:
            commit_cooldown -= 1
        knowledge["yellow_commit_cooldown"] = commit_cooldown

        if yellow_count == 0:
            knowledge["yellow_first_pick_pos"] = None
            first_pick_pos = None

        relay_drop_ttl = int(knowledge.get("yellow_recent_relay_drop_ttl", 0))
        if relay_drop_ttl > 0:
            relay_drop_ttl -= 1
        knowledge["yellow_recent_relay_drop_ttl"] = relay_drop_ttl

        def _is_avoided(cell):
            return (
                avoid_active
                and cell is not None
                and self._manhattan(cell, avoid_pos) <= 1
            )

        def _is_no_repick(cell):
            return (
                no_repick_ttl > 0
                and no_repick_pos is not None
                and cell is not None
                and cell == no_repick_pos
            )

        if _is_avoided(msg_target):
            msg_target = None

        known_yellow_positions = [
            p for p, info in knowledge.get("known_waste", {}).items()
            if info.get("type") == "yellow"
            and self._can_move_to(p[0], p[1], self.allowed_zones)
            and not _is_avoided(p)
            and not _is_no_repick(p)
            and not (carrying_partial and first_pick_pos is not None and p == first_pick_pos)
        ]
        nearest_yellow = min(known_yellow_positions, key=lambda p: self._manhattan(pos, p)) if known_yellow_positions else None
        has_known_yellow = bool(known_yellow_positions)
        known_yellow_count = sum(
            max(1, int(knowledge.get("known_waste", {}).get(p, {}).get("count", 1)))
            for p in known_yellow_positions
        )
        # Teacher constraint: yellow relies on local perception + communicated
        # positions only (no global waste count oracle).
        global_yellow_total = known_yellow_count
        knowledge["yellow_observed_total"] = int(global_yellow_total)
        prev_wait_msg_target = knowledge.get("yellow_wait_pair_last_msg_target")
        prev_wait_target = knowledge.get("yellow_wait_pair_last_target")
        prev_wait_global_total = knowledge.get("yellow_wait_pair_last_global_total")
        msg_target_changed = bool(msg_target is not None and prev_wait_msg_target != msg_target)
        near_target_changed = (
            nearest_yellow is not None
            and prev_wait_target is not None
            and tuple(prev_wait_target) != nearest_yellow
            and self._manhattan(pos, nearest_yellow) <= 3
        )
        global_total_changed = (
            prev_wait_global_total is not None
            and int(prev_wait_global_total) != global_yellow_total
        )
        if msg_target_changed or near_target_changed or global_total_changed:
            wait_pair_idle_ticks = 0
            if msg_target_changed or near_target_changed or global_yellow_total >= 2:
                wait_pair_fallback_mode = False
                wait_pair_fallback_ticks = 0
                wait_pair_fallback_strategy = None
        knowledge["yellow_wait_pair_last_msg_target"] = msg_target
        knowledge["yellow_wait_pair_last_target"] = nearest_yellow
        knowledge["yellow_wait_pair_last_global_total"] = global_yellow_total
        knowledge["yellow_wait_pair_fallback_mode"] = wait_pair_fallback_mode
        knowledge["yellow_wait_pair_fallback_ticks"] = wait_pair_fallback_ticks
        knowledge["yellow_wait_pair_fallback_strategy"] = wait_pair_fallback_strategy
        has_yellow_here = (
            (pos in percepts and "yellow" in percepts[pos].get("waste", []))
            and not _is_avoided(pos)
            and not _is_no_repick(pos)
        )
        downstream_red_waiting = any(
            msg.get("type") == "load_status"
            and msg.get("content", {}).get("role") == "red"
            and msg.get("content", {}).get("available", 0) <= 1
            for msg in knowledge.get("messages", [])
        )
        downstream_red_idle = any(
            msg.get("type") == "load_status"
            and msg.get("content", {}).get("role") == "red"
            and (
                msg.get("content", {}).get("is_active") is False
                or msg.get("content", {}).get("last_action") == ACTION_IDLE
                or (
                    msg.get("content", {}).get("available", 0) == 0
                    and msg.get("content", {}).get("last_action") in (None, ACTION_IDLE)
                )
            )
            for msg in knowledge.get("messages", [])
        )

        mid_row = GRID_ROWS // 2
        default_decon_candidates = [
            ((0 + (ZONE_1_END - 1)) // 2, mid_row),
            ((ZONE_1_END + (ZONE_2_END - 1)) // 2, mid_row),
        ]
        known_decon = [
            p for p in knowledge.get("known_decontamination", set())
            if self._can_move_to(p[0], p[1], self.allowed_zones)
        ]
        decon_candidates = known_decon if known_decon else default_decon_candidates
        decon_target = min(
            decon_candidates,
            key=lambda p: self._manhattan(pos, p),
        )
        yellow_return_retarget = knowledge.get("yellow_return_retarget")
        if isinstance(yellow_return_retarget, (list, tuple)) and len(yellow_return_retarget) == 2:
            yellow_return_retarget = (int(yellow_return_retarget[0]), int(yellow_return_retarget[1]))
        else:
            yellow_return_retarget = None

        if yellow_return_retarget is not None:
            retarget_info = knowledge.get("known_waste", {}).get(yellow_return_retarget)
            if (retarget_info is None
                    or retarget_info.get("type") != "yellow"
                    or not self._can_move_to(yellow_return_retarget[0], yellow_return_retarget[1], self.allowed_zones)
                    or _is_avoided(yellow_return_retarget)
                    or _is_no_repick(yellow_return_retarget)):
                yellow_return_retarget = None

        if yellow_return_retarget is not None and known_yellow_positions:
            nearest_known_by_euclidean = min(
                known_yellow_positions,
                key=lambda point: self._euclidean(pos, point),
            )
            if (self._euclidean(pos, nearest_known_by_euclidean)
                    < self._euclidean(pos, yellow_return_retarget)):
                yellow_return_retarget = nearest_known_by_euclidean

        knowledge["yellow_return_retarget"] = yellow_return_retarget
        if "red" in inv:
            primary_target = border_target
        elif yellow_count >= self.transform_cost:
            primary_target = pos
        elif yellow_return_retarget is not None:
            primary_target = yellow_return_retarget
        elif msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
            primary_target = msg_target
        elif nearest_yellow:
            primary_target = nearest_yellow
        else:
            primary_target = (ZONE_1_END, GRID_ROWS // 2)

        in_survival = self._needs_survival_mode_dynamic_for_target(
            knowledge,
            primary_target=primary_target,
            decon_target=decon_target,
            role_prefix="yellow",
        )

        if in_survival and "red" not in inv and yellow_count == 0 and known_yellow_positions:
            yellow_return_retarget = min(
                known_yellow_positions,
                key=lambda point: self._euclidean(point, decon_target),
            )
            knowledge["yellow_return_retarget"] = yellow_return_retarget

        if "red" in inv or yellow_count > 0:
            knowledge["yellow_return_retarget"] = None

        if carrying_partial and "red" not in inv:
            if yellow_carry_mode == "recover":
                if (not in_survival) and energy >= carry_recover_exit:
                    yellow_carry_mode = "push"
            else:
                if energy <= carry_recover_enter:
                    yellow_carry_mode = "recover"
        else:
            yellow_carry_mode = "push"
        knowledge["yellow_carry_mode"] = yellow_carry_mode
        knowledge["yellow_carry_recover_enter"] = carry_recover_enter
        knowledge["yellow_carry_recover_exit"] = carry_recover_exit

        idle_no_transform_state = (
            not in_survival
            and "red" not in inv
            and yellow_count == 0
        )
        lone_yellow_wait_mode = (
            idle_no_transform_state
            and nearest_yellow is not None
            and global_yellow_total < 2
        )

        lone_wait_ready_threshold = AGENT_MAX_ENERGY
        if lone_yellow_wait_mode:
            lone_wait_ready_threshold = max(idle_recharge_threshold, 90)

        if lone_yellow_wait_mode:
            if energy >= lone_wait_ready_threshold:
                yellow_lone_ready = True
        else:
            yellow_lone_ready = False
        knowledge["yellow_lone_ready"] = yellow_lone_ready
        knowledge["yellow_lone_ready_threshold"] = lone_wait_ready_threshold

        if idle_no_transform_state:
            if lone_yellow_wait_mode:
                yellow_idle_mode = "stage" if yellow_lone_ready else "recharge"
            else:
                if yellow_idle_mode == "recharge":
                    if energy >= idle_recharge_threshold:
                        yellow_idle_mode = "stage"
                else:
                    if energy < idle_recharge_threshold:
                        yellow_idle_mode = "recharge"
        else:
            yellow_idle_mode = "stage"
        knowledge["yellow_idle_mode"] = yellow_idle_mode
        knowledge["yellow_idle_recharge_target"] = lone_wait_ready_threshold if lone_yellow_wait_mode else idle_recharge_threshold

        if (in_survival
                or "red" in inv
                or yellow_count > 0
                or nearest_yellow is None
                or global_yellow_total >= 2):
            wait_pair_fallback_mode = False
            wait_pair_fallback_ticks = 0
            wait_pair_fallback_strategy = None
            knowledge["yellow_wait_pair_fallback_mode"] = False
            knowledge["yellow_wait_pair_fallback_ticks"] = 0
            knowledge["yellow_wait_pair_fallback_strategy"] = None

        # Mission lock: if two yellow are already collected, prioritize transforming
        # before survival retreat (except under critical immediate energy pressure).
        has_two_yellow = yellow_count >= self.transform_cost
        critical_energy_floor = max(ENERGY_COST_MOVE + ENERGY_COST_DROP + 1, 4)
        transform_ready_col = ZONE_2_END - 3
        transform_zone_ready = pos[0] >= transform_ready_col
        knowledge["yellow_transform_zone_ready"] = bool(transform_zone_ready)

        carry_loss_now = self._carry_loss_for_inventory(inv)
        can_move_right_in_zone = (
            pos[0] < GRID_COLS - 1
            and self._can_move_to(pos[0] + 1, pos[1], self.allowed_zones)
        )
        if can_move_right_in_zone:
            next_pos = (pos[0] + 1, pos[1])
            steps_next_to_decon = self._estimate_steps(
                knowledge,
                next_pos,
                decon_target,
                inventory_override=inv,
            )
            required_after_next = self._estimate_required_energy(
                knowledge,
                steps_next_to_decon,
                inventory_override=inv,
            ) + ENERGY_COST_DROP
            projected_after_next = energy - (ENERGY_COST_MOVE + carry_loss_now)
            can_relay_step_safely = projected_after_next >= max(critical_energy_floor, required_after_next)
        else:
            can_relay_step_safely = False
        knowledge["yellow_can_relay_step_safely"] = bool(can_relay_step_safely)

        if has_two_yellow and "red" not in inv:
            inv_after_transform = list(inv)
            for _ in range(self.transform_cost):
                if "yellow" in inv_after_transform:
                    inv_after_transform.remove("yellow")
            inv_after_transform.append("red")

            transform_plan_drop_target = (ZONE_2_END - 1, pos[1])
            transform_plan_reserve = 1.0
            best_transform_target = None
            best_transform_margin = -999.0

            for tx in range(pos[0], ZONE_2_END):
                candidate = (tx, pos[1])
                if not self._can_move_to(candidate[0], candidate[1], self.allowed_zones):
                    continue

                steps_to_candidate = self._estimate_steps(
                    knowledge,
                    pos,
                    candidate,
                    inventory_override=inv,
                )
                steps_candidate_to_drop = self._estimate_steps(
                    knowledge,
                    candidate,
                    transform_plan_drop_target,
                    inventory_override=inv_after_transform,
                )
                steps_drop_to_decon = self._estimate_steps(
                    knowledge,
                    transform_plan_drop_target,
                    decon_target,
                    inventory_override=[],
                )

                required_energy_plan = (
                    self._estimate_required_energy(
                        knowledge,
                        steps_to_candidate,
                        inventory_override=inv,
                    )
                    + ENERGY_COST_TRANSFORM
                    + self._estimate_required_energy(
                        knowledge,
                        steps_candidate_to_drop,
                        inventory_override=inv_after_transform,
                    )
                    + ENERGY_COST_DROP
                    + self._estimate_required_energy(
                        knowledge,
                        steps_drop_to_decon,
                        inventory_override=[],
                    )
                )

                energy_margin_plan = energy - required_energy_plan
                if energy_margin_plan < transform_plan_reserve:
                    continue

                if (best_transform_target is None
                        or tx > best_transform_target[0]
                        or (tx == best_transform_target[0] and energy_margin_plan < best_transform_margin)):
                    best_transform_target = candidate
                    best_transform_margin = energy_margin_plan

            knowledge["yellow_transform_plan_target"] = best_transform_target
            knowledge["yellow_transform_plan_margin"] = round(float(best_transform_margin), 2)

            if best_transform_target is not None:
                if pos != best_transform_target:
                    self._set_decision_debug(knowledge, "exact_transform_east_plan_move", target=best_transform_target)
                    return self._navigate_to_target(knowledge, best_transform_target)
                if self.has_energy_for(ACTION_TRANSFORM):
                    self._set_decision_debug(knowledge, "exact_transform_east_plan_transform", target=best_transform_target)
                    return ACTION_TRANSFORM

            # If far from the z2 frontier, relay yellow east first (carry forward,
            # drop if we must recharge, then come back and continue).
            if not transform_zone_ready:
                steps_transform_to_decon = self._estimate_steps(
                    knowledge,
                    pos,
                    decon_target,
                    inventory_override=inv_after_transform,
                )
                required_transform_recover = (
                    ENERGY_COST_TRANSFORM
                    + self._estimate_required_energy(
                        knowledge,
                        steps_transform_to_decon,
                        inventory_override=inv_after_transform,
                    )
                )
                low_transform_margin = energy <= (required_transform_recover + 6)

                if self.has_energy_for(ACTION_TRANSFORM) and (in_survival or low_transform_margin):
                    self._set_decision_debug(knowledge, "survival_transform_before_relay")
                    return ACTION_TRANSFORM

                relay_target = (transform_ready_col, pos[1])
                if (self.has_energy_for(ACTION_MOVE_RIGHT)
                        and can_relay_step_safely):
                    self._set_decision_debug(knowledge, "relay_yellow_east_before_transform", target=relay_target)
                    return self._navigate_to_target(knowledge, relay_target)

                # Prefer preserving progress: transform 2 yellow -> 1 red before
                # considering a relay-drop fallback.
                if self.has_energy_for(ACTION_TRANSFORM):
                    self._set_decision_debug(knowledge, "transform_before_relay_drop")
                    return ACTION_TRANSFORM

                # Guard: do not relay-drop too far west; keep advancing first.
                if self.has_energy_for(ACTION_DROP) and pos[0] >= (ZONE_1_END - 1):
                    knowledge["yellow_relay_drop"] = True
                    knowledge["yellow_recent_relay_drop_ttl"] = 20
                    knowledge["yellow_recharge_lock"] = 0
                    knowledge["pickup_cooldown"] = max(int(knowledge.get("pickup_cooldown", 0)), 10)
                    knowledge["yellow_avoid_pos"] = pos
                    knowledge["yellow_avoid_ttl"] = max(int(knowledge.get("yellow_avoid_ttl", 0)), 24)
                    knowledge["yellow_no_repick_pos"] = pos
                    knowledge["yellow_no_repick_ttl"] = max(int(knowledge.get("yellow_no_repick_ttl", 0)), 24)
                    knowledge["yellow_commit_cooldown"] = max(int(knowledge.get("yellow_commit_cooldown", 0)), 12)
                    self._set_decision_debug(knowledge, "relay_drop_yellow_before_recharge")
                    return ACTION_DROP

            if (self.has_energy_for(ACTION_TRANSFORM)
                    and (not in_survival or energy > critical_energy_floor)):
                self._set_decision_debug(knowledge, "transform_two_yellow_priority")
                return ACTION_TRANSFORM

        # Dynamic push window (carry 1 yellow): if energy allows full mini-mission,
        # keep pushing instead of prematurely switching to survival/recharge.
        yellow_push_window = False
        yellow_transform_window = False
        yellow_push_margin = -999.0
        if carrying_partial and nearest_yellow is not None:
            steps_to_second = self._estimate_steps(
                knowledge,
                pos,
                nearest_yellow,
                inventory_override=inv,
            )
            relay_x = min(ZONE_2_END - 1, nearest_yellow[0] + 3)
            relay_target = (relay_x, nearest_yellow[1])
            steps_to_relay = self._estimate_steps(
                knowledge,
                nearest_yellow,
                relay_target,
                inventory_override=["red"],
            )
            steps_relay_to_decon = self._estimate_steps(
                knowledge,
                relay_target,
                decon_target,
                inventory_override=[],
            )

            required_energy = 0.0
            required_energy += self._estimate_required_energy(
                knowledge,
                steps_to_second,
                inventory_override=inv,
            )
            required_energy += ENERGY_COST_PICKUP
            required_energy += ENERGY_COST_TRANSFORM
            required_energy += self._estimate_required_energy(
                knowledge,
                steps_to_relay,
                inventory_override=["red"],
            )
            required_energy += ENERGY_COST_DROP
            required_energy += self._estimate_required_energy(
                knowledge,
                steps_relay_to_decon,
                inventory_override=[],
            )

            required_transform_energy = (
                self._estimate_required_energy(
                    knowledge,
                    steps_to_second,
                    inventory_override=inv,
                )
                + ENERGY_COST_PICKUP
                + ENERGY_COST_TRANSFORM
            )
            yellow_transform_window = energy >= (required_transform_energy + 2)

            yellow_push_margin = energy - required_energy
            yellow_push_window = yellow_push_margin >= 4

        knowledge["yellow_push_window"] = bool(yellow_push_window)
        knowledge["yellow_transform_window"] = bool(yellow_transform_window)
        knowledge["yellow_push_margin"] = round(float(yellow_push_margin), 2)
        if in_survival and (yellow_push_window or yellow_transform_window):
            in_survival = False
            knowledge["yellow_survival_override"] = True
        else:
            knowledge["yellow_survival_override"] = False

        recent_relay_drop_active = int(knowledge.get("yellow_recent_relay_drop_ttl", 0)) > 0
        nearby_yellow_window = (
            nearest_yellow is not None
            and self._manhattan(pos, nearest_yellow) <= 2
        )
        nearby_relay_repickup = (
            recent_relay_drop_active
            and nearest_yellow is not None
            and self._manhattan(pos, nearest_yellow) <= 3
        )
        if nearby_relay_repickup:
            knowledge["yellow_recharge_lock"] = 0

        predicted_inv = list(inv) + ["yellow"]
        carry_loss_after_pick = self._carry_loss_for_inventory(predicted_inv)
        projected_after_pick = energy - ENERGY_COST_PICKUP - carry_loss_after_pick
        decon_steps = self._manhattan(pos, decon_target)
        enter_after_pick = HEALTH_LOW_THRESHOLD + 2 + decon_steps * (ENERGY_COST_MOVE + carry_loss_after_pick)
        safe_pickup_here = projected_after_pick > (enter_after_pick + 2)
        can_pickup_now = knowledge.get("pickup_cooldown", 0) == 0 and (safe_pickup_here or yellow_push_window)
        can_pickup_for_transform_now = (
            carrying_partial
            and has_yellow_here
            and self.can_carry_more()
            and self.has_energy_for(ACTION_PICK_UP)
            and self.has_energy_for(ACTION_TRANSFORM)
            and energy >= (ENERGY_COST_PICKUP + ENERGY_COST_TRANSFORM + max(6, critical_energy_floor))
        )
        knowledge["yellow_pickup_safe"] = bool(safe_pickup_here)
        knowledge["yellow_pickup_cooldown"] = int(knowledge.get("pickup_cooldown", 0))
        knowledge["yellow_pickup_for_transform_now"] = bool(can_pickup_for_transform_now)

        nearest_pick_plan_required = None
        nearest_pick_plan_safe = False
        if (not in_survival
                and "red" not in inv
                and yellow_count == 0
                and nearest_yellow is not None):
            steps_to_nearest = self._estimate_steps(
                knowledge,
                pos,
                nearest_yellow,
                inventory_override=inv,
            )
            steps_nearest_to_decon = self._estimate_steps(
                knowledge,
                nearest_yellow,
                decon_target,
                inventory_override=["yellow"],
            )
            nearest_pick_plan_required = (
                self._estimate_required_energy(knowledge, steps_to_nearest, inventory_override=inv)
                + ENERGY_COST_PICKUP
                + self._estimate_required_energy(
                    knowledge,
                    steps_nearest_to_decon,
                    inventory_override=["yellow"],
                )
            )
            nearest_pick_plan_safe = energy >= (nearest_pick_plan_required + 2)
        knowledge["yellow_nearest_pick_plan_safe"] = bool(nearest_pick_plan_safe)

        recharge_lock = int(knowledge.get("yellow_recharge_lock", 0))
        if recharge_lock > 0:
            recharge_lock -= 1
        knowledge["yellow_recharge_lock"] = recharge_lock

        blocked_pickup_here = (
            not in_survival
            and has_yellow_here
            and self.can_carry_more()
            and not can_pickup_now
            and not yellow_push_window
            and not nearby_relay_repickup
        )
        if blocked_pickup_here:
            knowledge["yellow_recharge_lock"] = max(int(knowledge.get("yellow_recharge_lock", 0)), 4)

        if (not in_survival
                and knowledge.get("yellow_recharge_lock", 0) > 0
                and "red" not in inv
                and yellow_count == 0
                and not nearby_relay_repickup):
            if has_yellow_here and self.can_carry_more() and self.has_energy_for(ACTION_PICK_UP):
                self._set_decision_debug(knowledge, "pickup_for_relay_unsafe_lock", target=pos)
                return ACTION_PICK_UP
            self._set_decision_debug(knowledge, "recharge_lock_after_unsafe_pickup", target=decon_target)
            return self._decontamination_action(knowledge)

        if (not in_survival
                and "red" not in inv
                and yellow_count == 0
                and nearest_yellow is not None
                and self._manhattan(pos, nearest_yellow) <= 3
                and not nearest_pick_plan_safe):
            knowledge["yellow_recharge_lock"] = max(int(knowledge.get("yellow_recharge_lock", 0)), 6)
            self._set_decision_debug(knowledge, "recharge_before_unsafe_near_pick", target=decon_target)
            return self._decontamination_action(knowledge)

        # Safety override: in survival mode, only emergency-drop transformed output.
        if in_survival and "red" in inv and self.has_energy_for(ACTION_DROP):
            knowledge["pickup_cooldown"] = 6
            self._set_decision_debug(knowledge, "survival_drop_output")
            return ACTION_DROP

        # If survival starts while carrying yellow, try to relay east one step at a time
        # before emergency drop, so yellow flow progresses toward the frontier.
        if (in_survival
                and "red" not in inv
                and yellow_count > 0
                and pos[0] < ZONE_2_END - 1
                and energy > critical_energy_floor
                and self.has_energy_for(ACTION_MOVE_RIGHT)
                and can_relay_step_safely):
            self._set_decision_debug(knowledge, "survival_relay_right")
            return ACTION_MOVE_RIGHT

        if (in_survival
                and "red" not in inv
                and yellow_count > 0):
            if self.has_energy_for(ACTION_TRANSFORM) and has_two_yellow:
                self._set_decision_debug(knowledge, "survival_transform_priority")
                return ACTION_TRANSFORM
            if self.has_energy_for(ACTION_DROP) and pos[0] >= (ZONE_1_END - 1):
                knowledge["yellow_relay_drop"] = True
                knowledge["yellow_recent_relay_drop_ttl"] = 20
                knowledge["yellow_recharge_lock"] = 0
                knowledge["pickup_cooldown"] = max(int(knowledge.get("pickup_cooldown", 0)), 10)
                knowledge["yellow_avoid_pos"] = pos
                knowledge["yellow_avoid_ttl"] = max(int(knowledge.get("yellow_avoid_ttl", 0)), 24)
                knowledge["yellow_no_repick_pos"] = pos
                knowledge["yellow_no_repick_ttl"] = max(int(knowledge.get("yellow_no_repick_ttl", 0)), 24)
                knowledge["yellow_commit_cooldown"] = max(int(knowledge.get("yellow_commit_cooldown", 0)), 12)
                self._set_decision_debug(knowledge, "survival_relay_drop")
                return ACTION_DROP
            self._set_decision_debug(knowledge, "survival_decon_fallback", target=decon_target)
            return self._decontamination_action(knowledge)

        if (not in_survival
                and "red" in inv
                and downstream_red_idle
                and global_yellow_total >= 2
                and self.has_energy_for(ACTION_DROP)):
            self._set_decision_debug(knowledge, "flow_drop_red_red_idle")
            return ACTION_DROP

        if (not in_survival
                and "red" in inv
                and self._manhattan(pos, border_target) <= 2
                and self.has_energy_for(ACTION_DROP)):
            self._set_decision_debug(knowledge, "relay_drop_for_red")
            return ACTION_DROP

        if (not in_survival
                and "red" not in inv
                and yellow_count == 0
                and knowledge.get("yellow_return_retarget") is not None):
            retarget = tuple(knowledge.get("yellow_return_retarget"))
            if retarget == pos:
                if (has_yellow_here
                        and self.can_carry_more()
                        and can_pickup_now
                        and self.has_energy_for(ACTION_PICK_UP)):
                    self._set_decision_debug(knowledge, "pickup_return_retarget_on_cell", target=retarget)
                    return ACTION_PICK_UP
                knowledge.get("known_waste", {}).pop(retarget, None)
                knowledge["yellow_return_retarget"] = None
            else:
                self._set_decision_debug(knowledge, "seek_return_retarget", target=retarget)
                return self._navigate_to_target(knowledge, retarget)

        # If carrying exactly one yellow, prioritize known yellow targets anywhere
        # in z1-z2 before corridor-only exploration.
        if (not in_survival
                and "red" not in inv
                and carrying_partial
                and nearest_yellow is not None):
            if yellow_carry_mode == "recover":
                self._set_decision_debug(knowledge, "carry_one_recover_recharge", target=decon_target)
                return self._decontamination_action(knowledge)
            pickup_second_transform_ready = (
                can_pickup_for_transform_now
                or (can_pickup_now and yellow_transform_window)
            )
            if (nearest_yellow == pos
                    and has_yellow_here
                    and self.can_carry_more()
                    and pickup_second_transform_ready
                    and self.has_energy_for(ACTION_PICK_UP)):
                self._set_decision_debug(knowledge, "pickup_second_yellow_on_cell", target=pos)
                return ACTION_PICK_UP
            self._set_decision_debug(knowledge, "carry_one_seek_nearest_yellow", target=nearest_yellow)
            return self._navigate_to_target(knowledge, nearest_yellow)

        if (not in_survival
                and "red" not in inv
                and carrying_partial
                and nearest_yellow is None):
            if yellow_carry_mode == "recover":
                self._set_decision_debug(knowledge, "carry_one_recover_recharge", target=decon_target)
                return self._decontamination_action(knowledge)
            buffer_target = decon_target
            if self._manhattan(pos, buffer_target) <= 1:
                self._set_decision_debug(knowledge, "carry_one_buffer_drop_before_recharge", target=buffer_target)
                return self._decontamination_action(knowledge)
            buffer_stage = self._adjacent_staging_cell(knowledge, buffer_target)
            if buffer_stage:
                self._set_decision_debug(knowledge, "carry_one_buffer_stage", target=buffer_stage)
                return self._navigate_to_target(knowledge, buffer_stage)
            self._set_decision_debug(knowledge, "carry_one_buffer_recharge_fallback", target=buffer_target)
            return self._decontamination_action(knowledge)

        # Wait-for-pair policy: when empty and fewer than two yellow blocks exist,
        # stage next to the lone yellow and wait before picking the first.
        wait_pair_distance_gate = 6
        lone_far_pursuit_enabled = (
            not in_survival
            and "red" not in inv
            and yellow_count == 0
            and nearest_yellow is not None
            and known_yellow_count == 1
            and global_yellow_total < 2
            and energy >= 72
            and wait_pair_cooldown == 0
        )
        if lone_far_pursuit_enabled:
            wait_pair_distance_gate = 14
        knowledge["yellow_wait_pair_distance_gate"] = wait_pair_distance_gate

        wait_for_pair_mode = (
            not in_survival
            and "red" not in inv
            and yellow_count == 0
            and nearest_yellow is not None
            and global_yellow_total < 2
            and self._manhattan(pos, nearest_yellow) <= wait_pair_distance_gate
            and not wait_pair_fallback_mode
            and wait_pair_cooldown == 0
        )

        distance_gate_failed = (
            not in_survival
                and "red" not in inv
                and yellow_count == 0
                and nearest_yellow is not None
                and global_yellow_total < 2
                and self._manhattan(pos, nearest_yellow) > wait_pair_distance_gate
        )
        if distance_gate_failed and lone_far_pursuit_enabled:
            self._set_decision_debug(knowledge, "wait_pair_far_lone_yellow_pursuit", target=nearest_yellow)
            return self._navigate_to_target(knowledge, nearest_yellow)

        if distance_gate_failed and not wait_pair_fallback_mode:
            wait_pair_fallback_mode = True
            wait_pair_fallback_ticks = 6
            standby_target = (ZONE_1_END, GRID_ROWS // 2)
            wait_pair_fallback_strategy = "standby" if self._manhattan(pos, standby_target) > 1 else "scout"
            knowledge["yellow_wait_pair_fallback_mode"] = True
            knowledge["yellow_wait_pair_fallback_ticks"] = 6
            knowledge["yellow_wait_pair_fallback_strategy"] = wait_pair_fallback_strategy

        if (wait_pair_fallback_mode
                and not in_survival
                and "red" not in inv
                and yellow_count == 0
                and nearest_yellow is not None
                and global_yellow_total < 2):
            standby_target = (ZONE_1_END, GRID_ROWS // 2)
            if wait_pair_fallback_strategy is None:
                wait_pair_fallback_strategy = "standby" if self._manhattan(pos, standby_target) > 1 else "scout"
                knowledge["yellow_wait_pair_fallback_strategy"] = wait_pair_fallback_strategy
            if wait_pair_fallback_strategy == "scout":
                self._set_decision_debug(knowledge, "wait_pair_distance_gate_fallback_scout")
                return self._explore_action(knowledge)
            if self._manhattan(pos, standby_target) <= 1:
                if wait_pair_fallback_ticks <= 2:
                    wait_pair_fallback_strategy = "scout"
                    knowledge["yellow_wait_pair_fallback_strategy"] = "scout"
                self._set_decision_debug(knowledge, "wait_pair_distance_gate_fallback_probe", target=standby_target)
                return self._explore_action(knowledge)
            self._set_decision_debug(knowledge, "wait_pair_distance_gate_fallback_standby", target=standby_target)
            return self._navigate_to_target(knowledge, standby_target)

        if wait_for_pair_mode:
            if yellow_idle_mode == "recharge":
                knowledge["yellow_wait_pair_idle_ticks"] = 0
                self._set_decision_debug(knowledge, "wait_pair_recharge_low_energy", target=decon_target)
                return self._decontamination_action(knowledge)
            stage_cell = self._adjacent_staging_cell(knowledge, nearest_yellow)
            if stage_cell:
                if pos == nearest_yellow:
                    knowledge["yellow_wait_pair_idle_ticks"] = 0
                    self._set_decision_debug(knowledge, "wait_pair_leave_lone_yellow", target=stage_cell)
                    return self._navigate_to_target(knowledge, stage_cell)
                if pos == stage_cell:
                    wait_pair_idle_ticks += 1
                    knowledge["yellow_wait_pair_idle_ticks"] = wait_pair_idle_ticks
                    if wait_pair_idle_ticks >= 10:
                        knowledge["yellow_wait_pair_idle_ticks"] = 0
                        knowledge["yellow_wait_pair_cooldown"] = 8
                        if global_yellow_total > 0:
                            self._set_decision_debug(knowledge, "wait_pair_stage_timeout_scout")
                            return self._explore_action(knowledge)
                        standby_target = (ZONE_1_END, GRID_ROWS // 2)
                        self._set_decision_debug(knowledge, "wait_pair_stage_timeout_standby", target=standby_target)
                        return self._navigate_to_target(knowledge, standby_target)
                    self._set_decision_debug(knowledge, "wait_pair_stage_idle", target=nearest_yellow)
                    return ACTION_IDLE
                knowledge["yellow_wait_pair_idle_ticks"] = 0
                self._set_decision_debug(knowledge, "wait_pair_stage_move", target=stage_cell)
                return self._navigate_to_target(knowledge, stage_cell)
        else:
            knowledge["yellow_wait_pair_idle_ticks"] = 0

        lone_pickup_guard = (
            not in_survival
            and "red" not in inv
            and yellow_count == 0
            and has_yellow_here
            and known_yellow_count < self.transform_cost
            and global_yellow_total < self.transform_cost
            and not msg_target
            and wait_pair_cooldown == 0
        )
        if lone_pickup_guard:
            stage_cell = self._adjacent_staging_cell(knowledge, pos)
            if stage_cell:
                self._set_decision_debug(knowledge, "wait_pair_leave_lone_yellow", target=stage_cell)
                return self._navigate_to_target(knowledge, stage_cell)
            self._set_decision_debug(knowledge, "wait_pair_hold_lone_yellow")
            return ACTION_IDLE

        if (not in_survival
                and has_yellow_here
                and self.can_carry_more()
            and can_pickup_now
                and self.has_energy_for(ACTION_PICK_UP)):
            if yellow_count == 0:
                knowledge["yellow_first_pick_pos"] = pos
            self._set_decision_debug(knowledge, "pickup_on_cell", target=pos)
            return ACTION_PICK_UP

        # Commitment window: when very close to a known yellow, keep pursuing it
        # if a full pickup->decon safety plan is feasible. This avoids recharge/seek
        # oscillations near staged pickups.
        urgent_near_yellow = (
            not in_survival
            and "red" not in inv
            and yellow_count == 0
            and nearest_yellow is not None
            and self._manhattan(pos, nearest_yellow) <= 3
            and commit_cooldown == 0
            and (global_yellow_total >= 2)
        )
        if urgent_near_yellow:
            steps_to_target = self._estimate_steps(
                knowledge,
                pos,
                nearest_yellow,
                inventory_override=inv,
            )
            steps_after_pick_to_decon = self._estimate_steps(
                knowledge,
                nearest_yellow,
                decon_target,
                inventory_override=["yellow"],
            )
            required_energy_urgent = (
                self._estimate_required_energy(knowledge, steps_to_target, inventory_override=inv)
                + ENERGY_COST_PICKUP
                + self._estimate_required_energy(
                    knowledge,
                    steps_after_pick_to_decon,
                    inventory_override=["yellow"],
                )
            )
            if energy >= (required_energy_urgent + 2):
                if nearest_yellow == pos:
                    if (has_yellow_here
                            and self.can_carry_more()
                            and can_pickup_now
                            and self.has_energy_for(ACTION_PICK_UP)):
                        self._set_decision_debug(knowledge, "pickup_on_cell", target=pos)
                        return ACTION_PICK_UP

                    knowledge.get("known_waste", {}).pop(pos, None)
                    knowledge["intention_lock"] = 0
                    knowledge["yellow_avoid_pos"] = pos
                    knowledge["yellow_avoid_ttl"] = max(int(knowledge.get("yellow_avoid_ttl", 0)), 12)
                    knowledge["yellow_commit_cooldown"] = max(int(knowledge.get("yellow_commit_cooldown", 0)), 10)
                    self._set_decision_debug(knowledge, "clear_stale_commit_target", target=pos)
                    return self._explore_action(knowledge)

                self._set_decision_debug(knowledge, "commit_near_yellow_pickup", target=nearest_yellow)
                return self._navigate_to_target(knowledge, nearest_yellow)

        # Pre-position: if only one known yellow exists and we cannot transform yet,
        # move to an adjacent standby cell to reduce future response time.
        lone_yellow_mode = (
            not in_survival
            and "red" not in inv
            and yellow_count == 0
            and commit_cooldown == 0
            and nearest_pick_plan_safe
            and knowledge.get("yellow_recharge_lock", 0) == 0
            and known_yellow_count == 1
            and nearest_yellow is not None
            and nearest_yellow != pos
        )
        if lone_yellow_mode:
            stage_cell = self._adjacent_staging_cell(knowledge, nearest_yellow)
            if stage_cell:
                wait_count = knowledge.get("yellow_stage_wait", 0)
                wait_limit = 0
                if pos == stage_cell:
                    has_second_yellow_signal = (global_yellow_total >= 2) or (known_yellow_count >= 2)
                    if not has_second_yellow_signal:
                        knowledge["yellow_stage_wait"] = wait_count + 1
                        self._set_decision_debug(knowledge, "stage_adjacent_wait", target=nearest_yellow)
                        return ACTION_IDLE
                    if wait_count < wait_limit:
                        knowledge["yellow_stage_wait"] = wait_count + 1
                        self._set_decision_debug(knowledge, "stage_adjacent_wait", target=nearest_yellow)
                        return ACTION_IDLE
                    knowledge["yellow_stage_wait"] = 0
                    self._set_decision_debug(knowledge, "stage_to_pickup", target=nearest_yellow)
                    return self._navigate_to_target(knowledge, nearest_yellow)
                knowledge["yellow_stage_wait"] = 0
                self._set_decision_debug(knowledge, "stage_adjacent_move", target=stage_cell)
                return self._navigate_to_target(knowledge, stage_cell)

        # If yellow has no actionable objective, pre-position near green-zone frontier.
        if (not in_survival
                and "red" not in inv
            and yellow_count == 0
                and not has_yellow_here
                and not has_known_yellow
                and not msg_target):
            if yellow_idle_mode == "recharge":
                self._set_decision_debug(knowledge, "recharge_idle_no_task", target=decon_target)
                return self._decontamination_action(knowledge)
            if global_yellow_total > 0:
                self._set_decision_debug(knowledge, "scout_global_yellow_hint")
                return self._explore_action(knowledge)
            standby_target = (ZONE_1_END, GRID_ROWS // 2)
            if self._manhattan(pos, standby_target) <= 1:
                self._set_decision_debug(knowledge, "idle_standby_no_yellow", target=standby_target)
                return ACTION_IDLE
            self._set_decision_debug(knowledge, "move_standby_no_yellow", target=standby_target)
            return self._navigate_to_target(knowledge, standby_target)

        knowledge["yellow_idle_no_task_ticks"] = 0

        patrol_target = (ZONE_1_END, GRID_ROWS // 2)

        candidates = []
        if in_survival:
            candidates.append((INTENT_SURVIVE, 200.0, None))
        else:
            if "red" in inv:
                candidates.append((INTENT_DELIVER, 180.0 - self._manhattan(pos, border_target), border_target))
            if yellow_count >= self.transform_cost:
                candidates.append((INTENT_TRANSFORM, 105.0, None))
            if has_yellow_here and self.can_carry_more():
                if can_pickup_now:
                    candidates.append((INTENT_PICKUP, 95.0, pos))
                else:
                    candidates.append((INTENT_RECHARGE, 140.0, None))
            if msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
                base = YELLOW_MESSAGE_SEEK_BASE_SCORE + (26.0 if carrying_partial else 0.0)
                risk_penalty = self._energy_risk_penalty(knowledge, msg_target, reserve_target=decon_target)
                candidates.append((INTENT_SEEK_WASTE, base - self._manhattan(pos, msg_target) - risk_penalty, msg_target))
            if nearest_yellow:
                base = (YELLOW_SEEK_BASE_SCORE + 45.0) if carrying_partial else (YELLOW_SEEK_BASE_SCORE + 28.0)
                risk_penalty = self._energy_risk_penalty(knowledge, nearest_yellow, reserve_target=decon_target)
                candidates.append((INTENT_SEEK_WASTE, base - self._manhattan(pos, nearest_yellow) - risk_penalty, nearest_yellow))
            explore_score = 34.0 if carrying_partial else 20.0
            candidates.append((INTENT_EXPLORE, explore_score - self._manhattan(pos, patrol_target), patrol_target))

        intent, target = self._select_intention(knowledge, candidates)
        self._set_decision_debug(knowledge, f"intent={intent}", target=target)

        if intent == INTENT_SURVIVE:
            return self._decontamination_action(knowledge)
        if intent == INTENT_RECHARGE:
            return self._decontamination_action(knowledge)
        if intent == INTENT_DELIVER:
            if pos[0] >= ZONE_2_END - 1:
                return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
            knowledge["facing"] = "right"
            return self._navigate_to_target(knowledge, target or border_target)
        if intent == INTENT_TRANSFORM:
            return ACTION_TRANSFORM if self.has_energy_for(ACTION_TRANSFORM) else ACTION_IDLE
        if intent == INTENT_PICKUP:
            return ACTION_PICK_UP if self.has_energy_for(ACTION_PICK_UP) else ACTION_IDLE
        if intent == INTENT_SEEK_WASTE and target:
            if target == pos or knowledge.get("seek_idle_counter", 0) >= 2:
                knowledge.get("known_waste", {}).pop(target, None)
                knowledge["intention_lock"] = 0
                return self._forage_second_yellow(knowledge) if carrying_partial else self._explore_action(knowledge)
            knowledge["facing"] = "right" if target[0] > pos[0] else "left"
            return self._navigate_to_target(knowledge, target)
        if intent == INTENT_EXPLORE:
            if carrying_partial:
                return self._forage_second_yellow(knowledge)
            return self._explore_action(knowledge)
        if target:
            return self._navigate_to_target(knowledge, target)
        return ACTION_IDLE


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
        energy = knowledge.get("energy", AGENT_MAX_ENERGY)
        disposal_target = (GRID_COLS - 1, pos[1])
        msg_target = self._check_messages_for_target(knowledge)
        red_unsafe_avoid_pos = knowledge.get("red_unsafe_avoid_pos")
        red_unsafe_avoid_ttl = int(knowledge.get("red_unsafe_avoid_ttl", 0))
        if red_unsafe_avoid_ttl > 0:
            red_unsafe_avoid_ttl -= 1
        knowledge["red_unsafe_avoid_ttl"] = red_unsafe_avoid_ttl
        if red_unsafe_avoid_ttl <= 0:
            knowledge["red_unsafe_avoid_pos"] = None
            red_unsafe_avoid_pos = None
        elif red_unsafe_avoid_pos is not None:
            red_unsafe_avoid_pos = tuple(red_unsafe_avoid_pos)

        def _is_red_unsafe_avoid(cell):
            return (
                red_unsafe_avoid_pos is not None
                and red_unsafe_avoid_ttl > 0
                and cell is not None
                and cell == red_unsafe_avoid_pos
            )

        known_red_positions = [
            p for p, info in knowledge.get("known_waste", {}).items()
            if info.get("type") == "red"
            and self._can_move_to(p[0], p[1], self.allowed_zones)
            and not _is_red_unsafe_avoid(p)
        ]
        nearest_red = min(known_red_positions, key=lambda p: self._manhattan(pos, p)) if known_red_positions else None
        has_known_red = bool(known_red_positions)
        known_red_count = sum(
            max(1, int(knowledge.get("known_waste", {}).get(p, {}).get("count", 1)))
            for p in known_red_positions
        )
        has_red_here = pos in percepts and "red" in percepts[pos].get("waste", [])
        standby_target = (ZONE_2_END - 1, GRID_ROWS // 2)
        observed_red_total = known_red_count + (1 if "red" in inv else 0)
        knowledge["red_observed_total"] = int(observed_red_total)
        red_recharge_enter = AGENT_MAX_ENERGY - 8
        red_idle_mode = knowledge.get("red_idle_mode", "standby")

        if observed_red_total > 0:
            red_idle_mode = "standby"

        decon_target = ((ZONE_2_END + (GRID_COLS - 1)) // 2, GRID_ROWS // 2)
        on_decon = bool(pos in percepts and percepts[pos].get("decontamination", False))
        if "red" in inv:
            primary_target = disposal_target
        elif nearest_red:
            primary_target = nearest_red
        elif msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
            primary_target = msg_target
        else:
            primary_target = standby_target

        in_survival = self._needs_survival_mode_dynamic_for_target(
            knowledge,
            primary_target=primary_target,
            decon_target=decon_target,
            role_prefix="red",
        )

        red_pickup_plan_safe = True
        if "red" not in inv and self.can_carry_more():
            steps_pick_to_disposal = self._estimate_steps(
                knowledge,
                pos,
                disposal_target,
                inventory_override=["red"],
            )
            steps_disposal_to_decon_no_carry = self._estimate_steps(
                knowledge,
                disposal_target,
                decon_target,
                inventory_override=[],
            )
            required_pick_plan = (
                ENERGY_COST_PICKUP
                + self._estimate_required_energy(
                    knowledge,
                    steps_pick_to_disposal,
                    inventory_override=["red"],
                )
                + ENERGY_COST_DROP
                + self._estimate_required_energy(
                    knowledge,
                    steps_disposal_to_decon_no_carry,
                    inventory_override=[],
                )
            )
            red_pickup_plan_safe = energy >= max(ENERGY_COST_PICKUP + ENERGY_COST_DROP + 2, required_pick_plan)
        knowledge["red_pickup_plan_safe"] = bool(red_pickup_plan_safe)

        if "red" in inv:
            steps_to_disposal = self._estimate_steps(
                knowledge,
                pos,
                disposal_target,
                inventory_override=inv,
            )
            steps_disposal_to_decon = self._estimate_steps(
                knowledge,
                disposal_target,
                decon_target,
                inventory_override=[],
            )
            required_deliver_plan = (
                self._estimate_required_energy(knowledge, steps_to_disposal, inventory_override=inv)
                + ENERGY_COST_DROP
                + self._estimate_required_energy(knowledge, steps_disposal_to_decon, inventory_override=[])
            )
            can_safe_deliver_plan = energy >= max(ENERGY_COST_DROP + 2, required_deliver_plan)
            knowledge["red_can_safe_deliver_plan"] = bool(can_safe_deliver_plan)

            # Carrying red always prioritizes disposal when still feasible.
            if can_safe_deliver_plan:
                if pos[0] >= GRID_COLS - 1:
                    self._set_decision_debug(knowledge, "dispose_on_border", target=disposal_target)
                    return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
                self._set_decision_debug(knowledge, "survival_deliver_override", target=disposal_target)
                return self._navigate_to_target(knowledge, disposal_target)

        # Safety override: in survival mode, emergency-drop any carried waste.
        if in_survival and inv and self.has_energy_for(ACTION_DROP):
            self._set_decision_debug(knowledge, "survival_drop")
            return ACTION_DROP

        # While in survival mode, do not engage pickups/chasing tasks.
        # Go decontaminate until hysteresis exits survival mode.
        if in_survival:
            self._set_decision_debug(knowledge, "intent=survive")
            return self._decontamination_action(knowledge)

        # Hard priority 1: if carrying red, always deliver.
        if "red" in inv:
            if pos[0] >= GRID_COLS - 1:
                self._set_decision_debug(knowledge, "dispose_on_border", target=disposal_target)
                return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
            self._set_decision_debug(knowledge, "deliver_red", target=disposal_target)
            return self._navigate_to_target(knowledge, disposal_target)

        # Hard priority 2: if there is a known actionable red target, go for it.
        if nearest_red:
            if nearest_red == pos and has_red_here:
                if not red_pickup_plan_safe:
                    unsafe_target = nearest_red if nearest_red is not None else pos
                    knowledge["red_unsafe_avoid_pos"] = unsafe_target
                    knowledge["red_unsafe_avoid_ttl"] = max(int(knowledge.get("red_unsafe_avoid_ttl", 0)), 24)
                    self._set_decision_debug(knowledge, "defer_pickup_unsafe_red_plan", target=decon_target)
                    return self._decontamination_action(knowledge)
                self._set_decision_debug(knowledge, "pickup_on_cell", target=nearest_red)
                return ACTION_PICK_UP if self.has_energy_for(ACTION_PICK_UP) else ACTION_IDLE
            self._set_decision_debug(knowledge, "seek_known_red", target=nearest_red)
            return self._navigate_to_target(knowledge, nearest_red)

        if msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
            self._set_decision_debug(knowledge, "seek_message_red", target=msg_target)
            return self._navigate_to_target(knowledge, msg_target)

        # No red task: stay parked near z2/z3 handoff instead of wandering.
        if (not in_survival
                and "red" not in inv
                and not has_red_here
                and not has_known_red
                and not msg_target):
            if observed_red_total == 0:
                if red_idle_mode == "recharge":
                    if energy >= AGENT_MAX_ENERGY:
                        red_idle_mode = "standby"
                    else:
                        knowledge["red_idle_mode"] = "recharge"
                        if on_decon:
                            self._set_decision_debug(knowledge, "idle_recharge_no_red")
                            return ACTION_IDLE
                        self._set_decision_debug(knowledge, "move_recharge_no_red", target=decon_target)
                        return self._navigate_to_target(knowledge, decon_target)

                if energy <= red_recharge_enter:
                    knowledge["red_idle_mode"] = "recharge"
                    if on_decon:
                        self._set_decision_debug(knowledge, "idle_recharge_no_red")
                        return ACTION_IDLE
                    self._set_decision_debug(knowledge, "move_recharge_no_red", target=decon_target)
                    return self._navigate_to_target(knowledge, decon_target)

            knowledge["red_idle_mode"] = "standby"
            hold_radius = 1 if observed_red_total == 0 else 2
            if self._manhattan(pos, standby_target) <= hold_radius:
                self._set_decision_debug(knowledge, "idle_standby")
                return ACTION_IDLE
            self._set_decision_debug(knowledge, "move_standby", target=standby_target)
            return self._navigate_to_target(knowledge, standby_target)

        candidates = []
        if in_survival:
            candidates.append((INTENT_SURVIVE, 200.0, None))
        else:
            if "red" in inv:
                candidates.append((INTENT_DELIVER, 125.0 - self._manhattan(pos, disposal_target), disposal_target))
            if has_red_here and self.can_carry_more() and red_pickup_plan_safe:
                candidates.append((INTENT_PICKUP, 95.0, pos))
            if msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
                risk_penalty = self._energy_risk_penalty(knowledge, msg_target, reserve_target=decon_target)
                candidates.append((INTENT_SEEK_WASTE, 85.0 - self._manhattan(pos, msg_target) - risk_penalty, msg_target))
            if nearest_red:
                risk_penalty = self._energy_risk_penalty(knowledge, nearest_red, reserve_target=decon_target)
                candidates.append((INTENT_SEEK_WASTE, 70.0 - self._manhattan(pos, nearest_red) - risk_penalty, nearest_red))
            patrol_target = (ZONE_2_END, pos[1])
            candidates.append((INTENT_EXPLORE, 20.0 - self._manhattan(pos, patrol_target), patrol_target))

        intent, target = self._select_intention(knowledge, candidates)
        self._set_decision_debug(knowledge, f"intent={intent}", target=target)

        if intent == INTENT_SURVIVE:
            return self._decontamination_action(knowledge)
        if intent == INTENT_DELIVER:
            if pos[0] >= GRID_COLS - 1:
                return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
            knowledge["facing"] = "right"
            return self._navigate_to_target(knowledge, target or disposal_target)
        if intent == INTENT_PICKUP:
            return ACTION_PICK_UP if self.has_energy_for(ACTION_PICK_UP) else ACTION_IDLE
        if intent == INTENT_SEEK_WASTE and target:
            knowledge["facing"] = "right" if target[0] > pos[0] else "left"
            return self._navigate_to_target(knowledge, target)
        if intent == INTENT_EXPLORE:
            return self._explore_action(knowledge)
        if target:
            return self._navigate_to_target(knowledge, target)
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
