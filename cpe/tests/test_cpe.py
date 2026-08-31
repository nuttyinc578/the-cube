from __future__ import annotations

import json
import queue
import shutil
import subprocess
import threading
import unittest
from pathlib import Path

from cpe import BridgeClient, CubePhysicsEngine, IntegratedParticleEngine, ProtocolError
from cpe.protocol import compile_command, parse_numeric_line


ROOT = Path(__file__).resolve().parents[2]
NODE_SERVER = ROOT / "cpe" / "node-bridge" / "server.js"


class ProtocolTests(unittest.TestCase):
    def test_compile_and_parse_polygon(self):
        compiled = compile_command(
            4,
            {
                "action": "spawn",
                "shape": "polygon",
                "x": 150,
                "y": 75,
                "sides": 7,
                "size": 21,
                "mass": 2,
                "color": [10, 20, 30],
            },
        )
        self.assertEqual(compiled.to_line(), "CPE/1 4 3 150 75 7 21 2 10 20 30")
        parsed = parse_numeric_line(compiled.to_line())
        self.assertEqual(parsed.name, "spawn_polygon")
        self.assertEqual(parsed.values[2], 7)

    def test_protocol_rejects_source_code_and_nonfinite_numbers(self):
        with self.assertRaises(ProtocolError):
            compile_command(1, {"action": "execute_code", "source": "print('unsafe')"})
        with self.assertRaises(ProtocolError):
            parse_numeric_line("CPE/1 1 10 nan 900")


class ParticleAndPhysicsTests(unittest.TestCase):
    def test_particle_engine_is_bounded_and_expires_particles(self):
        particles = IntegratedParticleEngine(max_particles=10, seed=1)
        self.assertEqual(particles.emit(10, 20, count=50, lifetime=0.1), 10)
        particles.update(0.1)
        particles.update(0.1)
        self.assertEqual(len(particles.particles), 0)

    def test_engine_executes_numeric_commands(self):
        engine = CubePhysicsEngine(width=500, height=400, particle_seed=1)
        result = engine.execute_line("CPE/1 1 1 200 50 20 1 220 100 40")
        entity_id = result["entity_id"]
        engine.execute_line(f"CPE/1 2 11 {entity_id} 500 -300")
        engine.execute_line("CPE/1 3 20 200 120 18 200 1 250 190 70")
        for _ in range(20):
            engine.step(1 / 60)
        snapshot = engine.snapshot()
        self.assertEqual(snapshot["engine"], "CPE")
        self.assertEqual(len(snapshot["bodies"]), 1)
        self.assertGreater(snapshot["particle_count"], 0)
        engine.execute_line("CPE/1 4 30")
        self.assertEqual(engine.snapshot()["bodies"], [])


    def test_pygame_renderer_draws_physics_and_ipe(self):
        import pygame

        engine = CubePhysicsEngine(width=320, height=240, particle_seed=3)
        engine.execute_line("CPE/1 1 2 120 60 18 1 80 180 235")
        engine.execute_line("CPE/1 2 20 120 80 12 100 2 250 190 70")
        surface = pygame.Surface((320, 240))
        engine.render(surface)
        self.assertEqual(surface.get_size(), (320, 240))
        self.assertNotEqual(surface.get_at((120, 60))[:3], (24, 32, 42))


@unittest.skipUnless(shutil.which("node"), "Node.js is required for the bridge integration test")
class NodeBridgeIntegrationTests(unittest.TestCase):
    def setUp(self):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            ["node", str(NODE_SERVER), "--host", "127.0.0.1", "--port", "0"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=flags,
        )
        output: queue.Queue[str] = queue.Queue()
        reader = threading.Thread(target=lambda: output.put(self.process.stdout.readline()), daemon=True)
        reader.start()
        try:
            ready = json.loads(output.get(timeout=8))
        except queue.Empty as exc:
            self.process.kill()
            raise RuntimeError("Node bridge did not start") from exc
        self.client = BridgeClient("127.0.0.1", ready["port"])

    def tearDown(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        if self.process.stdout is not None:
            self.process.stdout.close()
        if self.process.stderr is not None:
            self.process.stderr.close()

    def test_node_compiles_and_python_executes_commands(self):
        self.assertTrue(self.client.health()["ok"])
        accepted = self.client.submit(
            {"action": "spawn", "shape": "circle", "x": 180, "y": 60, "size": 22, "color": [90, 180, 230]}
        )
        self.assertEqual(accepted["line"].split()[2], "2")
        self.client.submit({"action": "burst", "x": 180, "y": 100, "count": 14})
        engine = CubePhysicsEngine(width=500, height=400, particle_seed=2)
        results = self.client.pump(engine)
        self.assertEqual(len(results), 2)
        self.assertEqual(len(engine.bodies), 1)
        self.assertGreaterEqual(len(engine.particles.particles), 14)
        self.assertTrue(self.client.publish_state(engine.snapshot())["ok"])
        self.assertEqual(self.client.state()["state"]["engine"], "CPE")


if __name__ == "__main__":
    unittest.main()
