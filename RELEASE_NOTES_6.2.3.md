# The Cube Beta Fall Edition 6.2.3

6.2.3 corrects the Developer Mode OG library so it installs real historical releases from the official `nuttyinc578/the-cube` GitHub repository.

## GitHub OG installer

- Loads the current historical-release catalog directly from the GitHub Releases API.
- Downloads the exact EXE, MSI/CAB, Python, ZIP, or source asset attached to the chosen release.
- Shows a dedicated download screen with asset name, byte progress, and cancellation.
- Confirms GitHub asset sizes, records a SHA-256 digest, and stores download metadata beside the legacy version.
- Creates a restore snapshot before every historical download.
- Keeps downloads isolated under `legacy-versions/<tag>` and then launches the real historical installer or application.
- Supports the 5.1 Christmas MSI/CAB release and older Python releases.
- Uses the GitHub source archive when a release exists but has no attached application, as with 6.2.1.

> [!CAUTION]
> **The Cube Beta 5.0 and earlier are unsupported.** They receive no fixes, compatibility updates, security updates, or technical support. The OG menu shows an additional warning before downloading these versions.

The 6.2.3 installer displays the MIT License and requires acceptance. Windows downloads are unsigned, so Microsoft Defender SmartScreen may show an unknown-publisher warning.
