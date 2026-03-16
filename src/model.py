# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
RobotMission model: manages the grid, agents, waste, and game logic.
"""

import random
import src.config as _cfg
from src.config import (
    GRID_COLS, GRID_ROWS, ZONE_1_END, ZONE_2_END,
    RADIATION_SPAWN_COUNT, RADIATION_SPAWN_RAMP,
    GREEN_TO_YELLOW_COST, YELLOW_TO_RED_COST,
)
from src.objects import Waste, Radioactivity, WasteDisposalZone
from src.agents import (
    GreenAgent, YellowAgent, RedAgent,
    ACTION_MOVE_UP, ACTION_MOVE_DOWN, ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT,
    ACTION_PICK_UP, ACTION_TRANSFORM, ACTION_DROP, ACTION_IDLE,
)


class RobotMission:
    """The world model."""

    def __init__(self):
        self.tick = 0
        self.game_over = False
        self.score = 0
        self.waste_disposed = 0
        self.spawn_accumulator = 0.0
        self.events = []  # list of (event_type, pos, data) for visual effects

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
            w = Waste(x, y, "green")
            self.waste_map.setdefault((x, y), []).append(w)

        # Create robots
        agent_id = 0
        for _ in range(_cfg.NUM_GREEN_ROBOTS):
            x = random.randint(0, ZONE_1_END - 1)
            y = random.randint(0, GRID_ROWS - 1)
            self.robots.append(GreenAgent(agent_id, x, y))
            agent_id += 1

        for _ in range(_cfg.NUM_YELLOW_ROBOTS):
            x = random.randint(ZONE_1_END, ZONE_2_END - 1)
            y = random.randint(0, GRID_ROWS - 1)
            self.robots.append(YellowAgent(agent_id, x, y))
            agent_id += 1

        for _ in range(_cfg.NUM_RED_ROBOTS):
            x = random.randint(ZONE_2_END, GRID_COLS - 1)
            y = random.randint(0, GRID_ROWS - 1)
            self.robots.append(RedAgent(agent_id, x, y))
            agent_id += 1

    @staticmethod
    def _get_zone(col):
        if col < ZONE_1_END:
            return 1
        elif col < ZONE_2_END:
            return 2
        return 3

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
                    waste = Waste(pos[0], pos[1], wtype)
                    self.waste_map.setdefault(pos, []).append(waste)

        return self.get_percepts(agent)

    # -- Step ------------------------------------------------------------------

    def step(self):
        """Advance the simulation by one tick."""
        if self.game_over:
            return
        self.events = []

        self.tick += 1

        # Spawn new green waste periodically
        if self.tick % _cfg.RADIATION_SPAWN_INTERVAL == 0:
            self.spawn_accumulator += RADIATION_SPAWN_RAMP
            count = int(RADIATION_SPAWN_COUNT + self.spawn_accumulator)
            for _ in range(count):
                x = random.randint(0, ZONE_1_END - 1)
                y = random.randint(0, GRID_ROWS - 1)
                w = Waste(x, y, "green")
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

        self.history["tick"].append(self.tick)
        self.history["total_waste"].append(total)
        self.history["green_waste"].append(green_count)
        self.history["yellow_waste"].append(yellow_count)
        self.history["red_waste"].append(red_count)
        self.history["waste_disposed"].append(self.waste_disposed)

        self.score += 1  # survival bonus

    def total_waste(self):
        return sum(len(wl) for wl in self.waste_map.values())
