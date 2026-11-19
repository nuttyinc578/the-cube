# Sky Gate archive DVD

Real rendered frames, not recreations. The capture script runs in dummy SDL and saves the actual display buffer:

- `10.png`, `20.png`, `30.png`: official GitHub release scripts from `1.0.0.0`, `2.0`, and `3.0`.
- `40.png` and `49.png`: 4.0 and 4.9 release scripts from GitHub tags `4.1` and `4.5`.
- `50.png`: official 5.0 release script.
- `51.png`: the repository's archived v5.1 Christmas Python source. Not extracted from its MSI.
- `60.png`: the original login screen of the 5.3 script in the `6.0.0` release tag. It represents the tagged source, not the separately shipped installer binary. No login or network call was made.

Missing files render an unavailable card rather than another version's image. Use `tools/Capture-Archive.py --originals <folder>` to refresh the source captures from original, checked assets.
