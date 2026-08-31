"""Cube Physics Engine (CPE) public API."""

from .client import BridgeClient, BridgeError
from .engine import CubePhysicsEngine
from .particles import IntegratedParticleEngine, Particle
from .protocol import NumericCommand, ProtocolError, compile_command, parse_numeric_line
from .runtime import CPEBridgeRuntime

__all__ = [
    "BridgeClient",
    "BridgeError",
    "CubePhysicsEngine",
    "CPEBridgeRuntime",
    "IntegratedParticleEngine",
    "NumericCommand",
    "Particle",
    "ProtocolError",
    "compile_command",
    "parse_numeric_line",
]

__version__ = "1.0.0"
