"""Interactive or headless CPE runner."""

from __future__ import annotations

import argparse
import os
import random
import time
from typing import Any

from .client import BridgeClient, BridgeError
from .engine import CubePhysicsEngine
from .protocol import compile_command


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cube Physics Engine with Integrated Particle Engine")
    parser.add_argument("--aspire-ip", default=os.environ.get("CPE_ASPIRE_IP", "127.0.0.1"))
    parser.add_argument("--node-port", type=int, default=int(os.environ.get("CPE_NODE_PORT", "4310")))
    parser.add_argument("--bridge-url", default=os.environ.get("CPE_BRIDGE_URL"))
    parser.add_argument("--offline", action="store_true", help="run without the Node/Aspire bridge")
    parser.add_argument("--headless", action="store_true", help="run the engine without a Pygame window")
    parser.add_argument("--duration", type=float, default=0, help="stop after N seconds; zero runs until closed")
    parser.add_argument("--empty", action="store_true", help="do not seed the demonstration shapes")
    return parser.parse_args()


def _seed_scene(engine: CubePhysicsEngine) -> None:
    colors = ((222, 108, 39), (250, 198, 72), (102, 122, 58), (187, 62, 38))
    for index in range(6):
        engine.spawn("box" if index % 2 == 0 else "circle", 380 + index * 55, 90 + index * 8, 24, 1, colors[index % 4])


def run(args: argparse.Namespace) -> int:
    engine = CubePhysicsEngine(particle_seed=7)
    if not args.empty:
        _seed_scene(engine)
    client = None if args.offline else BridgeClient(args.aspire_ip, args.node_port, base_url=args.bridge_url)
    connected = False
    next_connection_attempt = 0.0
    next_state_publish = 0.0
    local_sequence = 1
    started = previous = time.monotonic()

    pygame: Any = None
    screen: Any = None
    clock: Any = None
    font: Any = None
    if not args.headless:
        import pygame as pygame_module

        pygame = pygame_module
        pygame.init()
        screen = pygame.display.set_mode((engine.width, engine.height))
        pygame.display.set_caption("Cube Physics Engine (CPE) + Integrated Particle Engine (IPE)")
        clock = pygame.time.Clock()
        font = pygame.font.SysFont("segoeui", 17)

    running = True
    try:
        while running:
            now = time.monotonic()
            dt = min(0.1, now - previous)
            previous = now
            if args.duration > 0 and now - started >= args.duration:
                break

            if client is not None:
                if not connected and now >= next_connection_attempt:
                    try:
                        health = client.health()
                        connected = health.get("ok") is True
                    except BridgeError:
                        connected = False
                        next_connection_attempt = now + 1.0
                if connected:
                    try:
                        client.pump(engine)
                        if now >= next_state_publish:
                            client.publish_state(engine.snapshot())
                            next_state_publish = now + 0.5
                    except BridgeError:
                        connected = False
                        next_connection_attempt = now + 1.0

            if pygame is not None:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                        running = False
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        payload = {
                            "action": "spawn",
                            "shape": random.choice(("box", "circle", "polygon")),
                            "x": event.pos[0],
                            "y": event.pos[1],
                            "sides": random.randint(3, 8),
                            "size": random.randint(18, 38),
                            "color": random.choice(((222, 108, 39), (250, 198, 72), (102, 122, 58))),
                        }
                        if client is not None and connected:
                            client.submit(payload)
                        else:
                            engine.execute(compile_command(local_sequence, payload))
                            local_sequence += 1
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_b:
                        x, y = pygame.mouse.get_pos()
                        engine.execute(compile_command(local_sequence, {"action": "burst", "x": x, "y": y}))
                        local_sequence += 1
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                        engine.execute(compile_command(local_sequence, {"action": "clear"}))
                        local_sequence += 1
                    elif event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                        engine.execute(
                            compile_command(local_sequence, {"action": "pause", "paused": not engine.paused})
                        )
                        local_sequence += 1

            engine.step(dt)
            if pygame is not None:
                engine.render(screen)
                status = f"CPE/1 | {'NODE CONNECTED' if connected else 'LOCAL'} | {len(engine.bodies)} bodies | {len(engine.particles.particles)} IPE particles"
                surface = font.render(status, True, (244, 238, 218))
                screen.blit(surface, (16, 14))
                help_text = font.render("Click: shape   B: particle burst   C: clear   P: pause   Esc: exit", True, (210, 200, 182))
                screen.blit(help_text, (16, 39))
                pygame.display.flip()
                clock.tick(120)
            else:
                time.sleep(1 / 120)
    except KeyboardInterrupt:
        pass
    finally:
        if pygame is not None:
            pygame.quit()
    return 0


def main() -> int:
    return run(_arguments())


if __name__ == "__main__":
    raise SystemExit(main())
