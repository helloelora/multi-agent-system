# =============================================================================
# Group 19
# Date: 2026-03-16
# Members: Ali Dor, Elora Drouilhet
# =============================================================================

"""Pixel-art sprite system. Drawn at native resolution, saved to assets/."""

import pygame
import math
import os
import random as _rand

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

DEFAULT_DESIGN = "claude"


# =============================================================================
# Color Palettes: one multi-color scheme per robot type
# =============================================================================

ROBOT_PALETTES = {
    "green": {
        # Deep forest ranger: rich greens + warm gold + earthy belly
        "body":      (40, 145, 65),
        "body_dark": (22, 90, 38),
        "body_lit":  (95, 210, 110),
        "belly":     (225, 195, 130),
        "outline":   (15, 48, 25),
        "eye_white": (255, 255, 255),
        "eye_pupil": (18, 38, 22),
        "eye_shine": (190, 255, 205),
        "mouth":     (15, 48, 25),
        "cheek":     (255, 150, 130, 100),
        "antenna":   (155, 120, 35),
        "ant_tip":   (255, 225, 60),
        "accent":    (200, 155, 45),
        "boots":     (90, 60, 30),
    },
    "yellow": {
        # Electric engineer: hot amber + deep violet + cyan sparks
        "body":      (240, 185, 25),
        "body_dark": (170, 120, 10),
        "body_lit":  (255, 225, 70),
        "belly":     (205, 180, 230),
        "outline":   (70, 40, 10),
        "eye_white": (255, 255, 255),
        "eye_pupil": (50, 20, 75),
        "eye_shine": (140, 240, 255),
        "mouth":     (70, 40, 10),
        "cheek":     (255, 175, 90, 100),
        "antenna":   (90, 45, 130),
        "ant_tip":   (50, 225, 255),
        "accent":    (110, 65, 170),
        "boots":     (75, 40, 110),
    },
    "red": {
        # Intense fire captain: deep crimson + hot orange + cool steel
        "body":      (205, 35, 30),
        "body_dark": (125, 18, 18),
        "body_lit":  (245, 85, 65),
        "belly":     (170, 180, 200),
        "outline":   (55, 12, 12),
        "eye_white": (255, 255, 255),
        "eye_pupil": (50, 10, 8),
        "eye_shine": (255, 195, 140),
        "mouth":     (55, 12, 12),
        "cheek":     (255, 130, 70, 100),
        "antenna":   (215, 125, 20),
        "ant_tip":   (255, 190, 30),
        "accent":    (255, 155, 30),
        "boots":     (50, 52, 65),
    },
}

# Claude-style palette overrides: warm terminal tones
CLAUDE_PALETTES = {
    "green": {
        # Vivid teal terminal, pops against dark panels
        "body":      (40, 165, 150),
        "body_dark": (20, 95, 85),
        "body_lit":  (80, 210, 190),
        "belly":     (18, 32, 38),
        "outline":   (12, 45, 40),
        "eye_white": (170, 245, 235),
        "eye_pupil": (12, 42, 38),
        "eye_shine": (120, 255, 240),
        "mouth":     (12, 45, 40),
        "cheek":     (90, 210, 185, 70),
        "antenna":   (35, 110, 100),
        "ant_tip":   (80, 255, 230),
        "accent":    (65, 210, 195),
        "boots":     (25, 65, 60),
    },
    "yellow": {
        # Rich terracotta, warm glowing amber
        "body":      (220, 125, 55),
        "body_dark": (155, 80, 30),
        "body_lit":  (250, 170, 90),
        "belly":     (32, 28, 22),
        "outline":   (75, 38, 14),
        "eye_white": (255, 230, 200),
        "eye_pupil": (60, 28, 10),
        "eye_shine": (255, 210, 150),
        "mouth":     (75, 38, 14),
        "cheek":     (255, 175, 95, 70),
        "antenna":   (185, 95, 40),
        "ant_tip":   (255, 190, 90),
        "accent":    (250, 165, 70),
        "boots":     (95, 48, 22),
    },
    "red": {
        # Vivid coral/rose, strong contrast
        "body":      (210, 70, 60),
        "body_dark": (140, 40, 35),
        "body_lit":  (245, 115, 95),
        "belly":     (38, 22, 22),
        "outline":   (65, 18, 15),
        "eye_white": (255, 215, 205),
        "eye_pupil": (55, 15, 10),
        "eye_shine": (255, 185, 175),
        "mouth":     (65, 18, 15),
        "cheek":     (255, 125, 100, 70),
        "antenna":   (170, 50, 40),
        "ant_tip":   (255, 125, 100),
        "accent":    (245, 105, 85),
        "boots":     (75, 32, 28),
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
    "z1_grass_top":    (88, 195, 70),
    "z1_grass_mid":    (65, 160, 50),
    "z1_dirt":         (175, 115, 55),
    "z1_dirt_dark":    (140, 88, 38),
    "z1_flower1":      (255, 90, 100),
    "z1_flower2":      (255, 210, 60),
    "z2_sand_top":     (225, 195, 125),
    "z2_sand_mid":     (200, 170, 100),
    "z2_rock":         (155, 130, 85),
    "z2_rock_dark":    (125, 100, 65),
    "z2_crack":        (105, 80, 48),
    "z3_stone_top":    (90, 72, 82),
    "z3_stone_mid":    (65, 52, 62),
    "z3_lava_glow":    (255, 110, 25),
    "z3_lava":         (210, 55, 15),
    "z3_lava_dark":    (145, 30, 10),
}

# Dark terminal-style world colors for Claude design
DARK_WORLD_COLORS = {
    "z1_top":       (18, 28, 32),
    "z1_mid":       (14, 22, 26),
    "z1_line":      (35, 60, 65),
    "z1_dot":       (45, 85, 80),
    "z1_glow":      (55, 135, 125),
    "z2_top":       (28, 24, 18),
    "z2_mid":       (22, 19, 14),
    "z2_line":      (60, 45, 28),
    "z2_dot":       (95, 65, 30),
    "z2_glow":      (175, 105, 45),
    "z3_top":       (30, 18, 18),
    "z3_mid":       (24, 14, 14),
    "z3_line":      (65, 30, 25),
    "z3_dot":       (105, 40, 30),
    "z3_glow":      (175, 55, 35),
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


def _clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


# =============================================================================
# Robot Sprites
# =============================================================================

def _draw_mech_robot(pal, size=32, frame=0, facing="right"):
    """Heavy mech: layered armor, visor, radar antenna."""
    s = _surf(size, size)
    cx = size // 2

    # Squash-and-stretch bounce
    bounce_raw = math.sin(frame * 0.5)
    bounce = int(bounce_raw * 2)
    squash_x = 1.0 + bounce_raw * 0.04  # wider on down
    squash_y = 1.0 - bounce_raw * 0.04  # shorter on down
    body_y = 8 + bounce
    leg_offset = int(math.sin(frame * 0.6) * 3)

    # Breathing (idle body width pulse)
    breath = math.sin(frame * 0.15) * 0.5

    # Shadow squashes with bounce
    shadow_w = int(20 + bounce_raw * 2)
    _ellipse(s, (0, 0, 0, 55), (cx - shadow_w // 2, size - 5, shadow_w, 5))

    # Boots (chunky treaded soles)
    leg_y = body_y + 16
    for lx_base, lo in [(cx - 10 - leg_offset, 0), (cx + 2 + leg_offset, 0)]:
        # Boot outline
        _rect(s, pal["outline"], (lx_base, leg_y + 4, 9, 6), border_radius=1)
        _rect(s, pal["boots"], (lx_base + 1, leg_y + 5, 7, 4), border_radius=1)
        # Tread lines
        for t in range(3):
            _rect(s, pal["outline"], (lx_base + 2 + t * 2, leg_y + 8, 1, 1))

    # Legs with knee joints
    for lx_base, lo in [(cx - 9 - leg_offset, 0), (cx + 3 + leg_offset, 0)]:
        _rect(s, pal["outline"], (lx_base, leg_y, 6, 7), border_radius=1)
        _rect(s, pal["body_dark"], (lx_base + 1, leg_y + 1, 4, 5), border_radius=1)
        _rect(s, pal["accent"], (lx_base + 1, leg_y + 2, 1, 3))
        # Knee joint circle
        _circle(s, pal["accent"], lx_base + 3, leg_y, 1)

    # Torso: layered armor
    bw = int(20 + breath)
    _rect(s, pal["outline"], (cx - bw // 2, body_y + 2, bw, 15), border_radius=2)
    _rect(s, pal["body"], (cx - bw // 2 + 1, body_y + 3, bw - 2, 13), border_radius=1)
    _rect(s, pal["body_dark"], (cx - bw // 2 + 1, body_y + 10, bw - 2, 6), border_radius=1)
    # Upper plate highlight
    _rect(s, pal["body_lit"], (cx - 7, body_y + 4, 6, 4))
    # Belly plate
    _rect(s, pal["belly"], (cx - 5, body_y + 6, 10, 7), border_radius=1)
    # Panel lines on belly
    _rect(s, pal["body_dark"], (cx, body_y + 7, 1, 5))
    # Top/bottom accent trim
    _rect(s, pal["accent"], (cx - bw // 2 + 1, body_y + 3, bw - 2, 1))
    _rect(s, pal["accent"], (cx - bw // 2 + 1, body_y + 14, bw - 2, 1))
    # Rivets at corners
    for bx, by in [(cx - 7, body_y + 4), (cx + 6, body_y + 4),
                    (cx - 7, body_y + 13), (cx + 6, body_y + 13)]:
        _circle(s, pal["accent"], bx, by, 1)
    # Vent detail on back side
    vent_side = -1 if facing == "right" else 1
    for vy in range(3):
        _rect(s, pal["body_dark"], (cx + vent_side * 7, body_y + 5 + vy * 3, 2, 1))

    # Shoulder plates (layered pauldrons)
    for side in [-1, 1]:
        sx = cx + side * 10
        _rect(s, pal["outline"], (sx - 3, body_y + 2, 6, 4), border_radius=1)
        _rect(s, pal["body_lit"], (sx - 2, body_y + 3, 4, 2), border_radius=1)
        _rect(s, pal["accent"], (sx - 2, body_y + 2, 4, 1))

    # Arms with accent bands
    arm_swing = int(math.sin(frame * 0.4) * 3)
    _rect(s, pal["outline"], (cx - 15, body_y + 5 + arm_swing, 5, 10), border_radius=1)
    _rect(s, pal["body"], (cx - 14, body_y + 6 + arm_swing, 3, 8), border_radius=1)
    _rect(s, pal["accent"], (cx - 14, body_y + 8 + arm_swing, 3, 1))
    _rect(s, pal["outline"], (cx + 10, body_y + 5 - arm_swing, 5, 10), border_radius=1)
    _rect(s, pal["body"], (cx + 11, body_y + 6 - arm_swing, 3, 8), border_radius=1)
    _rect(s, pal["accent"], (cx + 11, body_y + 8 - arm_swing, 3, 1))

    # Head
    head_y = body_y - 2
    _rect(s, pal["outline"], (cx - 7, head_y - 5, 14, 9), border_radius=1)
    _rect(s, pal["body"], (cx - 6, head_y - 4, 12, 7), border_radius=1)
    _rect(s, pal["body_lit"], (cx - 5, head_y - 4, 5, 3))
    # Wide visor with pulsing light
    visor_off = 1 if facing == "right" else -1
    visor_pulse = 0.5 + 0.5 * math.sin(frame * 0.25)
    _rect(s, pal["accent"], (cx - 6, head_y - 3, 12, 4))
    _rect(s, pal["outline"], (cx - 5, head_y - 2, 10, 3))
    visor_bright = tuple(_clamp(c + int(40 * visor_pulse)) for c in pal["eye_white"])
    _rect(s, visor_bright, (cx - 4 + visor_off, head_y - 1, 8, 1))
    # Scanning light sweep
    scan_x = cx - 3 + int((math.sin(frame * 0.2) + 1) * 3)
    _rect(s, pal["eye_shine"], (scan_x, head_y - 1, 2, 1))

    # Antenna with spinning radar dish
    _rect(s, pal["antenna"], (cx - 1, head_y - 9, 2, 5))
    radar_angle = frame * 0.4
    rx1 = cx + int(math.cos(radar_angle) * 3)
    ry1 = head_y - 9 + int(math.sin(radar_angle) * 1)
    rx2 = cx - int(math.cos(radar_angle) * 3)
    ry2 = head_y - 9 - int(math.sin(radar_angle) * 1)
    pygame.draw.line(s, pal["ant_tip"], (rx1, ry1), (rx2, ry2), 2)
    _circle(s, pal["ant_tip"], cx, head_y - 9, 1)

    return s


def _draw_ninja_robot(pal, size=32, frame=0, facing="right"):
    """Ninja: angular, scarf, blade, after-image trail."""
    s = _surf(size, size)
    cx = size // 2
    bounce = int(math.sin(frame * 0.7) * 1)
    body_y = 9 + bounce
    run_phase = math.sin(frame * 0.7)
    leg_offset = int(run_phase * 4)

    # Lean forward when moving
    lean = 1 if facing == "right" else -1

    # Very light shadow (ninja is light on feet)
    _ellipse(s, (0, 0, 0, 22), (cx - 5, size - 3, 10, 2))

    # Legs with darting motion (wider offset)
    leg_y = body_y + 14
    pygame.draw.line(s, pal["outline"], (cx - 3 - leg_offset, leg_y),
                     (cx - 6 - leg_offset, leg_y + 9), 2)
    _rect(s, pal["boots"], (cx - 8 - leg_offset, leg_y + 7, 5, 3), border_radius=1)
    pygame.draw.line(s, pal["outline"], (cx + 3 + leg_offset, leg_y),
                     (cx + 6 + leg_offset, leg_y + 9), 2)
    _rect(s, pal["boots"], (cx + 4 + leg_offset, leg_y + 7, 5, 3), border_radius=1)

    # Scarf: more segments, dramatic wave
    scarf_wave = math.sin(frame * 0.5 + 1.5) * 4
    scarf_x = cx + (7 if facing == "left" else -7)
    for i in range(6):
        alpha = max(20, 180 - i * 28)
        scarf_c = (*pal["ant_tip"][:3], alpha)
        sy_off = body_y + 1 + i * 3
        wave_off = int(math.sin(frame * 0.5 + i * 0.7) * (2 + i))
        _rect(s, scarf_c, (scarf_x + wave_off - i, sy_off, 5 - i // 3, 3), border_radius=1)

    # After-image trail (fading ghost behind)
    trail_dir = -1 if facing == "right" else 1
    for t in range(2):
        ta = max(10, 35 - t * 15)
        trail_c = (*pal["ant_tip"][:3], ta)
        tx_off = trail_dir * (3 + t * 3)
        _rect(s, trail_c, (cx - 5 + tx_off, body_y + 2, 10, 12), border_radius=2)

    # Body: angular, with slash marks and stealth panel lines
    _rect(s, pal["outline"], (cx - 6 + lean, body_y + 2, 12, 13), border_radius=2)
    _rect(s, pal["body"], (cx - 5 + lean, body_y + 3, 10, 11), border_radius=1)
    # Stealth panel lines
    pygame.draw.line(s, pal["body_dark"], (cx - 3 + lean, body_y + 4),
                     (cx + 4 + lean, body_y + 10), 1)
    pygame.draw.line(s, pal["body_lit"], (cx - 3 + lean, body_y + 5),
                     (cx + 4 + lean, body_y + 11), 1)
    # Horizontal slash marks
    pygame.draw.line(s, pal["body_dark"], (cx - 4 + lean, body_y + 7),
                     (cx + 3 + lean, body_y + 7), 1)
    pygame.draw.line(s, pal["body_dark"], (cx - 2 + lean, body_y + 9),
                     (cx + 5 + lean, body_y + 9), 1)
    # Belt with accent buckle
    _rect(s, pal["outline"], (cx - 6 + lean, body_y + 10, 12, 2))
    _rect(s, pal["accent"], (cx - 2 + lean, body_y + 10, 4, 2))

    # Arms (blade-like, leaner)
    arm_swing = int(math.sin(frame * 0.6 + 0.5) * 3)
    pygame.draw.line(s, pal["outline"], (cx - 6 + lean, body_y + 5),
                     (cx - 12, body_y + 9 + arm_swing), 2)
    blade_dir = 1 if facing == "right" else -1
    pygame.draw.line(s, pal["outline"], (cx + 6 + lean, body_y + 5),
                     (cx + 12, body_y + 9 - arm_swing), 2)

    # Blade with proper gleam
    bx = cx + 12 * blade_dir
    by = body_y + 9 - arm_swing
    blade_end_x = bx + 5 * blade_dir
    blade_end_y = by - 4
    pygame.draw.line(s, pal["accent"], (bx, by), (blade_end_x, blade_end_y), 2)
    # Gleam highlight on blade
    gleam_phase = (frame * 0.3) % (math.pi * 2)
    gleam_pos = 0.5 + 0.5 * math.sin(gleam_phase)
    gx = int(bx + (blade_end_x - bx) * gleam_pos)
    gy = int(by + (blade_end_y - by) * gleam_pos)
    _circle(s, (255, 255, 255, 180), gx, gy, 1)

    # Head (angular, sharp)
    head_y = body_y - 3
    pts = [(cx - 5 + lean, head_y + 5), (cx - 6 + lean, head_y),
           (cx - 2 + lean, head_y - 4), (cx + 2 + lean, head_y - 4),
           (cx + 6 + lean, head_y), (cx + 5 + lean, head_y + 5)]
    pygame.draw.polygon(s, pal["outline"], pts)
    inner = [(cx - 4 + lean, head_y + 4), (cx - 5 + lean, head_y + 1),
             (cx - 1 + lean, head_y - 3), (cx + 1 + lean, head_y - 3),
             (cx + 5 + lean, head_y + 1), (cx + 4 + lean, head_y + 4)]
    pygame.draw.polygon(s, pal["body"], inner)

    # Visor (glowing, with after-image fade)
    visor_off = 1 if facing == "right" else -1
    visor_pulse = 0.5 + 0.5 * math.sin(frame * 0.3)
    visor_alpha = int(220 * visor_pulse)
    visor_color = (*pal["ant_tip"][:3], visor_alpha)
    _rect(s, visor_color, (cx - 4 + visor_off + lean, head_y, 8, 2))
    _rect(s, pal["eye_shine"], (cx - 1 + visor_off * 2 + lean, head_y, 3, 2))
    # Visor trail glow
    trail_alpha = int(60 * visor_pulse)
    _rect(s, (*pal["ant_tip"][:3], trail_alpha),
          (cx - 4 + visor_off + lean - lean * 2, head_y, 8, 2))

    return s


def _draw_tank_robot(pal, size=32, frame=0, facing="right"):
    """Tank: wide body, treads, dual exhaust, turret cannon."""
    s = _surf(size, size)
    cx = size // 2
    bounce = int(math.sin(frame * 0.3) * 1)
    body_y = 10 + bounce

    # Heavy dark shadow
    _ellipse(s, (0, 0, 0, 70), (cx - 14, size - 5, 28, 6))

    # Treads (boots color) with clear rolling teeth
    tread_y = body_y + 15
    tread_phase = (frame * 2) % 8
    for side_x in [cx - 14, cx + 5]:
        _rect(s, pal["outline"], (side_x, tread_y, 10, 9), border_radius=2)
        _rect(s, pal["boots"], (side_x + 1, tread_y + 1, 8, 7), border_radius=1)
        # Rolling tread teeth
        for i in range(4):
            tx = side_x + 1 + ((i * 2 + tread_phase) % 8)
            if tx < side_x + 9:
                _rect(s, pal["outline"], (tx, tread_y + 2, 1, 5))
        # Wheel circles at ends
        _circle(s, pal["outline"], side_x + 2, tread_y + 4, 2)
        _circle(s, pal["boots"], side_x + 2, tread_y + 4, 1)
        _circle(s, pal["outline"], side_x + 7, tread_y + 4, 2)
        _circle(s, pal["boots"], side_x + 7, tread_y + 4, 1)

    # Body (wider, fills the cell)
    _rect(s, pal["outline"], (cx - 13, body_y, 26, 16), border_radius=3)
    _rect(s, pal["body"], (cx - 12, body_y + 1, 24, 14), border_radius=2)
    _rect(s, pal["body_dark"], (cx - 12, body_y + 8, 24, 7), border_radius=2)
    _rect(s, pal["body_lit"], (cx - 10, body_y + 2, 8, 5))
    # Belly plate
    _rect(s, pal["belly"], (cx - 8, body_y + 4, 16, 8), border_radius=2)
    # Welded seam lines
    pygame.draw.line(s, pal["body_dark"], (cx - 12, body_y + 7), (cx + 12, body_y + 7), 1)
    pygame.draw.line(s, pal["body_dark"], (cx, body_y + 2), (cx, body_y + 14), 1)
    # Accent stripes
    _rect(s, pal["accent"], (cx - 12, body_y + 1, 24, 1))
    _rect(s, pal["accent"], (cx - 12, body_y + 14, 24, 1))
    # Rivets in grid
    for rx in [cx - 10, cx - 5, cx + 4, cx + 9]:
        for ry in [body_y + 3, body_y + 12]:
            _circle(s, pal["accent"], rx, ry, 1)

    # Dual exhaust pipes with animated smoke
    for pipe_off in [-1, 1]:
        pipe_side = -1 if facing == "right" else 1
        px = cx + pipe_side * 12
        py = body_y + 1 + pipe_off * 3
        _rect(s, pal["antenna"], (px, py, 3, 3), border_radius=1)
        _circle(s, pal["outline"], px + 1, py + 1, 1)
        # Smoke puffs rising
        for sp in range(2):
            smoke_t = (frame * 0.15 + sp * 1.5 + pipe_off) % 3
            smoke_y = py - 2 - int(smoke_t * 3)
            smoke_a = max(0, int(70 - smoke_t * 25))
            smoke_r = 1 + int(smoke_t)
            _circle(s, (180, 180, 190, smoke_a), px + 1 + pipe_side, smoke_y, smoke_r)

    # Turret cannon (slowly sweeps)
    cannon_dir = 1 if facing == "right" else -1
    turret_sweep = math.sin(frame * 0.08) * 0.3
    cannon_angle = turret_sweep
    cannon_x = cx + cannon_dir * 5
    cannon_y = body_y + 3
    # Turret base
    _circle(s, pal["outline"], cx, body_y + 2, 4)
    _circle(s, pal["body"], cx, body_y + 2, 3)
    _circle(s, pal["accent"], cx, body_y + 2, 1)
    # Barrel
    barrel_len = 12
    barrel_ex = cannon_x + int(math.cos(cannon_angle) * barrel_len * cannon_dir)
    barrel_ey = cannon_y + int(math.sin(cannon_angle) * barrel_len)
    pygame.draw.line(s, pal["outline"], (cannon_x, cannon_y), (barrel_ex, barrel_ey), 3)
    pygame.draw.line(s, pal["accent"], (cannon_x, cannon_y), (barrel_ex, barrel_ey), 2)
    # Muzzle brake
    _rect(s, pal["accent"], (barrel_ex - 1, barrel_ey - 2, 3, 5))

    # Head: small armored dome with scanning light
    head_y = body_y - 4
    _rect(s, pal["outline"], (cx - 5, head_y - 2, 10, 6), border_radius=3)
    _rect(s, pal["body"], (cx - 4, head_y - 1, 8, 4), border_radius=2)
    # Scanning light sweep
    scan_phase = (math.sin(frame * 0.2) + 1) * 0.5
    scan_x = cx - 3 + int(scan_phase * 6)
    visor_off = 1 if facing == "right" else -1
    _rect(s, pal["eye_white"], (cx - 3 + visor_off, head_y, 6, 2))
    _circle(s, pal["eye_shine"], scan_x, head_y + 1, 1)

    # Antenna stub
    _rect(s, pal["antenna"], (cx, head_y - 4, 1, 3))
    _circle(s, pal["ant_tip"], cx, head_y - 4, 1)

    return s


def _draw_drone_robot(pal, size=32, frame=0, facing="right"):
    """Drone: crossed propellers, scanning beam, side thrusters."""
    s = _surf(size, size)
    cx = size // 2
    hover = int(math.sin(frame * 0.4) * 3)  # More pronounced hover bob
    body_y = 12 + hover

    # Bigger hover glow
    glow_pulse = 0.5 + 0.5 * math.sin(frame * 0.3)
    glow_alpha = max(0, int(65 * glow_pulse))
    _ellipse(s, (*pal["ant_tip"][:3], glow_alpha), (cx - 10, size - 7, 20, 6))
    _ellipse(s, (*pal["ant_tip"][:3], max(0, glow_alpha // 2)), (cx - 7, size - 5, 14, 4))
    _ellipse(s, (*pal["ant_tip"][:3], max(0, glow_alpha // 3)), (cx - 5, size - 4, 10, 3))

    # Crossed propeller blades (2 lines that rotate)
    prop_y = body_y - 8
    _rect(s, pal["antenna"], (cx - 1, prop_y, 2, 5))
    prop_angle = frame * 0.9
    prop_len = 11
    for blade_idx in range(2):
        angle = prop_angle + blade_idx * (math.pi / 2)
        bx1 = cx + int(math.cos(angle) * prop_len)
        by1 = prop_y + int(math.sin(angle) * 2)
        bx2 = cx - int(math.cos(angle) * prop_len)
        by2 = prop_y - int(math.sin(angle) * 2)
        pygame.draw.line(s, pal["outline"], (bx1, by1), (bx2, by2), 2)
        pygame.draw.line(s, pal["accent"], (bx1, by1), (bx2, by2), 1)
    # Hub
    _circle(s, pal["outline"], cx, prop_y, 2)
    _circle(s, pal["ant_tip"], cx, prop_y, 1)

    # Body (rounded techy)
    _ellipse(s, pal["outline"], (cx - 10, body_y - 2, 20, 14))
    _ellipse(s, pal["body"], (cx - 9, body_y - 1, 18, 12))
    _ellipse(s, pal["body_dark"], (cx - 9, body_y + 4, 18, 7))
    _ellipse(s, pal["body_lit"], (cx - 6, body_y - 1, 8, 5))
    # Belly panel
    _rect(s, pal["belly"], (cx - 5, body_y + 1, 10, 6), border_radius=2)
    # Tech panel lines
    pygame.draw.line(s, pal["body_dark"], (cx - 4, body_y + 2), (cx + 4, body_y + 2), 1)
    pygame.draw.line(s, pal["body_dark"], (cx - 3, body_y + 5), (cx + 3, body_y + 5), 1)
    # Blinking status lights
    light1_on = (frame // 6) % 3 == 0
    light2_on = (frame // 6) % 3 == 1
    if light1_on:
        _circle(s, (80, 255, 80), cx - 3, body_y + 3, 1)
    else:
        _circle(s, (40, 80, 40), cx - 3, body_y + 3, 1)
    if light2_on:
        _circle(s, (255, 80, 80), cx + 3, body_y + 3, 1)
    else:
        _circle(s, (80, 40, 40), cx + 3, body_y + 3, 1)
    # Accent ring
    pygame.draw.ellipse(s, pal["accent"], (cx - 10, body_y - 2, 20, 14), 1)

    # Sensor eye: bigger with scanning beam
    eye_x = cx + (2 if facing == "right" else -2)
    eye_y = body_y + 3
    _circle(s, pal["outline"], eye_x, eye_y, 5)
    _circle(s, pal["eye_white"], eye_x, eye_y, 4)
    pupil_off = 1 if facing == "right" else -1
    _circle(s, pal["eye_pupil"], eye_x + pupil_off, eye_y, 2)
    scan_pulse = 0.5 + 0.5 * math.sin(frame * 0.25)
    scan_alpha = int(140 * scan_pulse)
    _circle(s, (*pal["ant_tip"][:3], scan_alpha), eye_x + pupil_off, eye_y, 1)
    _circle(s, pal["eye_shine"], eye_x + pupil_off - 1, eye_y - 1, 1)
    # Scanning beam going down
    beam_len = 6 + int(scan_pulse * 4)
    for bl in range(beam_len):
        ba = max(0, int(80 * scan_pulse * (1 - bl / beam_len)))
        _rect(s, (*pal["ant_tip"][:3], ba), (eye_x + pupil_off - 1, eye_y + 5 + bl, 3, 1))

    # Side thrusters with animated flame/glow
    for side in [-1, 1]:
        tx = cx + side * 10
        ty = body_y + 4
        _rect(s, pal["outline"], (tx - 2, ty, 4, 4), border_radius=1)
        _rect(s, pal["accent"], (tx - 1, ty + 1, 2, 2))
        # Flame glow: animated flicker
        flame_flicker = 0.5 + 0.5 * math.sin(frame * 0.6 + side * 2)
        flame_a = int(70 * flame_flicker)
        _circle(s, (*pal["ant_tip"][:3], flame_a), tx, ty + 6, 3)
        _circle(s, (255, 200, 100, int(flame_a * 0.5)), tx, ty + 5, 2)

    # Antenna array (multiple sticks)
    for ax_off in [-6, -3, 6, 3]:
        ah = 2 + abs(ax_off) // 2
        _rect(s, pal["antenna"], (cx + ax_off, body_y - 4 - ah, 1, ah))
        _circle(s, pal["ant_tip"], cx + ax_off, body_y - 4 - ah, 0)

    return s


def _draw_knight_robot(pal, size=32, frame=0, facing="right"):
    """Knight: T-visor helmet, plume, shield, sword, cape."""
    s = _surf(size, size)
    cx = size // 2
    bounce = int(math.sin(frame * 0.5) * 1)
    body_y = 9 + bounce
    leg_offset = int(math.sin(frame * 0.6) * 2)

    _ellipse(s, (0, 0, 0, 45), (cx - 9, size - 4, 18, 4))

    # Legs with articulated armor joints
    leg_y = body_y + 15
    for lx, off in [(cx - 6 - leg_offset, 0), (cx + 2 + leg_offset, 0)]:
        _rect(s, pal["outline"], (lx, leg_y, 5, 8), border_radius=1)
        _rect(s, pal["body_dark"], (lx + 1, leg_y + 1, 3, 6), border_radius=1)
        _rect(s, pal["accent"], (lx + 1, leg_y + 1, 3, 1))
        # Knee joint
        _circle(s, pal["accent"], lx + 2, leg_y + 3, 1)
        # Armored boots
        _rect(s, pal["boots"], (lx - 1, leg_y + 6, 7, 3), border_radius=1)
        _rect(s, pal["accent"], (lx, leg_y + 6, 5, 1))

    # Cape/tabard hanging from belt (uses belly color, flowing fabric)
    cape_wave = math.sin(frame * 0.35)
    for ci in range(4):
        cape_alpha = max(80, 200 - ci * 30)
        c_off = int(math.sin(frame * 0.35 + ci * 0.5) * (1 + ci * 0.5))
        _rect(s, (*pal["belly"][:3], cape_alpha),
              (cx - 4 + c_off, body_y + 13 + ci * 2, 8, 3), border_radius=1)

    # Shield (belly colored with emblem: inner circle + decorative border)
    shield_side = -1 if facing == "right" else 1
    shield_x = cx + shield_side * 10
    shield_y = body_y + 3
    shield_pts = [
        (shield_x - 5, shield_y), (shield_x + 5, shield_y),
        (shield_x + 5, shield_y + 9), (shield_x, shield_y + 13),
        (shield_x - 5, shield_y + 9),
    ]
    pygame.draw.polygon(s, pal["outline"], shield_pts)
    inner_shield = [
        (shield_x - 4, shield_y + 1), (shield_x + 4, shield_y + 1),
        (shield_x + 4, shield_y + 8), (shield_x, shield_y + 12),
        (shield_x - 4, shield_y + 8),
    ]
    pygame.draw.polygon(s, pal["belly"], inner_shield)
    # Decorative border (inner outline)
    inner_border = [
        (shield_x - 3, shield_y + 2), (shield_x + 3, shield_y + 2),
        (shield_x + 3, shield_y + 7), (shield_x, shield_y + 10),
        (shield_x - 3, shield_y + 7),
    ]
    pygame.draw.polygon(s, pal["accent"], inner_border, 1)
    # Central emblem: circle with cross
    _circle(s, pal["accent"], shield_x, shield_y + 5, 3)
    _circle(s, pal["belly"], shield_x, shield_y + 5, 2)
    pygame.draw.line(s, pal["accent"], (shield_x, shield_y + 3), (shield_x, shield_y + 7), 1)
    pygame.draw.line(s, pal["accent"], (shield_x - 2, shield_y + 5), (shield_x + 2, shield_y + 5), 1)

    # Sword arm (proper hilt, crossguard, gleaming blade)
    sword_side = 1 if facing == "right" else -1
    sword_x = cx + sword_side * 10
    sword_y = body_y + 3
    arm_swing = int(math.sin(frame * 0.4 + 0.5) * 3)
    pygame.draw.line(s, pal["outline"], (cx + sword_side * 6, body_y + 5),
                     (sword_x, sword_y + arm_swing), 2)
    # Hilt (hand grip)
    _rect(s, pal["boots"], (sword_x - 1, sword_y + arm_swing, 3, 3))
    # Crossguard
    _rect(s, pal["accent"], (sword_x - 3, sword_y + arm_swing - 1, 7, 2))
    # Blade
    blade_tip_y = sword_y + arm_swing - 11
    pygame.draw.line(s, pal["accent"], (sword_x, sword_y + arm_swing - 1),
                     (sword_x, blade_tip_y), 2)
    pygame.draw.line(s, (230, 235, 255), (sword_x, sword_y + arm_swing - 1),
                     (sword_x, blade_tip_y), 1)
    # Blade gleam (traveling highlight)
    gleam_t = (frame * 0.2) % 1.0
    gleam_y = int(sword_y + arm_swing - 1 + (blade_tip_y - sword_y - arm_swing + 1) * gleam_t)
    _circle(s, (255, 255, 255, 200), sword_x, gleam_y, 1)

    # Body (armored torso)
    _rect(s, pal["outline"], (cx - 7, body_y + 1, 14, 15), border_radius=2)
    _rect(s, pal["body"], (cx - 6, body_y + 2, 12, 13), border_radius=1)
    _rect(s, pal["body_lit"], (cx - 4, body_y + 3, 8, 5), border_radius=1)
    _rect(s, pal["belly"], (cx - 3, body_y + 4, 6, 3), border_radius=1)

    # Armored pauldrons (shoulder plates above body)
    for side in [-1, 1]:
        px = cx + side * 7
        _rect(s, pal["outline"], (px - 3, body_y, 7, 4), border_radius=2)
        _rect(s, pal["body_lit"], (px - 2, body_y + 1, 5, 2), border_radius=1)
        _rect(s, pal["accent"], (px - 2, body_y, 5, 1))

    # Accent belt
    _rect(s, pal["accent"], (cx - 7, body_y + 11, 14, 2))
    _rect(s, pal["ant_tip"], (cx - 1, body_y + 11, 2, 2))

    # Helmet with T-shaped visor opening
    head_y = body_y - 4
    _rect(s, pal["outline"], (cx - 7, head_y - 3, 14, 10), border_radius=3)
    _rect(s, pal["body"], (cx - 6, head_y - 2, 12, 8), border_radius=2)
    _rect(s, pal["body_lit"], (cx - 5, head_y - 2, 5, 3), border_radius=1)
    # Accent trim on helmet crest
    _rect(s, pal["accent"], (cx - 7, head_y - 3, 14, 1))
    # T-visor: horizontal top + vertical slit
    _rect(s, pal["outline"], (cx - 5, head_y + 1, 10, 2))  # horizontal bar
    _rect(s, pal["outline"], (cx - 1, head_y + 1, 2, 4))    # vertical slit
    # Visor glow inside T
    _rect(s, (15, 15, 25), (cx - 4, head_y + 1, 8, 1))
    visor_off = 1 if facing == "right" else -1
    _rect(s, pal["eye_white"], (cx - 3 + visor_off, head_y + 1, 3, 1))
    _rect(s, pal["eye_white"], (cx + 1 + visor_off, head_y + 1, 3, 1))

    # Plume (ant_tip color, more segments, dynamic flow)
    plume_wave = math.sin(frame * 0.4)
    plume_base_y = head_y - 5
    for i in range(6):
        plume_alpha = max(40, 230 - i * 35)
        plume_c = (*pal["ant_tip"][:3], plume_alpha)
        wave_off = int(math.sin(frame * 0.4 + i * 0.6) * (1 + i * 0.5))
        px = cx + wave_off
        py = plume_base_y - i
        r = max(1, 3 - i // 2)
        _circle(s, plume_c, px, py, r)
    _circle(s, pal["ant_tip"], cx, plume_base_y + 1, 2)

    return s


def _draw_claude_robot(pal, size=32, frame=0, facing="right"):
    """Round head, expressive eyes, terminal chest panel."""
    s = _surf(size, size)
    cx = size // 2

    # Squash-and-stretch bounce
    bounce_raw = math.sin(frame * 0.4)
    bounce = int(bounce_raw * 1.5)
    body_y = 9 + bounce
    leg_offset = int(math.sin(frame * 0.6) * 2)

    # Breathing (subtle torso width pulse)
    breath = math.sin(frame * 0.12) * 0.6

    # Shadow
    shadow_w = int(16 + bounce_raw * 2)
    _ellipse(s, (0, 0, 0, 40), (cx - shadow_w // 2, size - 4, shadow_w, 4))

    # Legs: simple rectangular, clean
    leg_y = body_y + 16
    for lx, off in [(cx - 6 - leg_offset, 0), (cx + 3 + leg_offset, 0)]:
        _rect(s, pal["outline"], (lx, leg_y, 4, 7), border_radius=1)
        _rect(s, pal["boots"], (lx + 1, leg_y + 1, 2, 5), border_radius=1)
        # Feet
        _rect(s, pal["outline"], (lx - 1, leg_y + 5, 6, 3), border_radius=1)
        _rect(s, pal["boots"], (lx, leg_y + 6, 4, 1))

    # Body: rounder, warmer shape (less boxy)
    bw = int(16 + breath)
    bh = 15
    _rect(s, pal["outline"], (cx - bw // 2, body_y + 2, bw, bh), border_radius=4)
    _rect(s, pal["body"], (cx - bw // 2 + 1, body_y + 3, bw - 2, bh - 2), border_radius=3)

    # Chest terminal panel with 3 animated text lines
    _rect(s, pal["belly"], (cx - 5, body_y + 5, 10, 9), border_radius=2)
    # Animated text lines (shift positions)
    text_offset = (frame // 12) % 3
    line_widths = [6, 4, 5]
    for li in range(3):
        lw = line_widths[(li + text_offset) % 3]
        ly = body_y + 7 + li * 2
        _rect(s, pal["accent"], (cx - 3, ly, lw, 1))
    # Blinking cursor: more visible
    cursor_blink = (frame // 6) % 2
    if cursor_blink:
        cursor_y = body_y + 7 + (text_offset % 3) * 2
        _rect(s, pal["ant_tip"], (cx + 3, cursor_y, 2, 1))

    # Arms: mitten-like rounded hands
    arm_swing = int(math.sin(frame * 0.4) * 2)
    for side, sw in [(-1, arm_swing), (1, -arm_swing)]:
        ax = cx + side * (bw // 2 + 1)
        ay = body_y + 4 + sw
        _rect(s, pal["outline"], (ax - 1, ay, 3, 9), border_radius=1)
        _rect(s, pal["body_dark"], (ax, ay + 1, 1, 7))
        # Mitten hand (rounded circle instead of rectangle)
        _circle(s, pal["outline"], ax, ay + 10, 2)
        _circle(s, pal["body_dark"], ax, ay + 10, 1)

    # Head: bigger, rounder, friendlier
    head_y = body_y - 4
    _rect(s, pal["outline"], (cx - 8, head_y - 5, 16, 11), border_radius=5)
    _rect(s, pal["body"], (cx - 7, head_y - 4, 14, 9), border_radius=4)
    _rect(s, pal["body_lit"], (cx - 6, head_y - 4, 7, 3), border_radius=2)

    # Eyes: expressive with pupils that look around and blinking
    visor_off = 1 if facing == "right" else -1
    # Pupil shift based on facing + idle wandering
    idle_look_x = int(math.sin(frame * 0.1) * 1)
    pupil_dx = visor_off + idle_look_x
    pupil_dy = int(math.sin(frame * 0.08 + 1) * 0.5)

    # Blink: every ~40 frames, squint for 3 frames
    blink_cycle = frame % 42
    is_blinking = blink_cycle >= 39

    # Left eye
    lex, ley = cx - 4, head_y - 1
    if is_blinking:
        # Closed eye: flat line
        pygame.draw.line(s, pal["outline"], (lex - 1, ley + 1), (lex + 2, ley + 1), 1)
    else:
        _rect(s, pal["eye_white"], (lex - 1, ley, 4, 3), border_radius=1)
        _circle(s, pal["eye_pupil"], lex + 1 + pupil_dx, ley + 1 + pupil_dy, 1)
        _rect(s, pal["eye_shine"], (lex + pupil_dx, ley, 1, 1))

    # Right eye
    rex, rey = cx + 3, head_y - 1
    if is_blinking:
        pygame.draw.line(s, pal["outline"], (rex - 1, rey + 1), (rex + 2, rey + 1), 1)
    else:
        _rect(s, pal["eye_white"], (rex - 1, rey, 4, 3), border_radius=1)
        _circle(s, pal["eye_pupil"], rex + 1 + pupil_dx, rey + 1 + pupil_dy, 1)
        _rect(s, pal["eye_shine"], (rex + pupil_dx, rey, 1, 1))

    # Cheek blush marks (translucent pink circles)
    _circle(s, pal["cheek"], cx - 5, head_y + 2, 2)
    _circle(s, pal["cheek"], cx + 5, head_y + 2, 2)

    # Mouth: small friendly line
    _rect(s, pal["accent"], (cx - 2, head_y + 4, 4, 1))

    # Antenna: thin with glowing orb and pulsing halo
    _rect(s, pal["antenna"], (cx - 1, head_y - 9, 2, 5))
    # Pulsing halo glow (bigger outer ring)
    glow_pulse = 0.5 + 0.5 * math.sin(frame * 0.3)
    glow_alpha = max(0, int(60 * glow_pulse))
    _circle(s, (*pal["ant_tip"][:3], max(0, glow_alpha // 2)), cx, head_y - 10, 6)
    _circle(s, (*pal["ant_tip"][:3], glow_alpha), cx, head_y - 10, 4)
    _circle(s, pal["ant_tip"], cx, head_y - 10, 2)
    _circle(s, (255, 255, 255), cx, head_y - 11, 1)

    return s


ROBOT_DESIGNS = {
    "claude":  _draw_claude_robot,
    "mech":   _draw_mech_robot,
    "ninja":  _draw_ninja_robot,
    "tank":   _draw_tank_robot,
    "drone":  _draw_drone_robot,
    "knight": _draw_knight_robot,
}


# =============================================================================
# Waste Sprites: radioactive barrels
# =============================================================================

def _draw_waste(pal, size=32, frame=0):
    s = _surf(size + 8, size + 8)
    cx, cy = size // 2 + 4, size // 2 + 4

    pulse = 0.5 + 0.5 * math.sin(frame * 0.35)

    # Dramatic glow halo
    glow_r = int(14 * pulse) + 5
    glow_color = (*pal["glow"][:3], int(45 * pulse))
    _circle(s, glow_color, cx, cy, glow_r + 5)
    _circle(s, glow_color, cx, cy, glow_r + 3)
    _circle(s, glow_color, cx, cy, glow_r)

    # Determine barrel variant by palette color hue
    is_green = pal["core"][1] > pal["core"][0] and pal["core"][1] > pal["core"][2]
    is_red = pal["core"][0] > pal["core"][1] and pal["core"][0] > pal["core"][2]

    if is_green:
        # Small round canister
        barrel_w, barrel_h = 10, 12
        bx, by = cx - barrel_w // 2, cy - barrel_h // 2

        # Barrel body
        _rect(s, pal["dark"], (bx, by, barrel_w, barrel_h), border_radius=3)
        _rect(s, pal["core"], (bx + 1, by + 1, barrel_w - 2, barrel_h - 2), border_radius=2)
        # Highlight
        _rect(s, pal["light"], (bx + 2, by + 2, 3, barrel_h - 4), border_radius=1)
        # Lid
        _rect(s, pal["dark"], (bx - 1, by - 1, barrel_w + 2, 3), border_radius=1)
        _rect(s, pal["dark"], (bx - 1, by + barrel_h - 2, barrel_w + 2, 3), border_radius=1)

        # Hazard trefoil: 3 small wedges around center dot
        for angle_deg in [0, 120, 240]:
            rad = math.radians(angle_deg)
            dx = int(math.cos(rad) * 3)
            dy = int(math.sin(rad) * 3)
            _circle(s, pal["dark"], cx + dx, cy + dy, 1)
        _circle(s, pal["light"], cx, cy, 1)

        # Leaking green goo drops
        for di in range(2):
            drop_y = cy + barrel_h // 2 + 1 + int((frame * 0.3 + di * 4) % 6)
            drop_a = max(0, 180 - int((frame * 0.3 + di * 4) % 6) * 30)
            drop_x = cx - 2 + di * 4
            _circle(s, (*pal["glow"][:3], drop_a), drop_x, drop_y, 1)

    elif is_red:
        # Large reinforced container
        barrel_w, barrel_h = 14, 14
        bx, by = cx - barrel_w // 2, cy - barrel_h // 2

        # Barrel body
        _rect(s, pal["dark"], (bx, by, barrel_w, barrel_h), border_radius=2)
        _rect(s, pal["core"], (bx + 1, by + 1, barrel_w - 2, barrel_h - 2), border_radius=1)
        _rect(s, pal["light"], (bx + 2, by + 2, 3, barrel_h - 4))
        # Reinforcement bands
        _rect(s, pal["dark"], (bx, by + 3, barrel_w, 2))
        _rect(s, pal["dark"], (bx, by + barrel_h - 5, barrel_w, 2))
        # Lid
        _rect(s, pal["dark"], (bx - 1, by - 1, barrel_w + 2, 3), border_radius=1)
        _rect(s, pal["dark"], (bx - 1, by + barrel_h - 2, barrel_w + 2, 3), border_radius=1)
        # Warning marking: X
        pygame.draw.line(s, (255, 220, 50), (cx - 3, cy - 3), (cx + 3, cy + 3), 1)
        pygame.draw.line(s, (255, 220, 50), (cx + 3, cy - 3), (cx - 3, cy + 3), 1)

        # Hazard trefoil
        for angle_deg in [0, 120, 240]:
            rad = math.radians(angle_deg)
            dx = int(math.cos(rad) * 3)
            dy = int(math.sin(rad) * 3)
            _circle(s, pal["dark"], cx + dx, cy + dy, 1)
        _circle(s, pal["light"], cx, cy, 1)

    else:
        # Medium barrel (yellow): dented, warning tape stripe
        barrel_w, barrel_h = 12, 13
        bx, by = cx - barrel_w // 2, cy - barrel_h // 2

        # Barrel body
        _rect(s, pal["dark"], (bx, by, barrel_w, barrel_h), border_radius=2)
        _rect(s, pal["core"], (bx + 1, by + 1, barrel_w - 2, barrel_h - 2), border_radius=1)
        _rect(s, pal["light"], (bx + 2, by + 2, 3, barrel_h - 4))
        # Dent (dark circle)
        _circle(s, pal["dark"], cx + 2, cy + 2, 2)
        # Lid
        _rect(s, pal["dark"], (bx - 1, by - 1, barrel_w + 2, 3), border_radius=1)
        _rect(s, pal["dark"], (bx - 1, by + barrel_h - 2, barrel_w + 2, 3), border_radius=1)
        # Warning tape stripe (diagonal)
        for ti in range(0, barrel_w, 3):
            _rect(s, (40, 40, 40), (bx + ti, cy - 1, 2, 2))

        # Hazard trefoil
        for angle_deg in [0, 120, 240]:
            rad = math.radians(angle_deg)
            dx = int(math.cos(rad) * 3)
            dy = int(math.sin(rad) * 3)
            _circle(s, pal["dark"], cx + dx, cy + dy, 1)
        _circle(s, pal["light"], cx, cy, 1)

    # Bubbling effect: small circles rising from top
    for bi in range(3):
        bubble_phase = (frame * 0.2 + bi * 2.5) % 5
        bubble_y = cy - 8 - int(bubble_phase * 2)
        bubble_a = max(0, int(150 - bubble_phase * 35))
        bubble_x = cx - 2 + bi * 2 + int(math.sin(frame * 0.3 + bi) * 1)
        _circle(s, (*pal["glow"][:3], bubble_a), bubble_x, bubble_y, 1)

    return s


# =============================================================================
# Disposal Zone Sprite: containment facility
# =============================================================================

def _draw_disposal(size=32, frame=0):
    s = _surf(size, size)
    # Metallic colors
    metal = (85, 95, 110)
    metal_dark = (55, 62, 75)
    metal_light = (120, 130, 150)
    metal_highlight = (150, 165, 185)

    # Armored vault door (thick rectangle, rounded)
    _rect(s, metal_dark, (4, 5, 24, 24), border_radius=3)
    _rect(s, metal, (5, 6, 22, 22), border_radius=2)
    # Metallic sheen highlight
    _rect(s, metal_light, (6, 6, 6, 20), border_radius=1)
    _rect(s, metal_dark, (22, 6, 4, 20), border_radius=1)

    # Hazard stripes on edges (yellow/black diagonal)
    stripe_yellow = (210, 180, 30)
    stripe_black = (30, 30, 30)
    for i in range(0, 24, 4):
        y_top = 5 + i
        if y_top < 28:
            _rect(s, stripe_yellow, (4, y_top, 2, 2))
            _rect(s, stripe_black, (4, y_top + 2, 2, 2))
            _rect(s, stripe_yellow, (26, y_top, 2, 2))
            _rect(s, stripe_black, (26, y_top + 2, 2, 2))

    # Central circular vent/intake with glowing ring
    vent_cx, vent_cy = 16, 17
    pulse = 0.5 + 0.5 * math.sin(frame * 0.25)
    glow_a = int(80 * pulse)
    _circle(s, (100, 200, 255, glow_a), vent_cx, vent_cy, 7)
    _circle(s, metal_dark, vent_cx, vent_cy, 5)
    _circle(s, metal, vent_cx, vent_cy, 4)
    pygame.draw.circle(s, metal_light, (vent_cx, vent_cy), 4, 1)
    _circle(s, (100, 200, 255, int(140 * pulse)), vent_cx, vent_cy, 3)
    _circle(s, metal_dark, vent_cx, vent_cy, 2)

    # Hazard chevrons above vent
    chevron_c = (210, 180, 30)
    pygame.draw.line(s, chevron_c, (12, 8), (16, 6), 1)
    pygame.draw.line(s, chevron_c, (16, 6), (20, 8), 1)
    pygame.draw.line(s, chevron_c, (12, 10), (16, 8), 1)
    pygame.draw.line(s, chevron_c, (16, 8), (20, 10), 1)

    # Status lights (small blinking dots)
    light1_on = (frame // 8) % 2 == 0
    light2_on = (frame // 8) % 2 == 1
    _circle(s, (80, 255, 80) if light1_on else (30, 80, 30), 8, 26, 1)
    _circle(s, (255, 80, 80) if light2_on else (80, 30, 30), 24, 26, 1)
    _circle(s, (80, 80, 255), 16, 26, 1)  # always-on blue

    # Bottom rim
    _rect(s, metal_dark, (4, 27, 24, 3), border_radius=1)
    _rect(s, metal_highlight, (5, 27, 22, 1))

    return s


# =============================================================================
# Tile Textures
# =============================================================================

def _make_zone1_tile(size, parity):
    """Grassland tile: greens, mushrooms, wildflowers, moss."""
    s = pygame.Surface((size, size))
    wc = WORLD_COLORS

    # Base grass with variation
    if parity == 0:
        s.fill(wc["z1_grass_top"])
        _rect(s, wc["z1_grass_mid"], (0, size // 2, size, size // 2))
    else:
        s.fill(wc["z1_grass_mid"])
        _rect(s, wc["z1_grass_top"], (0, 0, size, size // 2))

    # Multiple grass heights (tufts)
    tuft_light = tuple(min(255, c + 35) for c in wc["z1_grass_top"])
    tuft_dark = tuple(max(0, c - 10) for c in wc["z1_grass_top"])
    grass_positions = [(4, 8), (14, 4), (24, 10), (8, 22), (20, 26), (28, 16),
                       (10, 14), (18, 20), (2, 18), (26, 6)]
    for i, (px, py) in enumerate(grass_positions):
        if px < size and py < size:
            h = 3 + (i % 3)
            tc = tuft_light if i % 2 == 0 else tuft_dark
            pygame.draw.line(s, tc, (px, py), (px - 1, py - h), 1)
            pygame.draw.line(s, tc, (px, py), (px + 1, py - h + 1), 1)

    # Moss patches (darker green irregular shapes)
    moss_c = tuple(max(0, c - 25) for c in wc["z1_grass_mid"])
    if parity == 0:
        _circle(s, moss_c, 6, 20, 2)
        _circle(s, moss_c, 22, 24, 3)
    else:
        _circle(s, moss_c, 14, 18, 2)
        _circle(s, moss_c, 28, 10, 2)

    # Wildflower clusters (bright dots)
    if parity == 0:
        _circle(s, wc["z1_flower1"], 10, 14, 1)
        _circle(s, wc["z1_flower2"], 22, 20, 1)
        _circle(s, (180, 120, 255), 16, 8, 1)  # purple wildflower
    else:
        _circle(s, wc["z1_flower2"], 8, 10, 1)
        _circle(s, (255, 160, 200), 26, 18, 1)  # pink wildflower
        _circle(s, wc["z1_flower1"], 18, 26, 1)

    # Small mushrooms (tiny colored caps)
    if parity == 1:
        # Stem
        pygame.draw.line(s, (200, 180, 150), (4, 28), (4, 26), 1)
        # Cap
        _circle(s, (200, 60, 50), 4, 25, 2)
        _circle(s, (255, 255, 200), 3, 24, 0)  # spot

    # Tiny puddle (blue-grey reflective spot)
    if parity == 0:
        puddle_c = (120, 150, 180, 80)
        _ellipse(s, puddle_c, (18, 28, 6, 2))

    # Beetle/bug dots
    bug_x = 12 + parity * 8
    bug_y = 6 + parity * 14
    if bug_x < size and bug_y < size:
        s.set_at((bug_x, bug_y), (30, 20, 15))
        s.set_at((bug_x + 1, bug_y), (30, 20, 15))

    return s


def _make_zone2_tile(size, parity):
    """Desert tile: sand ripples, rocks, cracks, cactus."""
    s = pygame.Surface((size, size))
    wc = WORLD_COLORS

    if parity == 0:
        s.fill(wc["z2_sand_top"])
        _rect(s, wc["z2_sand_mid"], (0, size // 2, size, size // 2))
    else:
        s.fill(wc["z2_sand_mid"])
        _rect(s, wc["z2_sand_top"], (0, 0, size, size // 2))

    # Wind ripple lines (curved wavy lines)
    ripple_c = tuple(max(0, c - 12) for c in wc["z2_sand_top"])
    for ry in [8, 16, 24]:
        points = []
        for rx in range(0, size, 4):
            wave_y = ry + int(math.sin(rx * 0.3 + parity * 2) * 1.5)
            points.append((rx, wave_y))
        if len(points) > 1:
            pygame.draw.lines(s, ripple_c, False, points, 1)

    # Dried crack patterns (branching brown lines)
    crack = wc["z2_crack"]
    if parity == 0:
        pygame.draw.line(s, crack, (3, 10), (10, 14), 1)
        pygame.draw.line(s, crack, (7, 12), (5, 18), 1)  # branch
        pygame.draw.line(s, crack, (18, 5), (26, 10), 1)
        pygame.draw.line(s, crack, (22, 7), (24, 3), 1)  # branch
        pygame.draw.line(s, crack, (12, 22), (20, 28), 1)
    else:
        pygame.draw.line(s, crack, (5, 8), (14, 6), 1)
        pygame.draw.line(s, crack, (9, 7), (8, 12), 1)
        pygame.draw.line(s, crack, (20, 18), (28, 22), 1)
        pygame.draw.line(s, crack, (24, 20), (22, 25), 1)

    # Scattered bones/fossils (tiny white shapes)
    bone_c = (230, 220, 200)
    if parity == 0:
        pygame.draw.line(s, bone_c, (22, 16), (25, 16), 1)
        s.set_at((23, 15), bone_c)  # bone knob
    else:
        pygame.draw.line(s, bone_c, (8, 24), (11, 24), 1)
        s.set_at((9, 23), bone_c)

    # Small rock cairns (stacked grey dots)
    pebble = wc["z2_rock_dark"]
    rock = wc["z2_rock"]
    if parity == 0:
        _circle(s, pebble, 8, 20, 2)
        _circle(s, rock, 8, 18, 1)
        _circle(s, pebble, 24, 12, 1)
    else:
        _circle(s, pebble, 26, 8, 2)
        _circle(s, rock, 26, 6, 1)
        _circle(s, rock, 27, 6, 0)

    # Tiny tumbleweed dot
    tumble_c = (140, 110, 60)
    if parity == 1:
        _circle(s, tumble_c, 14, 14, 1)

    # Occasional cactus silhouette (tiny green shape)
    if parity == 0:
        cactus_c = (70, 120, 50)
        pygame.draw.line(s, cactus_c, (28, 8), (28, 4), 1)
        s.set_at((27, 6), cactus_c)  # arm left
        s.set_at((29, 5), cactus_c) if 29 < size else None  # arm right

    # Heat haze suggestion (very faint wavy overlay)
    if parity == 1:
        haze_c = (255, 240, 200, 12)
        temp = _surf(size, 1)
        temp.fill(haze_c)
        s.blit(temp, (0, size // 3))

    return s


def _make_zone3_tile(size, parity):
    """Volcano tile: obsidian, lava, ash, embers."""
    s = pygame.Surface((size, size))
    wc = WORLD_COLORS

    if parity == 0:
        s.fill(wc["z3_stone_top"])
        _rect(s, wc["z3_stone_mid"], (0, size // 2, size, size // 2))
    else:
        s.fill(wc["z3_stone_mid"])
        _rect(s, wc["z3_stone_top"], (0, 0, size, size // 2))

    # Subtle stone texture lines (short segments, not full width)
    brick_line = tuple(max(0, c - 14) for c in wc["z3_stone_mid"])
    if parity == 0:
        pygame.draw.line(s, brick_line, (2, 10), (14, 10), 1)
        pygame.draw.line(s, brick_line, (18, 22), (28, 22), 1)
    else:
        pygame.draw.line(s, brick_line, (6, 8), (20, 8), 1)
        pygame.draw.line(s, brick_line, (0, 20), (12, 20), 1)

    # Crystal flecks (tiny bright dots on obsidian)
    crystal_colors = [(180, 160, 200), (150, 200, 180), (200, 180, 150)]
    fleck_positions = [(5, 3), (18, 7), (28, 14), (10, 19), (22, 25), (3, 28)]
    for i, (fx, fy) in enumerate(fleck_positions):
        if fx < size and fy < size:
            s.set_at((fx, fy), crystal_colors[i % len(crystal_colors)])

    # Lava-filled cracks that glow (orange/red lines with yellow center)
    lava = wc["z3_lava"]
    lava_g = wc["z3_lava_glow"]
    lava_center = (255, 200, 60)
    if parity == 0:
        pygame.draw.line(s, lava, (4, 20), (14, 24), 1)
        pygame.draw.line(s, lava_g, (5, 20), (13, 24), 1)
        pygame.draw.line(s, lava_center, (7, 21), (11, 23), 1)
        # Branch crack
        pygame.draw.line(s, lava, (9, 22), (6, 28), 1)
        pygame.draw.line(s, lava_g, (9, 23), (7, 27), 1)
    else:
        pygame.draw.line(s, lava, (16, 12), (26, 18), 1)
        pygame.draw.line(s, lava_g, (17, 12), (25, 18), 1)
        pygame.draw.line(s, lava_center, (19, 13), (23, 16), 1)
        pygame.draw.line(s, lava, (20, 14), (18, 20), 1)

    # Ash patches (grey speckle areas)
    ash_c = (100, 90, 95)
    for ax, ay in [(12, 6), (24, 10), (6, 16), (20, 22)]:
        if ax < size and ay < size:
            s.set_at((ax, ay), ash_c)
            if ax + 1 < size:
                s.set_at((ax + 1, ay), ash_c)

    # Ember dots (tiny orange dots scattered)
    ember_c = (255, 140, 40)
    ember_positions = [(8, 4), (22, 8), (14, 16), (26, 24), (4, 26)]
    for ex, ey in ember_positions:
        if ex < size and ey < size:
            s.set_at((ex, ey), ember_c)

    # Jagged rock formations (angular dark shapes)
    rock_dark = tuple(max(0, c - 20) for c in wc["z3_stone_mid"])
    if parity == 0:
        pts = [(26, 14), (28, 8), (30, 14)]
        if all(0 <= p[0] < size and 0 <= p[1] < size for p in pts):
            pygame.draw.polygon(s, rock_dark, pts)
    else:
        pts = [(2, 22), (4, 16), (6, 22)]
        pygame.draw.polygon(s, rock_dark, pts)

    # Subtle lava glow spots (not full-width bands)
    glow_c = wc["z3_lava_glow"]
    if parity == 0:
        _circle(s, (*glow_c[:3], 30), 8, size - 4, 3)
        _circle(s, (*glow_c[:3], 20), 24, size - 3, 2)
    else:
        _circle(s, (*glow_c[:3], 25), 16, size - 4, 3)

    return s


# =============================================================================
# Dark Terminal Tiles (Claude aesthetic)
# =============================================================================

def _make_dark_zone1_tile(size, parity):
    """Dark teal tile: circuit traces, hex grid."""
    s = pygame.Surface((size, size))
    dc = DARK_WORLD_COLORS
    s.fill(dc["z1_top"] if parity == 0 else dc["z1_mid"])

    # Subtle grid lines
    line_c = dc["z1_line"]
    pygame.draw.line(s, line_c, (0, 0), (size, 0), 1)
    pygame.draw.line(s, line_c, (0, 0), (0, size), 1)

    # Faint hex grid pattern
    hex_c = (*dc["z1_line"], 25)
    temp = _surf(size, size)
    for hy in range(0, size, 8):
        offset = 4 if (hy // 8) % 2 == 1 else 0
        for hx in range(offset, size, 8):
            pygame.draw.circle(temp, hex_c, (hx, hy), 3, 1)
    s.blit(temp, (0, 0))

    # Circuit-board traces (thin lines connecting dots)
    trace_c = (*dc["z1_dot"], 70)
    dot_positions = [(4, 4), (size - 4, 4), (4, size - 4), (size - 4, size - 4),
                     (size // 2, size // 2)]
    temp2 = _surf(size, size)
    for i, (px, py) in enumerate(dot_positions):
        pygame.draw.rect(temp2, trace_c, (px - 1, py - 1, 3, 3))
    # Connect traces
    if parity == 0:
        pygame.draw.line(temp2, trace_c, dot_positions[0], dot_positions[4], 1)
        pygame.draw.line(temp2, trace_c, dot_positions[4], dot_positions[3], 1)
        pygame.draw.line(temp2, trace_c, dot_positions[1], (dot_positions[1][0], size // 2), 1)
    else:
        pygame.draw.line(temp2, trace_c, dot_positions[1], dot_positions[4], 1)
        pygame.draw.line(temp2, trace_c, dot_positions[4], dot_positions[2], 1)
        pygame.draw.line(temp2, trace_c, dot_positions[0], (size // 2, dot_positions[0][1]), 1)
    s.blit(temp2, (0, 0))

    # Faint scan line
    if parity == 0:
        scan_c = (*dc["z1_glow"], 18)
        temp3 = _surf(size, 1)
        temp3.fill(scan_c)
        s.blit(temp3, (0, size // 2))

    return s


def _make_dark_zone2_tile(size, parity):
    """Dark amber tile: data streams, dots."""
    s = pygame.Surface((size, size))
    dc = DARK_WORLD_COLORS
    s.fill(dc["z2_top"] if parity == 0 else dc["z2_mid"])

    line_c = dc["z2_line"]
    pygame.draw.line(s, line_c, (0, 0), (size, 0), 1)
    pygame.draw.line(s, line_c, (0, 0), (0, size), 1)

    # Vertical dashed data stream lines
    stream_c = (*dc["z2_dot"], 50)
    temp = _surf(size, size)
    for sx in [8, 16, 24]:
        if sx < size:
            for sy in range(0, size, 4):
                if (sy // 4 + parity) % 2 == 0:
                    pygame.draw.rect(temp, stream_c, (sx, sy, 1, 2))
    s.blit(temp, (0, 0))

    # Matrix-style dots (scattered small dots)
    dot_c = (*dc["z2_dot"], 45)
    temp2 = _surf(size, size)
    positions = [(6, 6), (14, 10), (22, 4), (10, 20), (18, 26), (26, 16),
                 (4, 14), (20, 22), (28, 8)]
    for px, py in positions:
        if px < size and py < size and (px + py + parity) % 3 == 0:
            pygame.draw.rect(temp2, dot_c, (px, py, 2, 2))
    s.blit(temp2, (0, 0))

    # Warning hash marks
    dot_c2 = (*dc["z2_dot"], 40)
    for px, py in [(8, 8), (24, 24)]:
        if px < size and py < size:
            temp3 = _surf(2, 2)
            pygame.draw.rect(temp3, dot_c2, (0, 0, 2, 2))
            s.blit(temp3, (px, py))

    # Diagonal caution stripe (very subtle)
    if parity == 1:
        stripe_c = (*dc["z2_glow"], 12)
        temp4 = _surf(size, size)
        pygame.draw.line(temp4, stripe_c, (0, size), (size, 0), 1)
        s.blit(temp4, (0, 0))

    return s


def _make_dark_zone3_tile(size, parity):
    """Dark red tile: alert pattern, hash marks, pulsing corners."""
    s = pygame.Surface((size, size))
    dc = DARK_WORLD_COLORS
    s.fill(dc["z3_top"] if parity == 0 else dc["z3_mid"])

    line_c = dc["z3_line"]
    pygame.draw.line(s, line_c, (0, 0), (size, 0), 1)
    pygame.draw.line(s, line_c, (0, 0), (0, size), 1)

    # Pulsing corner markers (red alert pattern)
    corner_c = (*dc["z3_dot"], 60)
    temp = _surf(size, size)
    corner_len = 4
    # Top-left
    pygame.draw.line(temp, corner_c, (1, 1), (corner_len, 1), 1)
    pygame.draw.line(temp, corner_c, (1, 1), (1, corner_len), 1)
    # Top-right
    pygame.draw.line(temp, corner_c, (size - 2, 1), (size - corner_len - 1, 1), 1)
    pygame.draw.line(temp, corner_c, (size - 2, 1), (size - 2, corner_len), 1)
    # Bottom-left
    pygame.draw.line(temp, corner_c, (1, size - 2), (corner_len, size - 2), 1)
    pygame.draw.line(temp, corner_c, (1, size - 2), (1, size - corner_len - 1), 1)
    # Bottom-right
    pygame.draw.line(temp, corner_c, (size - 2, size - 2), (size - corner_len - 1, size - 2), 1)
    pygame.draw.line(temp, corner_c, (size - 2, size - 2), (size - 2, size - corner_len - 1), 1)
    s.blit(temp, (0, 0))

    # Danger hash marks (diagonal lines)
    hash_c = (*dc["z3_dot"], 35)
    temp2 = _surf(size, size)
    if parity == 0:
        for di in range(0, size, 6):
            pygame.draw.line(temp2, hash_c, (di, 0), (di + 4, 4), 1)
    else:
        for di in range(0, size, 6):
            pygame.draw.line(temp2, hash_c, (0, di), (4, di + 4), 1)
    s.blit(temp2, (0, 0))

    # Danger dots
    dot_c = (*dc["z3_dot"], 55)
    for px, py in [(6, 6), (20, 12), (12, 24)]:
        if px < size and py < size:
            temp3 = _surf(2, 2)
            pygame.draw.rect(temp3, dot_c, (0, 0, 2, 2))
            s.blit(temp3, (px, py))

    # Faint red glow at bottom
    glow_c = (*dc["z3_glow"], 15)
    temp4 = _surf(size, 6)
    temp4.fill(glow_c)
    s.blit(temp4, (0, size - 6))

    return s


# =============================================================================
# Particle System
# =============================================================================

class Particle:
    def __init__(self, x, y, color, vx=0, vy=0, life=20, size=3, shape=0):
        self.x, self.y = x, y
        self.color = color
        self.vx, self.vy = vx, vy
        self.life = life
        self.max_life = life
        self.size = size
        self.shape = shape  # 0=circle, 1=square, 2=diamond

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

        if self.shape == 0:
            # Circle
            surf = _surf(sz * 2 + 2, sz * 2 + 2)
            pygame.draw.circle(surf, color, (sz + 1, sz + 1), sz)
            screen.blit(surf, (int(self.x) - sz, int(self.y) - sz))
        elif self.shape == 1:
            # Square
            surf = _surf(sz * 2 + 2, sz * 2 + 2)
            pygame.draw.rect(surf, color, (1, 1, sz * 2, sz * 2))
            screen.blit(surf, (int(self.x) - sz, int(self.y) - sz))
        else:
            # Diamond (rotated square)
            surf = _surf(sz * 2 + 2, sz * 2 + 2)
            center = sz + 1
            pts = [(center, center - sz), (center + sz, center),
                   (center, center + sz), (center - sz, center)]
            pygame.draw.polygon(surf, color, pts)
            screen.blit(surf, (int(self.x) - sz - 1, int(self.y) - sz - 1))


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit(self, x, y, color, count=8):
        for _ in range(count):
            vx = _rand.uniform(-2.5, 2.5)
            vy = _rand.uniform(-3.5, -0.5)
            life = _rand.randint(15, 35)
            size = _rand.randint(2, 5)
            shape = _rand.randint(0, 2)
            self.particles.append(Particle(x, y, color, vx, vy, life, size, shape))

    def emit_sparkle(self, x, y, color, count=5):
        for _ in range(count):
            angle = _rand.uniform(0, 2 * math.pi)
            speed = _rand.uniform(1, 3)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = _rand.randint(10, 20)
            shape = _rand.randint(0, 2)
            self.particles.append(Particle(x, y, color, vx, vy, life, 2, shape))

    def emit_burst(self, x, y, color, count=12):
        """Ring burst: particles radiate outward evenly."""
        for i in range(count):
            angle = (2 * math.pi * i) / count
            speed = _rand.uniform(2, 4)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = _rand.randint(15, 30)
            size = _rand.randint(2, 4)
            shape = _rand.randint(0, 2)
            self.particles.append(Particle(x, y, color, vx, vy, life, size, shape))

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
            # Use Claude palettes for the claude design, normal palettes otherwise
            palettes = CLAUDE_PALETTES if design_name == "claude" else ROBOT_PALETTES
            for robot_type, pal in palettes.items():
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

        # Standard tiles
        for parity in (0, 1):
            self._tile_cache[(1, parity)] = _make_zone1_tile(cs, parity)
            self._tile_cache[(2, parity)] = _make_zone2_tile(cs, parity)
            self._tile_cache[(3, parity)] = _make_zone3_tile(cs, parity)

        # Dark terminal tiles (for Claude design)
        for parity in (0, 1):
            self._tile_cache[("dark", 1, parity)] = _make_dark_zone1_tile(cs, parity)
            self._tile_cache[("dark", 2, parity)] = _make_dark_zone2_tile(cs, parity)
            self._tile_cache[("dark", 3, parity)] = _make_dark_zone3_tile(cs, parity)

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

    def get_tile(self, zone, parity, dark=False):
        if dark:
            return self._tile_cache.get(("dark", zone, parity))
        return self._tile_cache.get((zone, parity))
