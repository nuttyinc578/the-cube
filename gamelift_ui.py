"""Cloud multiplayer entry point in the BASE GAME, never in the flasher."""
import json
import queue
import threading
import pygame
from cube_core import app_path, FPS
from cube_launcher.cloud import DEFAULT_CLOUD, sign_in
from gamelift_client import GameLiftPeer, reserve


def play_gamelift(app):
    config = app_path()/'gamelift.json'
    try:
        if not config.is_file():
            raise ValueError('GameLift is not configured yet. See GAMELIFT_SETUP.md; LAN still works.')
        endpoint = json.loads(config.read_text(encoding='utf-8')).get('backend_url', '')
        if not endpoint:
            raise ValueError('Set backend_url in gamelift.json after deploying your multiplayer backend.')
    except (OSError, ValueError) as exc:
        app.notify(str(exc), 9)
        return
    result = queue.Queue()
    cancelled = threading.Event()
    def connect():
        try:
            session = sign_in(DEFAULT_CLOUD, return_session=True)
            if not cancelled.is_set():
                result.put((reserve(endpoint, session['access_token']), None))
        except Exception:
            # Never display access tokens, player-session credentials or HTTP payloads.
            result.put((None, 'Cloud connection failed. Check Cognito callback, backend configuration and server availability.'))
    threading.Thread(target=connect, daemon=True).start()
    while result.empty():
        events = pygame.event.get()
        if not app.common_events(events) or any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events):
            cancelled.set()
            return
        app.draw_background(pygame.time.get_ticks()/1000)
        app.title_block('Amazon GameLift', 'Connect to the Halloween sandbox',
            'Complete Nuttyinc Cloud sign-in in your browser. ESC cancels.', 150)
        pygame.display.flip()
        app.clock.tick(FPS)
    reservation, error = result.get_nowait()
    if error:
        app.notify(error, 9)
        return
    peer = GameLiftPeer(reservation)
    peer.start()
    app.run_simulation(peer, is_host=False)
