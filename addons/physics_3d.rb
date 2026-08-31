require "json"

# Physics 3D is a companion manifest for physics_3d.py. The game loads the
# shapes and events below, while the Python half also reads the physics_3d
# section to style and tune them.
addon = {
  name: "Physics 3D: Dimension Pack",
  version: "1.0.0",
  author: "Cube Labs",
  description: "Dimensional shapes, reactive materials, and cinematic physics events.",
  physics_3d: {
    badge: "PHYSICS 3D",
    accent: [89, 238, 255],
    secondary: [180, 100, 255],
    hot: [255, 111, 72],
    shadow: [8, 19, 45],
    grid: [86, 218, 255],
    extrusion: [7, 10],
    materials: {
      "Holo Orb" => {
        elasticity: 0.94,
        friction: 0.28,
        drag: 0.997,
        glow: 1.0
      },
      "Depth Cube" => {
        elasticity: 0.42,
        friction: 0.96,
        drag: 0.992,
        glow: 0.45
      },
      "Kinetic Prism" => {
        elasticity: 0.76,
        friction: 0.52,
        drag: 0.995,
        glow: 0.78
      },
      "Glass D8" => {
        elasticity: 0.88,
        friction: 0.34,
        drag: 0.996,
        glow: 0.9
      },
      "Flux Ring" => {
        elasticity: 1.02,
        friction: 0.18,
        drag: 0.998,
        glow: 1.0
      }
    }
  },
  shapes: [
    {
      name: "Holo Orb",
      kind: "circle",
      size: 35,
      color: [68, 225, 255],
      weight: 1.25
    },
    {
      name: "Depth Cube",
      kind: "polygon",
      sides: 4,
      size: 39,
      color: [138, 91, 255],
      weight: 1.15
    },
    {
      name: "Kinetic Prism",
      kind: "polygon",
      sides: 3,
      size: 36,
      color: [255, 119, 67],
      weight: 1.0
    }
  ],
  events: [
    {
      name: "Zero-G Orbit",
      duration: 11,
      wind: 0,
      gravity_scale: 0.04,
      spawn_count: 9,
      banner: "The lab opens an orbital field. Shapes spiral through depth!",
      color: [91, 228, 255]
    },
    {
      name: "Vortex Drive",
      duration: 9,
      wind: -120,
      gravity_scale: 0.46,
      spawn_count: 7,
      banner: "A moving gravity well twists every shape into a neon vortex!",
      color: [177, 99, 255]
    },
    {
      name: "Neon Quake",
      duration: 7,
      wind: 0,
      gravity_scale: 1.28,
      spawn_count: 11,
      banner: "The dimensional floor pulses with kinetic shockwaves!",
      color: [255, 112, 72]
    }
  ]
}

puts JSON.generate(addon)
