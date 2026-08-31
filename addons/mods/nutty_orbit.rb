# Experimental NuttyMod Ruby Mod.
require "json"
manifest = {
  name: "Nutty Orbit",
  version: "1.0-beta",
  author: "NuttyMod Studios",
  description: "Experimental Ruby orbit shape and low-gravity event.",
  shapes: [{name: "Orbit Gem", kind: "polygon", sides: 7, size: 34, color: [174, 120, 255], weight: 0.8}],
  events: [{name: "Orbit Shift", duration: 7, wind: 280, gravity_scale: 0.3, spawn_count: 5, banner: "Experimental Orbit Shift!", color: [174, 120, 255]}]
}
puts JSON.generate(manifest)
