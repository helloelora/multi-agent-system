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
    INITIAL_GREEN_WASTE,
    RADIATION_SPAWN_INTERVAL,
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

        # Human player mode
        self._human_mode = False
        self._human_color = "green"  # default selection
        self._run_mode = "auto"      # auto | step | step5

        # Settings (mutable copies of config defaults)
        self._settings = {
            "initial_waste": INITIAL_GREEN_WASTE,
            "spawn_interval": RADIATION_SPAWN_INTERVAL,
        }
        self._setting_ranges = {
            "initial_waste": (5, 50),
            "spawn_interval": (30, 300),
        }
        self._setting_labels = {
            "initial_waste": "Initial Green Waste",
            "spawn_interval": "Spawn Interval",
        }
        self._setting_order = [
            "initial_waste", "spawn_interval",
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
            "human_mode": self._human_mode,
            "human_color": self._human_color if self._human_mode else None,
            "run_mode": self._run_mode,
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

        # Mode toggle buttons (AI ONLY / HUMAN PLAYER)
        mode_y = 320
        panel_x = WINDOW_WIDTH // 2 - 200
        ai_btn = pygame.Rect(panel_x + 100, mode_y, 120, 26)
        human_btn = pygame.Rect(panel_x + 230, mode_y, 140, 26)
        if ai_btn.collidepoint(mx, my):
            self._human_mode = False
        elif human_btn.collidepoint(mx, my):
            self._human_mode = True

        # Color picker (only active if human mode)
        if self._human_mode:
            color_y = mode_y + 32
            colors = ["green", "yellow", "red"]
            color_start_x = panel_x + 100
            for i, c in enumerate(colors):
                crect = pygame.Rect(color_start_x + i * 60, color_y, 50, 24)
                if crect.collidepoint(mx, my):
                    self._human_color = c

        # Simulation mode selector (AUTO / STEP / STEP x5)
        run_mode_y = mode_y + (70 if self._human_mode else 38)
        run_btn_auto = pygame.Rect(panel_x + 100, run_mode_y, 80, 24)
        run_btn_step = pygame.Rect(panel_x + 190, run_mode_y, 80, 24)
        run_btn_step5 = pygame.Rect(panel_x + 280, run_mode_y, 90, 24)
        if run_btn_auto.collidepoint(mx, my):
            self._run_mode = "auto"
        elif run_btn_step.collidepoint(mx, my):
            self._run_mode = "step"
        elif run_btn_step5.collidepoint(mx, my):
            self._run_mode = "step5"

        # Settings +/- buttons (shifted down to accommodate mode selector)
        settings_y_offset = 500 if self._human_mode else 470
        sy = settings_y_offset
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

        # ── Mode selector (AI ONLY / HUMAN PLAYER) ──
        self._draw_mode_selector(mouse_pos)

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

    def _draw_mode_selector(self, mouse_pos):
        """Draw AI ONLY / HUMAN PLAYER toggle and color picker."""
        mx, my = mouse_pos
        panel_x = WINDOW_WIDTH // 2 - 200
        mode_y = 320

        # Label
        lbl = self.font_med.render("Mode:", True, _ACCENT)
        self.screen.blit(lbl, (panel_x, mode_y + 3))

        # AI ONLY button
        ai_btn = pygame.Rect(panel_x + 100, mode_y, 120, 26)
        ai_selected = not self._human_mode
        ai_hover = ai_btn.collidepoint(mx, my)
        ai_bg = _HIGHLIGHT if ai_selected else (_BTN_HOVER if ai_hover else _BTN_BG)
        ai_text_col = (10, 10, 10) if ai_selected else _BTN_TEXT
        pygame.draw.rect(self.screen, ai_bg, ai_btn, border_radius=4)
        ai_txt = self.font_sm.render("AI ONLY", True, ai_text_col)
        self.screen.blit(ai_txt, ai_txt.get_rect(center=ai_btn.center))

        # HUMAN PLAYER button
        human_btn = pygame.Rect(panel_x + 230, mode_y, 140, 26)
        human_selected = self._human_mode
        human_hover = human_btn.collidepoint(mx, my)
        human_bg = _HIGHLIGHT if human_selected else (_BTN_HOVER if human_hover else _BTN_BG)
        human_text_col = (10, 10, 10) if human_selected else _BTN_TEXT
        pygame.draw.rect(self.screen, human_bg, human_btn, border_radius=4)
        h_txt = self.font_sm.render("HUMAN PLAYER", True, human_text_col)
        self.screen.blit(h_txt, h_txt.get_rect(center=human_btn.center))

        # Color picker (only shown in human mode)
        if self._human_mode:
            color_y = mode_y + 32
            pick_lbl = self.font_sm.render("Play as:", True, _SUBTITLE_COLOR)
            self.screen.blit(pick_lbl, (panel_x, color_y + 3))

            colors = [
                ("green", (60, 200, 60)),
                ("yellow", (220, 200, 40)),
                ("red", (220, 60, 60)),
            ]
            color_start_x = panel_x + 100
            for i, (cname, crgb) in enumerate(colors):
                crect = pygame.Rect(color_start_x + i * 60, color_y, 50, 24)
                is_selected = (self._human_color == cname)
                border_col = (255, 255, 255) if is_selected else (80, 80, 100)
                pygame.draw.rect(self.screen, crgb, crect, border_radius=4)
                pygame.draw.rect(self.screen, border_col, crect, 2, border_radius=4)
                ctxt = self.font_sm.render(cname.upper(), True, (10, 10, 10))
                self.screen.blit(ctxt, ctxt.get_rect(center=crect.center))

        # Simulation mode selector
        run_mode_y = mode_y + (70 if self._human_mode else 38)
        run_lbl = self.font_sm.render("Sim mode:", True, _SUBTITLE_COLOR)
        self.screen.blit(run_lbl, (panel_x, run_mode_y + 4))

        mode_buttons = [
            ("auto", "AUTO", pygame.Rect(panel_x + 100, run_mode_y, 80, 24)),
            ("step", "STEP", pygame.Rect(panel_x + 190, run_mode_y, 80, 24)),
            ("step5", "STEP x5", pygame.Rect(panel_x + 280, run_mode_y, 90, 24)),
        ]
        for mode_key, mode_label, rect in mode_buttons:
            selected = self._run_mode == mode_key
            hovered = rect.collidepoint(mx, my)
            bg = _HIGHLIGHT if selected else (_BTN_HOVER if hovered else _BTN_BG)
            txt_col = (10, 10, 10) if selected else _BTN_TEXT
            pygame.draw.rect(self.screen, bg, rect, border_radius=4)
            txt = self.font_sm.render(mode_label, True, txt_col)
            self.screen.blit(txt, txt.get_rect(center=rect.center))

        n_hint = self.font_sm.render("In STEP modes: press N for next step(s)", True, (130, 130, 150))
        self.screen.blit(n_hint, (panel_x + 100, run_mode_y + 30))

    def _draw_settings(self, mouse_pos):
        mx, my = mouse_pos
        panel_x = WINDOW_WIDTH // 2 - 200
        sy = 500 if self._human_mode else 470

        header = self.font_med.render("Settings", True, _ACCENT)
        self.screen.blit(header, (panel_x, sy - 28))

        for key in self._setting_order:
            label = self._setting_labels[key]
            val = self._settings[key]
            lo, hi = self._setting_ranges[key]

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
