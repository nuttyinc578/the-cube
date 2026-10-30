# The Cube Beta 6.4.2-nightly

Experimental Fluent Halloween nightly. Stable release 6.4.1 is unchanged.

- Redesigned home, theme gallery, loading, settings and CPELoader confirmation/warnings.
- Halloween enabled on first nightly launch, then your theme choice is remembered.
- New Aurora, Midnight and Rose built-ins, alongside Halloween, Maple, Harvest and Twilight.
- Keyboard navigation (Tab/arrows, Enter), mouse buttons, F11 fullscreen, original click sound.
- Cube Beta Updater checks official GitHub releases, verifies SHA-256 and size, and asks before downloads or running an installer. It does not overwrite a running game. Unlocked/partially unlocked loaders and custom builds are blocked, even with a NuttyMod update override.
- Power & Remastered countdown on home/loading. No release date has been announced. Set `power_remastered_release_utc` in `nightly-config.json` to an ISO 8601 time with a timezone before building (for example, a date ending in `Z`). Until then it truthfully shows “Release date to be announced”.
- Windows runtime: Python **3.15.2**, pygame-ce **2.5.8**, Pymunk **7.3.1**, PyInstaller **6.22.3**. pygame-ce retains the pygame API; do not install original pygame in the same environment.

## Play

Extract the entire portable ZIP into a new folder and run **The Cube Beta Nightly.exe**, or use the separate MIT-consent nightly installer. Do not copy only the EXE: the locked CPELoader sidecars and integrity manifest are required. The installer refuses a nonempty folder to preserve existing installations. This nightly is unsigned; Windows may warn about an unknown publisher.

Halloween music still uses the official Pixabay source with the existing bundled fall fallback. The game works offline if that download is unavailable. Multiplayer hosting is not started by this update; existing LAN/multiplayer configuration is retained.

## Build and verify

Use Python 3.15.2 to create a new virtual environment, then `python -m pip install --only-binary=:all: -r requirements-nightly.txt`. Run `python tools/Build-Nightly.py` from this repository. Inno Setup 6 is needed for the installer. Outputs go to `build/nightly-download`, including portable ZIP, installer and SHA256SUMS.txt. It uses a new `build/nightly-game` folder and refuses to overwrite a previous nightly output.

The dedicated `build-nightly.yml` workflow builds and tests Windows artifacts without replacing 6.4.1 or automatically publishing a GitHub release. The successfully tested Windows artifact is available at:

https://nightly.link/nuttyinc578/the-cube/workflows/build-nightly/main/The-Cube-Beta-6.4.2-nightly-Windows.zip

Artifact downloads expire after 30 days; permanent downloads and checksums are on the [6.4.2-nightly prerelease](https://github.com/nuttyinc578/the-cube/releases/tag/6.4.2-nightly). The in-game updater never treats a nightly.link ZIP as a checksum-verified GitHub release; opening nightly.link is an explicitly confirmed browser action.
