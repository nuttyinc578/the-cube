# The Cube Beta 6.4.0 — Halloween Update

Enter the Broken Lands in the new Halloween experience, powered by CPE and IPE.

## Updated build: CPELoader and Rephysics

The installer and portable ZIP have been updated with CPELoader and the
experimental CPE Rephysics backend. The original 6.4.0 tag is unchanged;
the updated source is on the repository's `main` branch.

- Loader starts locked; engine flashing requires all three Python, Node.js,
  and Ruby loader components to be unlocked.
- Press **Ctrl+A**, read the warning, then **Y** to unlock and reset.
  **Shift+N** cancels without changing the lock.
- Unlocked startup pauses at **50%**; press **Enter** to continue.
- Changed managed files display a warning at the bottom of loading screens.
- In-game version and experience rewrites are blocked while unlocked. Use the
  external installer to update; installing resets the loader to locked.
- The verified Theme Store developer shortcut is now **Ctrl+Shift+D**.
- NuttyMod is isolated under `addons/nuttymod` and no longer automatically
  loads into or permanently rewrites the base game.
- CPE Rephysics is maintained separately at
  https://github.com/nuttyinc578/cpe-rephysics. It remains experimental, with
  limitations for complex stacks, joints, and fast-body collisions.

The loader is an application-level gate, not tamper-proof protection against
someone who can edit its code or saved state. This update passed 27 game tests
and four standalone Rephysics tests. SHA-256 checksums accompany the downloads.

## What is new

- New animated Halloween theme, loading experience, and menu.
- `SECURITY ???` door leading to a full-screen recovery terminal.
- Computer login and `OG.exe -<version>` recovery commands.
- Backup-first portable recovery for 6.3.0 and 6.2.2.
- Original Christmas 5.1 MSI/CAB recovery; no binary decompilation.
- Honest unavailable state for the expired 6.2.1 nightly artifact.
- Exact requested “Halloween Music” track by Sound4Stock, downloaded from its official Pixabay page on first launch and covered by the Pixabay Content License.
- Existing interactive physics, multiplayer, random shapes, add-ons, Theme Store, CPE, and IPE remain available.

## Recovery safety

OG.exe downloads to staging, validates ZIP paths, writes a file-hash manifest, and creates a complete `backup/og` restore point before any replacement is offered. The final portable overlay only runs after the active game exits.

## Support

The Cube Beta 5.0 remains unsupported. Upgrade to 6.4.0 for current fixes and recovery tooling.

## Music notice

“Halloween Music” by Sound4Stock is third-party copyrighted content licensed under the Pixabay Content License. It is not covered by the game’s MIT License and must not be redistributed as a standalone audio file.
