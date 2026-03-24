# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
GAME CONFIGURATION
==================
Every tunable parameter lives here. Change these values to customize
the simulation without touching any other code.

Sections:
  1. Display        - window size, frame rate, title
  2. Grid & Zones   - grid dimensions, zone layout
  3. Difficulty      - spawning, thresholds, ramp-up
  4. Agents          - robot counts, carrying capacity, speed
  5. Waste Rules     - transformation costs
  6. Visuals         - colors, fonts, animation
  7. Charts          - analytics display settings
"""


# =============================================================================
# 1. DISPLAY
# =============================================================================

WINDOW_WIDTH = 1360             # window width in pixels
WINDOW_HEIGHT = 720             # window height in pixels
FPS = 60                        # target frames per second
GAME_TITLE = "Radioactive Waste Mission"


# =============================================================================
# 2. GRID & ZONES
# =============================================================================

GRID_COLS = 30                  # number of columns in the grid
GRID_ROWS = 18                  # number of rows in the grid
CELL_SIZE = 32                  # pixel size of each cell

# Zone boundaries (column index, west to east)
#   Zone 1: columns [0, ZONE_1_END)        -> low radiation
#   Zone 2: columns [ZONE_1_END, ZONE_2_END) -> medium radiation
#   Zone 3: columns [ZONE_2_END, GRID_COLS)  -> high radiation
ZONE_1_END = 10                 # first column of zone 2
ZONE_2_END = 20                 # first column of zone 3

# Radioactivity level ranges per zone (used for visual intensity)
ZONE_1_RAD_RANGE = (0.0, 0.33)
ZONE_2_RAD_RANGE = (0.33, 0.66)
ZONE_3_RAD_RANGE = (0.66, 1.0)

# Disposal zone location (-1 = last column)
DISPOSAL_ZONE_COL = -1


# =============================================================================
# 3. DIFFICULTY
# =============================================================================

# Starting conditions
INITIAL_GREEN_WASTE = 20        # green waste lumps at start (placed in zone 1)

# Spawning
RADIATION_SPAWN_INTERVAL = 90   # ticks between new green waste spawns
RADIATION_SPAWN_COUNT = 2       # green wastes per spawn event
RADIATION_SPAWN_RAMP = 0.05     # extra waste added to spawn count each event
                                #   (e.g. after 50 events: 2 + 50*0.02 = 3 per spawn)
RADIATION_SPAWN_ENABLED = False  # False = finite mission, waste only at start

# Game over
MAX_RADIATION_THRESHOLD = 80    # if total waste on the grid reaches this -> MELTDOWN


# =============================================================================
# 4. AGENTS
# =============================================================================

# How many of each robot type to create
NUM_GREEN_ROBOTS = 1            # operate in zone 1 only
NUM_YELLOW_ROBOTS = 1           # operate in zones 1-2
NUM_RED_ROBOTS = 1              # operate in zones 1-2-3

# Agent capabilities
AGENT_MAX_CARRY = 10            # max waste items a single robot can hold
AGENT_TICK_RATE = 12            # game frames between each agent decision
                                #   lower = faster agents, higher = slower agents


# =============================================================================
# 5. WASTE RULES
# =============================================================================

GREEN_TO_YELLOW_COST = 2        # green robot: 2 green waste -> 1 yellow waste
YELLOW_TO_RED_COST = 2          # yellow robot: 2 yellow waste -> 1 red waste
                                # red robot: carries 1 red waste to disposal (no transform)


# =============================================================================
# 6. VISUALS
# =============================================================================

# Zone tile colors (light/dark for checkerboard pattern)
ZONE_1_COLOR_LIGHT = (144, 196, 140)   # grassy green
ZONE_1_COLOR_DARK  = (128, 180, 124)
ZONE_2_COLOR_LIGHT = (196, 180, 130)   # sandy brown
ZONE_2_COLOR_DARK  = (180, 164, 114)
ZONE_3_COLOR_LIGHT = (180, 130, 130)   # volcanic red
ZONE_3_COLOR_DARK  = (164, 114, 114)

# Waste colors
COLOR_GREEN_WASTE  = (80, 200, 80)
COLOR_YELLOW_WASTE = (220, 200, 40)
COLOR_RED_WASTE    = (220, 60, 60)

# Robot colors
COLOR_GREEN_ROBOT  = (40, 180, 40)
COLOR_YELLOW_ROBOT = (200, 180, 30)
COLOR_RED_ROBOT    = (200, 40, 40)

# Disposal zone color
COLOR_DISPOSAL     = (60, 60, 80)

# UI colors
BG_COLOR      = (24, 24, 32)           # background behind the grid
HUD_BG_COLOR  = (32, 32, 48)           # top bar background
TEXT_COLOR    = (220, 220, 220)         # default text color

# Font sizes
FONT_SIZE = 14
FONT_SIZE_LARGE = 22

# HUD layout
HUD_HEIGHT = 80                 # top bar height in pixels
SIDEBAR_WIDTH = 300             # right panel width in pixels

# Animation
ANIMATION_ENABLED = True        # set False to disable sprite animations
SPRITE_ANIM_SPEED = 8          # frames between animation ticks (lower = faster)
PARTICLE_ENABLED = True         # set False to disable particle effects


# =============================================================================
# 7. CHARTS
# =============================================================================

CHART_UPDATE_INTERVAL = 30      # frames between chart data refreshes
CHART_HISTORY_LENGTH = 300      # max data points shown on charts


# =============================================================================
# 9. ENERGY SYSTEM
# =============================================================================

ENERGY_ENABLED = True                   # toggle energy system on/off
AGENT_MAX_ENERGY = 100                  # starting and maximum energy
ENERGY_COST_MOVE = 1                    # energy cost to move one cell
ENERGY_COST_PICKUP = 1                  # energy cost to pick up waste
ENERGY_COST_TRANSFORM = 3              # energy cost to transform waste
ENERGY_COST_DROP = 1                    # energy cost to drop waste
ENERGY_RECHARGE_IDLE = 3               # energy regained per idle tick

# Additional health (life) pressure while transporting radioactive waste
HEALTH_LOSS_CARRY_GREEN = 1             # per tick while carrying green waste
HEALTH_LOSS_CARRY_YELLOW = 1.25         # per tick while carrying yellow waste
HEALTH_LOSS_CARRY_RED = 2.6             # per tick while carrying red waste

# Decontamination zones (life recovery)
DECONTAMINATION_ENABLED = True
DECONTAMINATION_ZONES_FIXED = True      # one zone centered in each world zone
HEALTH_RECOVERY_DECONTAMINATION = 8     # life recovered per tick in decon zone
HEALTH_LOW_THRESHOLD = 35               # below this, agents prioritize decontamination
HEALTH_RESUME_THRESHOLD = 90            # leave survival mode only above this level


# =============================================================================
# 10. DIFFICULTY RAMPING
# =============================================================================

DIFFICULTY_BONUS_INTERVAL = 200         # every N ticks, spawn count gets bonus
DIFFICULTY_BONUS_AMOUNT = 1             # bonus amount added per interval
Z2_SPAWN_AFTER_TICK = 500              # after this tick, yellow waste spawns in z2


# =============================================================================
# 11. DECISION SYSTEM
# =============================================================================

DECISION_INTENTION_HOLD_TICKS = 3       # keep chosen intention for at least N ticks
DECISION_SWITCH_MARGIN = 2.0            # switch only if new score is better by this margin
KNOWLEDGE_WASTE_TTL = 35                # ticks before forgetting unseen waste location
STUCK_REPLAN_TICKS = 4                  # force replanning when no progress
INTENTION_SWITCH_COOLDOWN_TICKS = 3     # minimum ticks before switching intention again
RECENT_POS_WINDOW = 6                   # recent positions tracked to penalize back-and-forth
RECENT_POS_PENALTY = 2.5                # penalty weight for recently visited cells
FRONTIER_INFO_GAIN_WEIGHT = 2.0         # weight of information gain in exploration score
TARGET_ENERGY_RISK_WEIGHT = 0.5         # weight of energy-risk penalty in target scoring

# Role-specific utility tuning (Step 1 behavior tuning)
YELLOW_SEEK_BASE_SCORE = 88.0           # make yellow actively chase known yellow waste
YELLOW_MESSAGE_SEEK_BASE_SCORE = 92.0   # stronger than generic seek when a target is known via message
GREEN_PICKUP_RISK_MARGIN = 16           # if energy close to low threshold + margin, penalize green pickup
GREEN_PICKUP_RISK_PENALTY = 24.0        # reduces risky pickup-lock near survival threshold


# =============================================================================
# 12. SOUND
# =============================================================================

SOUND_ENABLED = True                    # toggle sound on/off
SOUND_VOLUME = 0.3                      # master volume (0.0 - 1.0)


# =============================================================================
# 13. COMMUNICATION
# =============================================================================

COMMUNICATION_ENABLED = True            # Step 2: lightweight AUML-style communication enabled


# =============================================================================
# 13.b KNOWLEDGE MODEL
# =============================================================================

GLOBAL_KNOWLEDGE = False                # True: agents perceive whole map; False: local perception + memory


# =============================================================================
# 14. DEBUG LOGGING
# =============================================================================

DEBUG_STEP_LOG_ENABLED = True           # print robot states in terminal each simulation tick
DEBUG_STEP_LOG_EVERY = 1                # print every N ticks
DEBUG_HEATMAPS_ENABLED = True           # show live robot visit heatmaps in sidebar
DEBUG_STEP_LOG_COMPACT = True           # compact one-line per robot with reason/target/next
