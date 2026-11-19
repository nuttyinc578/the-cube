"""Take frames directly from reviewed legacy scripts with dummy SDL.

Point --originals at the downloaded official release scripts (not executables).
Run each pinned source in its own isolated, offline capture process.
"""
import argparse
import hashlib
import os
from pathlib import Path
import random
import runpy
import subprocess
import sys
import tempfile
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ('10.png', 'my.pygame.py', 'eaafb40867815d5b112ec936c1c10f5301af74be7ccce96dc9f01730fe6d5d42'),
    ('20.png', 'my.pygame.v2.0.py', '14e97edd6a148d43b68e756292bddfc351bbb2884c732c2759d7673d83e8b285'),
    ('30.png', 'thecubebeta.py', '16783f7ee15e8932df1c02417cc7b551d8fc278d0cd5189a74ccf1a7580a4fbc'),
    ('40.png', 'thecubebeta4.0.py', '3dd944bee573629a41ddd6dbfeb7787ab18e257ff89f76b89b3c9eac7313ad62'),
    ('49.png', 'thecubebeta4.9.py', 'b7a04f01450e0bbfc29dd77be1294b8a99da6fd8f90674e3d9ab65bf4e8d599c'),
    ('50.png', 'thecubebeta5.0.py', 'cf03c0d239842c86d1efac94cbc6f8401577d07b9ed3b99ac8340148a10f590f'),
    ('51.png', 'the_cube_beta_v5_1_christmas.py', '60448ba49f3eaabc6f866eee421db5692a5bf9a50bc00c1f411a5ae211fa4bc3'),
    ('60.png', 'the cube beta 5.3.py', '686401137ec1445337952f1feb3aba646dc0d562fbb340478c72982454a9b879'),
)


class Captured(Exception):
    pass


def capture(source, shot):
    import pygame
    import pymunk.pygame_util
    random.seed(143)
    scratch = Path.cwd().resolve()
    sys.dont_write_bytecode = True
    def guard(event, args):
        if event.startswith(('socket.', 'subprocess.')) or event in {'os.system', 'os.startfile', 'os.exec'}:
            raise PermissionError('Network or external process blocked during archival capture')
        if event == 'open' and (int(args[2]) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            if not isinstance(args[0], (str, bytes)) or not Path(os.fsdecode(args[0])).resolve().is_relative_to(scratch):
                raise PermissionError('Archive capture may write only to its scratch folder')
    sys.addaudithook(guard)
    if shot == '51.png':
        original_sound = pygame.mixer.Sound
        def legacy_sound(filename):
            try:
                return original_sound(filename)
            except FileNotFoundError as exc:
                # pygame-ce reports missing audio differently; let the old fallback run.
                raise pygame.error('Archived audio not present') from exc
        pygame.mixer.Sound = legacy_sound
    if shot == '60.png':
        def offline(*args, **kwargs):
            raise PermissionError('Archive source capture is offline')
        stub = ModuleType('requests')
        stub.get = offline
        sys.modules['requests'] = stub  # inactive on the first menu, no dependency or account required
    frame = 0
    def draw():
        nonlocal frame
        frame += 1
        if shot == '20.png' and frame == 1:
            for pos in ((288,170),(410,211),(474,149),(550,232)):
                pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=pos))
        if frame >= (35 if shot in {'10.png','20.png','30.png'} else 5):
            pygame.image.save(pygame.display.get_surface(), shot)
            raise Captured()
    pygame.display.flip = pygame.display.update = draw
    try:
        runpy.run_path(str(source),run_name='__main__')
    except Captured:
        return
    raise RuntimeError('Legacy source did not draw enough frames')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--originals', type=Path)
    parser.add_argument('--single', nargs=2)
    args = parser.parse_args()
    if args.single:
        capture(*args.single)
        return
    out = ROOT/'archive_assets'
    out.mkdir(exist_ok=True)
    for shot, name, digest in SOURCES:
        source = ((ROOT if shot in {'51.png','60.png'} else args.originals)/name).resolve()
        if digest and hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
            raise ValueError('Source asset does not match the published hash: '+name)
        with tempfile.TemporaryDirectory(prefix='archive-capture-', dir=ROOT/'build') as tmp:
            subprocess.run([sys.executable, '-I', '-B', __file__, '--single', str(source), shot],
                           cwd=tmp, env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',
                                             PYGAME_HIDE_SUPPORT_PROMPT='1'),check=True,timeout=30)
            (out/shot).write_bytes((Path(tmp)/shot).read_bytes())
        print('Captured',shot,'from',name,flush=True)


if __name__=='__main__':main()
