# The Cube Beta Fall Edition 6.2.2

6.2.2 is a major experience rewrite built on the existing CPE physics, multiplayer, particle engine, and add-on systems.

## Major additions

- A new staged loading screen shows CPE, theme verification, backups, multiplayer, and readiness progress.
- The new Theme Store accepts matching declarative `.py` manifests and `.jar` asset packs.
- Theme publishing verifies both files, creates a theme folder and README, pushes a fork branch, and opens a GitHub pull request.
- Theme Store builds are available as a separate nightly.link artifact.
- Every theme install, uninstall, experience switch, and legacy profile creates a backup first.
- Three successful **Verify & Reload** clicks arm the hidden **Ctrl+A** Developer Mode shortcut for 45 seconds.
- Developer Beta and Experimental Beta use the `0.0.2-dev-beta` CPE compatibility channel.
- The OG/Legacy library includes compatibility profiles from the original edition through 6.1.2, including the Christmas update.

## Theme safety warning

Themes can rewrite the whole game experience configuration, including menus, loading visuals, colors, layouts, and CPE presentation. Python theme manifests are parsed as literal data and are never executed. Theme JARs are inspected as asset archives and cannot contain executable classes or scripts. A backup is created before every change.

> [!CAUTION]
> **The Cube Beta 5.0 is no longer supported.** Its legacy entry is a safe presentation profile running on the current engine, not the unsupported 5.0 executable. Upgrade to 6.2.2 for current fixes, compatibility, and support.

The installer displays the MIT License and requires acceptance. Windows downloads are unsigned, so Microsoft Defender SmartScreen may show an unknown-publisher warning.
