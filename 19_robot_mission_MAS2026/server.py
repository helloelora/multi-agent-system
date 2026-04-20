# =============================================================================
# Group 19
# Date: 2026-04-05
# Members: Ali Dor, Elora Drouilhet
# =============================================================================

"""HTTP server for the Radioactive Waste Mission simulation.

Dashboard at localhost:8080, JSON API at /api/state,
start/stop/reset via POST to /api/{start,stop,reset}.
"""

import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# Headless pygame init before importing model
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()
# Dummy display so sprites can render
pygame.display.set_mode((1, 1))

from src.model import RobotMission
import src.config as _cfg

_lock = threading.Lock()
_model = RobotMission()
_running = False
_sim_thread = None


def _simulation_loop():
    """Step the model periodically in a background thread."""
    global _running
    while _running:
        with _lock:
            if not _model.game_over:
                _model.step()
        time.sleep(0.1)  # ~10 ticks per second


def _get_state():
    """Build a JSON snapshot of the model."""
    with _lock:
        m = _model
        waste_list = []
        for pos, wastes in m.waste_map.items():
            for w in wastes:
                waste_list.append({
                    "x": w.x, "y": w.y, "type": w.waste_type
                })
        robot_list = []
        for r in m.robots:
            robot_list.append({
                "id": r.agent_id,
                "type": r.robot_type,
                "x": r.x, "y": r.y,
                "inventory": list(r.inventory),
                "energy": getattr(r, "energy", 100),
            })
        return {
            "tick": m.tick,
            "game_over": m.game_over,
            "score": m.score,
            "waste_disposed": m.waste_disposed,
            "total_waste": m.total_waste(),
            "threshold": _cfg.MAX_RADIATION_THRESHOLD,
            "grid_cols": _cfg.GRID_COLS,
            "grid_rows": _cfg.GRID_ROWS,
            "zone_1_end": _cfg.ZONE_1_END,
            "zone_2_end": _cfg.ZONE_2_END,
            "waste": waste_list,
            "robots": robot_list,
            "history": {
                "tick": m.history["tick"][-200:],
                "green_waste": m.history["green_waste"][-200:],
                "yellow_waste": m.history["yellow_waste"][-200:],
                "red_waste": m.history["red_waste"][-200:],
                "total_waste": m.history["total_waste"][-200:],
                "waste_disposed": m.history["waste_disposed"][-200:],
                "avg_energy": m.history["avg_energy"][-200:],
            },
        }


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Radioactive Waste Mission - Dashboard</title>
<style>
  body { background: #181820; color: #ddd; font-family: 'Courier New', monospace; margin: 0; padding: 16px; }
  h1 { color: #ffd84a; margin-bottom: 4px; }
  .stats { display: flex; gap: 32px; margin: 12px 0; flex-wrap: wrap; }
  .stat { background: #222232; padding: 10px 18px; border-radius: 8px; border: 1px solid #444; }
  .stat .label { color: #888; font-size: 12px; }
  .stat .value { font-size: 22px; font-weight: bold; }
  .controls { margin: 12px 0; }
  .controls button { background: #334; border: 1px solid #556; color: #ccc; padding: 8px 18px;
    border-radius: 6px; cursor: pointer; font-family: inherit; font-size: 14px; margin-right: 8px; }
  .controls button:hover { background: #445; }
  .controls button.start { border-color: #4a4; color: #8f8; }
  .controls button.stop { border-color: #a44; color: #f88; }
  .panels { display: flex; gap: 16px; flex-wrap: wrap; }
  canvas { background: #12121a; border: 1px solid #333; border-radius: 6px; }
  #grid { image-rendering: pixelated; }
  .chart-label { color: #888; font-size: 12px; margin-top: 8px; }
</style>
</head>
<body>
<h1>RADIOACTIVE WASTE MISSION</h1>
<div class="controls">
  <button class="start" onclick="post('/api/start')">Start</button>
  <button class="stop" onclick="post('/api/stop')">Stop</button>
  <button onclick="post('/api/reset')">Reset</button>
</div>
<div class="stats" id="stats"></div>
<div class="panels">
  <div>
    <div class="chart-label">GRID STATE</div>
    <canvas id="grid" width="480" height="288"></canvas>
  </div>
  <div>
    <div class="chart-label">WASTE OVER TIME</div>
    <canvas id="chart" width="420" height="288"></canvas>
  </div>
</div>
<script>
const CELL = 16;
const COLORS = {green:'#50c850',yellow:'#dcc828',red:'#dc3c3c'};
const ROBOT_C = {green:'#28b428',yellow:'#c8b41e',red:'#c82828'};

function post(url){fetch(url,{method:'POST'});}

async function update(){
  try{
    const r = await fetch('/api/state');
    const s = await r.json();
    drawStats(s);
    drawGrid(s);
    drawChart(s);
  }catch(e){}
  setTimeout(update, 500);
}

function drawStats(s){
  document.getElementById('stats').innerHTML = [
    ['TICK',s.tick,'#ddd'],
    ['WASTE',s.total_waste+'/'+s.threshold, s.total_waste/s.threshold>0.7?'#f44':'#fa0'],
    ['DISPOSED',s.waste_disposed,'#4af'],
    ['SCORE',s.score,'#fd4'],
    ['STATUS',s.game_over?'MELTDOWN':'RUNNING',s.game_over?'#f44':'#4f4'],
  ].map(([l,v,c])=>`<div class="stat"><div class="label">${l}</div><div class="value" style="color:${c}">${v}</div></div>`).join('');
}

function drawGrid(s){
  const c = document.getElementById('grid').getContext('2d');
  const W = s.grid_cols * CELL, H = s.grid_rows * CELL;
  c.canvas.width = W; c.canvas.height = H;
  // Zones
  c.fillStyle='#607850'; c.fillRect(0,0,s.zone_1_end*CELL,H);
  c.fillStyle='#8a7a50'; c.fillRect(s.zone_1_end*CELL,0,(s.zone_2_end-s.zone_1_end)*CELL,H);
  c.fillStyle='#704040'; c.fillRect(s.zone_2_end*CELL,0,(s.grid_cols-s.zone_2_end)*CELL,H);
  // Grid lines
  c.strokeStyle='rgba(255,255,255,0.06)';
  for(let x=0;x<=s.grid_cols;x++){c.beginPath();c.moveTo(x*CELL,0);c.lineTo(x*CELL,H);c.stroke();}
  for(let y=0;y<=s.grid_rows;y++){c.beginPath();c.moveTo(0,y*CELL);c.lineTo(W,y*CELL);c.stroke();}
  // Waste
  for(const w of s.waste){
    c.fillStyle=COLORS[w.type]||'#fff';
    c.beginPath(); c.arc(w.x*CELL+CELL/2, w.y*CELL+CELL/2, 4, 0, Math.PI*2); c.fill();
  }
  // Robots
  for(const r of s.robots){
    c.fillStyle=ROBOT_C[r.type]||'#fff';
    c.fillRect(r.x*CELL+2, r.y*CELL+2, CELL-4, CELL-4);
    c.fillStyle='#fff'; c.font='8px monospace';
    c.fillText(r.type[0].toUpperCase(), r.x*CELL+4, r.y*CELL+CELL-3);
  }
}

function drawChart(s){
  const c = document.getElementById('chart').getContext('2d');
  const W = c.canvas.width, H = c.canvas.height;
  c.clearRect(0,0,W,H);
  const h = s.history;
  if(!h.tick||h.tick.length<2) return;
  const n = h.tick.length;
  const maxV = Math.max(s.threshold*1.1, Math.max(...h.total_waste));
  function line(data, color){
    c.strokeStyle=color; c.lineWidth=2; c.beginPath();
    for(let i=0;i<n;i++){
      const x=i/(n-1)*W, y=H-data[i]/maxV*H;
      i===0?c.moveTo(x,y):c.lineTo(x,y);
    } c.stroke();
  }
  line(h.green_waste,'#50c850');
  line(h.yellow_waste,'#dcc828');
  line(h.red_waste,'#dc3c3c');
  line(h.total_waste,'#fa8030');
  // Threshold line
  c.strokeStyle='#f44'; c.setLineDash([4,4]);
  const ty=H-s.threshold/maxV*H;
  c.beginPath(); c.moveTo(0,ty); c.lineTo(W,ty); c.stroke();
  c.setLineDash([]);
  // Legend
  c.font='11px monospace';
  [['Green','#50c850',10],['Yellow','#dcc828',70],['Red','#dc3c3c',140],['Total','#fa8030',190]].forEach(([l,co,x])=>{
    c.fillStyle=co; c.fillText(l,x,14);
  });
}

update();
</script>
</body>
</html>"""


class SimHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the simulation server."""

    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._send_html(_DASHBOARD_HTML)
        elif self.path == "/api/state":
            self._send_json(_get_state())
        else:
            self.send_error(404)

    def do_POST(self):
        global _running, _sim_thread, _model
        if self.path == "/api/start":
            if not _running:
                _running = True
                _sim_thread = threading.Thread(target=_simulation_loop, daemon=True)
                _sim_thread.start()
            self._send_json({"status": "started"})
        elif self.path == "/api/stop":
            _running = False
            self._send_json({"status": "stopped"})
        elif self.path == "/api/reset":
            _running = False
            time.sleep(0.15)
            with _lock:
                _model = RobotMission()
            self._send_json({"status": "reset"})
        else:
            self.send_error(404)


def main():
    port = 8080
    server = HTTPServer(("", port), SimHandler)
    print(f"Simulation server running at http://localhost:{port}")
    print("Endpoints:")
    print(f"  GET  http://localhost:{port}/           - Dashboard")
    print(f"  GET  http://localhost:{port}/api/state   - JSON state")
    print(f"  POST http://localhost:{port}/api/start   - Start simulation")
    print(f"  POST http://localhost:{port}/api/stop    - Stop simulation")
    print(f"  POST http://localhost:{port}/api/reset   - Reset simulation")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        global _running
        _running = False
        server.server_close()


if __name__ == "__main__":
    main()
