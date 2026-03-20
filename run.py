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
from src.agents import (
    ACTION_MOVE_UP, ACTION_MOVE_DOWN, ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT,
    ACTION_PICK_UP, ACTION_TRANSFORM, ACTION_DROP, ACTION_IDLE,
)

EVENT_COLORS = {
    "green": COLOR_GREEN_WASTE,
    "yellow": COLOR_YELLOW_WASTE,
    "red": COLOR_RED_WASTE,
}

RUN_MODE_AUTO = "auto"
RUN_MODE_STEP = "step"
RUN_MODE_STEP5 = "step5"


def _apply_settings(settings):
    """Write menu settings into the config module so the model picks them up."""
    config.NUM_GREEN_ROBOTS = 1
    config.NUM_YELLOW_ROBOTS = 1
    config.NUM_RED_ROBOTS = 1

    # Human mode keeps one robot per color; selected color becomes player-controlled
    human_mode = settings.get("human_mode", False)
    human_color = settings.get("human_color")

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
        human_mode = settings.get("human_mode", False)
        human_color = settings.get("human_color")
        _apply_settings(settings)

        # Create model & renderer with chosen design
        model = RobotMission(human_mode=human_mode, human_color=human_color)
        renderer = Renderer(screen, robot_design=design)

        paused = False
        speed = 1
        frame_count = 0
        go_to_menu = False
        game_over_sound_played = False
        run_mode = settings.get("run_mode", RUN_MODE_AUTO)
        step_budget = 0

        # Key mapping for human player actions
        _HUMAN_KEY_MAP = {
            pygame.K_UP: ACTION_MOVE_UP,
            pygame.K_DOWN: ACTION_MOVE_DOWN,
            pygame.K_LEFT: ACTION_MOVE_LEFT,
            pygame.K_RIGHT: ACTION_MOVE_RIGHT,
            pygame.K_SPACE: ACTION_PICK_UP,
            pygame.K_t: ACTION_TRANSFORM,
            pygame.K_f: ACTION_DROP,
            pygame.K_i: ACTION_IDLE,
        }

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

                    # Pause: ESC in human mode, SPACE in AI mode
                    elif ((human_mode and event.key == pygame.K_ESCAPE) or
                          (not human_mode and event.key == pygame.K_SPACE)):
                        if not model.game_over:
                            # Show pause menu
                            pause_menu = PauseMenu(screen)
                            action = pause_menu.run()
                            if action == PauseMenu.RESUME:
                                pass  # continue game
                            elif action == PauseMenu.RESTART:
                                model = RobotMission(
                                    human_mode=human_mode,
                                    human_color=human_color)
                                renderer._agent_positions.clear()
                                frame_count = 0
                                speed = 1
                                game_over_sound_played = False
                            elif action == PauseMenu.MAIN_MENU:
                                go_to_menu = True
                            elif action == PauseMenu.QUIT:
                                pygame.quit()
                                sys.exit()

                    # Human player controls
                    elif (human_mode and model.human_robot and
                          event.key in _HUMAN_KEY_MAP):
                        model.human_robot.pending_action = _HUMAN_KEY_MAP[event.key]

                    elif event.key == pygame.K_m:
                        go_to_menu = True
                    elif event.key == pygame.K_r:
                        model = RobotMission(
                            human_mode=human_mode,
                            human_color=human_color)
                        renderer._agent_positions.clear()
                        frame_count = 0
                        speed = 1
                        game_over_sound_played = False
                        step_budget = 0
                    elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                        speed = min(speed + 1, 10)
                    elif event.key == pygame.K_MINUS:
                        speed = max(speed - 1, 1)
                    elif event.key == pygame.K_1:
                        run_mode = RUN_MODE_AUTO
                        step_budget = 0
                    elif event.key == pygame.K_2:
                        run_mode = RUN_MODE_STEP
                        step_budget = 0
                    elif event.key == pygame.K_3:
                        run_mode = RUN_MODE_STEP5
                        step_budget = 0
                    elif event.key == pygame.K_n:
                        if run_mode == RUN_MODE_STEP:
                            step_budget += 1
                        elif run_mode == RUN_MODE_STEP5:
                            step_budget += 5
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
            can_step_now = False
            if run_mode == RUN_MODE_AUTO:
                can_step_now = True
            elif run_mode in (RUN_MODE_STEP, RUN_MODE_STEP5):
                can_step_now = step_budget > 0

            if not paused and not model.game_over and can_step_now:
                frame_count += 1
                ticks_per_frame = max(1, config.AGENT_TICK_RATE // speed)
                if frame_count % ticks_per_frame == 0:
                    model.step()
                    if run_mode in (RUN_MODE_STEP, RUN_MODE_STEP5):
                        step_budget = max(0, step_budget - 1)

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

            # Run mode indicator
            mode_label = {
                RUN_MODE_AUTO: "",
                RUN_MODE_STEP: "MODE: STEP | PRESS N",
                RUN_MODE_STEP5: "MODE: STEP x5 | PRESS N",
            }[run_mode]
            mode_text = renderer.font.render(mode_label, True, (180, 220, 255))
            screen.blit(mode_text, (WINDOW_WIDTH - 330, 30))

            if run_mode in (RUN_MODE_STEP, RUN_MODE_STEP5):
                budget_text = renderer.font.render(f"PENDING STEPS: {step_budget}", True, (220, 220, 180))
                screen.blit(budget_text, (WINDOW_WIDTH - 250, 50))

            pygame.display.flip()
            clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
