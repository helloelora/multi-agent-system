# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
Non-behavioral objects: Waste, Radioactivity, WasteDisposalZone.
"""

import random
from src.config import ZONE_1_RAD_RANGE, ZONE_2_RAD_RANGE, ZONE_3_RAD_RANGE


class Waste:
    """A waste item on the grid."""

    def __init__(self, x, y, waste_type="green", created_at=0):
        self.x = x
        self.y = y
        self.waste_type = waste_type  # "green", "yellow", "red"
        self.collected = False
        self.created_at = created_at  # tick when this waste was placed on the grid

    @property
    def pos(self):
        return (self.x, self.y)

    def __repr__(self):
        return f"Waste({self.waste_type} @ {self.x},{self.y})"


class Radioactivity:
    """Background radiation level for a grid cell."""

    def __init__(self, x, y, zone):
        self.x = x
        self.y = y
        self.zone = zone  # 1, 2, or 3

        if zone == 1:
            self.level = random.uniform(*ZONE_1_RAD_RANGE)
        elif zone == 2:
            self.level = random.uniform(*ZONE_2_RAD_RANGE)
        else:
            self.level = random.uniform(*ZONE_3_RAD_RANGE)

    @property
    def pos(self):
        return (self.x, self.y)


class WasteDisposalZone:
    """Marks a cell as the waste disposal destination."""

    def __init__(self, x, y):
        self.x = x
        self.y = y

    @property
    def pos(self):
        return (self.x, self.y)


class DecontaminationZone:
    """Marks a cell as a decontamination area where robots recover life."""

    def __init__(self, x, y):
        self.x = x
        self.y = y

    @property
    def pos(self):
        return (self.x, self.y)
