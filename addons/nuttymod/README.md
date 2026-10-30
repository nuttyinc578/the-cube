# NuttyMod Loader for The Cube Beta Halloween Update

This package provides NuttyMod Loader **1.4.5 Stable** and **1.5.0-beta**.
It supports The Cube Beta Halloween Update versions **6.4.0**, **6.4.1**,
and **6.4.2-nightly**.

## CPELoader unlock is required

NuttyMod refuses to start unless all three CPELoader components are installed
and the game's real CPELoader state is unlocked:

- `cpeloader.py`
- `cpeloader_core_runtime.js`
- `cpeloader_core.rb`

Open the game, press **Ctrl+A**, and then press **Y** to unlock CPELoader. The
loader validates `cpeloader_state.json` through the game's own `CPELoader`
implementation. It does not create, fake, or bypass an unlock.

## Stable and Beta channels

- Stable selects NuttyMod **1.4.5**.
- Beta selects NuttyMod **1.5.0-beta**.
- Channel selection is stored in
  `addons/nuttymod/.nuttymod_update_state.json`.
- Restart the game after changing channels.

Changing channels only updates the isolated NuttyMod state and profile JARs.
It never replaces `cube_core.py`, `cpeloader.py`, or another Halloween game
file. CPELoader's in-game update restrictions remain active; use a trusted,
signed external installer for game-core or loader-file updates.

## Isolation and compatibility

NuttyMod stays below `addons/nuttymod`. The base add-on manager scans only
files directly inside `addons`, so it does not automatically execute this
loader or the optional packs in `addons/nuttymod/addons`.

Permanent Install is disabled for the Halloween Update. The legacy backup and
uninstall routines remain only for recovery from older NuttyMod installations.
The Halloween `SECURITY ???` door and Broken Lands terminal continue to belong
to the main game in `halloween_update.py` and do not depend on NuttyMod.

The preserved loader recognizes `.py`, `.rb`, `.bat`, `.batch`, `.cs`, `.c#`,
and `.jar` add-ons. Java profiles can be inspected without executing Java.
The optional local connection helper supports Node.js 22 or newer; Go is only
needed to rebuild its local authentication helper.

Generated connection data, disabled-addon state, channel state, and recovery
backups remain inside this isolated folder. Local listeners bind only to
`127.0.0.1`, and local account information remains below
`%LOCALAPPDATA%\NuttyMod`.
