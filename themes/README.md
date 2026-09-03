# The Cube Beta Theme Store

[![Download verified themes](https://img.shields.io/badge/nightly.link-download_themes-7c3aed?style=for-the-badge)](https://nightly.link/nuttyinc578/the-cube/workflows/themes/main/The-Cube-Beta-Themes.zip)

Community themes appear in The Cube Beta after their pull request is reviewed and merged.

## Publish a theme

1. Create a declarative `.py` manifest containing only `THEME = {...}`.
2. Create a matching `.jar` asset archive with `theme.json` at its root.
3. In the game, open **Theme Store**, drop both files, then choose **Verify & Reload**.
4. Choose **Publish Theme**. The game creates a branch in your GitHub fork and opens a pull request here.

Git and GitHub CLI must be installed, and `gh auth login` must have been completed. Every theme folder must contain exactly one `.py`, one `.jar`, and a `README.md`.

> [!WARNING]
> Installing a theme rewrites the whole game experience configuration: menus, loading visuals, colors, layout settings, and CPE presentation. The Cube Beta creates a restore snapshot in `backup/themes` before every change. Python manifests are parsed as literal data and never executed. JARs are inspected as asset archives and must not contain executable classes or scripts.

The current Windows build is available from the [6.2.2 nightly artifact](https://nightly.link/nuttyinc578/the-cube/workflows/build-6.2.2/main/The-Cube-Beta-6.2.2-Windows.zip).
