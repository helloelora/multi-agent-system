# Radioactive Waste Mission

A multi-agent simulation where robots collaborate to collect, transform, and dispose of radioactive waste across a hostile environment divided into three zones of increasing radioactivity.

## Overview

Three types of robots work together in a pipeline:
- **Green robots** operate in Zone 1 (low radiation). They collect green waste, transform it into yellow waste, and pass it eastward.
- **Yellow robots** operate in Zones 1-2 (low-medium radiation). They collect yellow waste, transform it into red waste, and pass it eastward.
- **Red robots** operate in all zones. They collect red waste and transport it to the disposal zone at the eastern edge.

New radioactive waste continuously spawns in Zone 1 at an increasing rate. If total waste exceeds the threshold, the simulation ends in a meltdown.

## Requirements

- Python 3.9+
- Dependencies listed in `requirements.txt`

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
python run.py
```

## Controls

| Key       | Action                    |
|-----------|---------------------------|
| Space     | Pause / Resume            |
| R         | Restart simulation        |
| +/-       | Increase / Decrease speed |
| Q         | Quit                      |

## Configuration

All simulation parameters (grid size, agent counts, spawn rates, thresholds, etc.) can be adjusted in `src/config.py`.

## Project Structure

```
src/
  config.py     - Tunable parameters
  agents.py     - Robot agent classes (Green, Yellow, Red)
  objects.py    - Waste, Radioactivity, Disposal zone
  model.py      - World model and game logic
  renderer.py   - Pygame rendering and visualization
  sprites.py    - Programmatic pixel-art sprite generation
run.py          - Entry point
```
