# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
RobotMission model: manages the grid, agents, waste, and game logic.
Includes waste mutation, energy tracking, difficulty ramping, and communication.
"""

import random
import src.config as _cfg
from src.config import (
    GRID_COLS, GRID_ROWS, ZONE_1_END, ZONE_2_END,
    RADIATION_SPAWN_COUNT, RADIATION_SPAWN_RAMP,
    GREEN_TO_YELLOW_COST, YELLOW_TO_RED_COST,
    WASTE_MUTATION_ENABLED, WASTE_MUTATION_GREEN_TICKS, WASTE_MUTATION_YELLOW_TICKS,
    ENERGY_ENABLED, AGENT_MAX_ENERGY,
    DIFFICULTY_BONUS_INTERVAL, DIFFICULTY_BONUS_AMOUNT, Z2_SPAWN_AFTER_TICK,
    COMMUNICATION_ENABLED,
)
from src.objects import Waste, Radioactivity, WasteDisposalZone
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
        self.score = 0
        self.waste_disposed = 0
        self.spawn_accumulator = 0.0
        self.events = []  # list of (event_type, pos, data) for visual effects

        # Human player mode
        self.human_mode = human_mode
        self.human_color = human_color
        self.human_robot = None  # set during _setup if human_mode

        # Communication: message board for inter-agent messaging
        self.message_board = []   # messages posted this tick, delivered next tick
        self._pending_messages = []  # buffer for next tick delivery
        self.total_messages_sent = 0

        # Grid data: each cell can hold multiple objects
        self.radioactivity = {}   # (x,y) -> Radioactivity
        self.waste_map = {}       # (x,y) -> list[Waste]
        self.disposal_zones = set()

        self.robots = []

        # Analytics history
        self.history = {
            "tick": [],
            "total_waste": [],
            "green_waste": [],
            "yellow_waste": [],
            "red_waste": [],
            "waste_disposed": [],
            "avg_energy": [],
            "messages_sent": [],
        }

        self._setup()

    def _setup(self):
        # Place radioactivity on every cell
        for x in range(GRID_COLS):
            for y in range(GRID_ROWS):
                zone = self._get_zone(x)
                self.radioactivity[(x, y)] = Radioactivity(x, y, zone)

        # Place disposal zone on the last column
        disposal_y = random.randint(0, GRID_ROWS - 1)
        self.disposal_zones.add((GRID_COLS - 1, disposal_y))
        # Mark a few cells in the last column as disposal
        for y in range(GRID_ROWS):
            self.disposal_zones.add((GRID_COLS - 1, y))

        # Spawn initial green waste in z1
        for _ in range(_cfg.INITIAL_GREEN_WASTE):
            x = random.randint(0, ZONE_1_END - 1)
            y = random.randint(0, GRID_ROWS - 1)
            w = Waste(x, y, "green", created_at=0)
            self.waste_map.setdefault((x, y), []).append(w)

        # Create robots
        agent_id = 0

        # Robot type configs: (config_count, ai_class, color_name, spawn_x_range)
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
                # Create 1 human-controlled robot of this color
                human_cls = HUMAN_AGENT_CLASSES[color_name]
                x = random.randint(x_lo, x_hi)
                y = random.randint(0, GRID_ROWS - 1)
                human_robot = human_cls(agent_id, x, y)
                self.robots.append(human_robot)
                self.human_robot = human_robot
                agent_id += 1
            else:
                # Create normal AI robots
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

    # -- Communication ---------------------------------------------------------

    def _deliver_messages(self):
        """Deliver pending messages to agent mailboxes."""
        if not COMMUNICATION_ENABLED:
            return
        # Deliver messages from previous tick
        for msg in self._pending_messages:
            for robot in self.robots:
                if robot.agent_id != msg["from"]:
                    robot.mailbox.append(msg)
        self._pending_messages.clear()
        # Move current tick messages to pending for next tick delivery
        self._pending_messages = list(self.message_board)
        self.total_messages_sent += len(self.message_board)
        self.message_board.clear()

    # -- Waste Mutation --------------------------------------------------------

    def _mutate_waste(self):
        """Mutate waste that has been sitting on the grid too long."""
        if not WASTE_MUTATION_ENABLED:
            return
        mutations = []
        for pos, wastes in list(self.waste_map.items()):
            for w in wastes:
                age = self.tick - w.created_at
                if w.waste_type == "green" and age >= WASTE_MUTATION_GREEN_TICKS:
                    mutations.append((pos, w, "yellow"))
                elif w.waste_type == "yellow" and age >= WASTE_MUTATION_YELLOW_TICKS:
                    mutations.append((pos, w, "red"))

        for pos, w, new_type in mutations:
            w.waste_type = new_type
            w.created_at = self.tick  # reset timer for further mutation
            self.events.append(("mutate", pos, new_type))

    # -- Percepts --------------------------------------------------------------

    def get_percepts(self, agent):
        """Return what the agent can see: contents of current and adjacent cells."""
        percepts = {}
        ax, ay = agent.x, agent.y
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                nx, ny = ax + dx, ay + dy
                if 0 <= nx < GRID_COLS and 0 <= ny < GRID_ROWS:
                    cell = {}
                    # Radioactivity
                    rad = self.radioactivity.get((nx, ny))
                    if rad:
                        cell["radioactivity"] = rad.level
                        cell["zone"] = rad.zone

                    # Waste
                    wastes = self.waste_map.get((nx, ny), [])
                    if wastes:
                        cell["waste"] = [w.waste_type for w in wastes]

                    # Disposal
                    if (nx, ny) in self.disposal_zones:
                        cell["disposal"] = True

                    # Other robots
                    others = [r for r in self.robots
                              if r.pos == (nx, ny) and r is not agent]
                    if others:
                        cell["robots"] = [(r.robot_type, r.agent_id) for r in others]

                    percepts[(nx, ny)] = cell
        return percepts

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
            # Check bounds
            if 0 <= nx < GRID_COLS and 0 <= ny < GRID_ROWS:
                # Check zone access
                zone = self._get_zone(nx)
                if zone in agent.allowed_zones:
                    agent.x = nx
                    agent.y = ny
                    if dx > 0:
                        agent.knowledge["facing"] = "right"
                    elif dx < 0:
                        agent.knowledge["facing"] = "left"

        elif action == ACTION_PICK_UP:
            pos = agent.pos
            wastes = self.waste_map.get(pos, [])
            if wastes and agent.can_carry_more():
                # Pick up the first waste of the agent's target type
                for w in wastes:
                    if w.waste_type == agent.target_waste:
                        agent.inventory.append(w.waste_type)
                        self.events.append(("pickup", pos, w.waste_type))
                        wastes.remove(w)
                        if not wastes:
                            del self.waste_map[pos]
                        break

        elif action == ACTION_TRANSFORM:
            if agent.robot_type == "green":
                count = agent.inventory.count("green")
                if count >= GREEN_TO_YELLOW_COST:
                    for _ in range(GREEN_TO_YELLOW_COST):
                        agent.inventory.remove("green")
                    agent.inventory.append("yellow")
                    self.events.append(("transform", agent.pos, "yellow"))
            elif agent.robot_type == "yellow":
                count = agent.inventory.count("yellow")
                if count >= YELLOW_TO_RED_COST:
                    for _ in range(YELLOW_TO_RED_COST):
                        agent.inventory.remove("yellow")
                    agent.inventory.append("red")
                    self.events.append(("transform", agent.pos, "red"))

        elif action == ACTION_DROP:
            pos = agent.pos
            if agent.robot_type == "red" and pos in self.disposal_zones:
                # Dispose of red waste
                while "red" in agent.inventory:
                    agent.inventory.remove("red")
                    self.waste_disposed += 1
                    self.score += 100
                self.events.append(("dispose", pos, "red"))
            else:
                # Drop transformed waste on the ground for next robot type
                to_drop = []
                if agent.robot_type == "green":
                    to_drop = [w for w in agent.inventory if w == "yellow"]
                elif agent.robot_type == "yellow":
                    to_drop = [w for w in agent.inventory if w == "red"]

                for wtype in to_drop:
                    agent.inventory.remove(wtype)
                    waste = Waste(pos[0], pos[1], wtype, created_at=self.tick)
                    self.waste_map.setdefault(pos, []).append(waste)

        return self.get_percepts(agent)

    # -- Step ------------------------------------------------------------------

    def step(self):
        """Advance the simulation by one tick."""
        if self.game_over:
            return
        self.events = []

        self.tick += 1

        # Deliver messages from previous tick
        self._deliver_messages()

        # Waste mutation
        self._mutate_waste()

        # Spawn new green waste periodically
        if self.tick % _cfg.RADIATION_SPAWN_INTERVAL == 0:
            self.spawn_accumulator += RADIATION_SPAWN_RAMP
            count = int(RADIATION_SPAWN_COUNT + self.spawn_accumulator)

            # Difficulty bonus: every DIFFICULTY_BONUS_INTERVAL ticks, add bonus
            bonus = (self.tick // DIFFICULTY_BONUS_INTERVAL) * DIFFICULTY_BONUS_AMOUNT
            count += bonus

            for _ in range(count):
                x = random.randint(0, ZONE_1_END - 1)
                y = random.randint(0, GRID_ROWS - 1)
                w = Waste(x, y, "green", created_at=self.tick)
                self.waste_map.setdefault((x, y), []).append(w)

        # After Z2_SPAWN_AFTER_TICK, also spawn yellow waste in z2
        if self.tick >= Z2_SPAWN_AFTER_TICK:
            if self.tick % _cfg.RADIATION_SPAWN_INTERVAL == 0:
                z2_count = max(1, int(RADIATION_SPAWN_COUNT * 0.5))
                for _ in range(z2_count):
                    x = random.randint(ZONE_1_END, ZONE_2_END - 1)
                    y = random.randint(0, GRID_ROWS - 1)
                    w = Waste(x, y, "yellow", created_at=self.tick)
                    self.waste_map.setdefault((x, y), []).append(w)

        # All agents act simultaneously
        random.shuffle(self.robots)
        for robot in self.robots:
            robot.step_agent(self)

        # Check game over
        total = sum(len(wl) for wl in self.waste_map.values())
        if total >= _cfg.MAX_RADIATION_THRESHOLD:
            self.game_over = True

        # Record analytics
        green_count = sum(1 for wl in self.waste_map.values()
                          for w in wl if w.waste_type == "green")
        yellow_count = sum(1 for wl in self.waste_map.values()
                           for w in wl if w.waste_type == "yellow")
        red_count = sum(1 for wl in self.waste_map.values()
                        for w in wl if w.waste_type == "red")

        # Average energy across all robots
        if ENERGY_ENABLED and self.robots:
            avg_energy = sum(r.energy for r in self.robots) / len(self.robots)
        else:
            avg_energy = AGENT_MAX_ENERGY

        self.history["tick"].append(self.tick)
        self.history["total_waste"].append(total)
        self.history["green_waste"].append(green_count)
        self.history["yellow_waste"].append(yellow_count)
        self.history["red_waste"].append(red_count)
        self.history["waste_disposed"].append(self.waste_disposed)
        self.history["avg_energy"].append(avg_energy)
        self.history["messages_sent"].append(self.total_messages_sent)

        self.score += 1  # survival bonus

    def total_waste(self):
        return sum(len(wl) for wl in self.waste_map.values())
