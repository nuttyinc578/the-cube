# The Cube Beta custom installer

`TheCubeBetaFall.iss` builds a per-user Windows installer for The Cube Beta Fall Edition 6.2.1.

The installer:

- displays the complete MIT License and requires the player to select **I accept the MIT License** before continuing;
- installs the Fall Edition executable, current add-ons, CPE bridge, Go cache, Java client, and Aspire host;
- excludes old executables, update backups, Python caches, local account state, and the removed terms document;
- creates Start Menu shortcuts and offers an optional desktop shortcut;
- includes Windows uninstall support and preserves user-created add-on files that were not installed by Setup.

Build it by double-clicking `Build Installer.cmd`, or run:

```powershell
& 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' '.\installer\TheCubeBetaFall.iss'
```

The output is written to `installer-output\The-Cube-Beta-Fall-6.2.1-Setup.exe`.

The resulting installer is not digitally signed. Windows may display a SmartScreen warning until you sign it with a trusted code-signing certificate.
