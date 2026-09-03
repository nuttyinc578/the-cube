# The Cube Beta — Fall Edition 6.2.2

[![CPE release](https://img.shields.io/github/v/release/nuttyinc578/CPE-OPEN-source?style=for-the-badge&label=CPE)](https://github.com/nuttyinc578/CPE-OPEN-source/releases/latest)
[![CPE status](https://github.com/nuttyinc578/CPE-OPEN-source/actions/workflows/build.yml/badge.svg)](https://github.com/nuttyinc578/CPE-OPEN-source/actions/workflows/build.yml)

[![Build The Cube Beta 6.2.2](https://github.com/nuttyinc578/the-cube/actions/workflows/build-6.2.2.yml/badge.svg?branch=main)](https://github.com/nuttyinc578/the-cube/actions/workflows/build-6.2.2.yml)
[![Download 6.2.2](https://img.shields.io/badge/Download-6.2.2_Fall_Edition-f59e0b?style=for-the-badge&logo=windows)](https://nightly.link/nuttyinc578/the-cube/workflows/build-6.2.2/main/The-Cube-Beta-6.2.2-Windows.zip)
[![Theme Store](https://github.com/nuttyinc578/the-cube/actions/workflows/themes.yml/badge.svg?branch=main)](https://github.com/nuttyinc578/the-cube/actions/workflows/themes.yml)
[![Download themes](https://img.shields.io/badge/nightly.link-download_themes-7c3aed?style=for-the-badge)](https://nightly.link/nuttyinc578/the-cube/workflows/themes/main/The-Cube-Beta-Themes.zip)

> [!CAUTION]
> **The Cube Beta 5.0 is no longer supported.** It no longer receives bug fixes, compatibility updates, security updates, or technical support. Upgrade to 6.2.2.

The Cube Beta is an interactive physics sandbox powered by the Cube Physics Engine (CPE) and Integrated Particle Engine (IPE). The 6.2.2 major rewrite adds a staged loader, a verified Theme Store, reversible Developer and Experimental Beta modes, legacy experience profiles, multiplayer, random shapes, seasonal events, Python and Ruby add-ons, and bridges for Node.js, Java, Go, and .NET Aspire.

## Download

- [Download the latest successful main-branch artifact with nightly.link](https://nightly.link/nuttyinc578/the-cube/workflows/build-6.2.2/main/The-Cube-Beta-6.2.2-Windows.zip)
- [Open the 6.2.2 GitHub Release](https://github.com/nuttyinc578/the-cube/releases/tag/6.2.2)

The nightly.link ZIP contains:

- `The-Cube-Beta-Fall-6.2.2-Setup.exe`
- `The-Cube-Beta-Fall-6.2.2-Portable.zip`
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
python -m unittest test_summer_game test_theme_system cpe.tests.test_cpe cpe.tests.test_full_stack -v
```

Build the complete Windows downloads with Inno Setup 6 installed. The build downloads the verified Pixabay music from its immutable archived source commit and checks its SHA-256 hash:

```powershell
.\tools\Prepare-Release.ps1 -Version 6.2.2
```

## Theme Store

- [Download all verified themes with nightly.link](https://nightly.link/nuttyinc578/the-cube/workflows/themes/main/The-Cube-Beta-Themes.zip).
- To install, drop a matching `.py` manifest and `.jar` asset pack into the in-game Theme Store, then click **Verify & Reload** and **Install Dropped Pair**.
- To publish, click **Publish Theme**. With Git and an authenticated GitHub CLI, the game creates `themes/<theme-id>/`, writes its README and badge, pushes a branch in your fork, and opens a pull request.
- Every install, uninstall, mode change, and legacy-profile change writes a restore snapshot under `backup/themes`.

> [!WARNING]
> A theme can rewrite the whole game experience configuration, including menus, loading visuals, colors, layout, and CPE presentation. Python theme manifests are parsed only as literal data and never executed. Theme JARs are treated only as asset archives and cannot contain classes or scripts.

## Developer and OG modes

Click **Verify & Reload** successfully three times, then press **Ctrl+A** within 45 seconds. You can install Developer Beta or Experimental Beta, which use the CPE `0.0.2-dev-beta` compatibility channel. Developer Mode also includes safe OG/Legacy profiles through 6.1.2, including the Christmas update. These profiles use the current 6.2.2 engine; they do not download unsupported old executables.

## Add-ons

Drop Python (`.py`) or Ruby (`.rb`) add-ons into the `addons` folder. See `addons/README.md` for the supported hooks and examples.

## License and music

The game source is licensed under the [MIT License](LICENSE). The Fall Edition music attribution is listed in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).
