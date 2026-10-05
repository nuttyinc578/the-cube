"""Cube Physics Engine (CPE) public API."""

from .client import BridgeClient, BridgeError
from .backend import CubePhysicsEngine, physics_backend
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

__version__ = "0.0.2"
__dev_beta_version__ = "0.0.2-error-beta"
