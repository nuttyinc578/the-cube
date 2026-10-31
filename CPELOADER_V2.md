# CPELoader v2

Close the game before changing its lock state. Open **Open CPE Command Prompt.cmd** in the extracted portable folder, or the installer's **CPE Command Prompt** shortcut. The packaged cpe.exe needs no separate Python installation.

```bat
cpe -connect "C:\Games\The Cube Beta" -LOCK -cpeloader
```

The originally requested `cpe -connect -"C:\Games\The Cube Beta" -LOCK -cpeloader` form also works. Use quotes for paths with spaces. Omit `-LOCK` for read-only status. From another Command Prompt directory, use the full path to cpe.exe. Installation does not modify your global PATH.

Source checkout: `python cpeloader_cli.py -connect "." -LOCK -cpeloader`.

Show the version bundled with the command:

```bat
cpe -cpeloader --v
```

This prints `CPELoader v2`. `--version` is an alias. No game folder is required, and no game files or lock states are read or changed. If `-connect` is supplied, version mode still reports this command's bundled version, not the selected folder's loader. Version mode cannot be combined with `-LOCK`.

## Recovery image and repair screen

Close the game and CPE services, then run:

```bat
cpe --cpeloader -cpe/repair -cpeloader/repair
```

`--cpeloader` and `-cpeloader` are aliases. Without `-connect`, repair uses the folder containing `cpe.exe`, never the terminal's working directory. A bare `--connect` also selects that folder. Add `--connect "C:\Games\The Cube Beta"` to select another installation of the **same build**.

The visual recovery window shows a cube illustration, confirmation, real progress and the backup location. **Repair may take up to 3 minutes; slow disks can take longer.** Cancel is selected initially; no artificial countdown delays are added.

- `-cpe/repair` restores the official compiled game (which contains CPE), external CPE Python/bridge files and the backend configuration from the image embedded in `cpe.exe`. This replaces custom CPE/game changes after confirmation.
- `-cpeloader/repair` restores only the three Python, JavaScript and Ruby loader components, including missing components.
- `-fullgame/repair` restores every bundled game file covered by the full recovery image: the game executable, CPE, CPELoader, bundled themes/add-ons, launch scripts, documentation and licences. Changed bundled files are backed up before restoration. It does not replace the running `cpe.exe`, the original manifest, or mutable player data.
- `CPELOADER_MISSING` names missing files. CPE-only repair stops if loader files are missing; include loader repair to restore them. Version-only mode does not inspect game files.
- Originals go into `backup/cpe-cli/<timestamp>/original`, with a `repair.json` record. On failure, replaced files are rolled back; backups are retained. Interrupted repairs can be recovered manually from that folder.
- Saves, settings, extra custom files, lock state and the original integrity manifest are not rewritten. CPE-only repair leaves add-ons/themes unchanged; full-game repair restores **bundled** add-ons/themes but preserves additional custom files. Other modifications still trigger integrity warnings. Repair never unlocks, relocks or enables updates.
- A missing/damaged recovery image or mismatching/missing original manifest stops repair. Use a matching official installer in a new empty folder. If `cpe.exe` itself is damaged, use the installer.

For a console-only repair use `--no-gui`; it asks `[y/N]`. Add `--yes` only when explicitly accepting replacement. `--v` and `-LOCK` cannot be combined with repair.

Full-game console repair from the folder containing `cpe.exe`:

```bat
cpe --cpeloader --connect -fullgame/repair --no-gui
```

Or select a game folder explicitly:

```bat
cpe --cpeloader --connect "C:\Games\The Cube Beta" -fullgame/repair --no-gui
```

Neither command opens the repair window. The terminal displays the selected folder, the backup warning and real progress. An older CPE-only recovery image reports `FULLGAME_IMAGE_MISSING`; it cannot provide full-game recovery.

The bundled image is checksum-verified and tied to this release. It is an offline recovery mechanism, not protection against someone who can replace the executable running as your account.

Locking disables flashing for the Python, Node.js and Ruby components. It does **not** remove mods, rewrite game code, delete backups, regenerate an integrity baseline or certify a modified game as official. Existing warnings stay visible. The official updater refuses modified, unlocked, partially unlocked and custom games.

## Fast CPE

Press **Ctrl+Alt+T** in the game. The first confirmation defaults to Cancel. A second full-screen warning requires an explicit choice before enabling Fast CPE. It uses 12 solver iterations instead of 20 and caps IPE at 800 particles (or a lower configured limit). The fixed physics timestep stays at 120 Hz. Complex stacks may be less accurate; the tradeoff is experimental, not a guaranteed FPS improvement.

Press the shortcut again to restore normal quality. The mode is session-only and starts off on every launch. CPE Rephysics and third-party backends are not silently reconfigured.

## Cache protection

CPE 0.0.3-nightly captures immutable JSON snapshots, rejects unsupported/non-finite data, limits snapshots to 2 MiB and verifies SHA-256 before publication. Node sends a raw-payload digest to Go; Go checks it and publishes coherent data/version snapshots under one lock.

These are integrity and resource checks, not encryption, remote-client authentication or protection against malicious code already running as your Windows account. Keep the optional Node/Go bridge bound to localhost unless you provide an authenticated network boundary.
