from __future__ import annotations

import json
import os
import queue
import shutil
import socket
import subprocess
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from cube_core import AddonManager, PhysicsWorld


ROOT = Path(__file__).resolve().parents[2]
GO_DIRECTORY = ROOT / "cpe" / "go-cache"
GO_BINARY = GO_DIRECTORY / "bin" / "cpe-go-cache.exe"
NODE_SERVER = ROOT / "cpe" / "node-bridge" / "server.js"
JAVA_CLASSES = ROOT / "cpe" / "java-client" / "out"
JAVA_SOURCE = ROOT / "cpe" / "java-client" / "src" / "main" / "java" / "com" / "nuttyinc" / "cpe" / "CpeClient.java"


def free_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def wait_for_health(url: str, timeout: float = 8) -> dict:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"service did not become healthy: {url}: {last_error}")


@unittest.skipUnless(
    shutil.which("node") and shutil.which("go") and shutil.which("java") and shutil.which("javac"),
    "Node.js, Go, Java, and javac are required for the full CPE stack test",
)
class FullStackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        GO_BINARY.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["go", "build", "-o", str(GO_BINARY), "."], cwd=GO_DIRECTORY, check=True)
        subprocess.run(["javac", "-d", str(JAVA_CLASSES), str(JAVA_SOURCE)], cwd=ROOT, check=True)

    def test_java_to_node_to_embedded_game_to_go_cache(self):
        go_port = free_port()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        go_process = subprocess.Popen(
            [str(GO_BINARY), "--host", "127.0.0.1", "--port", str(go_port)],
            cwd=GO_DIRECTORY,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=flags,
        )
        node_process: subprocess.Popen[str] | None = None
        world: PhysicsWorld | None = None
        previous_url = os.environ.get("CPE_BRIDGE_URL")
        try:
            self.assertTrue(wait_for_health(f"http://127.0.0.1:{go_port}/health")["ok"])
            node_environment = os.environ.copy()
            node_environment["CPE_GO_CACHE_URL"] = f"http://127.0.0.1:{go_port}"
            node_process = subprocess.Popen(
                ["node", str(NODE_SERVER), "--host", "127.0.0.1", "--port", "0"],
                cwd=ROOT,
                env=node_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=flags,
            )
            output: queue.Queue[str] = queue.Queue()
            threading.Thread(target=lambda: output.put(node_process.stdout.readline()), daemon=True).start()
            ready = json.loads(output.get(timeout=8))
            node_port = int(ready["port"])
            os.environ["CPE_BRIDGE_URL"] = f"http://127.0.0.1:{node_port}"

            # Queue Java input before PhysicsWorld exists, matching the licence/menu flow.
            java = subprocess.run(
                [
                    "java",
                    "-cp",
                    str(JAVA_CLASSES),
                    "com.nuttyinc.cpe.CpeClient",
                    "127.0.0.1",
                    str(node_port),
                    "spawn",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=flags,
                check=True,
            )
            self.assertIn('"line":"CPE/1', java.stdout)

            world = PhysicsWorld(900, AddonManager(ROOT / "addons"))
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline and not world.cpe_status()["connected"]:
                time.sleep(0.03)
            self.assertTrue(world.cpe_status()["connected"], world.cpe_status())

            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                world.update(1 / 60)
                if any(entity.owner == "cpe-java" for entity in world.entities.values()):
                    break
                time.sleep(0.01)
            self.assertTrue(any(entity.owner == "cpe-java" for entity in world.entities.values()))

            deadline = time.monotonic() + 6
            cached = None
            while time.monotonic() < deadline:
                with urllib.request.urlopen(f"http://127.0.0.1:{go_port}/cache", timeout=1) as response:
                    cached = json.loads(response.read().decode("utf-8"))
                state = cached.get("state", {})
                if state.get("cache_source") == "cube_core" and state.get("bodies"):
                    break
                world.update(1 / 60)
                time.sleep(0.05)
            self.assertIsNotNone(cached)
            self.assertEqual(cached["state"]["engine"], "CPE")
            self.assertEqual(cached["state"]["cache_source"], "cube_core")
            self.assertEqual(cached["state"]["bodies"][0]["owner"], "cpe-java")
            self.assertGreater(cached["state"]["particle_count"], 0)
        finally:
            if world is not None:
                world.close()
            if previous_url is None:
                os.environ.pop("CPE_BRIDGE_URL", None)
            else:
                os.environ["CPE_BRIDGE_URL"] = previous_url
            for process in (node_process, go_process):
                if process is None:
                    continue
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()


if __name__ == "__main__":
    unittest.main()
