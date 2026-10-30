"""Verified NuttyMod game-level Root, with mutable preferences under userdata."""
import hashlib
import ipaddress
import json
import os
import re
import runpy
from pathlib import Path

from cpeloader import write_json


def validate_settings(value):
    from cube_core import THEMES
    if not isinstance(value, dict) or value.get('schema') != 1: raise ValueError('NuttyMod settings need schema: 1.')
    game, cpe = value.get('game', {}), value.get('cpe', {})
    if not isinstance(game, dict) or not isinstance(cpe, dict): raise ValueError('Game and CPE settings must be objects.')
    theme = game.get('theme', 'halloween')
    if theme not in THEMES: raise ValueError('Choose an installed game theme.')
    gravity = int(game.get('gravity', 900))
    if not 150 <= gravity <= 2200: raise ValueError('Gravity must be between 150 and 2200.')
    host = str(cpe.get('aspire_ip', '127.0.0.1')).strip()
    try: ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]{0,251}[a-zA-Z0-9]|[a-zA-Z0-9]', host):
            raise ValueError('Enter an IP address or hostname, not a URL.')
    port = int(cpe.get('node_port', 4310))
    if not 1 <= port <= 65535: raise ValueError('Node port must be 1–65535.')
    title = str(game.get('title', 'The Cube Beta — NuttyMod Root'))[:90]
    mode = value.get('root_mode', {})
    if not isinstance(mode, dict): raise ValueError('Root Mode settings must be an object.')
    interval = int(game.get('event_interval', 18))
    if not 6 <= interval <= 120: raise ValueError('Event interval must be 6–120 seconds.')
    return {'schema': 1, 'game': {'theme': theme, 'gravity': gravity, 'title': title,
            'music': game.get('music', True) is True, 'sound': game.get('sound', True) is True,
            'event_interval': interval},
            'root_mode': {'verbose_loading': mode.get('verbose_loading', True) is True, 'safety': True},
            'cpe': {'aspire_ip': host, 'node_port': port, 'bridge_enabled': cpe.get('bridge_enabled', True) is True}}


def initialize_nuttymod(app, root, profile, logger):
    app.cpeloader.require_flash()
    if not isinstance(profile, dict) or profile.get('schema') != 1: raise RuntimeError('Invalid NuttyMod Root profile.')
    expected = profile.get('files')
    if not isinstance(expected, dict) or not expected: raise RuntimeError('NuttyMod Root integrity records are missing.')
    data = (root/'userdata'/'nuttymod').resolve()
    physical = {p.relative_to(root).as_posix() for folder in (data/'loader', data/'cp')
                for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if physical != set(expected): raise RuntimeError('NuttyMod Root package inventory changed. Restore or reflash matching packages.')
    for relative, checksum in expected.items():
        path = (root/relative).resolve()
        if not path.is_relative_to(data) or not path.is_file(): raise RuntimeError('NuttyMod Root package file is missing.')
        with path.open('rb') as stream: actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != checksum: raise RuntimeError('NuttyMod Root package was modified: '+relative+'. Restore or reflash matching packages.')
    loader = profile.get('loader')
    if loader not in expected: raise RuntimeError('NuttyMod loader is not verified.')
    mode = profile.get('root_mode')
    if not isinstance(mode, dict) or mode.get('library') != '1.2': raise RuntimeError('Required Root Mode lib v1.2 is missing. Reflash matching packages.')
    mode_files = mode.get('files', {})
    if set(mode_files) != {'root_mode_runtime.py', 'root_mode_loader.py', 'rootmode_manifest.json'}:
        raise RuntimeError('Root Mode core integrity records are missing.')
    for name, checksum in mode_files.items():
        path = root/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise RuntimeError('Root Mode core file was modified: '+name)
    defaults = json.loads((data/'cp'/'root_manifest.json').read_text(encoding='utf-8'))
    settings_path = data/'settings.json'
    preferences = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else defaults['settings']
    app.nuttymod_root_settings = validate_settings(preferences)
    app.nuttymod_root_path = settings_path
    app.nuttymod_root_version = str(profile.get('version', '1.0.0'))
    # These modules are compiled from rootmode.tar into the rebuilt executable.
    from root_mode_loader import on_load
    on_load(app, root)
    namespace = runpy.run_path(str(root/loader), init_globals={'app': app, 'userdata': app.userdata, 'game_root': root, 'logger': logger})
    callback = namespace.get('on_load')
    if not callable(callback): raise RuntimeError('NuttyMod Root loader needs on_load(app, userdata).')
    callback(app, app.userdata)
    logger.info('NuttyMod Root verified and active: %s', app.nuttymod_root_version)


def apply_settings(app):
    import pygame
    from cube_core import save_settings
    app.cpeloader.require_flash()
    value = validate_settings(app.nuttymod_root_settings)
    app.nuttymod_root_settings = value
    app.settings.update({key: value['game'][key] for key in ('theme', 'gravity', 'music', 'sound', 'event_interval')})
    os.environ['CPE_ASPIRE_IP'] = value['cpe']['aspire_ip']
    os.environ['CPE_NODE_PORT'] = str(value['cpe']['node_port'])
    os.environ['CPE_DISABLE_BRIDGE'] = '0' if value['cpe']['bridge_enabled'] else '1'
    os.environ.pop('CPE_BRIDGE_URL', None)  # Explicit Root IP/port overrides an inherited URL.
    pygame.display.set_caption(value['game']['title'])
    if pygame.mixer.get_init():
        pygame.mixer.music.set_volume(1.0 if value['game']['music'] else 0.0)
    save_settings(app.settings)
    write_json(app.nuttymod_root_path, value)


def attach_root_settings(app):
    import pygame
    apply_settings(app)
    original_settings, original_events = app.settings_menu, app.common_events
    app.nuttymod_root_original_settings = original_settings
    app.settings_menu = lambda: root_settings_screen(app)
    def events(incoming):
        for event in list(incoming):
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r and event.mod & pygame.KMOD_CTRL and event.mod & pygame.KMOD_SHIFT and not getattr(app, '_nuttymod_root_menu_open', False):
                incoming.remove(event)
                root_settings_screen(app)
        return original_events(incoming)
    app.common_events = events
    app.nuttymod_root_enabled = True


def open_security_menu(app):
    """Enter the existing door/login/OG flow without changing loader policy."""
    door = getattr(app, 'security_door', None)
    if not callable(door): return 'Security / OG menu is unavailable in this game version.'
    door()
    return 'Returned from Security ??? / OG menu.'


def root_settings_screen(app):
    import pygame
    app._nuttymod_root_menu_open = True
    try: _root_settings_screen(app)
    finally:
        app._nuttymod_root_menu_open = False
        pygame.key.stop_text_input()


def _root_settings_screen(app):
    import pygame
    from cube_core import WIDTH, HEIGHT, FPS, THEMES
    editing, text, status = None, '', 'CPE changes apply to the next Play session; backend changes still require flashing.'
    while True:
        value = app.nuttymod_root_settings
        game, cpe = value['game'], value['cpe']
        labels = [('theme', 'GAME THEME: '+game['theme']), ('gravity', 'GRAVITY: '+str(game['gravity'])),
                  ('title', 'WINDOW TITLE: '+game['title']), ('host', 'CPE / ASPIRE IP: '+cpe['aspire_ip']),
                  ('port', 'NODE.JS PORT: '+str(cpe['node_port'])), ('bridge', 'CPE BRIDGE: '+('ON' if cpe['bridge_enabled'] else 'OFF')),
                  ('music', 'MUSIC: '+('ON' if game['music'] else 'OFF')), ('sound', 'CLICK SOUNDS: '+('ON' if game['sound'] else 'OFF')),
                  ('interval', 'EVENT INTERVAL: '+str(game['event_interval'])+'s'),
                  ('verbose', 'VP LOADING RECORD: '+('ON' if value['root_mode']['verbose_loading'] else 'OFF')),
                  ('security', 'SECURITY ??? / OG MENU'),
                  ('normal', 'BASE GAME SETTINGS'), ('back', 'SAVE / BACK')]
        rectangles = [pygame.Rect(55+(i%2)*(WIDTH//2), 185+(i//2)*64, WIDTH//2-80, 56) for i in range(len(labels))]
        rectangles[-1] = pygame.Rect(55, 185+((len(labels)-1)//2)*64, WIDTH-110, 56)
        events = pygame.event.get()
        if not app.common_events(events): raise SystemExit
        for event in events:
            if event.type == pygame.KEYDOWN:
                if editing and event.key == pygame.K_BACKSPACE: text = text[:-1]
                elif event.key == pygame.K_ESCAPE:
                    if editing: editing = None; pygame.key.stop_text_input()
                    else: return
                elif editing and event.key == pygame.K_RETURN:
                    candidate = json.loads(json.dumps(value))
                    try:
                        if editing == 'title': candidate['game']['title'] = text
                        elif editing == 'host': candidate['cpe']['aspire_ip'] = text
                        elif editing == 'port': candidate['cpe']['node_port'] = int(text)
                        app.nuttymod_root_settings = validate_settings(candidate); apply_settings(app)
                        status = 'Saved. New CPE connections use these settings.'
                    except (ValueError, OSError) as exc: status = str(exc)
                    editing = None; pygame.key.stop_text_input()
            elif event.type == pygame.TEXTINPUT and editing and len(text) < 90: text += event.text
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and not editing:
                for index, rect in enumerate(rectangles):
                    if not rect.collidepoint(event.pos): continue
                    action = labels[index][0]
                    if action == 'theme':
                        themes = list(THEMES); game['theme'] = themes[(themes.index(game['theme'])+1)%len(themes)]
                    elif action == 'gravity': game['gravity'] = 150 if game['gravity'] >= 2200 else min(2200, game['gravity']+150)
                    elif action == 'bridge': cpe['bridge_enabled'] = not cpe['bridge_enabled']
                    elif action in {'music', 'sound'}: game[action] = not game[action]
                    elif action == 'interval': game['event_interval'] = 6 if game['event_interval'] >= 120 else min(120, game['event_interval']+6)
                    elif action == 'verbose': value['root_mode']['verbose_loading'] = not value['root_mode']['verbose_loading']
                    elif action == 'security':
                        status = open_security_menu(app)
                        break  # Discard clicks remaining from the previous scene.
                    elif action == 'normal':
                        app.nuttymod_root_original_settings()
                        game.update({key: app.settings[key] for key in ('theme', 'gravity', 'music', 'sound', 'event_interval')})
                        apply_settings(app)
                    elif action == 'back': apply_settings(app); return
                    else:
                        editing = action
                        text = game['title'] if action == 'title' else cpe['aspire_ip'] if action == 'host' else str(cpe['node_port'])
                        pygame.key.start_text_input()
                    if action in {'theme', 'gravity', 'bridge', 'music', 'sound', 'interval', 'verbose'}: apply_settings(app)
        app.screen.fill((13, 9, 28))
        for message, y, font in [('NUTTYMOD ROOT SETTINGS', 65, app.large), ('GAME-LEVEL ROOT / CPELOADER WARNINGS REMAIN ON', 120, app.small)]:
            surface = font.render(message, True, (255, 170, 74)); app.screen.blit(surface, surface.get_rect(center=(WIDTH//2,y)))
        for (action, label), rect in zip(labels, rectangles):
            pygame.draw.rect(app.screen, (45, 30, 68), rect, border_radius=8)
            surface = app.small.render((label if editing != action else '> '+text+' _')[:85], True, (245, 238, 255))
            if surface.get_width() > rect.width-16:
                surface = pygame.transform.smoothscale(surface, (rect.width-16, surface.get_height()))
            app.screen.blit(surface, surface.get_rect(center=rect.center))
        surface = app.tiny.render(status[:112], True, (255, 215, 125)); app.screen.blit(surface, surface.get_rect(center=(WIDTH//2,HEIGHT-35)))
        pygame.display.flip(); app.clock.tick(FPS)
