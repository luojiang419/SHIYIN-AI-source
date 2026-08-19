import { readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { extname, resolve } from 'node:path';

function argumentValue(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : '';
}

const rootArgument = argumentValue('--root');
const version = argumentValue('--version');

if (!rootArgument) {
  throw new Error('Missing required --root directory');
}
if (!version || !/^\d+\.\d+\.\d+$/.test(version)) {
  throw new Error(`Invalid --version: ${version || '(empty)'}`);
}
const root = resolve(rootArgument);
if (!(await stat(root)).isDirectory()) {
  throw new Error(`Web root is not a directory: ${root}`);
}

async function collectTextAssets(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...await collectTextAssets(path));
    } else if (entry.isFile() && ['.html', '.js'].includes(extname(entry.name).toLowerCase())) {
      files.push(path);
    }
  }
  return files;
}

let changed = 0;
const assets = await collectTextAssets(root);
for (const path of assets) {
  const content = await readFile(path, 'utf8');
  if (!content.length) {
    throw new Error(`Refusing to stamp empty web asset: ${path}`);
  }
  const updated = content.replace(/([?&])v=[0-9A-Za-z._-]+/g, `$1v=${version}`);
  if (!updated.length) {
    throw new Error(`Cache-version rewrite unexpectedly emptied web asset: ${path}`);
  }
  if (updated !== content) {
    await writeFile(path, updated, 'utf8');
    changed += 1;
  }
}

process.stdout.write(`${JSON.stringify({ root, version, scanned: assets.length, changed })}\n`);
