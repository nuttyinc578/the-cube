"""Offline tests: no live account, browser, token or device approval required."""
import queue
import unittest
from github_signin import DEVICE, TOKEN, USER, VERIFY, device_flow


class Stop:
    def __init__(self, cancelled=False):
        self.cancelled = cancelled
        self.intervals = []

    def wait(self, seconds):
        self.intervals.append(seconds)
        return self.cancelled

    def is_set(self):
        return self.cancelled


class GitHubTests(unittest.TestCase):
    def fixture(self, results, *, uri=VERIFY, stop=None):
        output = queue.Queue()
        requests = []
        responses = iter(results)
        stop = stop or Stop()

        def fake(url, data=None, token=None):
            requests.append(url)
            if url == DEVICE:
                self.assertEqual(data['scope'], '')
                return {'device_code':'test-only-device', 'user_code':'TEST-1234',
                        'verification_uri':uri,'interval':5,'expires_in':900}
            if url == TOKEN:
                self.assertNotIn('client_secret',data)
                return next(responses)
            self.assertEqual(url,USER)
            self.assertEqual(token,'demo_token_not_real')
            return {'login':'Cube-Player'}

        device_flow(output,stop,send=fake)
        return list(output.queue), requests, stop.intervals

    def test_pending_slowdown_and_username_only(self):
        values, calls, waits = self.fixture([{'error':'authorization_pending'}, {'error':'slow_down'},
                                               {'access_token':'demo_token_not_real','scope':''}])
        self.assertEqual(values,[('code','TEST-1234'),('signed-in','Cube-Player')])
        self.assertEqual(calls,[DEVICE,TOKEN,TOKEN,TOKEN,USER])
        self.assertEqual(waits,[5,5,10])

    def test_declined_and_cancelled(self):
        self.assertIn('declined', self.fixture([{'error':'access_denied'}])[0][-1][1])
        self.assertEqual(self.fixture([],stop=Stop(True))[1],[DEVICE])

    def test_no_signin_with_extra_scopes(self):
        values, calls, _ = self.fixture([{'access_token':'demo_token_not_real','scope':'repo'}])
        self.assertEqual(values[-1][0],'error')
        self.assertNotIn(USER,calls)
