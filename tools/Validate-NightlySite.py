"""Check the existing GitHub Pages download links and local assets."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import struct

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.images, self.styles = set(), [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            assert attrs['id'] not in self.ids, 'Duplicate page id'
            self.ids.add(attrs['id'])
        if tag == 'a':
            self.links.append(attrs['href'])
        elif tag == 'img':
            assert attrs.get('alt') and attrs.get('width') and attrs.get('height')
            self.images.append(attrs['src'])
        elif tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.styles.append(attrs['href'])


def main():
    docs = ROOT/'docs'
    html = (docs/'index.html').read_text(encoding='utf-8')
    page = Page()
    page.feed(html)
    account = 'https://the-cube-beta-marketplace.memberful.com/account'
    assert 'plus.html' in page.links and account not in page.links
    membership = (docs/'plus.html').read_text(encoding='utf-8')
    assert account not in membership and 'id="membership-account" hidden' in membership
    assert 'id="microsoft-login" disabled' in membership
    assert 'src="auth-build/membership.js"' in membership
    assert 'src="auth-build/callback.js"' in (docs/'microsoft-callback.html').read_text(encoding='utf-8')
    assert account in (ROOT/'tools/site-auth/membership.js').read_text(encoding='utf-8')
    for link in page.links:
        if link.startswith('#'):
            assert link[1:] in page.ids, f'Missing anchor: {link}'
    for resource in page.images+page.styles:
        if not urlsplit(resource).scheme:
            assert (docs/resource).is_file(), f'Missing website asset: {resource}'
    base = 'https://github.com/nuttyinc578/the-cube/releases/download/'
    for filename in ('The-Cube-Beta-6.4.3-nightly.3-Setup.exe', 'The-Cube-Beta-Christmas-6.4.3-nightly.3-Portable.zip', 'SHA256SUMS.txt'):
        assert base+'6.4.3-nightly.3/'+filename in page.links
    assert base+'6.4.2/The-Cube-Beta-6.4.2-Setup.exe' in page.links
    assert base+'6.4.2/The-Cube-Beta-Halloween-6.4.2-Portable.zip' in page.links
    assert 'Build not yet available' not in html and 'No matching published package' not in html
    assert 'public GameLift hosting is not live' in html
    assert 'nightly3-special-player.png' in page.images
    image = (docs/'nightly3-special-player.png').read_bytes()
    assert image[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', image[16:24]) == (1100, 720)
    print('Website passed: stable and nightly downloads, anchors, accessible screenshot and hosting notice.')


if __name__ == '__main__':
    main()
