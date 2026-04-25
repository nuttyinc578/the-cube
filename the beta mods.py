import os
import importlib.util

MOD_FOLDER = "mods"

mods = []

for file in os.listdir(MOD_FOLDER):
    if file.endswith(".py"):
        path = os.path.join(MOD_FOLDER, file)

        spec = importlib.util.spec_from_file_location(file[:-3], path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        mods.append(mod)

print(f"Loaded {len(mods)} mods")