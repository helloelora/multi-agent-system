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
INITIAL_GREEN_WASTE = 15        # green waste lumps at start (placed in zone 1)

# Spawning
RADIATION_SPAWN_INTERVAL = 90   # ticks between new green waste spawns
RADIATION_SPAWN_COUNT = 2       # green wastes per spawn event
RADIATION_SPAWN_RAMP = 0.02     # extra waste added to spawn count each event
                                #   (e.g. after 50 events: 2 + 50*0.02 = 3 per spawn)

# Game over
MAX_RADIATION_THRESHOLD = 80    # if total waste on the grid reaches this -> MELTDOWN


# =============================================================================
# 4. AGENTS
# =============================================================================

# How many of each robot type to create
NUM_GREEN_ROBOTS = 4            # operate in zone 1 only
NUM_YELLOW_ROBOTS = 3           # operate in zones 1-2
NUM_RED_ROBOTS = 2              # operate in zones 1-2-3

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
