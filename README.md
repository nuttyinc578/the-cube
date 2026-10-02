# The Cube Beta — Halloween Update 6.4.0

[![CPE release](https://img.shields.io/github/v/release/nuttyinc578/CPE-OPEN-source?style=for-the-badge&label=CPE)](https://github.com/nuttyinc578/CPE-OPEN-source/releases/latest)
[![CPE status](https://github.com/nuttyinc578/CPE-OPEN-source/actions/workflows/build.yml/badge.svg)](https://github.com/nuttyinc578/CPE-OPEN-source/actions/workflows/build.yml)

[![Build The Cube Beta 6.4.0](https://github.com/nuttyinc578/the-cube/actions/workflows/build-6.4.0.yml/badge.svg?branch=main)](https://github.com/nuttyinc578/the-cube/actions/workflows/build-6.4.0.yml)
[![Download 6.4.0](https://img.shields.io/badge/Download-6.4.0_Halloween-ff7a18?style=for-the-badge&logo=windows)](https://nightly.link/nuttyinc578/the-cube/workflows/build-6.4.0/main/The-Cube-Beta-6.4.0-Windows.zip)
[![Theme Store](https://github.com/nuttyinc578/the-cube/actions/workflows/themes.yml/badge.svg?branch=main)](https://github.com/nuttyinc578/the-cube/actions/workflows/themes.yml)
[![Download themes](https://img.shields.io/badge/nightly.link-download_themes-7c3aed?style=for-the-badge)](https://nightly.link/nuttyinc578/the-cube/workflows/themes/main/The-Cube-Beta-Themes.zip)

> [!CAUTION]
> **The Cube Beta 5.0 is no longer supported.** It no longer receives bug fixes, compatibility updates, security updates, or technical support. Upgrade to 6.4.0.

The Cube Beta is an interactive physics sandbox powered by the Cube Physics Engine (CPE) and Integrated Particle Engine (IPE). Version 6.4.0 adds an animated Halloween world and a mysterious **SECURITY ???** door. It opens the full-screen Broken Lands terminal: log in to the abandoned computer, run `OG.exe -list`, and recover a supported historical version with `OG.exe -6.3.0`, `OG.exe -6.2.2`, or `OG.exe -5.1`.

OG recovery is deliberately backup-first. Portable releases download into staging, ZIP paths are checked, SHA-256 file manifests are written, and a full restore point is created under `backup/og` before replacement is offered. The old 6.2.1 nightly is shown as unavailable because its GitHub Actions artifact expired.

## Download

- [Download the latest successful main-branch artifact with nightly.link](https://nightly.link/nuttyinc578/the-cube/workflows/build-6.4.0/main/The-Cube-Beta-6.4.0-Windows.zip)
- [Open the 6.4.0 GitHub Release](https://github.com/nuttyinc578/the-cube/releases/tag/6.4.0)

The nightly.link ZIP contains:

- `The-Cube-Beta-Halloween-Update-6.4.0-Setup.exe`
- `The-Cube-Beta-Halloween-Update-6.4.0-Portable.zip`
- `SHA256SUMS.txt`

The custom installer displays the MIT License and requires acceptance before installation. The Windows files are not digitally signed, so SmartScreen may show an unknown-publisher warning.

## Run from source

Install Python 3.10 or newer, then run:

```powershell
python -m pip install -r requirements.txt
python the_cube_beta_summer.py
```

Run the automated tests with:

```powershell
python -m unittest test_halloween_music test_og_recovery test_error_update test_summer_game test_theme_system test_legacy_versions cpe.tests.test_cpe cpe.tests.test_full_stack -v
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

Click **Verify & Reload** successfully three times, then press **Ctrl+A** within 45 seconds. Developer Mode includes an **OG / Legacy Versions** menu that loads the actual releases from [`nuttyinc578/the-cube`](https://github.com/nuttyinc578/the-cube/releases). It downloads the real historical EXE, MSI/CAB, Python, ZIP, or source assets into `legacy-versions/<tag>`, records their SHA-256 hashes, creates a backup, and launches the selected installer or application. The Christmas 5.1 release is included. Version 5.0 and earlier remain unsupported and show an extra warning.

## Add-ons

Drop Python (`.py`) or Ruby (`.rb`) add-ons into the `addons` folder. See `addons/README.md` for the supported hooks and examples.

## License and music

The game source is licensed under the [MIT License](LICENSE). “Halloween Music” by Sound4Stock and the fallback Fall Edition track are licensed third-party content; details are in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt). The exact Halloween track is downloaded from its official Pixabay page on first launch and is not distributed as a standalone asset.
