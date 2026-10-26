"""Headless authoritative CPE physics worker. stdin/actions, stdout/snapshots."""
import contextlib
import json
import math
import os
import queue
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
with contextlib.redirect_stdout(sys.stderr):
    from cube_core import PhysicsWorld, FallEventController, WIDTH, FLOOR_Y


class Simulation:
    def __init__(self):
        addons = SimpleNamespace(shapes=[], events=[])
        self.world = PhysicsWorld(700, addons)
        self.events = FallEventController(35, addons)
        self.last_event = 0.0

    def action(self, player, data):
        if not isinstance(data, dict):
            return
        kind = data.get('action')
        try:
            x, y = float(data.get('x', WIDTH/2)), float(data.get('y', 100))
            if not math.isfinite(x) or not math.isfinite(y):
                return
            x, y = min(max(0, x), WIDTH), min(max(0, y), FLOOR_Y)
            if kind == 'spawn':
                self.world.spawn(x, y, player)
            elif kind == 'burst':
                self.world.burst((x, y))
            elif kind == 'spawn_rain':
                for i in range(8):
                    self.world.spawn(70+i*(WIDTH-140)/7, 90, player)
            elif kind == 'drag_start':
                entity = int(data.get('id', 0))
                if any(item[0] == entity for name, item in self.world.dragging.items() if name != player):
                    return
                self.world.begin_drag(player, (x, y), entity)
            elif kind == 'drag_move':
                self.world.move_drag(player, (x, y))
            elif kind in ('drag_end', 'disconnect'):
                self.world.end_drag(player)
            elif kind == 'event' and time.monotonic()-self.last_event > 10:
                self.events.trigger(self.world)
                self.last_event = time.monotonic()
        except (ValueError, TypeError, OverflowError):
            return

    def step(self):
        wind, scale = self.events.update(1/60, self.world)
        self.world.update(1/60, wind, scale)

    def snapshot(self):
        return {'type': 'snapshot', 'entities': self.world.snapshot()[:180],
            'particles': self.world.particle_snapshot()[:400], 'event': self.events.state(), 'paused': False}


def main():
    messages = queue.Queue(maxsize=256)
    ended = threading.Event()
    def read():
        try:
            for line in sys.stdin:
                if len(line) > 8192:
                    continue
                try:
                    messages.put(json.loads(line), timeout=1)
                except (ValueError, queue.Full):
                    continue
        finally:
            ended.set()
    threading.Thread(target=read, daemon=True).start()
    with contextlib.redirect_stdout(sys.stderr):
        simulation = Simulation()
    print(json.dumps({'type': 'ready'}), flush=True)
    ticks = 0
    while not ended.is_set():
        started = time.monotonic()
        with contextlib.redirect_stdout(sys.stderr):
            for _ in range(64):
                try:
                    message = messages.get_nowait()
                except queue.Empty:
                    break
                if isinstance(message, dict) and isinstance(message.get('player'), str):
                    simulation.action(message['player'], message.get('data'))
            simulation.step()
        ticks += 1
        if ticks % 3 == 0:
            print(json.dumps(simulation.snapshot(), separators=(',', ':'), allow_nan=False), flush=True)
        time.sleep(max(0, 1/60-(time.monotonic()-started)))


if __name__ == '__main__':
    main()
