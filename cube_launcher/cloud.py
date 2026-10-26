"""Public-client Cognito login: system browser, PKCE, loopback callback."""
import base64
import hashlib
import json
import re
import secrets
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

CALLBACK = 'http://localhost:8765/callback'
WEBSITE_SIGNUP_URL = ('https://ca-central-1kqtmazcpv.auth.ca-central-1.amazoncognito.com/signup'
    '?client_id=q2u1oorqn5lt2v89abisrg7rv&redirect_uri=https%3A%2F%2Fd84l1y8p4kdic.cloudfront.net'
    '&response_type=code&scope=email+openid+phone')


def open_website_signup():
    """Open the owner's website signup flow, not a launcher authentication session."""
    if not webbrowser.open(WEBSITE_SIGNUP_URL):
        raise RuntimeError('Could not open the signup browser.')


DEFAULT_CLOUD = {
    'cognito_domain': 'https://ca-central-1kqtmazcpv.auth.ca-central-1.amazoncognito.com',
    'cognito_client_id': 'q2u1oorqn5lt2v89abisrg7rv',
}


def authorization_url(settings, state, challenge):
    domain, client = validate_config(settings)
    return domain + '/oauth2/authorize?' + urlencode({'response_type': 'code', 'client_id': client,
        'redirect_uri': CALLBACK, 'scope': 'openid email', 'state': state,
        'code_challenge': challenge, 'code_challenge_method': 'S256'})


def validate_config(settings):
    domain = settings.get('cognito_domain', '').rstrip('/')
    client = settings.get('cognito_client_id', '')
    if not re.fullmatch(r'https://[a-z0-9-]+\.auth\.[a-z0-9-]+\.amazoncognito\.com', domain):
        raise ValueError('Configure your AWS Cognito managed-login domain in Settings first.')
    if not re.fullmatch(r'[A-Za-z0-9]{1,128}', client):
        raise ValueError('Configure the public Cognito app client ID (no client secret).')
    return domain, client


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Unexpected sign-in redirect.')


def sign_in(settings, return_session=False):
    domain, client = validate_config(settings)
    verifier, state = secrets.token_urlsafe(64), secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    outcome = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log codes or credentials.

        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            valid = parsed.path == '/callback' and secrets.compare_digest(query.get('state', [''])[0], state)
            if not valid:
                self.send_response(400)
                self.end_headers()
                return
            outcome['code'] = query.get('code', [''])[0]
            outcome['error'] = bool(query.get('error'))
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(b'Return to Cube Beta Launcher. Sign-in is being verified.')

    with HTTPServer(('127.0.0.1', 8765), Callback) as server:
        server.timeout = 0.5
        url = authorization_url(settings, state, challenge)
        if not webbrowser.open(url):
            raise RuntimeError('Could not open the sign-in browser.')
        deadline = time.monotonic() + 180
        while not outcome and time.monotonic() < deadline:
            server.handle_request()
    if not outcome.get('code') or outcome.get('error'):
        raise RuntimeError('Sign-in cancelled or timed out. You can still play offline.')
    opener = urllib.request.build_opener(NoRedirect())
    body = urlencode({'grant_type': 'authorization_code', 'client_id': client, 'code': outcome['code'],
        'redirect_uri': CALLBACK, 'code_verifier': verifier}).encode()
    with opener.open(urllib.request.Request(domain+'/oauth2/token', data=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}), timeout=30) as response:
        tokens = json.loads(response.read(128 * 1024))
    access = tokens.get('access_token')
    if not isinstance(access, str) or not access:
        raise RuntimeError('Cognito did not return an access token.')
    with opener.open(urllib.request.Request(domain+'/oauth2/userInfo', headers={'Authorization': 'Bearer '+access}), timeout=30) as response:
        profile = json.loads(response.read(128 * 1024))
    if not profile.get('sub'):
        raise RuntimeError('Cognito did not confirm the account.')
    # No tokens or passwords are saved to disk; account badge is session-only.
    label = str(profile.get('email') or profile.get('username') or 'Nuttyinc Cloud member')[:160]
    if return_session:
        return {'label': label, 'access_token': access}
    return label
