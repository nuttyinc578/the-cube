# Cube Physics Engine (CPE)

CPE is permanently embedded in The Cube Beta Fall Edition while preserving the existing menus, controls, add-ons, multiplayer, UI, GUI, and UX.

It combines:

- **Python + Pymunk** for authoritative rigid-body simulation.
- **Pygame** for the existing Fall Edition renderer.
- **IPE** (Integrated Particle Engine) for spawn, burst, command, and collision particles.
- A dependency-free **Node.js bridge** on port `4310` that converts commands into bounded numeric `CPE/1` lines.
- A dependency-free **Java client** that communicates with CPE through Node.
- A **Go cache service** on port `4311` that stores the latest `cube_core` physics and particle cache.
- A **.NET Aspire AppHost** that launches Go, Node, and the actual Fall Edition game and supplies their endpoint settings.

CPE converts a fixed command language into numbers. It never evaluates arbitrary Java, JavaScript, or Python source code.

## Easiest Windows launch

- Double-click `Run CPE Aspire.cmd` to start Go, Node, and The Cube Beta Fall Edition together.
- Double-click `Run The Cube Beta CPE.cmd` to run the CPE-powered game directly; it automatically connects when Aspire is available and keeps working in embedded mode when it is not.
- Double-click `Run CPE Java Client.cmd` after Aspire starts to send a Java polygon command into the running game.
- `Run CPE Offline.cmd` remains available as the standalone CPE/IPE laboratory.

These launchers use their own file location, so the current terminal folder does not matter.

## Architecture

```text
Java / JSON command
    -> Node.js bridge :4310
    -> CPE/1 sequence opcode number number ...
    -> cube_core CPE adapter
    -> embedded Python CPE
    -> Pymunk physics + IPE particles
    -> existing Pygame Fall Edition renderer

cube_core physics + particle cache
    -> CPE bridge
    -> Node.js
    -> Go cache :4311
```

Example Java/JSON command:

```json
{"action":"spawn","shape":"polygon","x":420,"y":90,"sides":6,"size":30,"color":[222,108,39]}
```

Node converts it to:

```text
CPE/1 1 3 420 90 6 30 1 222 108 39
```

## Run with .NET Aspire

The AppHost targets .NET 8 and Aspire 8.2.2 for the installed SDK:

```powershell
dotnet run --project "cpe/CPE.AppHost/CPE.AppHost.csproj" --launch-profile http
```

Aspire launches:

- `cpe-go-cache` at `http://127.0.0.1:4311`
- `cpe-node-bridge` at `http://127.0.0.1:4310`
- `the-cube-beta-fall`, using `CPE_BRIDGE_URL`, `CPE_ASPIRE_IP`, `CPE_NODE_PORT`, and `CPE_GO_CACHE_PORT`

The game still starts with its MIT Licence popup and the same Fall Edition interface.

## Java communication

Compile:

```powershell
javac -d "cpe/java-client/out" "cpe/java-client/src/main/java/com/nuttyinc/cpe/CpeClient.java"
```

Send a command after Aspire starts:

```powershell
java -cp "cpe/java-client/out" com.nuttyinc.cpe.CpeClient 127.0.0.1 4310 spawn
```

See `java-client/README.md` for API examples.

## Services and endpoints

Node bridge:

- `GET /health`
- `GET /protocol`
- `POST/GET /commands`
- `POST/GET /state`

Go cache:

- `GET /health`
- `POST/GET /cache`

Supported CPE commands are `spawn`, `gravity`, `impulse`, `force`, `burst`, `clear`, `pause`, and `resume`.

## Direct game and standalone laboratory

Run the CPE-powered Fall Edition directly:

```powershell
py -3.10 "the_cube_beta_summer.py"
```

Run the separate CPE/IPE laboratory:

```powershell
py -3.10 "CPE.py" --offline
```

## Tests

```powershell
py -3.10 -m unittest -v test_summer_game
py -3.10 -m unittest -v cpe.tests.test_cpe
py -3.10 -m unittest -v cpe.tests.test_full_stack
npm test --prefix cpe/node-bridge
go test -v ./cpe/go-cache/...
dotnet build cpe/CPE.AppHost/CPE.AppHost.csproj --no-restore
```