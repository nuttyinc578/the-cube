# The Cube Beta — 6.4.2 Stable / 6.4.3 Nightly

**Stable:** [6.4.2 installer and portable](https://github.com/nuttyinc578/the-cube/releases/tag/6.4.2).
**Experimental:** [6.4.3-nightly installer, portable and checksums](https://github.com/nuttyinc578/the-cube/releases/tag/6.4.3-nightly).
[Website](https://nuttyinc578.github.io/the-cube/).

The new nightly uses Python 3.15.2 with pygame-ce and brings the Christmas Workshop, eight themes, CPE 0.0.3-nightly protected caches, two-step Fast CPE consent (Ctrl+Alt+T), CPELoader v2 and the Cube Beta Updater. The Power & Remastered countdown awaits a release date. See [nightly notes and build instructions](NIGHTLY_6.4.3.md). Nightly builds are experimental; keep them separate from stable installs and backups.

[![CPE release](https://img.shields.io/github/v/release/nuttyinc578/CPE-OPEN-source?style=for-the-badge&label=CPE)](https://github.com/nuttyinc578/CPE-OPEN-source/releases/latest)
[![CPE status](https://github.com/nuttyinc578/CPE-OPEN-source/actions/workflows/build.yml/badge.svg)](https://github.com/nuttyinc578/CPE-OPEN-source/actions/workflows/build.yml)

[![Build The Cube Beta Nightly](https://github.com/nuttyinc578/the-cube/actions/workflows/build-nightly.yml/badge.svg?branch=main)](https://github.com/nuttyinc578/the-cube/actions/workflows/build-nightly.yml)
[![Download stable 6.4.2](https://img.shields.io/badge/Download-6.4.2_Stable-ff7a18?style=for-the-badge&logo=windows)](https://github.com/nuttyinc578/the-cube/releases/tag/6.4.2)
[![Download nightly](https://img.shields.io/badge/nightly.link-6.4.3_Nightly-9d59d4?style=for-the-badge)](https://nightly.link/nuttyinc578/the-cube/workflows/build-nightly/main/The-Cube-Beta-6.4.3-nightly-Windows.zip)
[![Theme Store](https://github.com/nuttyinc578/the-cube/actions/workflows/themes.yml/badge.svg?branch=main)](https://github.com/nuttyinc578/the-cube/actions/workflows/themes.yml)
[![Download themes](https://img.shields.io/badge/nightly.link-download_themes-7c3aed?style=for-the-badge)](https://nightly.link/nuttyinc578/the-cube/workflows/themes/main/The-Cube-Beta-Themes.zip)

> [!CAUTION]
> **The Cube Beta 5.0 is no longer supported.** It no longer receives bug fixes, compatibility updates, security updates, or technical support. Upgrade to stable 6.4.2.

The Cube Beta is an interactive physics sandbox powered by the Cube Physics Engine (CPE) and Integrated Particle Engine (IPE). Version 6.4.0 adds an animated Halloween world and a mysterious **SECURITY ???** door. It opens the full-screen Broken Lands terminal: log in to the abandoned computer, run `OG.exe -list`, and recover a supported historical version with `OG.exe -6.3.0`, `OG.exe -6.2.2`, or `OG.exe -5.1`.

## CPELoader v2

The Christmas nightly includes a standalone `cpe.exe`. Open **Open CPE Command Prompt.cmd** in the game folder and run `cpe -connect "C:\Games\The Cube Beta" -LOCK -cpeloader`. Omit `-LOCK` for read-only status. Relocking keeps existing file-modification warnings. See [command and Fast CPE documentation](CPELOADER_V2.md).

CPELoader starts locked and blocks engine flashing. Press **Ctrl+A** in the game
to open its warning screen; **Y** unlocks the Python, Node.js, and Ruby components
and resets the game. **Shift+N** cancels. Unlocked loading pauses at **50%** until
you press **Enter**. Changed managed files trigger a warning along the bottom.
In-game version updates are blocked while unlocked; update using the external
installer, which relocks the loader. Runtime settings, caches, backups, and
installer uninstall metadata are excluded from integrity comparisons.

This is an application-level lock, not an OS security boundary. Anyone who can
edit the loader code or state can bypass it. The verified developer shortcut in
the theme store is now **Ctrl+Shift+D** so it does not conflict with Ctrl+A.

OG recovery is deliberately backup-first. Portable releases download into staging, ZIP paths are checked, SHA-256 file manifests are written, and a full restore point is created under `backup/og` before replacement is offered. The old 6.2.1 nightly is shown as unavailable because its GitHub Actions artifact expired.

NuttyMod is isolated under `addons/nuttymod` and is not scanned during a normal launch. Its Permanent Install rewrite is disabled, while the Halloween security door remains built directly into the main game.

## Download

- [Download the latest successful main-branch artifact with nightly.link](https://nightly.link/nuttyinc578/the-cube/workflows/build-nightly/main/The-Cube-Beta-6.4.3-nightly-Windows.zip)
- [Open the stable 6.4.2 GitHub Release](https://github.com/nuttyinc578/the-cube/releases/tag/6.4.2)

The nightly.link ZIP contains:

- `The-Cube-Beta-6.4.3-nightly-Setup.exe`
- `The-Cube-Beta-Christmas-6.4.3-nightly-Portable.zip`
- `SHA256SUMS.txt`

The custom installer displays the MIT License and requires acceptance before installation. The Windows files are not digitally signed, so SmartScreen may show an unknown-publisher warning.

## Run from source

For the current nightly, use Python 3.15.2 in a dedicated virtual environment, then run:

```powershell
python -m pip install --only-binary=:all: -r requirements-nightly.txt
python the_cube_beta_summer.py
```

Run the automated tests with:

```powershell
python -m unittest test_halloween_music test_og_recovery test_nuttymod_isolation test_error_update test_summer_game test_theme_system test_legacy_versions cpe.tests.test_cpe cpe.tests.test_full_stack -v
```

Build the complete Windows downloads with Inno Setup 6 installed. The build downloads the verified Pixabay music from its immutable archived source commit and checks its SHA-256 hash:

```powershell
.\tools\Prepare-Release.ps1 -Version 6.4.0
```

## Theme Store

- [Download all verified themes with nightly.link](https://nightly.link/nuttyinc578/the-cube/workflows/themes/main/The-Cube-Beta-Themes.zip).
- To install, drop a matching `.py` manifest and `.jar` asset pack into the in-game Theme Store, then click **Verify & Reload** and **Install Dropped Pair**.
- To publish, click **Publish Theme**. With Git and an authenticated GitHub CLI, the game creates `themes/<theme-id>/`, writes its README and badge, pushes a branch in your fork, and opens a pull request.
- Every theme install, uninstall, mode change, and GitHub OG download writes a restore snapshot under `backup/themes`.

> [!WARNING]
> A theme can rewrite the whole game experience configuration, including menus, loading visuals, colors, layout, and CPE presentation. Python theme manifests are parsed only as literal data and never executed. Theme JARs are treated only as asset archives and cannot contain classes or scripts.

## Developer and OG modes

Click **Verify & Reload** successfully three times, then press **Ctrl+Shift+D** within 45 seconds. Developer Mode includes an **OG / Legacy Versions** menu that loads the actual releases from [`nuttyinc578/the-cube`](https://github.com/nuttyinc578/the-cube/releases). It downloads the real historical EXE, MSI/CAB, Python, ZIP, or source assets into `legacy-versions/<tag>`, records their SHA-256 hashes, creates a backup, and launches the selected installer or application. The Christmas 5.1 release is included. Version 5.0 and earlier remain unsupported and show an extra warning.

## Add-ons

Drop Python (`.py`) or Ruby (`.rb`) add-ons into the `addons` folder. See `addons/README.md` for the supported hooks and examples.

## License and music

The game source is licensed under the [MIT License](LICENSE). “Halloween Music” by Sound4Stock and the fallback Fall Edition track are licensed third-party content; details are in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt). The exact Halloween track is downloaded from its official Pixabay page on first launch and is not distributed as a standalone asset.
