# =============================================================================
# Group 19
# Date: 2026-03-14
# Members: Ali Dor, Elora Drouilhet
# =============================================================================

"""RobotMission model: grid, agents, waste, game logic."""

import random
import src.config as _cfg
from src.config import (
    GRID_COLS, GRID_ROWS, ZONE_1_END, ZONE_2_END,
    RADIATION_SPAWN_COUNT, RADIATION_SPAWN_RAMP,
    GREEN_TO_YELLOW_COST, YELLOW_TO_RED_COST,
    ENERGY_ENABLED, AGENT_MAX_ENERGY,
    DIFFICULTY_BONUS_INTERVAL, DIFFICULTY_BONUS_AMOUNT, Z2_SPAWN_AFTER_TICK,
    COMMUNICATION_ENABLED,
    DECONTAMINATION_ENABLED,
    HEALTH_RECOVERY_DECONTAMINATION,
    HEALTH_LOSS_CARRY_GREEN, HEALTH_LOSS_CARRY_YELLOW, HEALTH_LOSS_CARRY_RED,
)
from src.objects import Waste, Radioactivity, WasteDisposalZone, DecontaminationZone
from src.agents import (
    GreenAgent, YellowAgent, RedAgent,
    ACTION_MOVE_UP, ACTION_MOVE_DOWN, ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT,
    ACTION_PICK_UP, ACTION_TRANSFORM, ACTION_DROP, ACTION_IDLE,
    HUMAN_AGENT_CLASSES,
)


class RobotMission:
    """The world model."""

    def __init__(self, human_mode=False, human_color=None):
        self.tick = 0
        self.game_over = False
        self.mission_success = False
        self.score = 0
        self.waste_disposed = 0
        self.spawn_accumulator = 0.0
        self.events = []  # list of (event_type, pos, data) for visual effects

        # Human player mode
        self.human_mode = human_mode
        self.human_color = human_color
        self.human_robot = None  # set during _setup if human_mode

        # Messages posted this tick are delivered next tick
        self.message_board = []
        self._pending_messages = []
        self.total_messages_sent = 0

        self.radioactivity = {}   # (x,y) -> Radioactivity
        self.waste_map = {}       # (x,y) -> list[Waste]
        self.disposal_zones = set()
        self.decontamination_zones = set()

        self.robots = []

        self.pipeline_stats = {
            "green": {"pickups": 0, "transforms": 0, "deliveries": 0},
            "yellow": {"pickups": 0, "transforms": 0, "deliveries": 0},
            "red": {"pickups": 0, "transforms": 0, "disposals": 0},
        }

        # Last 50 messages for sidebar display
        self.message_log = []
        self._message_log_max = 50

        # Waste.uid values already counted in pickup stats.
        # Prevents drop -> re-pickup from double-counting the same physical block.
        self.counted_waste_uids = set()

        self.history = {
            "tick": [],
            "total_waste": [],
            "green_waste": [],
            "yellow_waste": [],
            "red_waste": [],
            "waste_disposed": [],
            "avg_energy": [],
            "messages_sent": [],
            "avg_energy_green": [],
            "avg_energy_yellow": [],
            "avg_energy_red": [],
        }

        self._setup()

    def _setup(self):
        for x in range(GRID_COLS):
            for y in range(GRID_ROWS):
                zone = self._get_zone(x)
                self.radioactivity[(x, y)] = Radioactivity(x, y, zone)

        disposal_y = random.randint(0, GRID_ROWS - 1)
        self.disposal_zones.add((GRID_COLS - 1, disposal_y))
        for y in range(GRID_ROWS):
            self.disposal_zones.add((GRID_COLS - 1, y))

        if DECONTAMINATION_ENABLED:
            mid_row = GRID_ROWS // 2
            zone_centers = [
                ((0 + (ZONE_1_END - 1)) // 2, mid_row),
                ((ZONE_1_END + (ZONE_2_END - 1)) // 2, mid_row),
                ((ZONE_2_END + (GRID_COLS - 1)) // 2, mid_row),
            ]
            self.decontamination_zones.update(zone_centers)

        for _ in range(_cfg.INITIAL_GREEN_WASTE):
            sampled = self._sample_non_decontam_pos(0, ZONE_1_END - 1)
            if sampled is None:
                continue
            x, y = sampled
            w = Waste(x, y, "green", created_at=0)
            self.waste_map.setdefault((x, y), []).append(w)

        agent_id = 0

        # (count, ai_class, color_name, spawn_x_range)
        robot_configs = [
            (_cfg.NUM_GREEN_ROBOTS, GreenAgent, "green",
             (0, ZONE_1_END - 1)),
            (_cfg.NUM_YELLOW_ROBOTS, YellowAgent, "yellow",
             (ZONE_1_END, ZONE_2_END - 1)),
            (_cfg.NUM_RED_ROBOTS, RedAgent, "red",
             (ZONE_2_END, GRID_COLS - 1)),
        ]

        for count, ai_cls, color_name, (x_lo, x_hi) in robot_configs:
            if self.human_mode and self.human_color == color_name:
                human_cls = HUMAN_AGENT_CLASSES[color_name]
                x = random.randint(x_lo, x_hi)
                y = random.randint(0, GRID_ROWS - 1)
                human_robot = human_cls(agent_id, x, y)
                self.robots.append(human_robot)
                self.human_robot = human_robot
                agent_id += 1
            else:
                for _ in range(count):
                    x = random.randint(x_lo, x_hi)
                    y = random.randint(0, GRID_ROWS - 1)
                    self.robots.append(ai_cls(agent_id, x, y))
                    agent_id += 1

    @staticmethod
    def _get_zone(col):
        if col < ZONE_1_END:
            return 1
        elif col < ZONE_2_END:
            return 2
        return 3

    def _sample_non_decontam_pos(self, x_min, x_max):
        """Sample a position in [x_min, x_max] x [0, GRID_ROWS-1] that is not decontamination."""
        candidates = [
            (x, y)
            for x in range(x_min, x_max + 1)
            for y in range(GRID_ROWS)
            if (x, y) not in self.decontamination_zones
        ]
        if not candidates:
            return None
        return random.choice(candidates)

    def _nearest_drop_pos_off_decontam(self, origin, allowed_zones=None):
        """Return a valid drop position nearest to origin that is not decontamination."""
        ox, oy = origin
        candidates = [origin, (ox - 1, oy), (ox + 1, oy), (ox, oy - 1), (ox, oy + 1)]
        for px, py in candidates:
            if not (0 <= px < GRID_COLS and 0 <= py < GRID_ROWS):
                continue
            if (px, py) in self.decontamination_zones:
                continue
            if allowed_zones is not None and self._get_zone(px) not in allowed_zones:
                continue
            return (px, py)
        return None

    # -- Communication ---------------------------------------------------------

    def _deliver_messages(self):
        """Deliver pending messages to agent mailboxes."""
        if not COMMUNICATION_ENABLED:
            return
        for msg in self._pending_messages:
            for robot in self.robots:
                if robot.agent_id != msg["from"]:
                    robot.mailbox.append(msg)
        self._pending_messages.clear()
        self._pending_messages = list(self.message_board)
        self.total_messages_sent += len(self.message_board)

        for msg in self.message_board:
            entry = {
                "tick": self.tick,
                "from": msg.get("from"),
                "from_type": msg.get("from_type", "?"),
                "type": msg.get("type", "?"),
                "content": msg.get("content", {}),
            }
            self.message_log.append(entry)
        if len(self.message_log) > self._message_log_max:
            self.message_log = self.message_log[-self._message_log_max:]

        self.message_board.clear()

    # -- Percepts --------------------------------------------------------------

    def get_percepts(self, agent):
        """Return what the agent can see in current + adjacent cells."""
        percepts = {}
        ax, ay = agent.x, agent.y
        if _cfg.GLOBAL_KNOWLEDGE:
            xs = range(GRID_COLS)
            ys = range(GRID_ROWS)
        else:
            xs = range(max(0, ax - 1), min(GRID_COLS, ax + 2))
            ys = range(max(0, ay - 1), min(GRID_ROWS, ay + 2))

        for nx in xs:
            for ny in ys:
                cell = {}
                rad = self.radioactivity.get((nx, ny))
                if rad:
                    cell["radioactivity"] = rad.level
                    cell["zone"] = rad.zone

                wastes = self.waste_map.get((nx, ny), [])
                if wastes:
                    cell["waste"] = [w.waste_type for w in wastes]

                if (nx, ny) in self.disposal_zones:
                    cell["disposal"] = True

                if (nx, ny) in self.decontamination_zones:
                    cell["decontamination"] = True

                others = [r for r in self.robots if r.pos == (nx, ny) and r is not agent]
                if others:
                    cell["robots"] = [(r.robot_type, r.agent_id) for r in others]

                percepts[(nx, ny)] = cell
        return percepts

    def get_waste_counts(self):
        """Return on-map waste counts by type."""
        counts = {"green": 0, "yellow": 0, "red": 0}
        for wastes in self.waste_map.values():
            for waste in wastes:
                if waste.waste_type in counts:
                    counts[waste.waste_type] += 1
        counts["total"] = counts["green"] + counts["yellow"] + counts["red"]
        return counts

    def get_waste_positions(self):
        """Return on-map waste positions by type."""
        positions = {"green": [], "yellow": [], "red": []}
        seen = {"green": set(), "yellow": set(), "red": set()}
        for pos, wastes in self.waste_map.items():
            for waste in wastes:
                waste_type = waste.waste_type
                if waste_type in positions and pos not in seen[waste_type]:
                    seen[waste_type].add(pos)
                    positions[waste_type].append(pos)
        positions["total"] = (
            len(positions["green"]) + len(positions["yellow"]) + len(positions["red"])
        )
        return positions

    # -- Action execution ------------------------------------------------------

    def do(self, agent, action):
        """Execute an action for the given agent. Returns new percepts."""
        if action == ACTION_IDLE:
            pass

        elif action in (ACTION_MOVE_UP, ACTION_MOVE_DOWN,
                        ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT):
            dx, dy = {
                ACTION_MOVE_UP: (0, -1),
                ACTION_MOVE_DOWN: (0, 1),
                ACTION_MOVE_LEFT: (-1, 0),
                ACTION_MOVE_RIGHT: (1, 0),
            }[action]
            nx, ny = agent.x + dx, agent.y + dy
            if 0 <= nx < GRID_COLS and 0 <= ny < GRID_ROWS:
                zone = self._get_zone(nx)
                entering_decontam_while_loaded = (
                    (nx, ny) in self.decontamination_zones and bool(agent.inventory)
                )
                if zone in agent.allowed_zones and not entering_decontam_while_loaded:
                    agent.x = nx
                    agent.y = ny
                    if dx > 0:
                        agent.knowledge["facing"] = "right"
                    elif dx < 0:
                        agent.knowledge["facing"] = "left"

        elif action == ACTION_PICK_UP:
            pos = agent.pos
            wastes = self.waste_map.get(pos, [])
            if pos not in self.decontamination_zones and wastes and agent.can_carry_more():
                for w in wastes:
                    if w.waste_type == agent.target_waste:
                        agent.inventory.append(w.waste_type)
                        agent.inventory_uids.append(w.uid)
                        self.events.append(("pickup", pos, w.waste_type))
                        if agent.robot_type in self.pipeline_stats:
                            self.pipeline_stats[agent.robot_type]["pickups"] += 1
                        wastes.remove(w)
                        if not wastes:
                            del self.waste_map[pos]
                        break

        elif action == ACTION_TRANSFORM:
            if agent.robot_type == "green":
                count = agent.inventory.count("green")
                while count >= GREEN_TO_YELLOW_COST:
                    for _ in range(GREEN_TO_YELLOW_COST):
                        idx = agent.inventory.index("green")
                        agent.inventory.pop(idx)
                        agent.inventory_uids.pop(idx)
                    agent.inventory.append("yellow")
                    agent.inventory_uids.append(Waste._new_uid())
                    self.events.append(("transform", agent.pos, "yellow"))
                    self.pipeline_stats["green"]["transforms"] += 1
                    count -= GREEN_TO_YELLOW_COST
            elif agent.robot_type == "yellow":
                count = agent.inventory.count("yellow")
                while count >= YELLOW_TO_RED_COST:
                    for _ in range(YELLOW_TO_RED_COST):
                        idx = agent.inventory.index("yellow")
                        agent.inventory.pop(idx)
                        agent.inventory_uids.pop(idx)
                    agent.inventory.append("red")
                    agent.inventory_uids.append(Waste._new_uid())
                    self.events.append(("transform", agent.pos, "red"))
                    self.pipeline_stats["yellow"]["transforms"] += 1
                    count -= YELLOW_TO_RED_COST

        elif action == ACTION_DROP:
            pos = agent.pos
            if agent.robot_type == "red" and pos in self.disposal_zones:
                disposed_count = agent.inventory.count("red")
                while "red" in agent.inventory:
                    idx = agent.inventory.index("red")
                    agent.inventory.pop(idx)
                    agent.inventory_uids.pop(idx)
                    self.waste_disposed += 1
                    self.score += 100
                self.pipeline_stats["red"]["disposals"] += disposed_count
                self.events.append(("dispose", pos, "red"))
            else:
                # Normal behavior: drop transformed output only.
                # Survival behavior: allow emergency drop of all carried waste.
                drop_all = bool(agent.knowledge.get("survival_mode", False)) or bool(
                    agent.knowledge.get("force_drop_all", False)
                )
                relay_drop_yellow = bool(agent.knowledge.get("yellow_relay_drop", False))
                to_drop = []
                if drop_all:
                    to_drop = list(agent.inventory)
                elif agent.robot_type == "green":
                    to_drop = [w for w in agent.inventory if w == "yellow"]
                elif agent.robot_type == "yellow":
                    if relay_drop_yellow:
                        to_drop = [w for w in agent.inventory if w in ("yellow", "red")]
                    else:
                        to_drop = [w for w in agent.inventory if w == "red"]

                drop_pos = self._nearest_drop_pos_off_decontam(pos, allowed_zones=agent.allowed_zones)
                if drop_pos is None:
                    return self.get_percepts(agent)

                for wtype in to_drop:
                    idx = agent.inventory.index(wtype)
                    agent.inventory.pop(idx)
                    uid = agent.inventory_uids.pop(idx)
                    waste = Waste(drop_pos[0], drop_pos[1], wtype, created_at=self.tick, uid=uid)
                    self.waste_map.setdefault(drop_pos, []).append(waste)
                    if agent.robot_type in self.pipeline_stats:
                        output = getattr(agent, "output_waste", None)
                        if output and wtype == output:
                            self.pipeline_stats[agent.robot_type]["deliveries"] += 1

                if "force_drop_all" in agent.knowledge:
                    agent.knowledge["force_drop_all"] = False
                if "yellow_relay_drop" in agent.knowledge:
                    agent.knowledge["yellow_relay_drop"] = False

        return self.get_percepts(agent)

    # -- Step ------------------------------------------------------------------

    def step(self):
        """Advance the simulation by one tick."""
        if self.game_over:
            return
        self.events = []

        self.tick += 1

        self._deliver_messages()

        if _cfg.RADIATION_SPAWN_ENABLED and self.tick % _cfg.RADIATION_SPAWN_INTERVAL == 0:
            self.spawn_accumulator += RADIATION_SPAWN_RAMP
            count = int(RADIATION_SPAWN_COUNT + self.spawn_accumulator)

            bonus = (self.tick // DIFFICULTY_BONUS_INTERVAL) * DIFFICULTY_BONUS_AMOUNT
            count += bonus

            for _ in range(count):
                sampled = self._sample_non_decontam_pos(0, ZONE_1_END - 1)
                if sampled is None:
                    continue
                x, y = sampled
                w = Waste(x, y, "green", created_at=self.tick)
                self.waste_map.setdefault((x, y), []).append(w)

        # After Z2_SPAWN_AFTER_TICK, also spawn yellow waste in z2
        if _cfg.RADIATION_SPAWN_ENABLED and self.tick >= Z2_SPAWN_AFTER_TICK:
            if self.tick % _cfg.RADIATION_SPAWN_INTERVAL == 0:
                z2_count = max(1, int(RADIATION_SPAWN_COUNT * 0.5))
                for _ in range(z2_count):
                    sampled = self._sample_non_decontam_pos(ZONE_1_END, ZONE_2_END - 1)
                    if sampled is None:
                        continue
                    x, y = sampled
                    w = Waste(x, y, "yellow", created_at=self.tick)
                    self.waste_map.setdefault((x, y), []).append(w)

        random.shuffle(self.robots)
        for robot in self.robots:
            robot.step_agent(self)

        # Life pressure from carrying radioactive waste + decon recovery
        if ENERGY_ENABLED:
            for robot in self.robots:
                if robot.pos in self.decontamination_zones:
                    robot.energy = min(
                        AGENT_MAX_ENERGY,
                        robot.energy + HEALTH_RECOVERY_DECONTAMINATION,
                    )

                carry_loss = 0
                for waste_type in robot.inventory:
                    if waste_type == "green":
                        carry_loss += HEALTH_LOSS_CARRY_GREEN
                    elif waste_type == "yellow":
                        carry_loss += HEALTH_LOSS_CARRY_YELLOW
                    elif waste_type == "red":
                        carry_loss += HEALTH_LOSS_CARRY_RED

                if carry_loss > 0:
                    robot.energy = max(0, robot.energy - carry_loss)
                robot.knowledge["energy"] = robot.energy

        total = sum(len(wl) for wl in self.waste_map.values())
        if total >= _cfg.MAX_RADIATION_THRESHOLD:
            self.mission_success = False
            self.game_over = True

        if ENERGY_ENABLED and any(r.energy <= 0 for r in self.robots):
            self.mission_success = False
            self.game_over = True

        inventories_remaining = sum(len(r.inventory) for r in self.robots)
        if total == 0 and inventories_remaining == 0:
            self.mission_success = True
            self.game_over = True

        green_count = sum(1 for wl in self.waste_map.values()
                          for w in wl if w.waste_type == "green")
        yellow_count = sum(1 for wl in self.waste_map.values()
                           for w in wl if w.waste_type == "yellow")
        red_count = sum(1 for wl in self.waste_map.values()
                        for w in wl if w.waste_type == "red")

        if ENERGY_ENABLED and self.robots:
            avg_energy = sum(r.energy for r in self.robots) / len(self.robots)
        else:
            avg_energy = AGENT_MAX_ENERGY

        def _avg_energy_for(robot_type):
            typed = [r.energy for r in self.robots if r.robot_type == robot_type]
            if not typed:
                return AGENT_MAX_ENERGY
            return sum(typed) / len(typed)

        self.history["tick"].append(self.tick)
        self.history["total_waste"].append(total)
        self.history["green_waste"].append(green_count)
        self.history["yellow_waste"].append(yellow_count)
        self.history["red_waste"].append(red_count)
        self.history["waste_disposed"].append(self.waste_disposed)
        self.history["avg_energy"].append(avg_energy)
        self.history["messages_sent"].append(self.total_messages_sent)
        self.history["avg_energy_green"].append(_avg_energy_for("green"))
        self.history["avg_energy_yellow"].append(_avg_energy_for("yellow"))
        self.history["avg_energy_red"].append(_avg_energy_for("red"))

        self.score += 1  # survival bonus

    def total_waste(self):
        return sum(len(wl) for wl in self.waste_map.values())
