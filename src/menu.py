# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
Menu system: start screen with robot design selector and settings,
and a pause overlay with resume / restart / quit options.
"""

import pygame
import math
from src.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, FPS, CELL_SIZE,
    BG_COLOR, HUD_BG_COLOR, TEXT_COLOR,
    NUM_GREEN_ROBOTS, NUM_YELLOW_ROBOTS, NUM_RED_ROBOTS,
    INITIAL_GREEN_WASTE, MAX_RADIATION_THRESHOLD,
    RADIATION_SPAWN_INTERVAL, AGENT_TICK_RATE,
)
from src.sprites import (
    SpriteCache, ROBOT_DESIGNS, ROBOT_PALETTES, DEFAULT_DESIGN,
)


# ── Colour constants for the menus ──────────────────────────────────────────

_DARK_BG = (16, 16, 24)
_PANEL_BG = (28, 28, 42)
_PANEL_BORDER = (55, 55, 75)
_ACCENT = (80, 200, 255)
_ACCENT_DIM = (50, 120, 160)
_BTN_BG = (40, 40, 60)
_BTN_HOVER = (60, 60, 90)
_BTN_TEXT = (220, 220, 240)
_TITLE_COLOR = (255, 220, 80)
_SUBTITLE_COLOR = (180, 180, 200)
_HIGHLIGHT = (100, 255, 150)
_RED_BTN = (180, 50, 50)
_RED_BTN_HOVER = (220, 70, 70)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


# =============================================================================
# Start Menu
# =============================================================================

class StartMenu:
    """Full-screen start menu with design picker and settings."""

    def __init__(self, screen, sprite_cache):
        self.screen = screen
        self.sprite_cache = sprite_cache
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_huge = pygame.font.SysFont("Courier", 42, bold=True)
        self.font_title = pygame.font.SysFont("Courier", 28, bold=True)
        self.font_med = pygame.font.SysFont("Courier", 20, bold=True)
        self.font_sm = pygame.font.SysFont("Courier", 15, bold=True)

        # Design selector state
        self._design_names = list(ROBOT_DESIGNS.keys())
        self._selected_idx = self._design_names.index(DEFAULT_DESIGN)
        self._anim_frame = 0

        # Settings (mutable copies of config defaults)
        self._settings = {
            "num_green":    NUM_GREEN_ROBOTS,
            "num_yellow":   NUM_YELLOW_ROBOTS,
            "num_red":      NUM_RED_ROBOTS,
            "initial_waste": INITIAL_GREEN_WASTE,
            "max_radiation": MAX_RADIATION_THRESHOLD,
            "spawn_interval": RADIATION_SPAWN_INTERVAL,
            "tick_rate":    AGENT_TICK_RATE,
        }
        self._setting_ranges = {
            "num_green":    (1, 10),
            "num_yellow":   (1, 10),
            "num_red":      (1, 10),
            "initial_waste": (5, 50),
            "max_radiation": (30, 200),
            "spawn_interval": (30, 300),
            "tick_rate":    (4, 30),
        }
        self._setting_labels = {
            "num_green":    "Green Robots",
            "num_yellow":   "Yellow Robots",
            "num_red":      "Red Robots",
            "initial_waste": "Initial Green Waste",
            "max_radiation": "Max Radiation",
            "spawn_interval": "Spawn Interval",
            "tick_rate":    "Agent Tick Rate",
        }
        self._setting_order = [
            "num_green", "num_yellow", "num_red",
            "initial_waste", "max_radiation", "spawn_interval", "tick_rate",
        ]

    # ── public entry point ──────────────────────────────────────────────

    def run(self):
        """Block until the player starts or quits.

        Returns ``None`` if the player chose to quit, otherwise a dict::

            {"design": str, "num_green": int, ...}
        """
        while True:
            self._anim_frame += 1
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        return None
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        return self._result()
                    if event.key == pygame.K_LEFT:
                        self._selected_idx = (self._selected_idx - 1) % len(self._design_names)
                    if event.key == pygame.K_RIGHT:
                        self._selected_idx = (self._selected_idx + 1) % len(self._design_names)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    action = self._handle_click(mouse_pos)
                    if action == "start":
                        return self._result()
                    if action == "quit":
                        return None

            self._draw(mouse_pos)
            pygame.display.flip()
            self.clock.tick(FPS)

    # ── internal ────────────────────────────────────────────────────────

    def _result(self):
        return {
            "design": self._design_names[self._selected_idx],
            **self._settings,
        }

    def _handle_click(self, pos):
        mx, my = pos
        # Design thumbnails
        thumb_y = 160
        thumb_w = 80
        total_w = len(self._design_names) * thumb_w + (len(self._design_names) - 1) * 12
        start_x = (WINDOW_WIDTH - total_w) // 2
        for i in range(len(self._design_names)):
            tx = start_x + i * (thumb_w + 12)
            if tx <= mx <= tx + thumb_w and thumb_y <= my <= thumb_y + thumb_w + 20:
                self._selected_idx = i
                return None

        # Settings +/- buttons
        panel_x = WINDOW_WIDTH // 2 - 200
        sy = 340
        for key in self._setting_order:
            btn_minus = pygame.Rect(panel_x + 260, sy, 28, 22)
            btn_plus = pygame.Rect(panel_x + 330, sy, 28, 22)
            lo, hi = self._setting_ranges[key]
            if btn_minus.collidepoint(mx, my):
                self._settings[key] = _clamp(self._settings[key] - 1, lo, hi)
            elif btn_plus.collidepoint(mx, my):
                self._settings[key] = _clamp(self._settings[key] + 1, lo, hi)
            sy += 30

        # START button
        start_btn = pygame.Rect(WINDOW_WIDTH // 2 - 100, sy + 20, 200, 45)
        if start_btn.collidepoint(mx, my):
            return "start"

        # QUIT button
        quit_btn = pygame.Rect(WINDOW_WIDTH // 2 - 60, sy + 80, 120, 35)
        if quit_btn.collidepoint(mx, my):
            return "quit"

        return None

    # ── drawing ─────────────────────────────────────────────────────────

    def _draw(self, mouse_pos):
        self.screen.fill(_DARK_BG)

        # Title
        title_surf = self.font_huge.render("RADIOACTIVE WASTE MISSION", True, _TITLE_COLOR)
        title_rect = title_surf.get_rect(center=(WINDOW_WIDTH // 2, 50))
        self.screen.blit(title_surf, title_rect)

        sub = self.font_sm.render("Select a robot design and configure settings", True, _SUBTITLE_COLOR)
        sub_rect = sub.get_rect(center=(WINDOW_WIDTH // 2, 90))
        self.screen.blit(sub, sub_rect)

        # ── Design selector row ──
        self._draw_design_selector(mouse_pos)

        # ── Live animated preview ──
        self._draw_preview()

        # ── Settings panel ──
        self._draw_settings(mouse_pos)

        # ── Hint ──
        blink = (self._anim_frame // 30) % 2 == 0
        if blink:
            hint = self.font_sm.render("Arrow keys to pick design  |  Enter to start  |  Q to quit", True, (120, 120, 140))
            hint_rect = hint.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 20))
            self.screen.blit(hint, hint_rect)

    def _draw_design_selector(self, mouse_pos):
        thumb_y = 130
        thumb_w = 80
        total_w = len(self._design_names) * thumb_w + (len(self._design_names) - 1) * 12
        start_x = (WINDOW_WIDTH - total_w) // 2
        mx, my = mouse_pos

        for i, name in enumerate(self._design_names):
            tx = start_x + i * (thumb_w + 12)
            selected = (i == self._selected_idx)
            hovered = tx <= mx <= tx + thumb_w and thumb_y <= my <= thumb_y + thumb_w + 20

            # Background card
            border_col = _HIGHLIGHT if selected else (_ACCENT if hovered else _PANEL_BORDER)
            bg_col = (38, 38, 55) if selected else _PANEL_BG
            pygame.draw.rect(self.screen, bg_col, (tx, thumb_y, thumb_w, thumb_w + 20), border_radius=6)
            pygame.draw.rect(self.screen, border_col, (tx, thumb_y, thumb_w, thumb_w + 20), 2, border_radius=6)

            # Draw a sample robot (green palette, animated)
            anim_f = (self._anim_frame // 8) % 16
            sprite = self.sprite_cache.get("robot", "green", anim_f, design=name)
            if sprite:
                # Scale up for visibility
                scaled = pygame.transform.scale(sprite, (48, 48))
                sx = tx + (thumb_w - 48) // 2
                sy = thumb_y + 4
                self.screen.blit(scaled, (sx, sy))

            # Design name label
            label = self.font_sm.render(name.upper(), True, _HIGHLIGHT if selected else _BTN_TEXT)
            lrect = label.get_rect(center=(tx + thumb_w // 2, thumb_y + thumb_w + 10))
            self.screen.blit(label, lrect)

    def _draw_preview(self):
        """Animated preview of the selected design, all 3 colours."""
        design = self._design_names[self._selected_idx]
        preview_y = 240
        anim_f = (self._anim_frame // 6) % 16

        label = self.font_med.render(f"Preview:  {design.upper()}", True, _ACCENT)
        self.screen.blit(label, (WINDOW_WIDTH // 2 - label.get_width() // 2, preview_y))

        colors = ["green", "yellow", "red"]
        total_w = len(colors) * 48 + (len(colors) - 1) * 24
        sx = (WINDOW_WIDTH - total_w) // 2
        for j, c in enumerate(colors):
            sprite = self.sprite_cache.get("robot", c, anim_f, design=design)
            if sprite:
                scaled = pygame.transform.scale(sprite, (48, 48))
                self.screen.blit(scaled, (sx + j * 72, preview_y + 24))

    def _draw_settings(self, mouse_pos):
        mx, my = mouse_pos
        panel_x = WINDOW_WIDTH // 2 - 200
        sy = 340

        header = self.font_med.render("Settings", True, _ACCENT)
        self.screen.blit(header, (panel_x, sy - 28))

        for key in self._setting_order:
            label = self._setting_labels[key]
            val = self._settings[key]
            lo, hi = self._setting_ranges[key]

            # Label
            lbl_surf = self.font_sm.render(label, True, _SUBTITLE_COLOR)
            self.screen.blit(lbl_surf, (panel_x, sy + 3))

            # Value
            val_surf = self.font_med.render(str(val), True, TEXT_COLOR)
            self.screen.blit(val_surf, (panel_x + 300, sy + 1))

            # Minus button
            btn_minus = pygame.Rect(panel_x + 260, sy, 28, 22)
            minus_hover = btn_minus.collidepoint(mx, my)
            pygame.draw.rect(self.screen, _BTN_HOVER if minus_hover else _BTN_BG,
                             btn_minus, border_radius=4)
            m_txt = self.font_med.render("-", True, _BTN_TEXT)
            self.screen.blit(m_txt, (btn_minus.x + 8, btn_minus.y))

            # Plus button
            btn_plus = pygame.Rect(panel_x + 330, sy, 28, 22)
            plus_hover = btn_plus.collidepoint(mx, my)
            pygame.draw.rect(self.screen, _BTN_HOVER if plus_hover else _BTN_BG,
                             btn_plus, border_radius=4)
            p_txt = self.font_med.render("+", True, _BTN_TEXT)
            self.screen.blit(p_txt, (btn_plus.x + 6, btn_plus.y))

            sy += 30

        # START button
        start_btn = pygame.Rect(WINDOW_WIDTH // 2 - 100, sy + 20, 200, 45)
        s_hover = start_btn.collidepoint(mx, my)
        pygame.draw.rect(self.screen, _HIGHLIGHT if s_hover else (60, 180, 100),
                         start_btn, border_radius=8)
        start_txt = self.font_title.render("START", True, (10, 10, 10))
        self.screen.blit(start_txt,
                         start_txt.get_rect(center=start_btn.center))

        # QUIT button
        quit_btn = pygame.Rect(WINDOW_WIDTH // 2 - 60, sy + 80, 120, 35)
        q_hover = quit_btn.collidepoint(mx, my)
        pygame.draw.rect(self.screen, _RED_BTN_HOVER if q_hover else _RED_BTN,
                         quit_btn, border_radius=6)
        quit_txt = self.font_med.render("QUIT", True, _BTN_TEXT)
        self.screen.blit(quit_txt,
                         quit_txt.get_rect(center=quit_btn.center))


# =============================================================================
# Pause Menu
# =============================================================================

class PauseMenu:
    """Semi-transparent pause overlay with multiple actions."""

    # Possible return values
    RESUME = "resume"
    RESTART = "restart"
    MAIN_MENU = "main_menu"
    QUIT = "quit"

    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font_huge = pygame.font.SysFont("Courier", 52, bold=True)
        self.font_med = pygame.font.SysFont("Courier", 22, bold=True)
        self.font_sm = pygame.font.SysFont("Courier", 16, bold=True)
        self._frame = 0

    def run(self):
        """Block until the player picks an action. Returns one of the class constants."""
        while True:
            self._frame += 1
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return self.QUIT
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        return self.RESUME
                    if event.key == pygame.K_r:
                        return self.RESTART
                    if event.key == pygame.K_m:
                        return self.MAIN_MENU
                    if event.key == pygame.K_q:
                        return self.QUIT
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    action = self._handle_click(mouse_pos)
                    if action:
                        return action

            self._draw(mouse_pos)
            pygame.display.flip()
            self.clock.tick(FPS)

    def _handle_click(self, pos):
        mx, my = pos
        btn_w, btn_h = 240, 40
        cx = WINDOW_WIDTH // 2
        start_y = WINDOW_HEIGHT // 2 - 10
        options = [
            (self.RESUME, "RESUME", pygame.K_SPACE),
            (self.RESTART, "RESTART", pygame.K_r),
            (self.MAIN_MENU, "MAIN MENU", pygame.K_m),
            (self.QUIT, "QUIT", pygame.K_q),
        ]
        for i, (action, _, _) in enumerate(options):
            by = start_y + i * 52
            rect = pygame.Rect(cx - btn_w // 2, by, btn_w, btn_h)
            if rect.collidepoint(mx, my):
                return action
        return None

    def _draw(self, mouse_pos):
        # Semi-transparent overlay (draw on top of whatever is already on screen)
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        # PAUSED title
        pulse = 0.7 + 0.3 * math.sin(self._frame * 0.06)
        alpha = int(255 * pulse)
        title = self.font_huge.render("PAUSED", True, (255, 255, 100))
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 80))
        self.screen.blit(title, title_rect)

        # Options
        mx, my = mouse_pos
        btn_w, btn_h = 240, 40
        cx = WINDOW_WIDTH // 2
        start_y = WINDOW_HEIGHT // 2 - 10

        options = [
            (self.RESUME, "RESUME  (Space)", (60, 180, 100)),
            (self.RESTART, "RESTART  (R)", _ACCENT),
            (self.MAIN_MENU, "MAIN MENU  (M)", _ACCENT_DIM),
            (self.QUIT, "QUIT  (Q)", _RED_BTN),
        ]

        for i, (action, label, color) in enumerate(options):
            by = start_y + i * 52
            rect = pygame.Rect(cx - btn_w // 2, by, btn_w, btn_h)
            hovered = rect.collidepoint(mx, my)
            bg = tuple(min(255, c + 30) for c in color) if hovered else color
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            txt = self.font_med.render(label, True, (240, 240, 240))
            self.screen.blit(txt, txt.get_rect(center=rect.center))
