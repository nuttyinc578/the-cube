# The Cube Beta 6.4.3-nightly — Christmas Workshop

Experimental Christmas build. **6.4.2 remains the stable release.**

- Snowy Christmas theme enabled on first launch, winter scenery, Santa cube icon and Snow Globe, Gift Shower and Sleigh Breeze events. Your later theme choice is remembered; Halloween and the other built-ins remain available.
- **CPE 0.0.3-nightly**: immutable bounded JSON cache snapshots, SHA-256 checks before publication, Node-to-Go payload checksums and coherent Go cache versions.
- **Ctrl+Alt+T: Fast CPE mode.** An Are You Sure dialog and a full-screen warning both require explicit consent. Uses 12 solver iterations and up to 800 particles; 120 Hz physics timing and integrity checks remain active. Toggle again to return to normal. Resets on next launch; speed gains are workload-dependent.
- **CPELoader v2**: included standalone `cpe.exe` command, status output and locking of all three components. Locking preserves the original manifest and modification warnings; it does not make modded files official.
- Fixed stale collision bookkeeping, stable/nightly executable detection and unsafe in-game updates after relocking modified files.
- Python 3.15.2, pygame-ce 2.5.8, Pymunk 7.3.1. Original click sound and existing bundled fallback music retained; no new Christmas track is downloaded.

## Install

Choose the MIT-consent installer, or extract the **entire** portable ZIP to a new empty folder. Run **The Cube Beta Nightly.exe**. Keep stable installations, saves and backups separate. The installer is unsigned.

## CPELoader command

Open **Open CPE Command Prompt.cmd** in the game folder:

```bat
cpe -connect "C:\Games\The Cube Beta" -LOCK -cpeloader
```

The `-"C:\Games\The Cube Beta"` spelling is also accepted. Omit `-LOCK` for read-only status. No global PATH changes are made. See CPELOADER_V2.md for details.

## Limits

Fast CPE is experimental and only supported by the bundled classic CPE backend. Cache digests detect corruption, not malicious software running as your account. The optional Node/Go bridge remains a localhost development service, not an authenticated public service.

This release does not turn on GameLift hosting. The Power & Remastered release date is still to be announced. Portable and installer hashes are in SHA256SUMS.txt.
