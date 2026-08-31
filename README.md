# The Cube Beta — Fall Edition 6.2.1

[![CPE release](https://img.shields.io/github/v/release/nuttyinc578/CPE-OPEN-source?style=for-the-badge&label=CPE)](https://github.com/nuttyinc578/CPE-OPEN-source/releases/latest)
[![CPE status](https://github.com/nuttyinc578/CPE-OPEN-source/actions/workflows/build.yml/badge.svg)](https://github.com/nuttyinc578/CPE-OPEN-source/actions/workflows/build.yml)

[![Build The Cube Beta 6.2.1](https://github.com/nuttyinc578/the-cube/actions/workflows/build-6.2.1.yml/badge.svg?branch=main)](https://github.com/nuttyinc578/the-cube/actions/workflows/build-6.2.1.yml)
[![Download 6.2.1](https://img.shields.io/badge/Download-6.2.1_Fall_Edition-f59e0b?style=for-the-badge&logo=windows)](https://nightly.link/nuttyinc578/the-cube/workflows/build-6.2.1/main/The-Cube-Beta-6.2.1-Windows.zip)

> [!CAUTION]
> **The Cube Beta 5.0 is no longer supported.** It no longer receives bug fixes, compatibility updates, security updates, or technical support. Upgrade to 6.2.1.

The Cube Beta is an interactive physics sandbox powered by the Cube Physics Engine (CPE) and Integrated Particle Engine (IPE). The Fall Edition includes multiplayer, random shapes, seasonal events, Python and Ruby add-ons, and bridges for Node.js, Java, Go, and .NET Aspire.

## Download

- [Download the latest successful main-branch artifact with nightly.link](https://nightly.link/nuttyinc578/the-cube/workflows/build-6.2.1/main/The-Cube-Beta-6.2.1-Windows.zip)
- [Open the 6.2.1 GitHub Release](https://github.com/nuttyinc578/the-cube/releases/tag/6.2.1)

The nightly.link ZIP contains:

- `The-Cube-Beta-Fall-6.2.1-Setup.exe`
- `The-Cube-Beta-Fall-6.2.1-Portable.zip`
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
python -m unittest test_summer_game cpe.tests.test_cpe cpe.tests.test_full_stack -v
```

Build the complete Windows downloads with Inno Setup 6 installed:

```powershell
.\tools\Prepare-Release.ps1 -Version 6.2.1
```

## Add-ons

Drop Python (`.py`) or Ruby (`.rb`) add-ons into the `addons` folder. See `addons/README.md` for the supported hooks and examples.

## License and music

The game source is licensed under the [MIT License](LICENSE). The Fall Edition music attribution is listed in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).
