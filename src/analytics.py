# =============================================================================
# Group: [Your Group Number]
# Date: 2026-03-16
# Members: [Names]
# =============================================================================

"""
Data export and matplotlib chart generation for simulation analytics.
"""

import os
import csv
import src.config as _cfg


class DataExporter:
    """Exports simulation history to CSV and generates matplotlib charts."""

    def __init__(self, history):
        self.history = history

    def export_csv(self, filepath):
        """Write tick-by-tick data to a CSV file."""
        keys = [k for k in self.history if self.history[k]]
        if not keys or not self.history.get("tick"):
            return
        n = len(self.history["tick"])
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(keys)
            for i in range(n):
                row = []
                for k in keys:
                    data = self.history[k]
                    row.append(data[i] if i < len(data) else "")
                writer.writerow(row)

    def plot_waste_over_time(self, save_path=None):
        """Line chart of green/yellow/red waste counts over time."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ticks = self.history.get("tick", [])
        if not ticks:
            return

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(ticks, self.history["green_waste"], color="green", label="Green")
        ax.plot(ticks, self.history["yellow_waste"], color="goldenrod", label="Yellow")
        ax.plot(ticks, self.history["red_waste"], color="red", label="Red")
        ax.set_xlabel("Tick")
        ax.set_ylabel("Waste Count")
        ax.set_title("Waste Levels Over Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=150)
        plt.close(fig)

    def plot_total_vs_threshold(self, save_path=None):
        """Total waste with threshold line."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ticks = self.history.get("tick", [])
        if not ticks:
            return

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(ticks, self.history["total_waste"], color="orange", label="Total Waste")
        ax.axhline(y=_cfg.MAX_RADIATION_THRESHOLD, color="red", linestyle="--",
                    label=f"Threshold ({_cfg.MAX_RADIATION_THRESHOLD})")
        ax.set_xlabel("Tick")
        ax.set_ylabel("Total Waste")
        ax.set_title("Total Waste vs Meltdown Threshold")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=150)
        plt.close(fig)

    def plot_disposal_rate(self, save_path=None):
        """Cumulative waste disposed over time."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ticks = self.history.get("tick", [])
        if not ticks:
            return

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(ticks, self.history["waste_disposed"], color="deepskyblue",
                label="Cumulative Disposed")
        ax.fill_between(ticks, self.history["waste_disposed"], alpha=0.2, color="deepskyblue")
        ax.set_xlabel("Tick")
        ax.set_ylabel("Waste Disposed")
        ax.set_title("Cumulative Waste Disposal")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=150)
        plt.close(fig)

    def plot_agent_energy(self, save_path=None):
        """Average agent energy over time (if energy system enabled)."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ticks = self.history.get("tick", [])
        energy_data = self.history.get("avg_energy", [])
        if not ticks or not energy_data:
            return

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(ticks, energy_data, color="mediumpurple", label="Avg Energy")
        ax.axhline(y=_cfg.AGENT_MAX_ENERGY, color="gray", linestyle=":",
                    label=f"Max ({_cfg.AGENT_MAX_ENERGY})", alpha=0.5)
        ax.set_xlabel("Tick")
        ax.set_ylabel("Average Energy")
        ax.set_title("Average Agent Energy Over Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        if save_path:
            fig.savefig(save_path, dpi=150)
        plt.close(fig)

    def generate_report(self, output_dir):
        """Generate all charts and CSV into the specified directory."""
        os.makedirs(output_dir, exist_ok=True)

        csv_path = os.path.join(output_dir, "simulation_data.csv")
        self.export_csv(csv_path)

        self.plot_waste_over_time(
            save_path=os.path.join(output_dir, "waste_over_time.png"))
        self.plot_total_vs_threshold(
            save_path=os.path.join(output_dir, "total_vs_threshold.png"))
        self.plot_disposal_rate(
            save_path=os.path.join(output_dir, "disposal_rate.png"))

        if _cfg.ENERGY_ENABLED:
            self.plot_agent_energy(
                save_path=os.path.join(output_dir, "agent_energy.png"))

        return output_dir
