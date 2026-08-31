# The Cube Beta add-ons

Drop `.py` or `.rb` files into this folder, then choose **Add-ons → Reload**
inside the game. You can also drag either file type directly onto the Add-on
Dock window.

Add-ons execute code on your computer. Only use files from creators you trust.

## Python

Create a file such as `my_addon.py`:

```python
def register(api):
    api.about(
        name="My Add-on",
        version="1.0",
        author="Your name",
        description="What it adds.",
    )
    api.shape(
        name="Blue Gem",
        kind="polygon",  # "polygon" or "circle"
        sides=6,         # 3 through 8 for polygons
        size=32,         # 15 through 58
        color=(50, 170, 255),
        weight=1.0,
    )
    api.event(
        name="Blue Breeze",
        duration=8,
        wind=700,            # negative blows left
        gravity_scale=0.5,   # 1.0 is normal
        spawn_count=5,
        banner="A cool breeze arrives!",
        color=(90, 210, 255),
    )
```

## Ruby

Ruby add-ons print one JSON manifest on their final output line. Ruby must be
installed and available as `ruby` on the computer running the game.

```ruby
require "json"

puts JSON.generate({
  name: "My Ruby Add-on",
  version: "1.0",
  author: "Your name",
  description: "What it adds.",
  shapes: [{
    name: "Ruby Triangle",
    kind: "polygon",
    sides: 3,
    size: 34,
    color: [230, 60, 90],
    weight: 1.2
  }],
  events: [{
    name: "Ruby Rush",
    duration: 6,
    wind: -900,
    gravity_scale: 0.8,
    spawn_count: 4,
    banner: "Ruby Rush sweeps across the beach!",
    color: [255, 100, 120]
  }]
})
```
