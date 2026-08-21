'use strict';

const assert = require('node:assert/strict');

global.window = {};
require('../static/js/shortcut-actions.js');

const shortcuts = global.window.ShortcutActions;
assert.ok(shortcuts);
assert.equal(shortcuts.actions.length, 64);
assert.equal(shortcuts.canonicalize('shift+ctrl+z'), 'Ctrl+Shift+Z');
assert.equal(shortcuts.canonicalize('ctrl+space'), 'Ctrl+Space');
assert.equal(shortcuts.fromEvent({code:'KeyZ', key:'z', ctrlKey:true, shiftKey:true}), 'Ctrl+Shift+Z');
assert.equal(shortcuts.fromEvent({code:'ControlLeft', key:'Control', ctrlKey:true}, {allowModifierOnly:true}), 'Ctrl');
assert.deepEqual(shortcuts.validate('Alt+F4'), {ok:false, binding:'Alt+F4', error:'该组合键由系统保留'});
assert.equal(shortcuts.validate('Ctrl+K').ok, true);

const overrides = {"canvas.undo":'Alt+Z', "canvas.toggleAssets":''};
const resolved = shortcuts.resolvedBindings(overrides);
assert.equal(resolved['canvas.undo'], 'Alt+Z');
assert.equal(resolved['canvas.toggleAssets'], '');
assert.equal(resolved['canvas.copy'], 'Ctrl+C');

assert.equal(
    shortcuts.findAction({code:'KeyZ', key:'z', altKey:true}, 'canvas', overrides).id,
    'canvas.undo'
);
assert.equal(
    shortcuts.findAction({code:'Space', key:' '}, 'canvas', {}, {hold:true}).id,
    'canvas.temporaryTool'
);
assert.equal(
    shortcuts.findAction({code:'ControlLeft', key:'Control', ctrlKey:true}, 'canvas', {}, {hold:true}).id,
    'canvas.temporaryControlTool'
);
assert.equal(shortcuts.conflicts({}, 'canvas.run', 'Ctrl+Shift+Enter')[0].id, 'canvas.runCascade');
assert.equal(shortcuts.conflicts({}, 'editor.apply', 'Ctrl+Enter').length, 0);

console.log('shortcut actions runtime: ok');
