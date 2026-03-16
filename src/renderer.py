# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
Pygame renderer with retro pixel-art aesthetic.
Smooth agent movement, particle effects, detailed HUD and live charts.
"""

import pygame
import math
import src.config as _cfg
from src.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, CELL_SIZE, GRID_COLS, GRID_ROWS,
    ZONE_1_END, ZONE_2_END, HUD_HEIGHT, SIDEBAR_WIDTH,
    BG_COLOR, HUD_BG_COLOR, TEXT_COLOR,
    COLOR_GREEN_WASTE, COLOR_YELLOW_WASTE, COLOR_RED_WASTE,
    COLOR_GREEN_ROBOT, COLOR_YELLOW_ROBOT, COLOR_RED_ROBOT,
    FONT_SIZE, FONT_SIZE_LARGE,
    CHART_HISTORY_LENGTH, SPRITE_ANIM_SPEED,
)
from src.sprites import SpriteCache


class Renderer:

    def __init__(self, screen, robot_design=None):
        self.screen = screen
        self.sprite_cache = SpriteCache(CELL_SIZE, num_frames=16)
        self.robot_design = robot_design  # None means use DEFAULT_DESIGN
        self.grid_offset_x = 16
        self.grid_offset_y = HUD_HEIGHT + 8
        self.frame_count = 0

        # Smooth movement tracking: agent_id -> {from, to, progress}
        self._agent_positions = {}

        # Camera shake
        self._shake_intensity = 0
        self._shake_offset = (0, 0)

        # Fonts
        self.font = pygame.font.SysFont("Courier", FONT_SIZE, bold=True)
        self.font_large = pygame.font.SysFont("Courier", FONT_SIZE_LARGE, bold=True)
        self.font_title = pygame.font.SysFont("Courier", 28, bold=True)
        self.font_huge = pygame.font.SysFont("Courier", 56, bold=True)

        # Pre-render grid surface (static tiles)
        self._grid_surface = None
        self._build_grid_surface()

    def _build_grid_surface(self):
        w = GRID_COLS * CELL_SIZE
        h = GRID_ROWS * CELL_SIZE
        self._grid_surface = pygame.Surface((w, h))
        use_dark = self.robot_design == "claude"
        for x in range(GRID_COLS):
            for y in range(GRID_ROWS):
                zone = self._get_zone(x)
                parity = (x + y) % 2
                tile = self.sprite_cache.get_tile(zone, parity, dark=use_dark)
                if tile:
                    self._grid_surface.blit(tile, (x * CELL_SIZE, y * CELL_SIZE))

    @staticmethod
    def _get_zone(col):
        if col < ZONE_1_END:
            return 1
        elif col < ZONE_2_END:
            return 2
        return 3

    def _grid_to_screen(self, gx, gy):
        sx = self.grid_offset_x + gx * CELL_SIZE + self._shake_offset[0]
        sy = self.grid_offset_y + gy * CELL_SIZE + self._shake_offset[1]
        return (sx, sy)

    def _update_shake(self, model):
        total = model.total_waste()
        ratio = total / _cfg.MAX_RADIATION_THRESHOLD
        if ratio > 0.7:
            self._shake_intensity = (ratio - 0.7) / 0.3 * 4
        else:
            self._shake_intensity *= 0.9

        if self._shake_intensity > 0.2:
            import random
            self._shake_offset = (
                int(random.uniform(-self._shake_intensity, self._shake_intensity)),
                int(random.uniform(-self._shake_intensity, self._shake_intensity)),
            )
        else:
            self._shake_offset = (0, 0)

    def _get_smooth_pos(self, robot, lerp_speed=0.2):
        """Get interpolated screen position for smooth movement."""
        aid = robot.agent_id
        target = (float(robot.x), float(robot.y))

        if aid not in self._agent_positions:
            self._agent_positions[aid] = {"x": target[0], "y": target[1]}

        pos = self._agent_positions[aid]
        pos["x"] += (target[0] - pos["x"]) * lerp_speed
        pos["y"] += (target[1] - pos["y"]) * lerp_speed

        sx = self.grid_offset_x + pos["x"] * CELL_SIZE + self._shake_offset[0]
        sy = self.grid_offset_y + pos["y"] * CELL_SIZE + self._shake_offset[1]
        return (int(sx), int(sy))

    def draw(self, model):
        self.frame_count += 1
        anim_frame = self.frame_count // SPRITE_ANIM_SPEED

        self._update_shake(model)
        self.screen.fill(BG_COLOR)

        self._draw_grid(model, anim_frame)
        self._draw_zone_borders()
        self._draw_disposal(model, anim_frame)
        self._draw_waste(model, anim_frame)
        self._draw_robots(model, anim_frame)

        # Particles
        self.sprite_cache.particle_system.update()
        self.sprite_cache.particle_system.draw(self.screen)

        self._draw_hud(model)
        self._draw_sidebar(model)

        if model.game_over:
            self._draw_game_over(model)

    def _draw_grid(self, model, anim_frame):
        gx = self.grid_offset_x + self._shake_offset[0]
        gy = self.grid_offset_y + self._shake_offset[1]
        self.screen.blit(self._grid_surface, (gx, gy))

        # Radiation shimmer on high-radiation cells
        total = model.total_waste()
        if total > _cfg.MAX_RADIATION_THRESHOLD * 0.5:
            danger = (total / _cfg.MAX_RADIATION_THRESHOLD - 0.5) * 2
            for x in range(GRID_COLS):
                for y in range(GRID_ROWS):
                    rad = model.radioactivity.get((x, y))
                    if rad and rad.level > 0.5:
                        sx, sy = self._grid_to_screen(x, y)
                        alpha = int(danger * rad.level * 25 *
                                    (0.7 + 0.3 * math.sin(
                                        self.frame_count * 0.05 + x * 0.3 + y * 0.2)))
                        alpha = min(60, max(0, alpha))
                        if alpha > 0:
                            overlay = pygame.Surface(
                                (CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                            overlay.fill((255, 40, 20, alpha))
                            self.screen.blit(overlay, (sx, sy))

    def _draw_zone_borders(self):
        use_dark = self.robot_design == "claude"

        # Zone separator lines (dashed)
        sep_color = (80, 180, 170) if use_dark else (255, 255, 255, 120)
        for col in [ZONE_1_END, ZONE_2_END]:
            sx = self.grid_offset_x + col * CELL_SIZE + self._shake_offset[0]
            sy_start = self.grid_offset_y + self._shake_offset[1]
            sy_end = sy_start + GRID_ROWS * CELL_SIZE

            for y in range(sy_start, sy_end, 8):
                pygame.draw.line(self.screen, sep_color,
                                 (sx, y), (sx, min(y + 4, sy_end)), 2)

        # Zone labels
        if use_dark:
            zone_labels = [
                (0, "ZONE 1", "LOW RAD", (80, 190, 175)),
                (ZONE_1_END, "ZONE 2", "MED RAD", (210, 140, 60)),
                (ZONE_2_END, "ZONE 3", "HIGH RAD", (200, 80, 70)),
            ]
        else:
            zone_labels = [
                (0, "ZONE 1", "GRASSLANDS", (100, 210, 100)),
                (ZONE_1_END, "ZONE 2", "DESERT", (220, 190, 110)),
                (ZONE_2_END, "ZONE 3", "VOLCANO", (210, 90, 80)),
            ]
        for start_col, name, subtitle, color in zone_labels:
            lx = self.grid_offset_x + start_col * CELL_SIZE + 6 + self._shake_offset[0]
            ly = self.grid_offset_y - 18 + self._shake_offset[1]
            txt = self.font.render(f"{name} - {subtitle}", True, color)
            self.screen.blit(txt, (lx, ly))

    def _draw_waste(self, model, anim_frame):
        for pos, wastes in model.waste_map.items():
            if not wastes:
                continue
            sx, sy = self._grid_to_screen(*pos)

            # Stack waste sprites with offset
            for i, w in enumerate(wastes[:4]):
                sprite = self.sprite_cache.get(
                    "waste", w.waste_type, anim_frame + i * 3)
                if sprite:
                    sw, sh = sprite.get_size()
                    offset_x = (i % 2) * 3 - 1
                    offset_y = -i * 2
                    blit_x = sx + (CELL_SIZE - sw) // 2 + offset_x
                    blit_y = sy + (CELL_SIZE - sh) // 2 + offset_y
                    self.screen.blit(sprite, (blit_x, blit_y))

            # Count badge
            if len(wastes) > 4:
                badge_surf = pygame.Surface((16, 12), pygame.SRCALPHA)
                badge_surf.fill((0, 0, 0, 160))
                badge_txt = self.font.render(str(len(wastes)), True, (255, 255, 255))
                badge_surf.blit(badge_txt, (2, 0))
                self.screen.blit(badge_surf, (sx + CELL_SIZE - 16, sy))

    def _draw_disposal(self, model, anim_frame):
        for pos in model.disposal_zones:
            sx, sy = self._grid_to_screen(*pos)
            sprite = self.sprite_cache.get("disposal", 0, anim_frame)
            if sprite:
                self.screen.blit(sprite, (sx, sy))

    def _draw_robots(self, model, anim_frame):
        for robot in model.robots:
            sx, sy = self._get_smooth_pos(robot)
            facing = robot.knowledge.get("facing", "right")
            kind = "robot_left" if facing == "left" else "robot"
            sprite = self.sprite_cache.get(kind, robot.robot_type, anim_frame,
                                              design=self.robot_design)
            if sprite:
                draw_sprite = sprite

                sw, sh = draw_sprite.get_size()
                blit_x = sx + (CELL_SIZE - sw) // 2
                blit_y = sy + (CELL_SIZE - sh) // 2
                self.screen.blit(draw_sprite, (blit_x, blit_y))

            # Inventory dots above robot
            carry = robot.carry_count()
            if carry > 0:
                dot_y = sy - 4
                total_width = min(carry, 8) * 5
                start_x = sx + (CELL_SIZE - total_width) // 2
                for i in range(min(carry, 8)):
                    wtype = robot.inventory[i] if i < len(robot.inventory) else "green"
                    color = {
                        "green": COLOR_GREEN_WASTE,
                        "yellow": COLOR_YELLOW_WASTE,
                        "red": COLOR_RED_WASTE,
                    }.get(wtype, (200, 200, 200))
                    pygame.draw.circle(self.screen, color,
                                       (start_x + i * 5 + 2, dot_y), 2)
                if carry > 8:
                    plus = self.font.render(f"+{carry - 8}", True, (255, 255, 255))
                    self.screen.blit(plus, (start_x + 42, dot_y - 6))

    def _draw_hud(self, model):
        # HUD background
        pygame.draw.rect(self.screen, HUD_BG_COLOR,
                         (0, 0, WINDOW_WIDTH, HUD_HEIGHT))

        # Bottom border with glow based on danger
        total = model.total_waste()
        ratio = min(1.0, total / _cfg.MAX_RADIATION_THRESHOLD)
        border_color = (
            min(255, int(60 + 160 * ratio)),
            max(0, int(80 * (1 - ratio))),
            max(0, int(80 * (1 - ratio))),
        )
        pygame.draw.line(self.screen, border_color,
                         (0, HUD_HEIGHT - 1), (WINDOW_WIDTH, HUD_HEIGHT - 1), 2)

        # Title
        title = self.font_title.render("RADIOACTIVE WASTE MISSION", True, TEXT_COLOR)
        self.screen.blit(title, (16, 8))

        # Stats row
        stats = [
            ("TICK", str(model.tick), TEXT_COLOR),
            ("WASTE", f"{total}/{_cfg.MAX_RADIATION_THRESHOLD}",
             COLOR_RED_WASTE if ratio > 0.7 else
             COLOR_YELLOW_WASTE if ratio > 0.4 else TEXT_COLOR),
            ("DISPOSED", str(model.waste_disposed), (100, 200, 255)),
            ("SCORE", str(model.score), (255, 220, 80)),
        ]

        x_pos = 16
        for label, value, color in stats:
            label_surf = self.font.render(label, True, (140, 140, 160))
            value_surf = self.font_large.render(value, True, color)
            self.screen.blit(label_surf, (x_pos, 40))
            self.screen.blit(value_surf, (x_pos, 54))
            x_pos += max(label_surf.get_width(), value_surf.get_width()) + 30

        # Danger bar
        bar_x = 16
        bar_y = HUD_HEIGHT - 8
        bar_w = GRID_COLS * CELL_SIZE
        bar_h = 4
        # Background
        pygame.draw.rect(self.screen, (20, 20, 30), (bar_x, bar_y, bar_w, bar_h),
                         border_radius=2)
        # Fill
        fill_w = int(bar_w * min(1.0, ratio))
        if fill_w > 0:
            bar_color = (
                int(80 + 175 * ratio),
                int(200 * (1 - ratio)),
                40,
            )
            pygame.draw.rect(self.screen, bar_color,
                             (bar_x, bar_y, fill_w, bar_h), border_radius=2)
            # Pulse at high danger
            if ratio > 0.7:
                pulse = 0.5 + 0.5 * math.sin(self.frame_count * 0.1)
                glow_surf = pygame.Surface((fill_w, bar_h + 4), pygame.SRCALPHA)
                glow_surf.fill((*bar_color, int(40 * pulse)))
                self.screen.blit(glow_surf, (bar_x, bar_y - 2))

    def _draw_sidebar(self, model):
        sb_x = self.grid_offset_x + GRID_COLS * CELL_SIZE + 16
        sb_y = HUD_HEIGHT + 8
        sb_w = SIDEBAR_WIDTH - 32

        # Panel background
        panel_rect = (sb_x - 8, sb_y, sb_w + 16, WINDOW_HEIGHT - sb_y - 8)
        pygame.draw.rect(self.screen, (28, 28, 40), panel_rect, border_radius=6)
        pygame.draw.rect(self.screen, (50, 50, 65), panel_rect, 1, border_radius=6)

        y = sb_y + 12

        # Waste breakdown chart
        y = self._draw_mini_chart(
            model, sb_x, y, sb_w, 130, "WASTE COUNT",
            [("green_waste", COLOR_GREEN_WASTE),
             ("yellow_waste", COLOR_YELLOW_WASTE),
             ("red_waste", COLOR_RED_WASTE)])

        y += 16

        # Total waste vs threshold
        y = self._draw_mini_chart(
            model, sb_x, y, sb_w, 130, "TOTAL vs LIMIT",
            [("total_waste", (220, 140, 60))],
            threshold=_cfg.MAX_RADIATION_THRESHOLD)

        y += 16

        # Agent roster
        self._draw_text("AGENTS", sb_x, y, self.font_large, TEXT_COLOR)
        y += 24

        robot_colors = {
            "green": COLOR_GREEN_ROBOT,
            "yellow": COLOR_YELLOW_ROBOT,
            "red": COLOR_RED_ROBOT,
        }

        for robot in sorted(model.robots, key=lambda r: (r.robot_type, r.agent_id)):
            if y > WINDOW_HEIGHT - 30:
                break
            color = robot_colors.get(robot.robot_type, TEXT_COLOR)

            # Robot icon (tiny colored square)
            pygame.draw.rect(self.screen, color, (sb_x, y + 2, 8, 8), border_radius=2)

            # Info
            inv_str = ""
            if robot.inventory:
                counts = {}
                for w in robot.inventory:
                    counts[w] = counts.get(w, 0) + 1
                inv_str = " ".join(f"{c}{t[0].upper()}" for t, c in counts.items())

            info = f" {robot.robot_type[0].upper()}{robot.agent_id}  ({robot.x},{robot.y})"
            if inv_str:
                info += f"  [{inv_str}]"

            self._draw_text(info, sb_x + 12, y, self.font, color)
            y += 16

    def _draw_mini_chart(self, model, x, y, w, h, title, series, threshold=None):
        self._draw_text(title, x, y, self.font, (140, 140, 160))
        y += 16

        chart_rect = (x, y, w, h)
        pygame.draw.rect(self.screen, (18, 18, 28), chart_rect, border_radius=4)
        pygame.draw.rect(self.screen, (45, 45, 58), chart_rect, 1, border_radius=4)

        if not model.history["tick"] or len(model.history["tick"]) < 2:
            return y + h

        n = min(CHART_HISTORY_LENGTH, len(model.history["tick"]))
        margin = 4

        for key, color in series:
            data = model.history[key][-n:]
            max_val = max(max(data), 1)
            if threshold:
                max_val = max(max_val, threshold * 1.1)

            points = []
            for i, val in enumerate(data):
                px = x + margin + int(i / max(n - 1, 1) * (w - margin * 2))
                py = y + h - margin - int(val / max_val * (h - margin * 2))
                points.append((px, py))

            if len(points) >= 2:
                # Filled area under curve
                area_points = points + [(points[-1][0], y + h - margin),
                                        (points[0][0], y + h - margin)]
                fill_color = (*color[:3], 30)
                fill_surf = pygame.Surface((w, h), pygame.SRCALPHA)
                shifted = [(px - x, py - y) for px, py in area_points]
                if len(shifted) >= 3:
                    pygame.draw.polygon(fill_surf, fill_color, shifted)
                    self.screen.blit(fill_surf, (x, y))

                # Line
                pygame.draw.lines(self.screen, color, False, points, 2)

                # Current value label
                val = data[-1]
                val_txt = self.font.render(str(val), True, color)
                self.screen.blit(val_txt, (points[-1][0] - 20, points[-1][1] - 14))

        if threshold:
            max_val = max(max(model.history[series[0][0]][-n:]), threshold * 1.1)
            ty = y + h - margin - int(threshold / max_val * (h - margin * 2))
            # Dashed threshold line
            for dash_x in range(x + margin, x + w - margin, 6):
                pygame.draw.line(self.screen, (220, 60, 60),
                                 (dash_x, ty), (min(dash_x + 3, x + w - margin), ty), 1)

        return y + h

    def _draw_game_over(self, model):
        # Animated dark overlay
        pulse = 0.5 + 0.2 * math.sin(self.frame_count * 0.05)
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((20, 0, 0, int(180 * pulse)))
        self.screen.blit(overlay, (0, 0))

        # Warning stripes
        stripe_y = WINDOW_HEIGHT // 2 - 80
        stripe_surf = pygame.Surface((WINDOW_WIDTH, 160), pygame.SRCALPHA)
        stripe_surf.fill((0, 0, 0, 140))
        self.screen.blit(stripe_surf, (0, stripe_y))

        # Hazard lines
        for i in range(0, WINDOW_WIDTH, 40):
            offset = (self.frame_count * 2) % 40
            pygame.draw.polygon(self.screen, (200, 160, 30, 80), [
                (i - 20 + offset, stripe_y),
                (i + offset, stripe_y),
                (i - 10 + offset, stripe_y + 6),
                (i - 30 + offset, stripe_y + 6),
            ])

        # MELTDOWN text with glow
        go_text = self.font_huge.render("MELTDOWN", True, (220, 60, 60))
        glow_text = self.font_huge.render("MELTDOWN", True, (255, 100, 80))
        rect = go_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 30))
        glow_rect = glow_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 30))
        if int(self.frame_count * 0.1) % 2 == 0:
            self.screen.blit(glow_text, glow_rect)
        else:
            self.screen.blit(go_text, rect)

        # Stats
        stats_text = self.font_title.render(
            f"Score: {model.score}     Disposed: {model.waste_disposed}     "
            f"Survived: {model.tick} ticks",
            True, TEXT_COLOR)
        stats_rect = stats_text.get_rect(center=(WINDOW_WIDTH // 2,
                                                  WINDOW_HEIGHT // 2 + 20))
        self.screen.blit(stats_text, stats_rect)

        # Restart hint
        blink = self.frame_count % 60 < 40
        if blink:
            hint = self.font_large.render(
                "[ R ] Restart     [ Q ] Quit", True, (180, 180, 180))
            hint_rect = hint.get_rect(center=(WINDOW_WIDTH // 2,
                                               WINDOW_HEIGHT // 2 + 60))
            self.screen.blit(hint, hint_rect)

    def _draw_text(self, text, x, y, font, color):
        surf = font.render(text, True, color)
        self.screen.blit(surf, (x, y))

    def emit_particles(self, grid_pos, color, count=8):
        sx, sy = self._grid_to_screen(*grid_pos)
        cx = sx + CELL_SIZE // 2
        cy = sy + CELL_SIZE // 2
        self.sprite_cache.particle_system.emit(cx, cy, color, count)
