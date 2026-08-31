"""Example Python add-on for The Cube Beta."""


def register(api):
    api.about(
        name="Summer Burst",
        version="1.0",
        author="Cube Studios",
        description="Adds a juicy orange octagon and the Citrus Gust event.",
    )
    api.shape(
        name="Citrus Slice",
        sides=8,
        size=32,
        color=(255, 151, 52),
        weight=1.4,
    )
    api.event(
        name="Citrus Gust",
        duration=7,
        wind=1050,
        gravity_scale=0.7,
        spawn_count=6,
        banner="A fizzy orange gust launches the whole beach!",
        color=(255, 181, 72),
    )
