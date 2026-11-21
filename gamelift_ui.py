"""Cloud multiplayer entry point in the BASE GAME, never in the flasher."""
import json
import queue
import threading
import pygame
from cube_core import app_path, FPS
from gamelift_client import GameLiftPeer, reserve
from microsoft_login import api_application_id, sign_in_online


def play_gamelift(app):
    config = app_path()/'gamelift.json'
    try:
        if not config.is_file():
            raise ValueError('GameLift is not configured yet. See GAMELIFT_SETUP.md; LAN still works.')
        settings = json.loads(config.read_text(encoding='utf-8'))
        if not isinstance(settings, dict):
            raise ValueError('Invalid GameLift configuration.')
        endpoint = settings.get('backend_url')
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError('Set backend_url in gamelift.json after deploying your multiplayer backend.')
        audience = api_application_id(settings.get('microsoft_api_app_id'))
    except (OSError, ValueError) as exc:
        app.notify(str(exc), 9)
        return
    result = queue.Queue()
    cancelled = threading.Event()
    def connect():
        try:
            token = sign_in_online(audience)
            if not cancelled.is_set():
                result.put((reserve(endpoint, token), None))
        except Exception:
            # Never display access tokens, player-session credentials or HTTP payloads.
            result.put((None, 'Online connection failed. Check Microsoft sign-in, server setup and availability.'))
    threading.Thread(target=connect, daemon=True).start()
    while result.empty():
        events = pygame.event.get()
        if not app.common_events(events) or any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events):
            cancelled.set()
            return
        app.draw_background(pygame.time.get_ticks()/1000)
        app.title_block('Amazon GameLift', 'Microsoft sign-in required',
            'Finish signing in in your browser. ESC returns to the game.', 150)
        pygame.display.flip()
        app.clock.tick(FPS)
    reservation, error = result.get_nowait()
    if error:
        app.notify(error, 9)
        return
    peer = GameLiftPeer(reservation)
    peer.start()
    app.run_simulation(peer, is_host=False)
