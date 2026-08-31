"""HTTP client connecting CPE Python to its Aspire-managed Node bridge."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping


class BridgeError(RuntimeError):
    pass


class BridgeClient:
    def __init__(
        self,
        aspire_ip: str | None = None,
        node_port: int | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 2.0,
    ):
        configured_url = base_url or os.environ.get("CPE_BRIDGE_URL")
        if configured_url:
            self.base_url = configured_url.rstrip("/")
        else:
            host = aspire_ip or os.environ.get("CPE_ASPIRE_IP", "127.0.0.1")
            port = int(node_port or os.environ.get("CPE_NODE_PORT", "4310"))
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            self.base_url = f"http://{host}:{port}"
        self.timeout = max(0.1, float(timeout))
        self.last_sequence = 0

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            detail = ""
            if isinstance(exc, urllib.error.HTTPError):
                try:
                    detail = exc.read().decode("utf-8")
                except OSError:
                    pass
            raise BridgeError(f"CPE bridge request failed: {exc}{': ' + detail if detail else ''}") from exc

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def submit(self, command: Mapping[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/commands", command)

    def poll(self, limit: int = 100) -> dict[str, Any]:
        safe_limit = max(1, min(250, int(limit)))
        return self._request("GET", f"/commands?after={self.last_sequence}&limit={safe_limit}")

    def pump(self, engine: Any, limit: int = 100) -> list[dict[str, Any]]:
        response = self.poll(limit)
        results: list[dict[str, Any]] = []
        for item in response.get("commands", []):
            sequence = int(item.get("sequence", 0))
            if sequence <= self.last_sequence:
                continue
            results.append(engine.execute_line(str(item["line"])))
            self.last_sequence = sequence
        return results

    def publish_state(self, state: Mapping[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/state", state)

    def state(self) -> dict[str, Any]:
        """Return the most recent physics snapshot published to the bridge."""
        return self._request("GET", "/state")
