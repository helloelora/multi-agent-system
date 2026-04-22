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
from datetime import datetime
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
    config.GLOBAL_KNOWLEDGE = bool(settings.get("global_knowledge", config.GLOBAL_KNOWLEDGE))


def _print_step_debug(model):
    """Print concise per-step robot state to terminal for debugging decisions."""
    if not getattr(config, "DEBUG_STEP_LOG_ENABLED", False):
        return
    every = max(1, int(getattr(config, "DEBUG_STEP_LOG_EVERY", 1)))
    if model.tick % every != 0:
        return

    green_count = sum(1 for wl in model.waste_map.values() for waste in wl if waste.waste_type == "green")
    yellow_count = sum(1 for wl in model.waste_map.values() for waste in wl if waste.waste_type == "yellow")
    red_count = sum(1 for wl in model.waste_map.values() for waste in wl if waste.waste_type == "red")

    print(f"[T{model.tick:04d}] W={green_count}/{yellow_count}/{red_count} D={model.waste_disposed} Tot={model.total_waste()}")

    for robot in sorted(model.robots, key=lambda item: item.agent_id):
        intent = robot.knowledge.get("current_intention", "-")
        action = robot.knowledge.get("last_action", "-")
        survival_mode = robot.knowledge.get("survival_mode", False)
        inventory = ",".join(robot.inventory) if robot.inventory else "-"
        target = robot.knowledge.get("decision_target") or robot.knowledge.get("intention_target")
        nav_next = robot.knowledge.get("nav_next")
        reason = robot.knowledge.get("decision_reason", "")
        if not reason:
            reason = f"intent={intent}"

        if getattr(config, "DEBUG_STEP_LOG_COMPACT", True):
            print(
                f"  R{robot.agent_id}:{robot.robot_type[0].upper()} pos={robot.pos} e={robot.energy:>3} "
                f"a={action:<10} t={target if target is not None else '-'} n={nav_next if nav_next is not None else '-'} "
                f"why={reason} inv=[{inventory}] s={survival_mode}"
            )
            continue

        lock = robot.knowledge.get("intention_lock", 0)
        print(
            f"  R{robot.agent_id} {robot.robot_type:<6} pos={robot.pos} "
            f"life={robot.energy:>3} inv=[{inventory}] intent={intent:<10} "
            f"lock={lock:<2} action={action:<10} survive={survival_mode} "
            f"target={target if target is not None else '-'} next={nav_next if nav_next is not None else '-'} why={reason}"
        )


class RunLogger:
    """Logs every tick's state to output/runXXX/log.txt for post-run analysis."""

    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(base_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        # Find next run number
        existing = [d for d in os.listdir(output_dir) if d.startswith("run") and d[3:].isdigit()]
        run_num = max((int(d[3:]) for d in existing), default=0) + 1
        self.run_dir = os.path.join(output_dir, f"run{run_num:03d}")
        os.makedirs(self.run_dir, exist_ok=True)
        self.log_path = os.path.join(self.run_dir, "log.txt")
        self._file = open(self.log_path, "w", encoding="utf-8")
        self._file.write(f"# Run {run_num:03d} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._file.write(f"# GLOBAL_KNOWLEDGE={config.GLOBAL_KNOWLEDGE} INITIAL_GREEN={config.INITIAL_GREEN_WASTE}\n\n")

    def log_tick(self, model):
        f = self._file
        gc = sum(1 for wl in model.waste_map.values() for w in wl if w.waste_type == "green")
        yc = sum(1 for wl in model.waste_map.values() for w in wl if w.waste_type == "yellow")
        rc = sum(1 for wl in model.waste_map.values() for w in wl if w.waste_type == "red")
        f.write(f"[T{model.tick:04d}] waste=g{gc}/y{yc}/r{rc} disposed={model.waste_disposed}\n")
        for robot in sorted(model.robots, key=lambda r: r.agent_id):
            k = robot.knowledge
            inv_str = ",".join(robot.inventory) if robot.inventory else "-"
            target = k.get("decision_target")
            known_types = {}
            for info in k.get("known_waste", {}).values():
                t = info.get("type", "?")
                known_types[t] = known_types.get(t, 0) + 1
            known_str = "/".join(f"{t}:{c}" for t, c in sorted(known_types.items())) or "-"
            dropped = k.get("dropped_waste")
            dropped_str = f" dropped={dropped['pos']}" if dropped else ""
            f.write(
                f"  {robot.robot_type[0].upper()}{robot.agent_id} pos={robot.pos} "
                f"e={robot.energy:>5.1f} inv=[{inv_str}] "
                f"act={k.get('decision_reason', '?'):<20} "
                f"tgt={target if target else '-'} "
                f"known=[{known_str}]{dropped_str}\n"
            )

    def log_end(self, model, reason="end"):
        g = model.pipeline_stats.get("green", {})
        y = model.pipeline_stats.get("yellow", {})
        r = model.pipeline_stats.get("red", {})
        self._file.write(
            f"\n=== END ({reason}) tick={model.tick} disposed={model.waste_disposed} ===\n"
            f"Green:  pickups={g.get('pickups',0)} transforms={g.get('transforms',0)} deliveries={g.get('deliveries',0)}\n"
            f"Yellow: pickups={y.get('pickups',0)} transforms={y.get('transforms',0)} deliveries={y.get('deliveries',0)}\n"
            f"Red:    pickups={r.get('pickups',0)} disposals={r.get('disposals',0)}\n"
        )
        self._file.close()
        print(f"Run log saved to: {self.log_path}")

    def close(self):
        if not self._file.closed:
            self._file.close()


def _append_intelligence_run_log(model, run_mode, reason):
    """Append one concise run-summary entry to reports/intelligence_log.md."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(base_dir, "reports", "intelligence_log.md")

        green_count = sum(1 for wl in model.waste_map.values() for waste in wl if waste.waste_type == "green")
        yellow_count = sum(1 for wl in model.waste_map.values() for waste in wl if waste.waste_type == "yellow")
        red_count = sum(1 for wl in model.waste_map.values() for waste in wl if waste.waste_type == "red")
        in_survival = sum(1 for robot in model.robots if robot.knowledge.get("survival_mode", False))
        alive = sum(1 for robot in model.robots if robot.energy > 0)

        if model.game_over:
            status = "success" if getattr(model, "mission_success", False) else "failure"
        else:
            status = "interrupted"

        entry = (
            "\n"
            f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"- **Change**: Auto-run summary | mode={run_mode} | reason={reason}.\n"
            f"- **Observed**: status={status}, tick={model.tick}, disposed={model.waste_disposed}, waste G/Y/R={green_count}/{yellow_count}/{red_count}, survival_agents={in_survival}, alive={alive}/{len(model.robots)}.\n"
            f"- **Decision**: Keep append log; tune next from this snapshot if yellow collection or handoff stalls.\n"
        )

        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(entry)
    except Exception as log_exc:
        print(f"Intelligence log append failed: {log_exc}")


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
        run_logger = RunLogger()

        paused = False
        speed = 1
        frame_count = 0
        go_to_menu = False
        game_over_sound_played = False
        run_mode = settings.get("run_mode", RUN_MODE_AUTO)
        step_budget = 0
        run_summary_logged = False

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

                elif event.type == pygame.MOUSEWHEEL:
                    renderer.handle_scroll(event.y)

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
                        if not run_summary_logged:
                            _append_intelligence_run_log(model, run_mode, reason="main_menu")
                            run_summary_logged = True
                        run_logger.log_end(model, reason="main_menu")
                        go_to_menu = True
                    elif event.key == pygame.K_r:
                        if not run_summary_logged:
                            _append_intelligence_run_log(model, run_mode, reason="restart")
                            run_summary_logged = True
                        run_logger.log_end(model, reason="restart")
                        model = RobotMission(
                            human_mode=human_mode,
                            human_color=human_color)
                        run_logger = RunLogger()
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
                    _print_step_debug(model)
                    run_logger.log_tick(model)
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

                    if model.game_over and not run_summary_logged:
                        _append_intelligence_run_log(model, run_mode, reason="game_over")
                        run_logger.log_end(model, reason="game_over")
                        run_summary_logged = True

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
