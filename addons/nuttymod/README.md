# NuttyMod Loader for The Cube Beta — isolated

NuttyMod is preserved in this separate folder for compatibility and recovery.
The Cube Beta's normal add-on manager scans only files directly inside `addons`,
so it does not discover or start anything in `addons/nuttymod`.

The Halloween `SECURITY ???` door and Broken Lands terminal are part of the main
game in `halloween_update.py`. They do not load or depend on NuttyMod.

## Current behavior

- NuttyMod does not start automatically with the game.
- NuttyMod cannot rewrite the main game: Permanent Install is disabled in the
  isolated feature layer and refuses before changing any files.
- The legacy uninstall and backup code remains available only to recover a game
  that used an older NuttyMod Permanent Install.
- The installer removes old top-level NuttyMod files during an upgrade so they
  cannot remain in the game's normal add-on scan path.

## Isolated files

The preserved files include the Python and Ruby loaders, optional Java profiles,
the local health service, connection helpers, and update configuration. Generated
connection files and recovery data stay below this folder:

- `nuttymod_bootstrap/`: Node.js, Go, PowerShell, HTML, and Electron helpers
- `addons/`: optional Fun Mode and Physics3D Python/Ruby pairs. They stay
  together for companion-file lookup and are not scanned by the base game.
- `update_backups/`: connection-repair and legacy recovery backups
- `.nuttymod_state.json`: local loader state, if NuttyMod is manually run
- `.nuttymod_disabled.json`: local disabled add-on state
- `.nuttymod_update_state.json`: local update-channel state
- `.nuttymod_permanent_install.json`: legacy transaction recovery manifest
- `.nuttymod_connection_state.json`: last local connection state

Local connection listeners bind only to `127.0.0.1`. Local account information,
if the preserved connection flow is manually used, remains under
`%LOCALAPPDATA%\NuttyMod`.

## Manual compatibility notes

NuttyMod's legacy loader recognizes `.py`, `.rb`, `.bat`, `.cs`, `.c#`, and
`.jar` add-ons. Java profiles require Java when executed; the included JARs have
embedded manifests that can be inspected without executing them. Some connection
helpers require Node.js 22 or newer, while Go is needed only to rebuild the local
authentication helper.

This folder is intentionally not a normal gameplay add-on. Moving its files back
to the top level of `addons` would make them eligible for automatic discovery and
undo the isolation provided by this update.
