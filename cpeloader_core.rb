# CPELoader Ruby policy reads the same three-component unlock state.
require 'json'
module CPELoaderCore
  COMPONENTS = %w[cpeloader.py cpeloader_core_runtime.js cpeloader_core.rb].freeze
  def self.unlocked?(root)
    state = JSON.parse(File.read(File.join(root, 'cpeloader_state.json')))
    state['unlocked'] == true && COMPONENTS.all? { |name| state.fetch('components', {})[name] == true && File.file?(File.join(root, name)) }
  rescue StandardError
    false
  end
  def self.require_flash(root)
    raise 'CPELoader locked: unlock from the game with Ctrl+A then Y.' unless unlocked?(root)
  end
end
if $PROGRAM_NAME == __FILE__
  root = ARGV[0] || __dir__
  begin
    CPELoaderCore.require_flash(root) if ARGV[1] == 'flash'
    puts JSON.generate({unlocked: CPELoaderCore.unlocked?(root)})
  rescue StandardError => error
    warn error.message
    exit 1
  end
end
