# The Cube Beta Legacy Versions Ruby add-on and launcher.
#
# Copy this file to the add-ons folder.  The game reads the final JSON line.
# Run it directly to download or launch an original release:
#   ruby cube_legacy_versions.rb install 4.0
#   ruby cube_legacy_versions.rb launch 4.0

require "fileutils"
require "json"
require "open-uri"

RELEASES = {
  "1.0" => {
    filename: "the_cube_beta_1.0.py",
    url: "https://github.com/nuttyinc578/the-cube/releases/download/1.0.0.0/my.pygame.py",
    label: "The Cube Beta 1.0 demo"
  },
  "5.0" => {
    filename: "the_cube_beta_5.0.py",
    url: "https://github.com/nuttyinc578/the-cube/releases/download/5.0/thecubebeta5.0.py",
    label: "The Cube Beta 5.0"
  },
  "4.0" => {
    filename: "the_cube_beta_4.0.py",
    url: "https://github.com/nuttyinc578/the-cube/releases/download/4.1/thecubebeta4.0.py",
    label: "The Cube Beta 4.0"
  },
  "3.0" => {
    filename: "the_cube_beta_3.0.py",
    url: "https://github.com/nuttyinc578/the-cube/releases/download/3.0/thecubebeta.py",
    label: "The Cube Beta 3.0"
  },
  "2.0" => {
    filename: "the_cube_beta_2.0.py",
    url: "https://github.com/nuttyinc578/the-cube/releases/download/2.0/my.pygame.v2.0.py",
    label: "The Cube Beta 2.0 demo"
  },
  "5.1" => {
    filename: "the_cube_beta_v5_1_christmas.py",
    label: "The Cube Beta 5.1 Christmas",
    local: true
  }
}.freeze

def legacy_dir
  File.join(__dir__, "legacy_versions")
end

def source_path(version)
  info = release_for(version)
  if info[:local]
    File.expand_path(File.join(__dir__, "..", "the cube beta", "legacy_christmas", info[:filename]))
  else
    File.join(legacy_dir, info[:filename])
  end
end

def release_for(version)
  RELEASES.fetch(version)
rescue KeyError
  abort "Choose one of: #{RELEASES.keys.join(', ')}"
end

def install(version)
  info = release_for(version)
  FileUtils.mkdir_p(legacy_dir)
  target = source_path(version)
  if info[:local]
    abort "The local Christmas 5.1 source is missing: #{target}" unless File.file?(target)
    puts "Christmas 5.1 is already installed: #{target}"
    return target
  end
  puts "Downloading #{info[:label]} from the official GitHub release..."
  URI.open(info[:url]) { |source| File.binwrite(target, source.read) }
  puts "Saved to: #{target}"
end

def launch(version)
  info = release_for(version)
  source = source_path(version)
  abort "#{info[:label]} is not installed. Run: install #{version}" unless File.file?(source)

  python = ENV.fetch("PYTHON", "python")
  spawn(python, source, chdir: legacy_dir)
  puts "Started #{info[:label]} separately from the Summer Edition."
end

def manifest
  {
    name: "Legacy Versions: Ruby Companion",
    version: "1.0.0",
    author: "Cube Community",
    description: "Ruby launcher for official 1.0 through 5.1 source releases, including local Christmas 5.1; never replaces Summer Edition.",
    shapes: [
      { name: "Ruby Retro Gem", kind: "polygon", sides: 6, size: 30, color: [205, 75, 120], weight: 0.9 }
    ],
    events: [
      { name: "Ruby Recall", duration: 7, wind: 300, gravity_scale: 0.75, spawn_count: 6,
        banner: "Ruby Recall! A legacy-era burst crosses the board.", color: [215, 85, 130] }
    ]
  }
end

if $PROGRAM_NAME == __FILE__ && !ARGV.empty?
  command, version = ARGV
  case command
  when "list"
    RELEASES.each { |number, info| puts "#{number}: #{info[:label]}" }
  when "install"
    abort "Usage: install VERSION" unless version
    install(version)
  when "launch"
    abort "Usage: launch VERSION" unless version
    launch(version)
  else
    warn "Usage: ruby #{File.basename(__FILE__)} [list|install|launch] [#{RELEASES.keys.join('|')}]"
  end
else
  puts JSON.generate(manifest)
end
