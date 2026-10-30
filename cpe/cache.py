"""Bounded, immutable bridge snapshots with corruption detection.

SHA-256 detects accidental changes; it is not authentication or a sandbox.
Only JSON data is stored, never executable pickle or marshalled Python code.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import dataclass
from typing import Any

MAX_CACHE_BYTES = 2 * 1024 * 1024


class CacheError(ValueError):
    pass


def _validate(value: Any) -> None:
    pending = [(value, 0)]
    visited = 0
    while pending:
        item, depth = pending.pop()
        visited += 1
        if depth > 24 or visited > 60_000:
            raise CacheError('Cache exceeds the supported structure limit')
        if item is None or type(item) in (bool, int):
            continue
        if type(item) is float:
            if not math.isfinite(item):
                raise CacheError('Cache numbers must be finite')
        elif type(item) is str:
            if len(item) > MAX_CACHE_BYTES:
                raise CacheError('Cache string too large')
        elif type(item) in (list, tuple):
            if len(item) > 60_000:
                raise CacheError('Cache collection too large')
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is dict:
            if len(item) > 60_000 or any(type(k) is not str for k in item):
                raise CacheError('Cache objects require bounded string keys')
            pending.extend((child, depth + 1) for child in item.values())
        else:
            raise CacheError('Cache accepts JSON data only')


@dataclass(frozen=True, slots=True)
class ProtectedSnapshot:
    data: bytes
    digest: str

    @classmethod
    def capture(cls, payload: dict) -> 'ProtectedSnapshot':
        if type(payload) is not dict:
            raise CacheError('Cache root must be an object')
        _validate(payload)
        try:
            encoded = json.dumps(payload, allow_nan=False, sort_keys=True,
                                 separators=(',', ':')).encode('utf-8')
        except (ValueError, TypeError, OverflowError) as exc:
            raise CacheError('Cache could not be encoded') from exc
        if len(encoded) > MAX_CACHE_BYTES:
            raise CacheError('Cache exceeds 2 MiB')
        return cls(encoded, hashlib.sha256(encoded).hexdigest())

    def restore(self) -> dict:
        if len(self.data) > MAX_CACHE_BYTES or not hmac.compare_digest(
                hashlib.sha256(self.data).hexdigest(), self.digest):
            raise CacheError('Cache integrity check failed')
        payload = json.loads(self.data)
        if type(payload) is not dict:
            raise CacheError('Cache root must be an object')
        return payload
