require "json"

addon = {
  name: "Tropical Twist",
  version: "1.0",
  author: "Cube Studios",
  description: "Adds a bright tropical gem and a floaty island event.",
  shapes: [
    {
      name: "Tropical Gem",
      kind: "polygon",
      sides: 5,
      size: 34,
      color: [79, 220, 164],
      weight: 1.3
    }
  ],
  events: [
    {
      name: "Island Float",
      duration: 9,
      wind: -340,
      gravity_scale: 0.12,
      spawn_count: 5,
      banner: "The island breeze makes every shape nearly weightless!",
      color: [83, 229, 190]
    }
  ]
}

puts JSON.generate(addon)
