#!/bin/bash
set -euo pipefail
cd /local/game
sudo -n dnf install -y python3.11 python3.11-pip mesa-libGL libX11
python3.11 -m venv /local/game/venv
/local/game/venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
sudo -n chmod +x /local/game/cube-server
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy /local/game/venv/bin/python -c 'from worker import Simulation; s=Simulation(); s.step(); assert s.snapshot()["type"] == "snapshot"'
