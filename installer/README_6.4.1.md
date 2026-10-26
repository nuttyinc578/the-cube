# The Cube Beta 6.4.1 installer

`TheCubeBeta641.iss` wraps the exact published 6.4.1 portable ZIP, verified with
SHA-256 `f8ae9222b0e0daaa25a914ad50a7c78b399cc702bf1de4f5035c5a27513cf8c7`.
It does not recompile or replace the portable download.

- Windows 10 or later, x64-compatible, per-user installation; no administrator permission required.
- Shows the MIT License and requires acceptance in normal interactive setup.
- Installs to a new version-specific folder, refusing non-empty target folders.
- Creates Start Menu shortcuts and offers an optional desktop shortcut.
- Registers Windows uninstall support; files created by the player afterward are preserved.
- No CPE Flasher, account credentials, live GameLift endpoint, or AWS hosting setup is added.

Build and verification are in `.github/workflows/installer-6.4.1.yml`.
The workflow installs and uninstalls only in a disposable runner's temporary
test directory, not on the developer's computer or an existing player installation.
It checks payload hashes, loader integrity, the installed game's smoke test,
overwrite refusal, licence acceptance for silent setup, and preservation of a
player-created file during uninstall.

For scripted installation, review `LICENCE.txt` first, then pass `/ACCEPTMIT=yes`
along with the normal Inno Setup silent-install flags. Omitting this explicit
acceptance aborts silent setup. No privacy or terms-of-service agreement is added.

The installer is unsigned; Windows may display a SmartScreen warning.
GameLift hosting remains offline, just as in the portable release.
