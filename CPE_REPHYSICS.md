# CPE Rephysics integration

Rephysics 0.1.0 is an experimental independent physics solver maintained at
https://github.com/nuttyinc578/cpe-rephysics under the MIT licence.

The game chooses its engine at startup through `cpe/backend.py`.
`cpe-backend.json` selects Rephysics, and `cube_core.py` uses the selected
body/shape API. The CPE/1 commands, Pygame interface, IPE, multiplayer messages,
and Node/Java/Aspire/Go bridge format remain compatible.

The package was installed through the separate repository's flash command.
Backups of previous engine configuration and files are under `backup/rephysics`.
Run `python -m cpe_rephysics.flash restore --game <game-source-folder> --backup
<backup-folder>` from the separate repository to restore an earlier engine.
Before installing or restoring, open the updated game, press Ctrl+A, read the
CPELoader warning and press Y to unlock all three components. The game resets;
close it before flashing. Shift+N cancels. Source and updated portable game
folders are supported; older executables need a rebuild with the backend selector.
Unlocked loading pauses at 50% until Enter is pressed, warns about changed files,
and blocks in-game updates. Use the external installer to update and relock.
The loader is an application-level gate, not an OS security boundary.

Rephysics implements circles, convex polygons, floor and side boundaries,
rotational impulses and friction. It is not a complete Pymunk API replacement.
Fast-body tunnelling, complex stacks, joints, arbitrary obstacles and concave
shapes need further development. Use the retained backup to return to classic
CPE if gameplay needs its more mature solver.
