# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
Robot agent classes: GreenAgent, YellowAgent, RedAgent.
Each follows the percepts -> deliberate -> do loop.
Includes energy system and inter-agent communication.

Decision logic uses a clean priority cascade:
  1. SURVIVE    -> if critical energy, drop cargo and go heal
  2. DELIVER    -> if carrying output, deliver to handoff border
  3. TRANSFORM  -> if have enough input, transform now
  4. PICKUP     -> if waste here, pick up (with energy safety check)
  5. SEEK       -> if know about waste, navigate to it
  6. PATROL     -> position near handoff zone where input arrives
  7. EXPLORE    -> search zone for waste
"""

import random
import heapq
from src.config import (
    ZONE_1_END, ZONE_2_END, GRID_COLS, GRID_ROWS,
    AGENT_MAX_CARRY, GREEN_TO_YELLOW_COST, YELLOW_TO_RED_COST,
    ENERGY_ENABLED, AGENT_MAX_ENERGY,
    GLOBAL_KNOWLEDGE,
    ENERGY_COST_MOVE, ENERGY_COST_PICKUP, ENERGY_COST_TRANSFORM,
    ENERGY_COST_DROP,
    COMMUNICATION_ENABLED,
    HEALTH_LOW_THRESHOLD,
    HEALTH_RESUME_THRESHOLD,
    KNOWLEDGE_WASTE_TTL,
    RECENT_POS_WINDOW,
    RECENT_POS_PENALTY,
    FRONTIER_INFO_GAIN_WEIGHT,
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
INTENT_PATROL = "patrol"
INTENT_ASSIST = "assist"

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
            "survival_mode": False,
            "path_goal": None,
            "path_plan": [],
            "explore_target": None,
            "recent_positions": [(x, y)],
            "visited_count": {(x, y): 0 for x in range(GRID_COLS) for y in range(GRID_ROWS)},
            "decision_reason": "",
            "decision_target": None,
            "nav_next": None,
            "dropped_waste": None,   # remembers where waste was dropped during survival
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
        msg = {
            "from": self.agent_id,
            "from_type": self.robot_type,
            "type": msg_type,
            "content": content,
        }
        model.message_board.append(msg)

    # -- Agent loop ------------------------------------------------------------

    def step_agent(self, model):
        # Deliver messages from mailbox into knowledge
        self.knowledge["messages"] = list(self.mailbox)
        self.mailbox.clear()

        # Decay known waste TTL once per tick (NOT in _update_knowledge which runs twice)
        for known_pos in list(self.knowledge["known_waste"].keys()):
            self.knowledge["known_waste"][known_pos]["ttl"] -= 1
            if self.knowledge["known_waste"][known_pos]["ttl"] <= 0:
                self.knowledge["known_waste"].pop(known_pos, None)

        # Fix knowledge leak: only use global waste counts when GLOBAL_KNOWLEDGE is on
        if GLOBAL_KNOWLEDGE:
            self.knowledge["global_waste_counts"] = model.get_waste_counts()
            self.knowledge["global_waste_positions"] = model.get_waste_positions()
        else:
            self.knowledge["global_waste_counts"] = self._estimate_waste_counts()
            self.knowledge["global_waste_positions"] = {"green": [], "yellow": [], "red": [], "total": 0}

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

        # Share ALL visible waste (any type) so downstream/upstream agents know
        for p, contents in percepts.items():
            for wtype in contents.get("waste", []):
                self.send_message(model, "waste_found", {"pos": p, "waste_type": wtype})

        # If we just picked up, notify others to remove stale entry
        if self.knowledge.get("last_action") == ACTION_PICK_UP:
            self.send_message(model, "waste_picked", {"pos": pos, "waste_type": self.target_waste})

        # If we just dropped transformed output (deliberate delivery, not survival/emergency),
        # announce it so the downstream agent knows where to find it
        last_reason = self.knowledge.get("decision_reason", "")
        if (self.knowledge.get("last_action") == ACTION_DROP
                and self.output_waste
                and last_reason.startswith("deliver")):
            self.send_message(model, "need_pickup", {"pos": pos, "waste_type": self.output_waste})

        # Load status for ALL agent types
        known_target = sum(
            1 for info in self.knowledge.get("known_waste", {}).values()
            if info.get("type") == self.target_waste
        )
        carrying_target = self.inventory.count(self.target_waste) if self.target_waste else 0
        self.send_message(model, "load_status", {
            "role": self.robot_type,
            "target_waste": self.target_waste,
            "available": known_target + carrying_target,
            "energy": self.energy,
            "intention": self.knowledge.get("current_intention", ""),
            "pos": pos,
        })

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

        # Process messages: update known_waste from waste_found/need_pickup, remove from waste_picked
        for msg in self.knowledge.get("messages", []):
            msg_type = msg.get("type")
            content = msg.get("content", {})
            if msg_type == "waste_picked":
                picked_pos = content.get("pos")
                if picked_pos is not None:
                    self.knowledge["known_waste"].pop(tuple(picked_pos), None)
            elif msg_type in ("waste_found", "need_pickup"):
                wpos = content.get("pos")
                wtype = content.get("waste_type")
                if wpos is not None and wtype:
                    self.knowledge["known_waste"][tuple(wpos)] = {
                        "type": wtype,
                        "ttl": KNOWLEDGE_WASTE_TTL,
                    }

    def deliberate(self, knowledge):
        raise NotImplementedError

    def _set_decision_debug(self, knowledge, reason, target=None):
        knowledge["decision_reason"] = reason
        knowledge["decision_target"] = target

    # -- Helpers ---------------------------------------------------------------

    def _estimate_waste_counts(self):
        """Count waste from agent's local knowledge only."""
        counts = {"green": 0, "yellow": 0, "red": 0}
        for pos, info in self.knowledge.get("known_waste", {}).items():
            wtype = info.get("type")
            if wtype in counts:
                counts[wtype] += 1
        counts["total"] = counts["green"] + counts["yellow"] + counts["red"]
        return counts

    def _check_messages_for_target(self, knowledge):
        """Check mailbox for waste_found or need_pickup matching our target type.
        Returns a target position or None."""
        if not COMMUNICATION_ENABLED:
            return None
        for msg in knowledge.get("messages", []):
            if msg["type"] in ("waste_found", "need_pickup"):
                if msg["content"].get("waste_type") == self.target_waste:
                    pos = msg["content"]["pos"]
                    known = knowledge.setdefault("known_waste", {})
                    known[pos] = {
                        "type": self.target_waste,
                        "ttl": KNOWLEDGE_WASTE_TTL,
                    }
                    return pos
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

    def _nearest_decon(self, knowledge):
        """Return the nearest decontamination position (known + defaults)."""
        candidates = self._all_decon_candidates(knowledge)
        pos = knowledge.get("pos", self.pos)
        if not candidates:
            return None
        return min(candidates, key=lambda p: self._manhattan(pos, p))

    def _can_complete_cycle(self, knowledge, waypoints, inventories=None, return_inv=None):
        """Check if agent can visit all waypoints and return to decon with enough energy.
        waypoints: list of (pos, action_cost) tuples
        inventories: list of inventory lists for each leg (optional)
        return_inv: inventory for the return trip to decon (default: empty, since agent usually drops)
        Returns (feasible: bool, margin: float)
        """
        if not ENERGY_ENABLED:
            return True, AGENT_MAX_ENERGY

        energy = knowledge.get("energy", AGENT_MAX_ENERGY)
        pos = knowledge["pos"]
        total_cost = 0
        current_pos = pos

        for i, (wp, action_cost) in enumerate(waypoints):
            inv = inventories[i] if inventories and i < len(inventories) else knowledge.get("inventory", [])
            steps = self._estimate_steps(knowledge, current_pos, wp, inventory_override=inv)
            move_cost = self._estimate_required_energy(knowledge, steps, inventory_override=inv)
            total_cost += move_cost + action_cost
            current_pos = wp

        # Cost to get back to nearest decon from the FINAL position (not current pos)
        # Find decon nearest to the final waypoint, not the agent's current position
        known_decon = self._all_decon_candidates(knowledge)
        if known_decon:
            nearest_return_decon = min(known_decon, key=lambda p: self._manhattan(current_pos, p))
            ret_inv = return_inv if return_inv is not None else []
            steps_to_decon = self._estimate_steps(knowledge, current_pos, nearest_return_decon, inventory_override=ret_inv)
            total_cost += self._estimate_required_energy(knowledge, steps_to_decon, inventory_override=ret_inv)

        margin = energy - total_cost - HEALTH_LOW_THRESHOLD
        return margin >= 0, margin

    def _explore_with_target(self, knowledge, min_col=0, max_col=None):
        """Explore with memory: prefer less-visited reachable cells, then A* to waypoint."""
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
            visited = knowledge.get("visited_count", {})
            candidates = []
            for tx in range(min_col, max_col + 1):
                for ty in range(0, GRID_ROWS):
                    if self._can_move_to(tx, ty, self.allowed_zones):
                        dist_score = self._manhattan(pos, (tx, ty))
                        if dist_score == 0:
                            continue
                        visit_score = visited.get((tx, ty), 0)
                        info_gain = self._frontier_information_gain(knowledge, (tx, ty))
                        recent_penalty = self._recent_position_penalty(knowledge, (tx, ty))
                        # Strongly prefer unvisited cells, penalize backtracking
                        total_score = info_gain - (0.5 * dist_score) - (3.0 * visit_score) - recent_penalty
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

    def _all_decon_candidates(self, knowledge):
        """Return known decon zones plus default zone centers as candidates."""
        candidates = set(knowledge.get("known_decontamination", set()))
        mid_row = GRID_ROWS // 2
        if 1 in self.allowed_zones:
            candidates.add(((0 + (ZONE_1_END - 1)) // 2, mid_row))
        if 2 in self.allowed_zones:
            candidates.add(((ZONE_1_END + (ZONE_2_END - 1)) // 2, mid_row))
        if 3 in self.allowed_zones:
            candidates.add(((ZONE_2_END + (GRID_COLS - 1)) // 2, mid_row))
        return list(candidates)

    def _decontamination_action(self, knowledge):
        """Return an action toward the closest decontamination zone."""
        pos = knowledge["pos"]
        all_decon = self._all_decon_candidates(knowledge)

        # If carrying waste, drop before stepping onto decon
        if knowledge.get("inventory"):
            if pos in all_decon:
                if self.has_energy_for(ACTION_DROP):
                    return ACTION_DROP
                return ACTION_IDLE
            if all_decon:
                closest = min(all_decon, key=lambda p: self._manhattan(pos, p))
                if self._manhattan(pos, closest) == 1:
                    if self.has_energy_for(ACTION_DROP):
                        return ACTION_DROP
                    return ACTION_IDLE

        if pos in all_decon:
            return ACTION_IDLE

        if all_decon:
            closest = min(all_decon, key=lambda p: self._manhattan(pos, p))
            knowledge["facing"] = "right" if closest[0] > pos[0] else "left"
            return self._navigate_to_target(knowledge, closest)

        # Fallback (shouldn't happen with defaults above)
        return self._random_move(pos, self.allowed_zones)

    def _assist_green(self, knowledge):
        """Move into zone 1 and explore to broadcast green waste for the green agent."""
        pos = knowledge["pos"]
        if self._get_zone(pos[0]) == 1:
            # Already in zone 1 — explore it (broadcasts happen automatically via _broadcast)
            return self._explore_with_target(knowledge, min_col=0, max_col=ZONE_1_END - 1)
        # Navigate toward zone 1 center
        target = (ZONE_1_END // 2, GRID_ROWS // 2)
        return self._navigate_to_target(knowledge, target)

    def _recover_dropped_waste(self, knowledge):
        """If we dropped waste during survival, navigate back to pick it up.
        Returns an action if recovery is in progress, or None if nothing to recover."""
        dropped = knowledge.get("dropped_waste")
        if not dropped:
            return None
        drop_pos = dropped["pos"]
        pos = knowledge["pos"]
        # Close enough to perceive the dropped waste — clear marker, let normal pickup handle it
        if self._manhattan(pos, drop_pos) <= 1:
            knowledge["dropped_waste"] = None
            return None
        # Navigate back to the drop position
        self._set_decision_debug(knowledge, "recover_dropped", target=drop_pos)
        return self._navigate_to_target(knowledge, drop_pos)


# =============================================================================
# GreenAgent
# =============================================================================

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
        energy = knowledge.get("energy", AGENT_MAX_ENERGY)
        green_count = inv.count("green")
        has_yellow = "yellow" in inv
        border = (ZONE_1_END - 1, pos[1])  # delivery border col 9
        has_green_here = pos in percepts and "green" in percepts[pos].get("waste", [])
        nearest_green = self._nearest_known_waste(knowledge, "green")
        on_decon = pos in percepts and percepts[pos].get("decontamination", False)

        # 1. SURVIVE - transform before dropping if possible
        in_survival = self._needs_survival_mode(knowledge)
        if in_survival:
            if green_count >= self.transform_cost and self.has_energy_for(ACTION_TRANSFORM):
                self._set_decision_debug(knowledge, "survive_transform_first")
                return ACTION_TRANSFORM
            if inv and self.has_energy_for(ACTION_DROP):
                knowledge["dropped_waste"] = {"pos": pos, "types": list(inv)}
                self._set_decision_debug(knowledge, "survive_drop")
                return ACTION_DROP
            self._set_decision_debug(knowledge, "survive_heal")
            return self._decontamination_action(knowledge)

        # 1.5 RECOVER dropped waste after survival
        recover = self._recover_dropped_waste(knowledge)
        if recover is not None:
            return recover

        # 2. DELIVER yellow to border
        if has_yellow:
            if pos[0] >= ZONE_1_END - 1:
                self._set_decision_debug(knowledge, "deliver_drop", target=border)
                return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
            self._set_decision_debug(knowledge, "deliver_move", target=border)
            return self._navigate_to_target(knowledge, border)

        # 3. TRANSFORM
        if green_count >= self.transform_cost and self.has_energy_for(ACTION_TRANSFORM):
            self._set_decision_debug(knowledge, "transform")
            return ACTION_TRANSFORM

        # 4. PICKUP green
        if has_green_here and self.can_carry_more() and self.has_energy_for(ACTION_PICK_UP):
            knowledge["dropped_waste"] = None
            self._set_decision_debug(knowledge, "pickup", target=pos)
            return ACTION_PICK_UP

        # 5. SEEK green waste
        if nearest_green:
            self._set_decision_debug(knowledge, "seek", target=nearest_green)
            return self._navigate_to_target(knowledge, nearest_green)

        msg_target = self._check_messages_for_target(knowledge)
        if msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
            self._set_decision_debug(knowledge, "seek_msg", target=msg_target)
            return self._navigate_to_target(knowledge, msg_target)

        # 6. RECHARGE if on decon and low energy, otherwise always explore
        if on_decon and energy < AGENT_MAX_ENERGY - 10:
            self._set_decision_debug(knowledge, "idle_recharge")
            return ACTION_IDLE

        # 7. EXPLORE z1 — green should always search, waste may be undiscovered
        self._set_decision_debug(knowledge, "explore")
        return self._explore_with_target(knowledge, min_col=0, max_col=ZONE_1_END - 1)


# =============================================================================
# YellowAgent
# =============================================================================

class YellowAgent(RobotAgent):
    """Collects yellow waste in z1-z2, transforms 2 yellow -> 1 red, transports east."""

    robot_type = "yellow"
    allowed_zones = [1, 2]
    target_waste = "yellow"
    transform_cost = YELLOW_TO_RED_COST
    output_waste = "red"

    # Yellow delivers red waste to a midpoint in z2 (closer than z2/z3 border)
    # This balances yellow's carry cost and red's pickup-to-disposal distance
    _DELIVERY_COL = ZONE_1_END + (ZONE_2_END - ZONE_1_END) * 7 // 10  # col 17

    # Yellow only seeks waste near the z1/z2 border where green delivers
    _SEEK_MIN_COL = max(0, ZONE_1_END - 4)   # col 6
    _SEEK_MAX_COL = ZONE_1_END + 4            # col 14

    def _nearest_border_yellow(self, knowledge):
        """Find nearest known yellow waste anywhere in allowed zones."""
        pos = knowledge["pos"]
        known_waste = knowledge.get("known_waste", {})
        candidates = [p for p, info in known_waste.items()
                      if info.get("type") == "yellow"
                      and self._can_move_to(p[0], p[1], self.allowed_zones)]
        if not candidates:
            return None
        return min(candidates, key=lambda p: self._manhattan(pos, p))

    def deliberate(self, knowledge):
        pos = knowledge["pos"]
        inv = knowledge["inventory"]
        percepts = knowledge["percepts"]
        energy = knowledge.get("energy", AGENT_MAX_ENERGY)
        yellow_count = inv.count("yellow")
        has_red = "red" in inv
        border = (self._DELIVERY_COL, pos[1])
        has_yellow_here = pos in percepts and "yellow" in percepts[pos].get("waste", [])
        nearest_yellow = self._nearest_border_yellow(knowledge)
        on_decon = pos in percepts and percepts[pos].get("decontamination", False)

        # 1. SURVIVE - transform if possible before dropping
        in_survival = self._needs_survival_mode(knowledge)
        if in_survival:
            if yellow_count >= self.transform_cost and self.has_energy_for(ACTION_TRANSFORM):
                self._set_decision_debug(knowledge, "survive_transform_first")
                return ACTION_TRANSFORM
            if inv and self.has_energy_for(ACTION_DROP):
                knowledge["dropped_waste"] = {"pos": pos, "types": list(inv)}
                self._set_decision_debug(knowledge, "survive_drop")
                return ACTION_DROP
            self._set_decision_debug(knowledge, "survive_heal")
            return self._decontamination_action(knowledge)

        # 1.5 RECOVER dropped waste after survival
        recover = self._recover_dropped_waste(knowledge)
        if recover is not None:
            return recover

        # 2. DELIVER red to border
        if has_red:
            if pos[0] >= self._DELIVERY_COL:
                self._set_decision_debug(knowledge, "deliver_drop", target=border)
                return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
            self._set_decision_debug(knowledge, "deliver_move", target=border)
            return self._navigate_to_target(knowledge, border)

        # 3. TRANSFORM
        if yellow_count >= self.transform_cost and self.has_energy_for(ACTION_TRANSFORM):
            self._set_decision_debug(knowledge, "transform")
            return ACTION_TRANSFORM

        # 4. PICKUP yellow
        if has_yellow_here and self.can_carry_more() and self.has_energy_for(ACTION_PICK_UP):
            knowledge["dropped_waste"] = None
            self._set_decision_debug(knowledge, "pickup", target=pos)
            return ACTION_PICK_UP

        # 5. SEEK yellow waste
        if nearest_yellow:
            self._set_decision_debug(knowledge, "seek", target=nearest_yellow)
            return self._navigate_to_target(knowledge, nearest_yellow)

        msg_target = self._check_messages_for_target(knowledge)
        if (msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones)):
            self._set_decision_debug(knowledge, "seek_msg", target=msg_target)
            return self._navigate_to_target(knowledge, msg_target)

        # 5.5 WAIT for 2nd yellow — carrying 1 but no 2nd known: idle to conserve energy
        #     Moving burns 2.25/tick (carry+move), idling burns 1.25/tick (carry only)
        #     Messages will notify us when a 2nd yellow appears
        if yellow_count >= 1:
            self._set_decision_debug(knowledge, "wait_for_2nd")
            return ACTION_IDLE

        # 6. RECHARGE on decon if low energy
        if on_decon and energy < AGENT_MAX_ENERGY - 10:
            self._set_decision_debug(knowledge, "idle_recharge")
            return ACTION_IDLE

        # 7. PATROL border — check the z1/z2 border for forgotten yellow waste
        self._set_decision_debug(knowledge, "patrol_border")
        return self._explore_with_target(knowledge, min_col=self._SEEK_MIN_COL, max_col=self._SEEK_MAX_COL)


# =============================================================================
# RedAgent
# =============================================================================

class RedAgent(RobotAgent):
    """Collects red waste, transports to disposal zone in z3."""

    robot_type = "red"
    allowed_zones = [1, 2, 3]
    target_waste = "red"
    transform_cost = 0
    output_waste = None

    def _can_pickup_and_deliver(self, knowledge, waste_pos):
        """Check if red can pick up waste at waste_pos, deliver to disposal, and return to decon."""
        inv_after = list(knowledge.get("inventory", [])) + ["red"]
        disposal = (GRID_COLS - 1, waste_pos[1])
        # Check from waste_pos (not current pos) - can we do pickup + delivery + return?
        temp_knowledge = dict(knowledge)
        temp_knowledge["pos"] = waste_pos
        feasible, margin = self._can_complete_cycle(
            temp_knowledge,
            [(disposal, ENERGY_COST_DROP)],
            inventories=[inv_after],
        )
        return feasible, margin

    def _nearest_reachable_red(self, knowledge):
        """Find nearest red waste that we could actually pick up and deliver."""
        pos = knowledge["pos"]
        known_waste = knowledge.get("known_waste", {})
        candidates = []
        for p, info in known_waste.items():
            if info.get("type") != "red":
                continue
            if not self._can_move_to(p[0], p[1], self.allowed_zones):
                continue
            # Check if the full cycle is feasible from that position at max energy
            feasible, _ = self._can_pickup_and_deliver(knowledge, p)
            if feasible:
                candidates.append(p)
        if not candidates:
            return None
        return min(candidates, key=lambda p: self._manhattan(pos, p))

    def deliberate(self, knowledge):
        pos = knowledge["pos"]
        inv = knowledge["inventory"]
        percepts = knowledge["percepts"]
        energy = knowledge.get("energy", AGENT_MAX_ENERGY)
        has_red = "red" in inv
        disposal = (GRID_COLS - 1, pos[1])
        has_red_here = pos in percepts and "red" in percepts[pos].get("waste", [])
        on_decon = pos in percepts and percepts[pos].get("decontamination", False)

        # 1. SURVIVE - drop cargo and heal
        in_survival = self._needs_survival_mode(knowledge)
        if in_survival:
            if inv and self.has_energy_for(ACTION_DROP):
                knowledge["dropped_waste"] = {"pos": pos, "types": list(inv)}
                self._set_decision_debug(knowledge, "survive_drop")
                return ACTION_DROP
            self._set_decision_debug(knowledge, "survive_heal")
            return self._decontamination_action(knowledge)

        # 1.5 RECOVER dropped waste after survival
        recover = self._recover_dropped_waste(knowledge)
        if recover is not None:
            return recover

        # 2. DELIVER red to disposal
        if has_red:
            if pos[0] >= GRID_COLS - 1:
                self._set_decision_debug(knowledge, "dispose", target=disposal)
                return ACTION_DROP if self.has_energy_for(ACTION_DROP) else ACTION_IDLE
            self._set_decision_debug(knowledge, "deliver_move", target=disposal)
            return self._navigate_to_target(knowledge, disposal)

        # 3. No TRANSFORM for red

        # 4. PICKUP red here
        if has_red_here and self.can_carry_more() and self.has_energy_for(ACTION_PICK_UP):
            knowledge["dropped_waste"] = None
            self._set_decision_debug(knowledge, "pickup", target=pos)
            return ACTION_PICK_UP

        # 5. SEEK red waste
        nearest_red = self._nearest_known_waste(knowledge, "red")
        if nearest_red:
            self._set_decision_debug(knowledge, "seek", target=nearest_red)
            return self._navigate_to_target(knowledge, nearest_red)

        msg_target = self._check_messages_for_target(knowledge)
        if msg_target and self._can_move_to(msg_target[0], msg_target[1], self.allowed_zones):
            self._set_decision_debug(knowledge, "seek_msg", target=msg_target)
            return self._navigate_to_target(knowledge, msg_target)

        # 6. IDLE on decon when nothing to do
        if on_decon and energy < AGENT_MAX_ENERGY:
            self._set_decision_debug(knowledge, "idle_recharge")
            return ACTION_IDLE

        # 7. ASSIST GREEN - no red waste to process, go help green find waste
        if not self._has_known_waste_type(knowledge, "red"):
            self._set_decision_debug(knowledge, "assist_green")
            return self._assist_green(knowledge)

        # 8. EXPLORE z2-z3 (red waste exists but not reachable yet)
        patrol_col = ZONE_2_END - 2
        self._set_decision_debug(knowledge, "explore")
        return self._explore_with_target(knowledge, min_col=patrol_col - 3, max_col=GRID_COLS - 1)


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
