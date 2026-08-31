require "json"

# Fun Mode's Ruby companion pack. The game reads the JSON printed on the
# final output line.
addon = {
  name: "Fun Mode: Chaos Pack",
  version: "1.1",
  author: "Cube Community",
  description: "Adds silly shapes, playful events, and the shared Fun Mode GUI theme.",
  gui: {
    badge: "FUN MODE  PY + RB",
    panel_title: "FUN METER",
    action: "PARTY EVENT  [F]",
    accent: [255, 70, 220],
    secondary: [65, 235, 205],
    confetti_colors: [
      [255, 70, 220],
      [65, 235, 205],
      [255, 205, 55],
      [105, 90, 245],
      [255, 105, 75]
    ]
  },
  shapes: [
    {
      name: "Jelly Drop",
      kind: "circle",
      size: 39,
      color: [65, 235, 205],
      weight: 0.45
    },
    {
      name: "Party Diamond",
      kind: "polygon",
      sides: 4,
      size: 31,
      color: [255, 70, 220],
      weight: 0.9
    },
    {
      name: "Lucky Hex",
      kind: "polygon",
      sides: 6,
      size: 35,
      color: [85, 230, 105],
      weight: 1.25
    }
  ],
  events: [
    {
      name: "Reverse Rush",
      duration: 7,
      wind: -1150,
      gravity_scale: 0.75,
      spawn_count: 10,
      banner: "Reverse Rush! The party suddenly zooms the other way!",
      color: [255, 105, 75]
    },
    {
      name: "Space Party",
      duration: 11,
      wind: -180,
      gravity_scale: 0.08,
      spawn_count: 7,
      banner: "Space Party! Shapes drift through a nearly weightless world!",
      color: [105, 90, 245]
    }
  ]
}

puts JSON.generate(addon)
