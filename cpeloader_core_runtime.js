// CPELoader Node policy: fail closed when the shared unlock state is absent.
const fs = require('node:fs');
const path = require('node:path');
const components = ['cpeloader.py', 'cpeloader_core_runtime.js', 'cpeloader_core.rb'];
function status(root = __dirname) {
  let state = {};
  try { state = JSON.parse(fs.readFileSync(path.join(root, 'cpeloader_state.json'), 'utf8')); } catch {}
  try {
    return {unlocked: state?.unlocked === true && components.every(name => state.components?.[name] === true && fs.statSync(path.join(root, name)).isFile())};
  } catch { return {unlocked: false}; }
}
function requireFlash(root) {
  if (!status(root).unlocked) throw new Error('CPELoader locked: unlock from the game with Ctrl+A then Y.');
}
module.exports = {status, requireFlash};
if (require.main === module) {
  const root = process.argv[2] || __dirname;
  try { if (process.argv[3] === 'flash') requireFlash(root); console.log(JSON.stringify(status(root))); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
