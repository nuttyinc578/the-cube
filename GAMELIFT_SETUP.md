# Cube Beta base game: Halloween and GameLift preparation

Changes are in **the game**, not CPE Flasher. The normal `the_cube_beta_summer.py` entry point installs the Halloween menu, theme, music screen and in-game Broken Lands door. Despite its historical filename, it is the Halloween base game. No flashing or loader unlocking is needed to use its seasonal UI. Existing user modifications are preserved.

The multiplayer menu now has **Amazon GameLift Online**, alongside existing LAN host/join. Online mode uses Nuttyinc Cloud sign-in, requests a reservation from your HTTPS backend and connects to the reserved game-server DNS/port using certificate-verified TLS. It sends the player session ID in a `join` JSON frame; later gameplay uses the game's existing newline-delimited action/snapshot protocol. AWS keys never belong in the game. Authentication credentials stay in memory.

## Dedicated server and bounded hosting test

### Test result: October 23, 2026 — not live

The Linux installation completed after fixing administrator permissions for package installation and the server executable's permissions. The managed fleet then reached ACTIVATING, but AWS reported repeated `SERVER_PROCESS_CRASHED` events. No public two-player verification or authenticated reservation API deployment completed. Local regression tests passed (30 tests); this does not establish successful managed GameLift startup.

The approved window ended at 15:30 UTC (11:30 a.m. Toronto). AWS refused fleet deletion during ACTIVATING. Desired capacity was set to zero and independent AWS-side deletion retries were enabled; fleet removal was verified afterward. Another paid hosting test needs a newly approved window. Diagnose the managed server startup before retrying. Do not advertise the prepared portable build as live online multiplayer.

### Local startup investigation (no new hosting)

The exact cause of the AWS crash is still unconfirmed: the failed fleet's events did not provide a downloadable process log. Source inspection found two concrete diagnostic/lifecycle defects. Host `log.Fatal` calls bypassed cleanup, and the Go SDK 5.6.0 default logger also calls `log.Fatal` when it cannot create `./logs`. The latter makes startup depend on the working directory's permissions; it is a possible cause, not a proven explanation for that fleet.

The host now returns stage-labelled errors and runs cleanup before exiting. It detects a Python worker that exits before readiness or while serving, shuts down the listener, and sends `ProcessEnding` once after successful SDK initialization. SDK initialization failures still call `Destroy` to release partial state. A custom SDK logger removes the default logger's working-directory dependency.

Startup milestones, worker stderr, and SDK warnings/errors go to a private per-process log under the OS temporary directory's `cube-server-logs` folder. Use `--log-file ABSOLUTE_PATH` to select another writable location. The file is also registered with `ProcessReady` for GameLift log collection; collection is not guaranteed if startup fails before `ProcessReady`. SDK protocol debug frames are disabled, known AWS/GameLift credential environment values are redacted, and URL query strings are removed from diagnostics. Do not publish raw server logs without reviewing them.

`go test -count=1 -v ./...` from `dedicated_server` exercises the managed lifecycle using a mocked SDK, a child worker, and real local TLS certificate/listener setup. It covers startup/worker failures, termination callbacks, context cancellation, cleanup order, and diagnostic redaction. It does **not** authenticate to AWS or prove managed fleet activation. `tools/Verify-DedicatedServer.py` separately uses two real local TLS clients and the actual Python CPE physics worker, with logs in `build/dedicated-tls-qa`. No paid instance is needed for either check.

Verification status for these startup changes: the existing 30 Python regression tests passed. The new Go lifecycle tests and rebuilt server are not yet verified: local Go tooling stalled, including a retry with vet disabled. The earlier two-player TLS result applies to the previous server binary, not this diagnostic revision. Do not upload or deploy this revision until its Go tests, Windows/Linux builds, and the real-worker TLS check finish successfully.

The dedicated host is now implemented in `dedicated_server/main.go`, using the official GameLift Go server SDK 5.6.0 and a headless Python CPE worker. It implements SDK lifecycle callbacks, certificate-verified TLS, accepted player sessions, authoritative simulation, bounded actions/snapshots, and per-player drag ownership. The existing LAN host is still NOT the internet-facing server. LAN and single-player remain available.

Local verification passed with two real TLS clients receiving the same authoritative physics world. The unit tests also cover reservations and scheduled shutdown. These checks do not prove that AWS fleet installation or public online play works.

`tools/Deploy-GameLiftTest.py` deploys only a bounded, explicitly approved test: one Linux c5.large instance in Canada Central, one four-player game session, and a Cognito-protected HTTP reservation API. The `prepare` phase arms AWS-side cleanup before the `start` phase can create a fleet. Its deadline is two hours after preparation, not two hours after the server becomes ready. Deletion is asynchronous and this is not a hard spending cap. Backend, transfer, storage, and tax charges can be additional. It does not enable indefinite hosting or autoscaling.

Live status and exact resource IDs are recorded locally in `build/gamelift-test-deployment/resources.json` after each deployment step. No deployed endpoint should be advertised until fleet activation and a two-client internet connection test pass. No AWS credentials are included in the game or server upload. The shutdown function can only target this deployment's recorded IDs and unique names; its deletion permissions are narrowed to the created resources.

Deployment components:

- `dedicated_server/install.sh`: Amazon Linux 2023 installation and real physics smoke test.
- `tools/Stage-DedicatedServer.py`: allowlisted upload payload, excluding mods and local credentials.
- `tools/Verify-DedicatedServer.py`: two-player local TLS integration check.
- `multiplayer_backend/session_api.py`: fixed-session reservations behind API Gateway JWT authorization.
- `multiplayer_backend/test_shutdown.py`: scheduled fleet and test API deletion.
- `tools/Deploy-GameLiftTest.py --phase prepare` then `--phase start`: approved operator workflow, not an automatic game update. Inspect existing state before any rerun to avoid duplicates.

The schedule removes fleet capacity and the HTTP API. Idle Lambda functions, IAM roles, scheduler groups, logs, and uploaded build metadata may remain for inspection and require separate cleanup. Review production security, monitoring, billing controls, account recovery, and availability before a public release.

Deployment checklist (the bounded test tooling implements these server/backend steps):

1. Build a dedicated authoritative server implementing `cube-json-tls-v1`. Integrate a supported GameLift Server SDK (C++, C# or Go) for InitSDK, ProcessReady, ActivateGameSession, AcceptPlayerSession, RemovePlayerSession and shutdown/health callbacks. A Python CPE physics worker can run behind that native host. Do not report a reservation as accepted merely because the client supplies a player-session ID.
2. Deploy a TLS-enabled fleet, configure its game port and create active game sessions. Server must send existing snapshot messages and validate/rate-limit each client's actions, bound object/particle counts and maintain separate player drag ownership. Never use client snapshots as authoritative physics.
3. Deploy an authenticated HTTPS `POST /sessions/reserve` service. Verify Cognito access JWT signature, issuer, client_id, token_use and expiry using a maintained JWT library; derive the player identity from verified `sub`, not JSON supplied by the player. Enforce throttling and per-player reservation limits. The `multiplayer_backend/gamelift_reservations.py` adapter is business logic, **not an exposed HTTP endpoint or authentication layer**. Use its `reserve_verified_player` only AFTER token verification. It joins an existing active game, not creates servers on demand. Handle full-session races at the API boundary with a retryable response.
4. Give only the BACKEND runtime a scoped GameLift role for search/reservations; use normal AWS credential providers there. Backend dependencies include boto3; the base game does not need it. Configure backend `AWS_REGION` and `GAMELIFT_FLEET_ID`. There is intentionally no automatic public endpoint or permissive IAM template.
5. Add Cognito callback `http://localhost:8765/callback` for development, use a public no-secret client with code + PKCE and `openid email`. Review native callback strategy before public production release. Browser registration on CloudFront is not a launcher/game authentication session.
6. Beside the base game's EXE create `gamelift.json` containing `{"backend_url": "https://YOUR-AUTHENTICATED-BACKEND"}`. Without this file the GameLift button explains setup is needed. Do not put tokens, passwords or AWS keys in it.

Backend response contract:

```json
{"protocol":"cube-json-tls-v1","dns_name":"YOUR-TLS-SERVER-DNS","port":27100,"player_session_id":"psess-RESERVATION-ID"}
```

Do not advertise this build as live GameLift multiplayer merely because a local build passed. Check the deployment result and public two-player test. Browser Cognito sign-in also needs an end-user verification; no account password is collected by the deployment tools.

## Local verification/build

Run `python -m unittest test_dedicated_server test_gamelift test_cube_launcher -v`. Build the **base game**, not flasher: `python -m PyInstaller --noconfirm --distpath build/halloween-gamelift-game summer_build.spec`. The output is `build/halloween-gamelift-game/The Cube Beta Halloween Update.exe`. Test with a fresh directory to avoid mixing portable payloads from older releases.

Network preparation also bounds received frame size and inbox depth and closes sockets on disconnect. These are targeted resource safeguards, not a complete security audit of the old LAN protocol. Keep LAN on trusted networks only.

AWS references: [client/backend/server flow](https://docs.aws.amazon.com/gameliftservers/latest/developerguide/gamelift-sdk-client-api.html), [server lifecycle](https://docs.aws.amazon.com/gameliftservers/latest/developerguide/gamelift-sdk-server-api.html), [supported SDKs](https://docs.aws.amazon.com/gameliftservers/latest/developerguide/gamelift-supported.html).
