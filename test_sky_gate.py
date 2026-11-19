import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import pygame

from sky_gate import ARCHIVE, HOLD_SECONDS, ArchiveView, PlayGate, stage, terminal_command
from archive_ending import CONTRIBUTE_URLS, FLIGHT_TIME, SCENES, ArchiveEnding, flight_frame, open_contribution


def key(kind, code):
    return pygame.event.Event(kind,key=code)


class SkyGateTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(settings={})
        self.play = PlayGate()
        save = patch('sky_gate.save_settings')
        save.start()
        self.addCleanup(save.stop)

    def test_progression_and_archive_keeps_other_world_work_possible(self):
        self.assertEqual(stage(self.app),0)
        self.assertIn('MISSING',terminal_command(self.app,'insert dvd')[0])
        self.assertIn('ACQUIRED',terminal_command(self.app,'key')[0])
        self.assertIn('ALREADY',terminal_command(self.app,'key')[0])
        self.play.process(self.app,[key(pygame.KEYDOWN,pygame.K_e)],now=12)
        self.play.process(self.app,[],now=12+HOLD_SECONDS+.1)
        self.assertEqual(stage(self.app),2)
        self.assertIsNone(self.play.view)
        for rect, n in ((self.play.dvd,3),(self.play.computer,4)):
            events = [pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=rect.center)]
            self.play.process(self.app,events,now=20)
            self.assertEqual(events,[])
            self.assertEqual(stage(self.app),n)
        events=[key(pygame.KEYDOWN,pygame.K_RIGHT)]
        self.play.process(self.app,events,now=21)
        self.assertEqual(self.play.view.index,1)
        self.assertEqual(events,[])
        self.play.process(self.app,[key(pygame.KEYDOWN,pygame.K_ESCAPE)],now=22)
        self.assertIsNone(self.play.view)
        self.assertEqual(stage(self.app),4)

    def test_quick_tap_and_focus_loss(self):
        terminal_command(self.app,'key')
        self.play.process(self.app,[key(pygame.KEYDOWN,pygame.K_e)],now=1)
        self.assertTrue(self.play.process(self.app,[key(pygame.KEYUP,pygame.K_e)],now=1.2))
        self.play.process(self.app,[key(pygame.KEYDOWN,pygame.K_e)],now=2)
        self.play.process(self.app,[pygame.event.Event(pygame.WINDOWFOCUSLOST)],now=2.1)
        self.play.process(self.app,[],now=12)
        self.assertEqual(stage(self.app),1)

    def test_gallery_renders_all_slots(self):
        pygame.init()
        self.addCleanup(pygame.quit)
        self.app.screen=pygame.display.set_mode((1100,720))
        for font, size in (('font',25),('large',52),('small',19),('tiny',15)):
            setattr(self.app,font,pygame.font.Font(None,size))
        view=ArchiveView()
        for view.index in range(len(ARCHIVE)):
            view.draw(self.app)
            _,_,name,_=ARCHIVE[view.index]
            if name:
                self.assertIsNotNone(view.images[name],name)

    def test_credits_achievement_flight_and_consent(self):
        view = ArchiveView()
        next_page = [key(pygame.KEYDOWN,pygame.K_RIGHT)]
        for _ in ARCHIVE:
            self.assertTrue(view.events(next_page,self.app))
        ending = view.ending
        self.assertEqual(ending.page,'credits')
        def click(action):
            btn = next(btn for btn,name in ending.controls() if action==name)
            return [pygame.event.Event(pygame.MOUSEBUTTONUP,button=1,pos=btn.rect.center)]
        self.app.play_click = lambda: None
        with patch('archive_ending.save_settings') as save, patch('archive_ending.webbrowser.open_new_tab',return_value=True) as browser:
            self.assertTrue(view.events(click('flight'),self.app,100))
            self.assertTrue(self.app.settings['special_player_unlocked'])
            self.assertEqual(ending.page,'flight')
            self.assertTrue(ending.new_achievement)
            save.assert_called_once_with(self.app.settings)
            self.assertTrue(view.events([],self.app,100+FLIGHT_TIME+1))
            self.assertEqual(ending.page,'offer')
            self.assertFalse(view.events(click('close'),self.app))
            browser.assert_not_called()
            self.assertTrue(view.events(click('contribute'),self.app))
            self.assertEqual(ending.page,'contribute')
            browser.assert_not_called()
            for action in CONTRIBUTE_URLS:
                self.assertTrue(view.events(click(action),self.app))
                browser.assert_called_with(CONTRIBUTE_URLS[action])
            self.assertIn('posted nothing',ending.status)
            self.assertFalse(open_contribution('unexpected'))
            replay = ArchiveEnding()
            replay.events(self.app, [pygame.event.Event(pygame.MOUSEBUTTONUP,button=1,
                          pos=replay.controls()[-1][0].rect.center)],100)
            self.assertFalse(replay.new_achievement)
            save.assert_called_once()

    def test_flight_order_and_skip_requires_explicit_contribution(self):
        start = 0
        for i, (_, _, duration) in enumerate(SCENES):
            index, phase = flight_frame(start+duration/2)
            self.assertEqual(index,i)
            self.assertAlmostEqual(phase,.5)
            start += duration
        self.assertEqual(flight_frame(FLIGHT_TIME+1),(4,1.0))
        ending = ArchiveEnding()
        ending.page, ending.started = 'flight', 20
        self.app.play_click = lambda: None
        with patch('archive_ending.webbrowser.open_new_tab') as browser:
            ending.events(self.app,[key(pygame.KEYDOWN,pygame.K_RETURN)],now=20)
            self.assertEqual(ending.page,'offer')
            self.assertFalse(ending.events(self.app,[key(pygame.KEYDOWN,pygame.K_RETURN)],now=21))
            browser.assert_not_called()
