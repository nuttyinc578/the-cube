"""Custom Root Mode loader compiled into the game by the flasher."""
def on_load(app, game_root):
    from root_mode_runtime import install
    install(app, game_root)
