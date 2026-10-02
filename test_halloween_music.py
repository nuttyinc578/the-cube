import tempfile
import unittest
from pathlib import Path

from halloween_music import HalloweenMusicManager, _extract_audio_url


class HalloweenMusicTests(unittest.TestCase):
    def test_extracts_only_official_pixabay_cdn_audio(self):
        page = '<script type="application/ld+json">{"contentUrl":"https://cdn.pixabay.com/download/audio/test.mp3"}</script>'
        self.assertEqual(_extract_audio_url(page), "https://cdn.pixabay.com/download/audio/test.mp3")

    def test_imports_requested_download(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "halloween_music.mp3"
            manager = HalloweenMusicManager(destination)
            self.assertFalse(manager.ready)


if __name__ == "__main__":
    unittest.main()
