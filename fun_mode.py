"""Fun Mode party pack for The Cube Beta.

Drop this file into the game's add-ons folder and reload add-ons.
"""


def register(api):
    api.about(
        name="Fun Mode: Party Pack",
        version="1.0",
        author="Cube Community",
        description=(
            "Adds colorful party shapes, a floaty Moon Bounce, "
            "and a fast Confetti Cannon event."
        ),
    )

    api.shape(
        name="Disco Ball",
        kind="circle",
        size=32,
        color=(150, 110, 255),
        weight=0.8,
    )
    api.shape(
        name="Confetti Star",
        kind="polygon",
        sides=5,
        size=25,
        color=(255, 75, 170),
        weight=0.65,
    )
    api.shape(
        name="Party Sun",
        kind="polygon",
        sides=8,
        size=38,
        color=(255, 205, 55),
        weight=1.1,
    )

    api.event(
        name="Moon Bounce",
        duration=10,
        wind=180,
        gravity_scale=0.16,
        spawn_count=8,
        banner="Moon Bounce! Everything is light, floaty, and ready to party!",
        color=(125, 155, 255),
    )
    api.event(
        name="Confetti Cannon",
        duration=6,
        wind=1200,
        gravity_scale=0.55,
        spawn_count=12,
        banner="Confetti Cannon! A colorful blast races across the beach!",
        color=(255, 80, 175),
    )
