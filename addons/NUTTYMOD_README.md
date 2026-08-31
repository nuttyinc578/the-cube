# NuttyMod Loader for The Cube Beta

## NuttyMod v1.4.2 — Fall Edition 6.2

NuttyMod 1.4.2 restores the Add-on/Mod loader, adds an upgraded modified menu,
and introduces a local connection flow plus a transactional Permanent Install
with verified uninstall.

## Startup behavior

- First accepted 1.4.2 launch: the full one-minute install and verification.
- Later launches: a short Add-on/Mod verification and Root Mode activation.
- Before the modified menu opens, NuttyMod runs a paced two-minute local
  connection screen.
- The main menu title is **THE CUBE BETA — FALL EDITION 6.2**, with Root Mode,
  Add-ons, Mods, Studios, and NuttyMod Settings shown below it.

Changing the Terms version intentionally asks for agreement again.

## Local connection and NuttyMod Auth

The two-minute connection completes these local steps:

1. Verify and repair the generated connection helpers.
2. Start the Node.js bridge on an operating-system-assigned local port.
3. Start the compiled Go Auth service on another local port.
4. Open PowerShell account setup only when no valid local account exists.
5. Sign in locally and open the local `nuttymod_bootstrap` page.
6. Finalize through Electron, or the Electron-compatible Node fallback.

Node.js 22 or newer is required. Go is used only when a missing or corrupt
NuttyMod Auth executable must be rebuilt. PowerShell is used only for first
account setup. Electron is optional. Every connection listener binds to
`127.0.0.1` and closes after the handshake; the flow does not use a remote
NuttyMod authentication service.

Generated helpers live under `addons/nuttymod_bootstrap`. Their SHA-256
fingerprints are checked before every connection. Missing files are installed
from embedded sources. Changed or corrupt files are backed up under
`addons/update_backups/<timestamp>-connection-repair`, atomically rewritten,
and verified again.

## NuttyMod Settings

The **NUTTYMOD SETTINGS** menu contains:

- Updates & Game Settings
- Verify Add-ons & Mods
- Permanent Install or Uninstall Permanent Install
- Account Settings
- Terms of Service

Open **Account Settings** to see the local sign-in state. **Log Out** asks for
confirmation, removes the active local token and last connection state, and
keeps the current game open. The next launch requests local account setup.

## Add-on formats

Regular Add-ons support `.py`, `.rb`, `.bat`, `.cs`, `.c#`, and `.jar`.
Stable Mods under `addons/mods` support `.rb`, `.cs`, and `.batch`.

Executable JARs require Java and must print a NuttyMod JSON manifest on their
final output line. The two built-in JARs use an embedded `nuttymod.json`
manifest, so the loader reads them without executing Java:

- `nuttymod_loader_patch.jar`
- `nuttymod_root_mode_profile.jar`

JARs can be installed by drag-and-drop and verified, but the Studios text editor
does not open binary JAR contents.

## Permanent Install

The separately confirmed installer displays a real one-minute progress bar. It
first backs up every tracked target under `addons/update_backups`, then creates
the NuttyMod 1.4.2 source layout:

- `cube_core.py`: removed completely after its verified backup is created
- `the_cube_beta_summer.py`: rewritten to import `nuttymod_core`
- `nuttymod_core.py`: permanent NuttyMod core facade and service hook
- `nuttymod_cube_core.py`: complete Fall Edition 6.2 game implementation
- `nuttymod_service.py`: local in-game health service beside the game files
- Both profile JARs beside the game files and inside source `addons`
- `addons/nuttymod_loader.py`: loader bootstrap
- `addons/_nuttymod_v140_patch.py`: readable 1.4.2 feature layer
- `addons/nuttymod_runtime_v122.pyc`: preserved compatible runtime
- `addons/nuttymod_loader.rb`: Ruby bridge

Python payloads are compiled before installation. Every written output is
verified with SHA-256, and deletion of `cube_core.py` is also verified. Any
failed operation restores the previous layout. The packaged executable must be
restarted and rebuilt after source installation.
## Uninstall Permanent Install

Choose **UNINSTALL PERMANENT INSTALL** in NuttyMod Settings and confirm.
NuttyMod restores exact pre-install backups and removes newly created tracked
files. If a permanent file was edited afterward, that version is copied into
the backup folder before restoration. Restart and rebuild after uninstalling.

## Recovery files

- `.nuttymod_state.json`: terms and first-install state
- `.nuttymod_disabled.json`: disabled Add-ons and Mods
- `.nuttymod_update_state.json`: Stable/Beta update state
- `.nuttymod_permanent_install.json`: permanent transaction manifest
- `.nuttymod_connection_state.json`: last successful local handshake
- `nuttymod_bootstrap/`: local connection helpers and integrity manifests
- `%LOCALAPPDATA%\NuttyMod\auth.json`: local account name and login token
- `update_backups/`: core, update, install, uninstall, and connection-repair
  recovery data

See `NUTTYMOD_TERMS.md` for the complete terms and safety explanation.
