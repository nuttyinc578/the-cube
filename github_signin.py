"""Optional GitHub identity for this session. No game privilege or persistent token."""
import json
import queue
import re
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

CLIENT_ID = 'Ov23lidGK36dZlN9a2cW'  # public OAuth App client ID
VERIFY = 'https://github.com/login/device'
DEVICE = VERIFY + '/code'
TOKEN = 'https://github.com/login/oauth/access_token'
USER = 'https://api.github.com/user'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request(url, data=None, token=None):
    if url not in (DEVICE, TOKEN, USER) or (token is not None and url != USER):
        raise ValueError('Unexpected GitHub endpoint')
    headers = {'Accept': 'application/json', 'User-Agent': 'TheCubeBeta/6.4.3-nightly.3'}
    if token is not None:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, data=None if data is None else urllib.parse.urlencode(data).encode('ascii'),
                                 headers=headers)
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=9) as response:
        body = response.read(65537)
    if len(body) > 65536:
        raise ValueError('Oversized response')
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError('Invalid response')
    return value


def device_flow(output, stop, *, send=request, client=CLIENT_ID):
    try:
        start = send(DEVICE, {'client_id': client, 'scope': ''})
        user_code, device = start['user_code'], start['device_code']
        if (start.get('verification_uri') != VERIFY or not isinstance(device, str) or not 1 <= len(device) <= 512
                or not isinstance(user_code, str) or not re.fullmatch(r'[A-Z0-9]{4}-[A-Z0-9]{4}', user_code)):
            raise ValueError('Unrecognized device response')
        interval = max(5, min(90, int(start.get('interval', 5))))
        expires = time.monotonic() + max(1, min(1800, int(start['expires_in'])))
        output.put(('code', user_code))
        while time.monotonic() + interval < expires and not stop.wait(interval):
            result = send(TOKEN, {'client_id': client, 'device_code': device,
                                  'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'})
            if stop.is_set():
                return
            error = result.get('error')
            if error == 'authorization_pending':
                continue
            if error == 'slow_down':
                interval += 5
                continue
            if error == 'access_denied':
                output.put(('error', 'GitHub sign-in declined. Guest play is available.'))
                return
            if error == 'expired_token':
                break
            token = result.get('access_token')
            if (error or result.get('scope', '') or not isinstance(token, str)
                    or not re.fullmatch(r'[A-Za-z0-9_]{10,512}', token)):
                raise ValueError('Unexpected token response')
            login = send(USER, token=token).get('login')
            if not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', login):
                raise ValueError('Invalid GitHub login')
            if not stop.is_set():
                output.put(('signed-in', login))
            return
        if not stop.is_set():
            output.put(('error', 'The GitHub code expired. Start again for a new code.'))
    except (ValueError, KeyError, TypeError, OSError):
        if not stop.is_set():
            output.put(('error', 'GitHub sign-in unavailable. Check your connection and try again.'))


def account_screen(app):
    import pygame
    from cube_core import FPS
    from fluent_ui import FluentButton, accent, buttons, paragraph, text
    from nightly_ui import render_loading

    username = getattr(app, 'github_login', '')
    output, stop = queue.Queue(), threading.Event()
    status, code, focus = ('Signed in for this session' if username else 'Authenticating with GitHub…'), '', 0
    started = time.monotonic()
    if not username:
        threading.Thread(target=device_flow, args=(output, stop), daemon=True).start()
    try:
        while True:
            events = pygame.event.get()
            if not app.common_events(events):
                return False
            if any(e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE for e in events):
                return True
            while not output.empty():
                kind, value = output.get_nowait()
                if kind == 'code':
                    code, status = value, 'Authenticating with GitHub…'
                elif kind == 'signed-in':
                    app.github_login = username = value
                    code, status = '', 'Signed in for this session'
                else:
                    code, status = '', value
            render_loading(app, 1 if username else .62, pygame.time.get_ticks()/1000, status, account_panel=False)
            pygame.draw.rect(app.screen, (26, 30, 43), (190, 371, 720, 239))
            text(app, status, (212, 389), accent(app), app.font, width=670)
            if username:
                text(app, '@' + username, (212, 437), font=app.font)
            elif code:
                text(app, code, (212, 431), font=app.large)
                paragraph(app, 'Enter this code only on github.com/login/device. Check that GitHub names The Cube Beta before approving.', pygame.Rect(212, 489, 674, 60))
            else:
                paragraph(app, 'GitHub sign-in is optional. The game does not request repository access, your password, or a token from you.', pygame.Rect(212, 441, 675, 89))
            controls = [FluentButton((212, 556, 318, 43), 'Continue' if username else 'Play as guest / Esc')]
            if code or username:
                controls.append(FluentButton((550, 556, 333, 43), 'Sign out' if username else 'Open GitHub in browser', accent(app)))
            selected, focus = buttons(app, controls, events, focus % len(controls))
            if selected == 0:
                return True
            if selected == 1 and username:
                app.github_login = ''
                return True
            if selected == 1 and code:
                try:
                    if not webbrowser.open_new(VERIFY):
                        status = 'Open github.com/login/device in your browser'
                except OSError:
                    status = 'Open github.com/login/device in your browser'
            pygame.display.flip()
            app.clock.tick(FPS)
    finally:
        stop.set()
