"""Session-only quality selection. Physics keeps its 120 Hz fixed timestep."""
from weakref import WeakSet

_engines = WeakSet()
_fast = False


def fast_enabled() -> bool:
    return _fast


def register(engine) -> None:
    _engines.add(engine)
    engine.set_fast_mode(_fast)


def set_fast_mode(enabled: bool) -> None:
    global _fast
    _fast = bool(enabled)
    for engine in tuple(_engines):
        engine.set_fast_mode(_fast)
