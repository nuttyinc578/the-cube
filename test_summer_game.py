"""Regression suite for the Fall Edition's non-visual systems."""

from __future__ import annotations

import socket
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from cube_core import AddonManager, FallEventController, NetworkPeer, PhysicsWorld, fall_countdown


class FallGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addons = AddonManager(Path("addons"))

    def test_python_and_ruby_examples_load(self):
        loaded = {(record.language, record.name) for record in self.addons.records if record.ok}
        self.assertIn(("PY", "Summer Burst"), loaded)
        self.assertIn(("RB", "Tropical Twist"), loaded)
        self.assertGreaterEqual(len(self.addons.shapes), 2)
        self.assertGreaterEqual(len(self.addons.events), 2)

    def test_physics_shapes_and_fall_event(self):
        world = PhysicsWorld(900, self.addons)
        self.addCleanup(world.close)
        self.assertIs(world.space, world.cpe.space)
        for index in range(8):
            world.spawn(120 + index * 70, 120)
        controller = FallEventController(18, self.addons)
        controller.trigger(world)
        wind, gravity_scale = controller.update(1 / 60, world)
        world.update(1 / 60, wind, gravity_scale)
        snapshot = world.snapshot()
        self.assertGreaterEqual(len(snapshot), 8)
        self.assertTrue(controller.state()["name"])
        self.assertGreater(len(world.particle_snapshot()), 0)
        self.assertTrue(all(3 <= item["sides"] <= 8 or item["kind"] == "circle" for item in snapshot))

    def test_fall_countdown_reaches_the_2026_equinox(self):
        text, seconds = fall_countdown(datetime(2026, 9, 22, 0, 5, tzinfo=timezone.utc))
        self.assertEqual(seconds, 86_400)
        self.assertEqual(text, "01D  00H  00M  00S")
        arrived, seconds = fall_countdown(datetime(2026, 9, 23, 0, 5, tzinfo=timezone.utc))
        self.assertEqual((arrived, seconds), ("FALL IS HERE!", 0))

    def test_host_and_guest_exchange_messages(self):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()

        host = NetworkPeer("host", port=port)
        guest = NetworkPeer("client", host="127.0.0.1", port=port)
        host.start()
        guest.start()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not (host.connected and guest.connected):
            time.sleep(0.02)
        self.assertTrue(host.connected and guest.connected)

        guest.send({"type": "action", "data": {"action": "spawn", "x": 100, "y": 100}})
        deadline = time.monotonic() + 2
        received = []
        while time.monotonic() < deadline and not received:
            received = host.messages()
            time.sleep(0.01)
        self.assertEqual(received[0]["data"]["action"], "spawn")

        host.send({"type": "snapshot", "entities": [{"id": 1}]})
        deadline = time.monotonic() + 2
        response = []
        while time.monotonic() < deadline and not response:
            response = guest.messages()
            time.sleep(0.01)
        self.assertEqual(response[0]["entities"][0]["id"], 1)
        guest.close()
        host.close()


if __name__ == "__main__":
    unittest.main()
