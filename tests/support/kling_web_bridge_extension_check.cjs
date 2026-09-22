const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..', '..');
const popup = fs.readFileSync(path.join(root, 'tools', 'chrome-local-asset-importer', 'popup.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'tools', 'chrome-local-asset-importer', 'popup.html'), 'utf8');
const readme = fs.readFileSync(path.join(root, 'tools', 'chrome-local-asset-importer', 'README.md'), 'utf8');

for (const text of ['scanKlingBtn', 'function isKlingPage(url)', 'function prioritizeKlingResults(items)', 'async function scanKlingResults()', "'可灵成片'", '读取账号凭据']) {
  if (!popup.includes(text) && !html.includes(text)) throw new Error(`Missing Kling bridge contract: ${text}`);
}
if (!readme.includes('可灵网页桥接') || !readme.includes('不会替用户提交生成')) {
  throw new Error('Kling bridge usage and read-only boundary must be documented');
}
console.log('Kling web bridge extension checks passed');
