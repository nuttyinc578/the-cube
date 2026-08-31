"""Non-blocking game connection to the Aspire-managed CPE services."""

from __future__ import annotations

import os
import queue
import threading
import time
from typing import Any, Mapping

from .client import BridgeClient, BridgeError
from .protocol import NumericCommand, ProtocolError, parse_numeric_line


class CPEBridgeRuntime:
    """Poll Node commands and publish cube_core cache without blocking Pygame."""

    def __init__(self, *, enabled: bool | None = None):
        if enabled is None:
            enabled = os.environ.get("CPE_DISABLE_BRIDGE", "0").lower() not in {"1", "true", "yes"}
        self.enabled = bool(enabled)
        self._commands: queue.Queue[str] = queue.Queue(maxsize=500)
        self._state_lock = threading.Lock()
        self._latest_cache: tuple[int, dict[str, Any]] | None = None
        self._published_generation = 0
        self._generation = 0
        self._status_lock = threading.Lock()
        self._connected = False
        self._detail = "CPE bridge disabled" if not self.enabled else "Connecting to CPE Node bridge"
        self._last_error = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if self.enabled:
            self._thread = threading.Thread(target=self._worker, name="cpe-bridge", daemon=True)
            self._thread.start()

    def _set_status(self, connected: bool, detail: str, error: str = "") -> None:
        with self._status_lock:
            self._connected = connected
            self._detail = detail
            self._last_error = error[:180]

    def _worker(self) -> None:
        client = BridgeClient(timeout=0.75)
        initialized = False
        while not self._stop.is_set():
            try:
                health = client.health()
                if not initialized:
                    initialized = True
                response = client.poll(limit=100)
                for item in response.get("commands", []):
                    sequence = int(item.get("sequence", 0))
                    if sequence <= client.last_sequence:
                        continue
                    try:
                        self._commands.put_nowait(str(item["line"]))
                    except queue.Full:
                        try:
                            self._commands.get_nowait()
                        except queue.Empty:
                            pass
                        self._commands.put_nowait(str(item["line"]))
                    client.last_sequence = sequence

                with self._state_lock:
                    pending = self._latest_cache
                if pending is not None and pending[0] > self._published_generation:
                    client.publish_state(pending[1])
                    self._published_generation = pending[0]

                service = str(health.get("service", "CPE Node bridge"))
                self._set_status(True, f"Connected to {service} at {client.base_url}")
                self._stop.wait(0.04)
            except BridgeError as exc:
                initialized = False
                self._set_status(False, f"CPE embedded mode; bridge retrying at {client.base_url}", str(exc))
                self._stop.wait(0.75)
            except Exception as exc:
                self._set_status(False, "CPE bridge recovered from an internal error", str(exc))
                self._stop.wait(0.75)

    def publish_cache(self, cache: Mapping[str, Any]) -> None:
        if not self.enabled:
            return
        payload = dict(cache)
        payload.setdefault("engine", "CPE")
        payload.setdefault("protocol", "CPE/1")
        payload["cache_source"] = "cube_core"
        payload["cache_timestamp"] = round(time.time(), 3)
        with self._state_lock:
            self._generation += 1
            self._latest_cache = self._generation, payload

    def drain_commands(self, limit: int = 100) -> list[NumericCommand]:
        commands: list[NumericCommand] = []
        for _ in range(max(0, min(250, int(limit)))):
            try:
                line = self._commands.get_nowait()
            except queue.Empty:
                break
            try:
                commands.append(parse_numeric_line(line))
            except ProtocolError as exc:
                self._set_status(self.connected, "CPE rejected an invalid bridge command", str(exc))
        return commands

    @property
    def connected(self) -> bool:
        with self._status_lock:
            return self._connected

    def status(self) -> dict[str, Any]:
        with self._status_lock:
            return {
                "enabled": self.enabled,
                "connected": self._connected,
                "detail": self._detail,
                "last_error": self._last_error,
            }

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)
