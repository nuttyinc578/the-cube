# The Cube Beta Error Update 6.3.0

6.3.0 is the **Error Update**, rebuilt around Cube Physics Engine **CPE 0.0.2** and its Integrated Particle Engine.

## Error Update experience

- New generated cracked error-cube executable, installer, and in-game logo.
- A blue-screen loading sequence reports **ERROR 21CPE — CPE CONNECT FILE ERROR**.
- “WE ARE DONE / WE ARE COOKED” appears five times during the loader.
- The first-run main menu is intentionally corrupted with shaking titles, error windows, glitch effects, and disabled game routes.
- The dedicated **Repair CPE 0.0.2** control remains reliable so the visual corruption never traps the player.
- After repair, the error popups disappear and a new animated fluent menu becomes active.
- The Error Update loading screen remains on later launches, while clearly showing that repair is verified.

## Real CPE repair

- Creates both theme/configuration and CPE bridge backups before making changes.
- Restores packaged, checksum-verified Node.js, Go, Java, and .NET Aspire bridge sources.
- Runs a real CPE numeric-command Pymunk self-test and an IPE particle test.
- Records the repaired state and diagnostics in `error_update_state.json` beside the game.
- Keeps recovery copies under `backup/cpe`.
- Introduces a CPE health report and higher-quality rendering with gradients, glow, shadows, highlights, and anti-aliased polygon edges.

## Existing features retained

Multiplayer, random physics shapes, fall events, Theme Store, Developer Mode, the real GitHub OG-version installer, and Python/Ruby add-ons remain available from the repaired menu.

> [!CAUTION]
> **The Cube Beta 5.0 and earlier remain unsupported.** They receive no fixes, compatibility updates, security updates, or technical support.

The installer displays the MIT License and requires acceptance. Windows downloads are unsigned, so Microsoft Defender SmartScreen may show an unknown-publisher warning.
