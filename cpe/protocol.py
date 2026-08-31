"""CPE/1 command compiler and numeric line parser.

The bridge accepts readable JSON, then emits bounded numeric instructions such as::

    CPE/1 42 1 320 80 32 1 238 108 56

That example is command sequence 42, opcode 1 (spawn box), followed by the
numeric values consumed by Pymunk and Pygame. No source code is evaluated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


PROTOCOL_VERSION = "CPE/1"
MAX_LINE_LENGTH = 1024

OPCODES = {
    "spawn_box": 1,
    "spawn_circle": 2,
    "spawn_polygon": 3,
    "gravity": 10,
    "impulse": 11,
    "force": 12,
    "particle_burst": 20,
    "clear": 30,
    "pause": 40,
}

COMMANDS = {value: key for key, value in OPCODES.items()}
ARITY = {
    1: 7,
    2: 7,
    3: 8,
    10: 2,
    11: 3,
    12: 3,
    20: 8,
    30: 0,
    40: 1,
}


class ProtocolError(ValueError):
    """Raised when a command cannot be represented safely by CPE/1."""


@dataclass(frozen=True, slots=True)
class NumericCommand:
    sequence: int
    opcode: int
    name: str
    values: tuple[float, ...]

    def to_line(self) -> str:
        tokens = [PROTOCOL_VERSION, str(self.sequence), str(self.opcode)]
        tokens.extend(_format_number(value) for value in self.values)
        return " ".join(tokens)


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return format(float(value), ".9g")


def _number(
    value: Any,
    label: str,
    low: float,
    high: float,
    *,
    integer: bool = False,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"{label} must be a number") from exc
    if not math.isfinite(number):
        raise ProtocolError(f"{label} must be finite")
    number = max(low, min(high, number))
    return float(round(number)) if integer else number


def _color(value: Any) -> tuple[float, float, float]:
    if value is None:
        value = (238, 108, 56)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 3:
        raise ProtocolError("color must contain three RGB numbers")
    return tuple(_number(channel, "color", 0, 255, integer=True) for channel in value)


def _command(sequence: int, opcode: int, values: Sequence[float]) -> NumericCommand:
    return NumericCommand(sequence, opcode, COMMANDS[opcode], tuple(float(value) for value in values))


def compile_command(sequence: int, payload: Mapping[str, Any]) -> NumericCommand:
    """Compile one readable command object into a bounded CPE/1 instruction."""

    sequence = int(_number(sequence, "sequence", 0, 2_147_483_647, integer=True))
    if not isinstance(payload, Mapping):
        raise ProtocolError("command payload must be an object")
    action = str(payload.get("action") or payload.get("command") or "").strip().lower()

    if action in {"spawn", "spawn_box", "spawn_circle", "spawn_polygon"}:
        shape = str(payload.get("shape") or "box").strip().lower()
        if action.startswith("spawn_"):
            shape = action.removeprefix("spawn_")
        if shape not in {"box", "circle", "polygon"}:
            raise ProtocolError("shape must be box, circle, or polygon")
        x = _number(payload.get("x", 320), "x", -10_000, 10_000)
        y = _number(payload.get("y", 80), "y", -10_000, 10_000)
        size = _number(payload.get("size", payload.get("radius", 28)), "size", 4, 250)
        mass = _number(payload.get("mass", 1), "mass", 0.05, 1_000)
        color = _color(payload.get("color"))
        if shape == "polygon":
            sides = _number(payload.get("sides", 6), "sides", 3, 12, integer=True)
            return _command(sequence, OPCODES["spawn_polygon"], (x, y, sides, size, mass, *color))
        opcode = OPCODES[f"spawn_{shape}"]
        return _command(sequence, opcode, (x, y, size, mass, *color))

    if action in {"gravity", "set_gravity"}:
        gx = _number(payload.get("x", payload.get("gx", 0)), "gravity x", -5_000, 5_000)
        gy = _number(payload.get("y", payload.get("gy", 900)), "gravity y", -5_000, 5_000)
        return _command(sequence, OPCODES["gravity"], (gx, gy))

    if action in {"impulse", "force"}:
        entity_id = _number(payload.get("id"), "entity id", 1, 2_147_483_647, integer=True)
        x = _number(payload.get("x", payload.get("ix" if action == "impulse" else "fx", 0)), "x", -100_000, 100_000)
        y = _number(payload.get("y", payload.get("iy" if action == "impulse" else "fy", 0)), "y", -100_000, 100_000)
        return _command(sequence, OPCODES[action], (entity_id, x, y))

    if action in {"burst", "particle_burst", "particles"}:
        x = _number(payload.get("x", 320), "x", -10_000, 10_000)
        y = _number(payload.get("y", 180), "y", -10_000, 10_000)
        count = _number(payload.get("count", 28), "count", 1, 500, integer=True)
        speed = _number(payload.get("speed", 260), "speed", 0, 5_000)
        lifetime = _number(payload.get("lifetime", 1.1), "lifetime", 0.05, 20)
        color = _color(payload.get("color", (250, 198, 72)))
        return _command(sequence, OPCODES["particle_burst"], (x, y, count, speed, lifetime, *color))

    if action == "clear":
        return _command(sequence, OPCODES["clear"], ())

    if action in {"pause", "resume"}:
        paused = action == "pause"
        if "paused" in payload:
            paused = bool(payload["paused"])
        return _command(sequence, OPCODES["pause"], (1.0 if paused else 0.0,))

    raise ProtocolError(f"unknown CPE action: {action or '<empty>'}")


def parse_numeric_line(line: str) -> NumericCommand:
    """Parse and validate a numeric line produced by the Node bridge."""

    if not isinstance(line, str) or not line.strip():
        raise ProtocolError("command line is empty")
    if len(line) > MAX_LINE_LENGTH:
        raise ProtocolError("command line is too long")
    parts = line.split()
    if len(parts) < 3 or parts[0] != PROTOCOL_VERSION:
        raise ProtocolError(f"command must start with {PROTOCOL_VERSION}")
    try:
        sequence_number = float(parts[1])
        opcode_number = float(parts[2])
    except ValueError as exc:
        raise ProtocolError("sequence and opcode must be integers") from exc
    if not sequence_number.is_integer() or not opcode_number.is_integer():
        raise ProtocolError("sequence and opcode must be integers")
    sequence = int(sequence_number)
    opcode = int(opcode_number)
    if sequence < 0:
        raise ProtocolError("sequence cannot be negative")
    if opcode not in ARITY:
        raise ProtocolError(f"unsupported opcode: {opcode}")
    if len(parts) - 3 != ARITY[opcode]:
        raise ProtocolError(f"opcode {opcode} requires {ARITY[opcode]} numeric values")
    try:
        values = tuple(float(token) for token in parts[3:])
    except ValueError as exc:
        raise ProtocolError("opcode values must be numbers") from exc
    if not all(math.isfinite(value) for value in values):
        raise ProtocolError("opcode values must be finite")
    return NumericCommand(sequence, opcode, COMMANDS[opcode], values)
