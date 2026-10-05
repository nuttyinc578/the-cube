# frozen_string_literal: true

# Ruby companion for NuttyMod Loader. The Cube Beta runs this file like any
# other Ruby add-on. Python also calls --loader-info to verify the Ruby half of
# the loader without granting elevated privileges or modifying system settings.

require "json"

LOADER_VERSION = "1.0.0"

if ARGV.first == "--loader-info"
  puts JSON.generate(
    component: "NuttyMod Ruby Bridge",
    version: LOADER_VERSION,
    status: "ready",
    ruby_version: RUBY_VERSION,
    platform: RUBY_PLATFORM
  )
  exit 0
end

manifest = {
  name: "NuttyMod Ruby Bridge",
  version: LOADER_VERSION,
  author: "nutty'inc",
  description: "Ruby runtime bridge and Root Prism content for NuttyMod Loader.",
  shapes: [
    {
      name: "Root Prism",
      kind: "polygon",
      sides: 6,
      size: 35,
      color: [171, 99, 255],
      weight: 1.15
    }
  ],
  events: [
    {
      name: "Kernel Pulse",
      duration: 6,
      wind: 480,
      gravity_scale: 0.45,
      spawn_count: 5,
      banner: "NuttyMod Kernel Pulse is active!",
      color: [199, 139, 255]
    }
  ]
}

puts JSON.generate(manifest)
