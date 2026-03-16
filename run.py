# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
Main entry point for the Radioactive Waste Mission simulation.
"""

import sys
import os
import pygame
import src.config as config
from src.config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, FPS, GAME_TITLE, AGENT_TICK_RATE,
    CELL_SIZE, COLOR_GREEN_WASTE, COLOR_YELLOW_WASTE, COLOR_RED_WASTE,
    SOUND_ENABLED,
)
from src.model import RobotMission
from src.renderer import Renderer
from src.sprites import SpriteCache, DEFAULT_DESIGN
from src.menu import StartMenu, PauseMenu
from src.sounds import SoundManager
from src.analytics import DataExporter

EVENT_COLORS = {
    "green": COLOR_GREEN_WASTE,
    "yellow": COLOR_YELLOW_WASTE,
    "red": COLOR_RED_WASTE,
}


def _apply_settings(settings):
    """Write menu settings into the config module so the model picks them up."""
    config.NUM_GREEN_ROBOTS = settings["num_green"]
    config.NUM_YELLOW_ROBOTS = settings["num_yellow"]
    config.NUM_RED_ROBOTS = settings["num_red"]
    config.INITIAL_GREEN_WASTE = settings["initial_waste"]
    config.MAX_RADIATION_THRESHOLD = settings["max_radiation"]
    config.RADIATION_SPAWN_INTERVAL = settings["spawn_interval"]
    config.AGENT_TICK_RATE = settings["tick_rate"]


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption(GAME_TITLE)
    clock = pygame.time.Clock()

    # Build sprite cache once (all designs are pre-rendered)
    sprite_cache = SpriteCache(CELL_SIZE, num_frames=16)

    # Sound manager
    sound_mgr = SoundManager()
    game_over_sound_played = False

    # ── Main loop: menu -> game -> menu ──────────────────────────────────
    while True:
        # Show start menu
        start_menu = StartMenu(screen, sprite_cache)
        settings = start_menu.run()
        if settings is None:
            # Player chose quit
            break

        design = settings.get("design", DEFAULT_DESIGN)
        _apply_settings(settings)

        # Create model & renderer with chosen design
        model = RobotMission()
        renderer = Renderer(screen, robot_design=design)

        paused = False
        speed = 1
        frame_count = 0
        go_to_menu = False
        game_over_sound_played = False

        running = True
        while running and not go_to_menu:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        pygame.quit()
                        sys.exit()
                    elif event.key == pygame.K_SPACE:
                        if not model.game_over:
                            # Show pause menu
                            pause_menu = PauseMenu(screen)
                            action = pause_menu.run()
                            if action == PauseMenu.RESUME:
                                pass  # continue game
                            elif action == PauseMenu.RESTART:
                                model = RobotMission()
                                renderer._agent_positions.clear()
                                frame_count = 0
                                speed = 1
                                game_over_sound_played = False
                            elif action == PauseMenu.MAIN_MENU:
                                go_to_menu = True
                            elif action == PauseMenu.QUIT:
                                pygame.quit()
                                sys.exit()
                    elif event.key == pygame.K_m:
                        go_to_menu = True
                    elif event.key == pygame.K_r:
                        model = RobotMission()
                        renderer._agent_positions.clear()
                        frame_count = 0
                        speed = 1
                        game_over_sound_played = False
                    elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                        speed = min(speed + 1, 10)
                    elif event.key == pygame.K_MINUS:
                        speed = max(speed - 1, 1)
                    elif event.key == pygame.K_e:
                        # Export analytics report
                        report_dir = os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            "reports",
                            f"report_tick_{model.tick}")
                        try:
                            exporter = DataExporter(model.history)
                            result_dir = exporter.generate_report(report_dir)
                            print(f"Report exported to: {result_dir}")
                        except Exception as e:
                            print(f"Export failed: {e}")

            if go_to_menu:
                break

            # Simulation stepping
            if not paused and not model.game_over:
                frame_count += 1
                ticks_per_frame = max(1, config.AGENT_TICK_RATE // speed)
                if frame_count % ticks_per_frame == 0:
                    model.step()

                    # Process events for particle effects and sounds
                    for evt_type, pos, data in model.events:
                        color = EVENT_COLORS.get(data, (255, 255, 255))
                        if evt_type == "transform":
                            renderer.emit_particles(pos, color, count=12)
                            sound_mgr.play("transform")
                        elif evt_type == "dispose":
                            renderer.emit_particles(pos, (100, 200, 255), count=16)
                            sound_mgr.play("dispose")
                        elif evt_type == "pickup":
                            renderer.emit_particles(pos, color, count=4)
                            sound_mgr.play("pickup")
                        elif evt_type == "mutate":
                            renderer.emit_particles(pos, color, count=8)
                            sound_mgr.play("mutate")

                    # Geiger counter sound based on waste level
                    sound_mgr.play_geiger(
                        model.total_waste(), config.MAX_RADIATION_THRESHOLD)

            # Game over sound
            if model.game_over and not game_over_sound_played:
                sound_mgr.play("gameover")
                game_over_sound_played = True

            # Render
            renderer.draw(model)

            # Speed indicator
            if speed > 1:
                spd_text = renderer.font.render(f"SPEED: {speed}x", True, (180, 180, 220))
                screen.blit(spd_text, (WINDOW_WIDTH - 130, 8))

            pygame.display.flip()
            clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
