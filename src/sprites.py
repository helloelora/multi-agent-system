# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
Pixel-art sprite system with Mario-inspired aesthetic.
Sprites are drawn at native resolution and saved to assets/.
Multiple robot design styles, lush world tiles, glowing waste.
"""

import pygame
import math
import os
import random as _rand

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

DEFAULT_DESIGN = "mech"


# =============================================================================
# Color Palettes — each robot type has a UNIQUE multi-color scheme
# =============================================================================

ROBOT_PALETTES = {
    "green": {
        # Forest ranger vibe: greens + brown leather + gold accents
        "body":      (55, 160, 85),
        "body_dark": (35, 110, 55),
        "body_lit":  (90, 200, 115),
        "belly":     (210, 190, 140),    # tan/leather belly
        "outline":   (25, 60, 35),
        "eye_white": (255, 255, 255),
        "eye_pupil": (25, 45, 30),
        "eye_shine": (200, 255, 210),
        "mouth":     (25, 60, 35),
        "cheek":     (255, 160, 140, 90),
        "antenna":   (140, 110, 50),     # gold antenna
        "ant_tip":   (255, 220, 80),     # bright gold tip
        "accent":    (180, 140, 60),     # gold trim
        "boots":     (100, 70, 40),      # brown boots
    },
    "yellow": {
        # Electric engineer vibe: amber + deep purple + cyan sparks
        "body":      (230, 180, 40),
        "body_dark": (180, 130, 20),
        "body_lit":  (255, 215, 80),
        "belly":     (200, 180, 220),    # lavender belly
        "outline":   (80, 50, 15),
        "eye_white": (255, 255, 255),
        "eye_pupil": (60, 30, 80),       # purple pupils
        "eye_shine": (180, 240, 255),    # cyan shine
        "mouth":     (80, 50, 15),
        "cheek":     (255, 180, 100, 90),
        "antenna":   (100, 60, 130),     # purple antenna
        "ant_tip":   (80, 220, 255),     # cyan tip
        "accent":    (120, 80, 160),     # purple trim
        "boots":     (90, 55, 120),      # dark purple boots
    },
    "red": {
        # Fire captain vibe: crimson + dark steel + orange flame accents
        "body":      (195, 50, 45),
        "body_dark": (140, 30, 30),
        "body_lit":  (235, 90, 75),
        "belly":     (180, 185, 195),    # steel grey belly
        "outline":   (65, 18, 18),
        "eye_white": (255, 255, 255),
        "eye_pupil": (60, 15, 10),
        "eye_shine": (255, 200, 150),    # warm shine
        "mouth":     (65, 18, 18),
        "cheek":     (255, 140, 80, 90),
        "antenna":   (200, 120, 30),     # orange antenna
        "ant_tip":   (255, 180, 40),     # flame tip
        "accent":    (255, 150, 40),     # orange trim
        "boots":     (60, 60, 70),       # dark steel boots
    },
}

WASTE_PALETTES = {
    "green": {
        "core":  (60, 200, 70),
        "dark":  (35, 130, 45),
        "light": (130, 240, 140),
        "glow":  (80, 255, 100),
    },
    "yellow": {
        "core":  (230, 200, 40),
        "dark":  (170, 140, 20),
        "light": (255, 235, 100),
        "glow":  (255, 240, 80),
    },
    "red": {
        "core":  (220, 55, 50),
        "dark":  (150, 30, 30),
        "light": (250, 110, 100),
        "glow":  (255, 80, 70),
    },
}

WORLD_COLORS = {
    "z1_grass_top":    (100, 200, 80),
    "z1_grass_mid":    (80, 170, 65),
    "z1_dirt":         (180, 120, 60),
    "z1_dirt_dark":    (150, 95, 45),
    "z1_flower1":      (255, 100, 100),
    "z1_flower2":      (255, 200, 80),
    "z2_sand_top":     (220, 190, 130),
    "z2_sand_mid":     (195, 165, 105),
    "z2_rock":         (160, 135, 90),
    "z2_rock_dark":    (130, 105, 70),
    "z2_crack":        (110, 85, 55),
    "z3_stone_top":    (100, 80, 90),
    "z3_stone_mid":    (75, 60, 70),
    "z3_lava_glow":    (255, 100, 30),
    "z3_lava":         (200, 60, 20),
    "z3_lava_dark":    (140, 35, 15),
}


# =============================================================================
# Drawing Helpers
# =============================================================================

def _surf(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _circle(surf, color, cx, cy, r):
    if len(color) == 4:
        temp = _surf(r * 2 + 2, r * 2 + 2)
        pygame.draw.circle(temp, color, (r + 1, r + 1), r)
        surf.blit(temp, (cx - r - 1, cy - r - 1))
    else:
        pygame.draw.circle(surf, color, (cx, cy), r)


def _ellipse(surf, color, rect):
    if len(color) == 4:
        temp = _surf(rect[2], rect[3])
        pygame.draw.ellipse(temp, color, (0, 0, rect[2], rect[3]))
        surf.blit(temp, (rect[0], rect[1]))
    else:
        pygame.draw.ellipse(surf, color, rect)


def _rect(surf, color, rect, border_radius=0):
    if len(color) == 4:
        temp = _surf(rect[2], rect[3])
        pygame.draw.rect(temp, color, (0, 0, rect[2], rect[3]),
                         border_radius=border_radius)
        surf.blit(temp, (rect[0], rect[1]))
    else:
        pygame.draw.rect(surf, color, rect, border_radius=border_radius)


# =============================================================================
# Robot Sprites — each design uses the multi-color palette fully
# =============================================================================

def _draw_mech_robot(pal, size=32, frame=0, facing="right"):
    """Boxy armored robot with colored trim, distinct boots, accented visor."""
    s = _surf(size, size)
    cx = size // 2
    bounce = int(math.sin(frame * 0.5) * 1)
    body_y = 8 + bounce
    leg_offset = int(math.sin(frame * 0.6) * 2)

    _ellipse(s, (0, 0, 0, 40), (cx - 9, size - 4, 18, 4))

    # Boots (unique color)
    leg_y = body_y + 16
    _rect(s, pal["outline"], (cx - 10 - leg_offset, leg_y + 5, 8, 5), border_radius=1)
    _rect(s, pal["boots"], (cx - 9 - leg_offset, leg_y + 6, 6, 3), border_radius=1)
    _rect(s, pal["outline"], (cx + 2 + leg_offset, leg_y + 5, 8, 5), border_radius=1)
    _rect(s, pal["boots"], (cx + 3 + leg_offset, leg_y + 6, 6, 3), border_radius=1)

    # Legs (with accent stripe)
    _rect(s, pal["outline"], (cx - 9 - leg_offset, leg_y, 6, 7), border_radius=1)
    _rect(s, pal["body_dark"], (cx - 8 - leg_offset, leg_y + 1, 4, 5), border_radius=1)
    _rect(s, pal["accent"], (cx - 7 - leg_offset, leg_y + 2, 1, 3))
    _rect(s, pal["outline"], (cx + 3 + leg_offset, leg_y, 6, 7), border_radius=1)
    _rect(s, pal["body_dark"], (cx + 4 + leg_offset, leg_y + 1, 4, 5), border_radius=1)
    _rect(s, pal["accent"], (cx + 6 + leg_offset, leg_y + 2, 1, 3))

    # Torso
    _rect(s, pal["outline"], (cx - 10, body_y + 2, 20, 15), border_radius=2)
    _rect(s, pal["body"], (cx - 9, body_y + 3, 18, 13), border_radius=1)
    _rect(s, pal["body_dark"], (cx - 9, body_y + 10, 18, 6), border_radius=1)
    _rect(s, pal["body_lit"], (cx - 7, body_y + 4, 6, 4))
    # Belly plate (distinct color)
    _rect(s, pal["belly"], (cx - 5, body_y + 6, 10, 7), border_radius=1)
    # Accent trim lines
    _rect(s, pal["accent"], (cx - 9, body_y + 3, 18, 1))
    _rect(s, pal["accent"], (cx - 9, body_y + 14, 18, 1))
    # Bolts
    for bx, by in [(cx - 7, body_y + 4), (cx + 6, body_y + 4),
                    (cx - 7, body_y + 13), (cx + 6, body_y + 13)]:
        _circle(s, pal["accent"], bx, by, 1)

    # Arms (with accent bands)
    arm_swing = int(math.sin(frame * 0.4) * 2)
    _rect(s, pal["outline"], (cx - 14, body_y + 4 + arm_swing, 5, 10), border_radius=1)
    _rect(s, pal["body"], (cx - 13, body_y + 5 + arm_swing, 3, 8), border_radius=1)
    _rect(s, pal["accent"], (cx - 13, body_y + 7 + arm_swing, 3, 1))
    _rect(s, pal["outline"], (cx + 9, body_y + 4 - arm_swing, 5, 10), border_radius=1)
    _rect(s, pal["body"], (cx + 10, body_y + 5 - arm_swing, 3, 8), border_radius=1)
    _rect(s, pal["accent"], (cx + 10, body_y + 7 - arm_swing, 3, 1))

    # Head
    head_y = body_y - 2
    _rect(s, pal["outline"], (cx - 7, head_y - 5, 14, 9), border_radius=1)
    _rect(s, pal["body"], (cx - 6, head_y - 4, 12, 7), border_radius=1)
    _rect(s, pal["body_lit"], (cx - 5, head_y - 4, 5, 3))
    # Visor with accent frame
    visor_off = 1 if facing == "right" else -1
    _rect(s, pal["accent"], (cx - 6, head_y - 3, 12, 4))
    _rect(s, pal["outline"], (cx - 5, head_y - 2, 10, 3))
    _rect(s, pal["eye_white"], (cx - 4 + visor_off, head_y - 1, 8, 1))
    _rect(s, pal["eye_shine"], (cx - 1 + visor_off * 2, head_y - 1, 3, 1))

    # Antenna
    _rect(s, pal["antenna"], (cx - 1, head_y - 8, 2, 4))
    _circle(s, pal["ant_tip"], cx, head_y - 8, 2)

    return s


def _draw_ninja_robot(pal, size=32, frame=0, facing="right"):
    """Sleek ninja with scarf, blade, accent belt buckle."""
    s = _surf(size, size)
    cx = size // 2
    bounce = int(math.sin(frame * 0.7) * 1)
    body_y = 9 + bounce
    run_phase = math.sin(frame * 0.7)
    leg_offset = int(run_phase * 3)

    _ellipse(s, (0, 0, 0, 40), (cx - 6, size - 4, 12, 3))

    # Legs with boots
    leg_y = body_y + 14
    pygame.draw.line(s, pal["outline"], (cx - 3 - leg_offset, leg_y),
                     (cx - 5 - leg_offset, leg_y + 9), 2)
    _rect(s, pal["boots"], (cx - 7 - leg_offset, leg_y + 7, 5, 3), border_radius=1)
    pygame.draw.line(s, pal["outline"], (cx + 3 + leg_offset, leg_y),
                     (cx + 5 + leg_offset, leg_y + 9), 2)
    _rect(s, pal["boots"], (cx + 3 + leg_offset, leg_y + 7, 5, 3), border_radius=1)

    # Scarf (uses ant_tip color — bright and flowing)
    scarf_wave = int(math.sin(frame * 0.5 + 1.5) * 3)
    scarf_x = cx + (6 if facing == "left" else -6)
    for i in range(4):
        alpha = max(30, 160 - i * 35)
        scarf_c = (*pal["ant_tip"][:3], alpha)
        sy_off = body_y + 2 + i * 3
        _rect(s, scarf_c, (scarf_x + scarf_wave - i, sy_off, 5, 3), border_radius=1)

    # Body
    _rect(s, pal["outline"], (cx - 6, body_y + 2, 12, 13), border_radius=2)
    _rect(s, pal["body"], (cx - 5, body_y + 3, 10, 11), border_radius=1)
    # Chest slash detail
    pygame.draw.line(s, pal["body_dark"], (cx - 3, body_y + 4), (cx + 3, body_y + 10), 1)
    pygame.draw.line(s, pal["body_lit"], (cx - 3, body_y + 5), (cx + 3, body_y + 11), 1)
    # Belt with accent buckle
    _rect(s, pal["outline"], (cx - 6, body_y + 10, 12, 2))
    _rect(s, pal["accent"], (cx - 2, body_y + 10, 4, 2))

    # Arms (blade-like)
    arm_swing = int(math.sin(frame * 0.6 + 0.5) * 2)
    pygame.draw.line(s, pal["outline"], (cx - 6, body_y + 5),
                     (cx - 11, body_y + 9 + arm_swing), 2)
    blade_dir = 1 if facing == "right" else -1
    pygame.draw.line(s, pal["outline"], (cx + 6, body_y + 5),
                     (cx + 11, body_y + 9 - arm_swing), 2)
    # Blade
    bx = cx + 11 * blade_dir
    by = body_y + 9 - arm_swing
    pygame.draw.line(s, pal["accent"], (bx, by), (bx + 3 * blade_dir, by - 2), 2)
    pygame.draw.line(s, pal["eye_shine"], (bx, by), (bx + 3 * blade_dir, by - 2), 1)

    # Head (angular)
    head_y = body_y - 3
    pts = [(cx - 5, head_y + 5), (cx - 6, head_y),
           (cx - 2, head_y - 4), (cx + 2, head_y - 4),
           (cx + 6, head_y), (cx + 5, head_y + 5)]
    pygame.draw.polygon(s, pal["outline"], pts)
    inner = [(cx - 4, head_y + 4), (cx - 5, head_y + 1),
             (cx - 1, head_y - 3), (cx + 1, head_y - 3),
             (cx + 5, head_y + 1), (cx + 4, head_y + 4)]
    pygame.draw.polygon(s, pal["body"], inner)

    # Visor (glowing accent color)
    visor_off = 1 if facing == "right" else -1
    visor_pulse = 0.6 + 0.4 * math.sin(frame * 0.3)
    visor_alpha = int(200 * visor_pulse)
    visor_color = (*pal["ant_tip"][:3], visor_alpha)
    _rect(s, visor_color, (cx - 4 + visor_off, head_y, 8, 2))
    _rect(s, pal["eye_shine"], (cx - 1 + visor_off * 2, head_y, 3, 2))

    return s


def _draw_tank_robot(pal, size=32, frame=0, facing="right"):
    """Heavy tank with treads, cannon, accent rivets and exhaust."""
    s = _surf(size, size)
    cx = size // 2
    bounce = int(math.sin(frame * 0.3) * 1)
    body_y = 10 + bounce

    _ellipse(s, (0, 0, 0, 50), (cx - 12, size - 4, 24, 5))

    # Treads (boots color)
    tread_y = body_y + 15
    tread_phase = (frame * 2) % 6
    for side_x in [cx - 13, cx + 4]:
        _rect(s, pal["outline"], (side_x, tread_y, 9, 8), border_radius=2)
        _rect(s, pal["boots"], (side_x + 1, tread_y + 1, 7, 6), border_radius=1)
        for i in range(3):
            tx = side_x + 2 + ((i * 3 + tread_phase) % 7)
            _rect(s, pal["outline"], (tx, tread_y + 2, 1, 4))

    # Body (wide)
    _rect(s, pal["outline"], (cx - 12, body_y, 24, 16), border_radius=3)
    _rect(s, pal["body"], (cx - 11, body_y + 1, 22, 14), border_radius=2)
    _rect(s, pal["body_dark"], (cx - 11, body_y + 8, 22, 7), border_radius=2)
    _rect(s, pal["body_lit"], (cx - 9, body_y + 2, 8, 5))
    # Belly plate
    _rect(s, pal["belly"], (cx - 7, body_y + 4, 14, 8), border_radius=2)
    # Accent stripes
    _rect(s, pal["accent"], (cx - 11, body_y + 1, 22, 1))
    _rect(s, pal["accent"], (cx - 11, body_y + 14, 22, 1))
    # Accent rivets
    for rx, ry in [(cx - 9, body_y + 2), (cx + 8, body_y + 2),
                    (cx - 9, body_y + 13), (cx + 8, body_y + 13)]:
        _circle(s, pal["accent"], rx, ry, 1)

    # Exhaust (antenna color)
    pipe_side = -1 if facing == "right" else 1
    _rect(s, pal["antenna"], (cx + pipe_side * 11, body_y + 2, 3, 5), border_radius=1)
    smoke_y = body_y - 1 - int(abs(math.sin(frame * 0.2)) * 3)
    smoke_alpha = int(60 * abs(math.sin(frame * 0.2)))
    _circle(s, (180, 180, 180, smoke_alpha), cx + pipe_side * 12, smoke_y, 2)

    # Cannon arm (accent colored barrel)
    cannon_dir = 1 if facing == "right" else -1
    cannon_x = cx + cannon_dir * 8
    cannon_y = body_y + 4
    arm_recoil = int(math.sin(frame * 0.15) * 1)
    _circle(s, pal["outline"], cannon_x, cannon_y, 3)
    _circle(s, pal["body"], cannon_x, cannon_y, 2)
    barrel_end = cannon_x + cannon_dir * (10 + arm_recoil)
    pygame.draw.line(s, pal["outline"], (cannon_x + cannon_dir * 2, cannon_y),
                     (barrel_end, cannon_y), 3)
    pygame.draw.line(s, pal["accent"], (cannon_x + cannon_dir * 2, cannon_y),
                     (barrel_end, cannon_y), 2)
    _rect(s, pal["accent"], (barrel_end - 1, cannon_y - 2, 3, 5))

    # Head
    head_y = body_y - 4
    _rect(s, pal["outline"], (cx - 4, head_y - 2, 8, 6), border_radius=2)
    _rect(s, pal["body"], (cx - 3, head_y - 1, 6, 4), border_radius=1)
    visor_off = 1 if facing == "right" else -1
    _rect(s, pal["eye_white"], (cx - 2 + visor_off, head_y, 4, 2))
    _rect(s, pal["eye_shine"], (cx + visor_off * 2, head_y, 2, 2))
    _rect(s, pal["antenna"], (cx, head_y - 4, 1, 3))
    _circle(s, pal["ant_tip"], cx, head_y - 4, 1)

    return s


def _draw_drone_robot(pal, size=32, frame=0, facing="right"):
    """Hovering drone with propeller, sensor eye, accent thrusters."""
    s = _surf(size, size)
    cx = size // 2
    hover = int(math.sin(frame * 0.4) * 2)
    body_y = 12 + hover

    # Hover glow (ant_tip color)
    glow_pulse = 0.5 + 0.5 * math.sin(frame * 0.3)
    glow_alpha = int(50 * glow_pulse)
    _ellipse(s, (*pal["ant_tip"][:3], glow_alpha), (cx - 8, size - 6, 16, 5))
    _ellipse(s, (*pal["ant_tip"][:3], glow_alpha // 2), (cx - 6, size - 5, 12, 3))

    # Propeller
    prop_y = body_y - 8
    _rect(s, pal["antenna"], (cx - 1, prop_y, 2, 5))
    if frame % 2 == 0:
        prop_len = 10
        blade_x1 = cx + int(math.cos(frame * 0.8) * prop_len)
        blade_x2 = cx - int(math.cos(frame * 0.8) * prop_len)
        pygame.draw.line(s, pal["outline"], (blade_x1, prop_y), (blade_x2, prop_y), 2)
        pygame.draw.line(s, pal["accent"], (blade_x1, prop_y), (blade_x2, prop_y), 1)
    else:
        prop_len = 10
        blade_x1 = cx + int(math.sin(frame * 0.8) * prop_len)
        blade_x2 = cx - int(math.sin(frame * 0.8) * prop_len)
        pygame.draw.line(s, pal["outline"], (blade_x1, prop_y), (blade_x2, prop_y), 2)
        pygame.draw.line(s, pal["accent"], (blade_x1, prop_y), (blade_x2, prop_y), 1)
    _circle(s, pal["outline"], cx, prop_y, 2)
    _circle(s, pal["ant_tip"], cx, prop_y, 1)

    # Body (rounded techy)
    _ellipse(s, pal["outline"], (cx - 10, body_y - 2, 20, 14))
    _ellipse(s, pal["body"], (cx - 9, body_y - 1, 18, 12))
    _ellipse(s, pal["body_dark"], (cx - 9, body_y + 4, 18, 7))
    _ellipse(s, pal["body_lit"], (cx - 6, body_y - 1, 8, 5))
    # Belly panel
    _rect(s, pal["belly"], (cx - 5, body_y + 1, 10, 6), border_radius=2)
    # Accent ring
    pygame.draw.ellipse(s, pal["accent"], (cx - 10, body_y - 2, 20, 14), 1)

    # Sensor eye
    eye_x = cx + (2 if facing == "right" else -2)
    eye_y = body_y + 2
    _circle(s, pal["outline"], eye_x, eye_y, 4)
    _circle(s, pal["eye_white"], eye_x, eye_y, 3)
    pupil_off = 1 if facing == "right" else -1
    _circle(s, pal["eye_pupil"], eye_x + pupil_off, eye_y, 2)
    scan_pulse = 0.5 + 0.5 * math.sin(frame * 0.25)
    scan_alpha = int(120 * scan_pulse)
    _circle(s, (*pal["ant_tip"][:3], scan_alpha), eye_x + pupil_off, eye_y, 1)
    _circle(s, pal["eye_shine"], eye_x + pupil_off - 1, eye_y - 1, 1)

    # Thrusters (accent colored)
    for side in [-1, 1]:
        tx = cx + side * 10
        ty = body_y + 4
        _rect(s, pal["outline"], (tx - 1, ty, 3, 4), border_radius=1)
        _rect(s, pal["accent"], (tx, ty + 1, 1, 2))
        thr_alpha = int(40 * glow_pulse)
        _circle(s, (*pal["ant_tip"][:3], thr_alpha), tx, ty + 5, 2)

    # Side antenna stubs
    _rect(s, pal["antenna"], (cx - 8, body_y - 4, 1, 3))
    _rect(s, pal["antenna"], (cx + 7, body_y - 4, 1, 3))

    return s


def _draw_knight_robot(pal, size=32, frame=0, facing="right"):
    """Medieval knight with helmet plume, shield, sword — accent on trim."""
    s = _surf(size, size)
    cx = size // 2
    bounce = int(math.sin(frame * 0.5) * 1)
    body_y = 9 + bounce
    leg_offset = int(math.sin(frame * 0.6) * 2)

    _ellipse(s, (0, 0, 0, 40), (cx - 8, size - 4, 16, 4))

    # Legs with armored boots
    leg_y = body_y + 15
    for lx, off in [(cx - 6 - leg_offset, 0), (cx + 2 + leg_offset, 0)]:
        _rect(s, pal["outline"], (lx, leg_y, 5, 8), border_radius=1)
        _rect(s, pal["body_dark"], (lx + 1, leg_y + 1, 3, 6), border_radius=1)
        _rect(s, pal["accent"], (lx + 1, leg_y + 1, 3, 1))  # accent trim on greave
        _rect(s, pal["boots"], (lx - 1, leg_y + 6, 7, 3), border_radius=1)

    # Shield (belly colored with accent cross)
    shield_side = -1 if facing == "right" else 1
    shield_x = cx + shield_side * 9
    shield_y = body_y + 3
    shield_pts = [
        (shield_x - 4, shield_y), (shield_x + 4, shield_y),
        (shield_x + 4, shield_y + 8), (shield_x, shield_y + 12),
        (shield_x - 4, shield_y + 8),
    ]
    pygame.draw.polygon(s, pal["outline"], shield_pts)
    inner_shield = [
        (shield_x - 3, shield_y + 1), (shield_x + 3, shield_y + 1),
        (shield_x + 3, shield_y + 7), (shield_x, shield_y + 11),
        (shield_x - 3, shield_y + 7),
    ]
    pygame.draw.polygon(s, pal["belly"], inner_shield)
    # Accent cross on shield
    pygame.draw.line(s, pal["accent"], (shield_x, shield_y + 2), (shield_x, shield_y + 9), 2)
    pygame.draw.line(s, pal["accent"], (shield_x - 2, shield_y + 5), (shield_x + 2, shield_y + 5), 2)

    # Sword arm (accent blade)
    sword_side = 1 if facing == "right" else -1
    sword_x = cx + sword_side * 9
    sword_y = body_y + 3
    arm_swing = int(math.sin(frame * 0.4 + 0.5) * 3)
    pygame.draw.line(s, pal["outline"], (cx + sword_side * 6, body_y + 5),
                     (sword_x, sword_y + arm_swing), 2)
    _rect(s, pal["boots"], (sword_x - 2, sword_y + arm_swing - 1, 4, 3))
    blade_tip_y = sword_y + arm_swing - 10
    pygame.draw.line(s, pal["accent"], (sword_x, sword_y + arm_swing - 1),
                     (sword_x, blade_tip_y), 2)
    pygame.draw.line(s, (240, 240, 255), (sword_x, sword_y + arm_swing - 1),
                     (sword_x, blade_tip_y), 1)

    # Body (armored torso)
    _rect(s, pal["outline"], (cx - 7, body_y + 1, 14, 15), border_radius=2)
    _rect(s, pal["body"], (cx - 6, body_y + 2, 12, 13), border_radius=1)
    _rect(s, pal["body_lit"], (cx - 4, body_y + 3, 8, 5), border_radius=1)
    _rect(s, pal["belly"], (cx - 3, body_y + 4, 6, 3), border_radius=1)
    # Accent belt
    _rect(s, pal["accent"], (cx - 7, body_y + 11, 14, 2))
    _rect(s, pal["ant_tip"], (cx - 1, body_y + 11, 2, 2))

    # Helmet
    head_y = body_y - 4
    _rect(s, pal["outline"], (cx - 6, head_y - 3, 12, 9), border_radius=3)
    _rect(s, pal["body"], (cx - 5, head_y - 2, 10, 7), border_radius=2)
    _rect(s, pal["body_lit"], (cx - 4, head_y - 2, 5, 3), border_radius=1)
    # Accent trim on helmet
    _rect(s, pal["accent"], (cx - 6, head_y - 3, 12, 1))
    # Visor
    _rect(s, pal["outline"], (cx - 4, head_y + 1, 8, 3))
    _rect(s, (20, 20, 30), (cx - 3, head_y + 2, 6, 1))
    visor_off = 1 if facing == "right" else -1
    _rect(s, pal["eye_white"], (cx - 2 + visor_off, head_y + 2, 2, 1))
    _rect(s, pal["eye_white"], (cx + 2 + visor_off, head_y + 2, 2, 1))

    # Plume (ant_tip color — bright and distinctive)
    plume_wave = int(math.sin(frame * 0.4) * 2)
    plume_base_y = head_y - 5
    for i in range(4):
        plume_alpha = max(60, 220 - i * 40)
        plume_c = (*pal["ant_tip"][:3], plume_alpha)
        px = cx + i * 1 + plume_wave
        py = plume_base_y - i
        _circle(s, plume_c, px, py, 2)
    _circle(s, pal["ant_tip"], cx, plume_base_y + 1, 2)

    return s


ROBOT_DESIGNS = {
    "mech":   _draw_mech_robot,
    "ninja":  _draw_ninja_robot,
    "tank":   _draw_tank_robot,
    "drone":  _draw_drone_robot,
    "knight": _draw_knight_robot,
}


# =============================================================================
# Waste Sprites
# =============================================================================

def _draw_waste(pal, size=32, frame=0):
    s = _surf(size + 8, size + 8)
    cx, cy = size // 2 + 4, size // 2 + 4

    pulse = 0.6 + 0.4 * math.sin(frame * 0.35)
    glow_r = int(12 * pulse) + 4
    glow_color = (*pal["glow"][:3], int(35 * pulse))
    _circle(s, glow_color, cx, cy, glow_r + 4)
    _circle(s, glow_color, cx, cy, glow_r + 2)

    r = 6
    _circle(s, pal["dark"], cx, cy + 1, r)
    _circle(s, pal["core"], cx, cy, r)
    _circle(s, pal["core"], cx - 3, cy - 1, r - 2)
    _circle(s, pal["core"], cx + 3, cy + 1, r - 2)
    _circle(s, pal["light"], cx - 2, cy - 3, r - 4)

    sym_r = 3
    for angle_deg in [0, 120, 240]:
        rad = math.radians(angle_deg + frame * 3)
        dx = int(math.cos(rad) * sym_r)
        dy = int(math.sin(rad) * sym_r)
        _circle(s, pal["dark"], cx + dx, cy + dy, 2)
    _circle(s, pal["light"], cx, cy, 1)

    return s


# =============================================================================
# Disposal Zone Sprite
# =============================================================================

def _draw_disposal(size=32, frame=0):
    s = _surf(size, size)
    pipe_color = (80, 90, 105)
    pipe_dark = (55, 62, 75)
    pipe_light = (110, 120, 140)
    pipe_rim = (95, 105, 125)
    highlight = (140, 155, 175)

    _rect(s, pipe_dark, (6, 8, 20, 20), border_radius=2)
    _rect(s, pipe_color, (7, 8, 18, 19), border_radius=2)
    _rect(s, pipe_light, (8, 9, 4, 17))
    _rect(s, pipe_dark, (20, 9, 3, 17))
    _rect(s, pipe_rim, (4, 6, 24, 5), border_radius=2)
    _rect(s, highlight, (5, 6, 22, 2), border_radius=1)

    hx, hy = 16, 18
    _circle(s, (200, 170, 30), hx, hy, 4)
    _circle(s, pipe_color, hx, hy, 2)
    _rect(s, pipe_dark, (5, 26, 22, 3), border_radius=1)

    return s


# =============================================================================
# Tile Textures
# =============================================================================

def _make_zone1_tile(size, parity):
    s = pygame.Surface((size, size))
    wc = WORLD_COLORS
    if parity == 0:
        s.fill(wc["z1_grass_top"])
        _rect(s, wc["z1_grass_mid"], (0, size // 2, size, size // 2))
    else:
        s.fill(wc["z1_grass_mid"])
        _rect(s, wc["z1_grass_top"], (0, 0, size, size // 2))

    tuft = tuple(min(255, c + 30) for c in wc["z1_grass_top"])
    for px, py in [(4, 8), (14, 4), (24, 10), (8, 22), (20, 26), (28, 16)]:
        if px < size and py < size:
            pygame.draw.line(s, tuft, (px, py), (px - 1, py - 4), 1)
            pygame.draw.line(s, tuft, (px, py), (px + 1, py - 3), 1)

    if parity == 0:
        _circle(s, wc["z1_flower1"], 10, 14, 1)
        _circle(s, wc["z1_flower2"], 22, 20, 1)

    border = tuple(max(0, c - 15) for c in wc["z1_grass_mid"])
    pygame.draw.rect(s, border, (0, 0, size, size), 1)
    return s


def _make_zone2_tile(size, parity):
    s = pygame.Surface((size, size))
    wc = WORLD_COLORS
    if parity == 0:
        s.fill(wc["z2_sand_top"])
        _rect(s, wc["z2_sand_mid"], (0, size // 2, size, size // 2))
    else:
        s.fill(wc["z2_sand_mid"])
        _rect(s, wc["z2_sand_top"], (0, 0, size, size // 2))

    dot = wc["z2_rock"]
    for pos in [(6, 5), (20, 8), (12, 22), (26, 18), (4, 28)]:
        if pos[0] < size and pos[1] < size:
            s.set_at(pos, dot)
            s.set_at((pos[0] + 1, pos[1]), dot)

    crack = wc["z2_crack"]
    pygame.draw.line(s, crack, (3, 12), (10, 15), 1)
    pygame.draw.line(s, crack, (18, 6), (25, 9), 1)
    pygame.draw.line(s, crack, (14, 24), (20, 28), 1)

    pebble = wc["z2_rock_dark"]
    _circle(s, pebble, 8, 18, 1)
    _circle(s, pebble, 24, 12, 1)

    border = tuple(max(0, c - 12) for c in wc["z2_sand_mid"])
    pygame.draw.rect(s, border, (0, 0, size, size), 1)
    return s


def _make_zone3_tile(size, parity):
    s = pygame.Surface((size, size))
    wc = WORLD_COLORS
    if parity == 0:
        s.fill(wc["z3_stone_top"])
        _rect(s, wc["z3_stone_mid"], (0, size // 2, size, size // 2))
    else:
        s.fill(wc["z3_stone_mid"])
        _rect(s, wc["z3_stone_top"], (0, 0, size, size // 2))

    brick_line = tuple(max(0, c - 15) for c in wc["z3_stone_mid"])
    for y in [8, 16, 24]:
        pygame.draw.line(s, brick_line, (0, y), (size, y), 1)
    for row, y_start in enumerate([0, 8, 16, 24]):
        offset = 0 if row % 2 == 0 else size // 2
        for x in range(offset, size, size):
            if 0 < x < size:
                pygame.draw.line(s, brick_line, (x, y_start),
                                 (x, min(y_start + 8, size)), 1)

    glow = (*wc["z3_lava_glow"][:3], 25)
    _rect(s, glow, (0, size - 4, size, 4))
    lava = wc["z3_lava"]
    pygame.draw.line(s, lava, (4, 20), (12, 24), 1)
    lava_g = wc["z3_lava_glow"]
    pygame.draw.line(s, lava_g, (5, 21), (11, 25), 1)

    border = tuple(max(0, c - 10) for c in wc["z3_stone_mid"])
    pygame.draw.rect(s, border, (0, 0, size, size), 1)
    return s


# =============================================================================
# Particle System
# =============================================================================

class Particle:
    def __init__(self, x, y, color, vx=0, vy=0, life=20, size=3):
        self.x, self.y = x, y
        self.color = color
        self.vx, self.vy = vx, vy
        self.life = life
        self.max_life = life
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.08
        self.life -= 1

    def draw(self, screen):
        if self.life <= 0:
            return
        t = self.life / self.max_life
        alpha = int(255 * t)
        sz = max(1, int(self.size * t))
        color = (*self.color[:3], alpha)
        surf = _surf(sz * 2 + 2, sz * 2 + 2)
        pygame.draw.circle(surf, color, (sz + 1, sz + 1), sz)
        screen.blit(surf, (int(self.x) - sz, int(self.y) - sz))


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit(self, x, y, color, count=8):
        for _ in range(count):
            vx = _rand.uniform(-2.5, 2.5)
            vy = _rand.uniform(-3.5, -0.5)
            life = _rand.randint(15, 35)
            size = _rand.randint(2, 5)
            self.particles.append(Particle(x, y, color, vx, vy, life, size))

    def emit_sparkle(self, x, y, color, count=5):
        for _ in range(count):
            angle = _rand.uniform(0, 2 * math.pi)
            speed = _rand.uniform(1, 3)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = _rand.randint(10, 20)
            self.particles.append(Particle(x, y, color, vx, vy, life, 2))

    def update(self):
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]

    def draw(self, screen):
        for p in self.particles:
            p.draw(screen)


# =============================================================================
# Sprite Cache
# =============================================================================

class SpriteCache:

    def __init__(self, cell_size=32, num_frames=16):
        self.cell_size = cell_size
        self.num_frames = num_frames
        self._cache = {}
        self._tile_cache = {}
        self.particle_system = ParticleSystem()
        self._build()

    def _build(self):
        cs = self.cell_size

        for design_name, draw_fn in ROBOT_DESIGNS.items():
            for robot_type, pal in ROBOT_PALETTES.items():
                for f in range(self.num_frames):
                    sprite_r = draw_fn(pal, cs, f, "right")
                    sprite_l = pygame.transform.flip(sprite_r, True, False)
                    self._cache[("robot", design_name, robot_type, f)] = sprite_r
                    self._cache[("robot_left", design_name, robot_type, f)] = sprite_l

        for wtype, pal in WASTE_PALETTES.items():
            for f in range(self.num_frames):
                self._cache[("waste", wtype, f)] = _draw_waste(pal, cs, f)

        for f in range(self.num_frames):
            self._cache[("disposal", 0, f)] = _draw_disposal(cs, f)

        for parity in (0, 1):
            self._tile_cache[(1, parity)] = _make_zone1_tile(cs, parity)
            self._tile_cache[(2, parity)] = _make_zone2_tile(cs, parity)
            self._tile_cache[(3, parity)] = _make_zone3_tile(cs, parity)

        self._save_samples()

    def _save_samples(self):
        sprite_dir = os.path.join(ASSET_DIR, "sprites")
        os.makedirs(sprite_dir, exist_ok=True)
        tile_dir = os.path.join(ASSET_DIR, "tiles")
        os.makedirs(tile_dir, exist_ok=True)

        for design_name in ROBOT_DESIGNS:
            for robot_type in ("green", "yellow", "red"):
                s = self._cache.get(("robot", design_name, robot_type, 0))
                if s:
                    pygame.image.save(s, os.path.join(
                        sprite_dir, f"robot_{design_name}_{robot_type}.png"))

        for wtype in ("green", "yellow", "red"):
            s = self._cache.get(("waste", wtype, 0))
            if s:
                pygame.image.save(s, os.path.join(sprite_dir, f"waste_{wtype}.png"))

        s = self._cache.get(("disposal", 0, 0))
        if s:
            pygame.image.save(s, os.path.join(sprite_dir, "disposal.png"))

        for zone in (1, 2, 3):
            t = self._tile_cache.get((zone, 0))
            if t:
                pygame.image.save(t, os.path.join(tile_dir, f"zone{zone}_tile.png"))

    def get(self, kind, variant, frame, design=None):
        f = frame % self.num_frames
        if kind in ("robot", "robot_left"):
            d = design if design else DEFAULT_DESIGN
            return self._cache.get((kind, d, variant, f))
        return self._cache.get((kind, variant, f))

    def get_tile(self, zone, parity):
        return self._tile_cache.get((zone, parity))
