# The Cube Beta Halloween Update 6.4.1

## Download

Download `The-Cube-Beta-Halloween-6.4.1-Portable.zip`, extract it to a new folder,
and run `The Cube Beta Halloween Update.exe`. Do not extract over a modified
installation; keep your previous version and backups separately.

This release provides the base game, not CPE Flasher. Single-player and LAN
multiplayer remain available. Ruby add-ons need a separate Ruby installation.

## Changes

- GameLift Online menu and certificate-verified TLS client preparation.
- Nuttyinc Cloud browser sign-in integration and launcher source.
- Dedicated Go GameLift server with authoritative Python CPE physics.
- Startup diagnostics, worker-exit handling, and safer server cleanup.
- Bounded network input and Linux installation permission fixes.
- Explicit TLS 1.2 minimum for GameLift transport and connection checks.
- Linux/Windows server tests and real two-player local TLS verification.

## Important: online hosting is not live

The public GameLift game server and authenticated reservation API are **not
deployed**. This download does not include an active backend address or promise
working internet matchmaking. The GameLift button explains that setup is needed.
Local/mock SDK tests are not proof of successful managed GameLift activation;
the earlier managed startup failure still needs a separately approved hosting test.

AWS credits are not included with the game. Publishing this release does not
start AWS resources or authorize charges. See `GAMELIFT_SETUP.md` for details.

The MIT copyright licence applies to the project code. Music and other
third-party components retain their own licences; see `THIRD_PARTY_NOTICES.txt`.
