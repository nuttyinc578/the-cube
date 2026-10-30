# CPELoader v2

Close the game before changing its lock state. Open **Open CPE Command Prompt.cmd** in the extracted portable folder, or the installer's **CPE Command Prompt** shortcut. The packaged cpe.exe needs no separate Python installation.

```bat
cpe -connect "C:\Games\The Cube Beta" -LOCK -cpeloader
```

The originally requested `cpe -connect -"C:\Games\The Cube Beta" -LOCK -cpeloader` form also works. Use quotes for paths with spaces. Omit `-LOCK` for read-only status. From another Command Prompt directory, use the full path to cpe.exe. Installation does not modify your global PATH.

Source checkout: `python cpeloader_cli.py -connect "." -LOCK -cpeloader`.

Locking disables flashing for the Python, Node.js and Ruby components. It does **not** remove mods, rewrite game code, delete backups, regenerate an integrity baseline or certify a modified game as official. Existing warnings stay visible. The official updater refuses modified, unlocked, partially unlocked and custom games.

## Fast CPE

Press **Ctrl+Alt+T** in the game. The first confirmation defaults to Cancel. A second full-screen warning requires an explicit choice before enabling Fast CPE. It uses 12 solver iterations instead of 20 and caps IPE at 800 particles (or a lower configured limit). The fixed physics timestep stays at 120 Hz. Complex stacks may be less accurate; the tradeoff is experimental, not a guaranteed FPS improvement.

Press the shortcut again to restore normal quality. The mode is session-only and starts off on every launch. CPE Rephysics and third-party backends are not silently reconfigured.

## Cache protection

CPE 0.0.3-nightly captures immutable JSON snapshots, rejects unsupported/non-finite data, limits snapshots to 2 MiB and verifies SHA-256 before publication. Node sends a raw-payload digest to Go; Go checks it and publishes coherent data/version snapshots under one lock.

These are integrity and resource checks, not encryption, remote-client authentication or protection against malicious code already running as your Windows account. Keep the optional Node/Go bridge bound to localhost unless you provide an authenticated network boundary.
