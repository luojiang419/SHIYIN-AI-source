#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_root"

version="$(tr -d '[:space:]' < VERSION)"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid VERSION: $version" >&2
  exit 1
fi

machine="$(uname -m)"
case "$machine" in
  arm64|aarch64) artifact_arch="arm64" ;;
  x86_64|amd64) artifact_arch="x64" ;;
  *) echo "Unsupported macOS architecture: $machine" >&2; exit 1 ;;
esac

build_root="$project_root/.build/macos/$artifact_arch"
stage_root="$build_root/stage"
backend_dist="$build_root/backend-dist"
backend_work="$build_root/backend-work"
output_root="$project_root/dist/macos"
case "$build_root" in
  "$project_root"/.build/macos/*) rm -rf "$build_root" ;;
  *) echo "Refusing to clean unexpected build path: $build_root" >&2; exit 1 ;;
esac
mkdir -p "$stage_root/app/backend" "$stage_root/app/runtime" "$output_root"

python3 -m PyInstaller --noconfirm --clean \
  --distpath "$backend_dist" --workpath "$backend_work" canvas-backend.spec
npm run css:build

cp -R "$backend_dist/canvas-backend" "$stage_root/app/backend/canvas-backend"
cp -R static "$stage_root/app/web"
python3 tools/prepare-kling-runtime.py --output "$build_root/kling-runtime"
cp -R "$build_root/kling-runtime" "$stage_root/app/runtime/kling"
cp -R skills "$stage_root/app/skills"
cp .agents/skills/sd25-pe/SKILL.md "$stage_root/app/skills/video-prompt-polish/seedance-2.5/SKILL.md"
mkdir -p "$stage_root/app/connectors" "$stage_root/app/licenses"
cp -R tools/chrome-local-asset-importer "$stage_root/app/connectors/chrome"
cp -R tools/photoshop-asset-connector "$stage_root/app/connectors/photoshop"
cp -R tools/blender-addon "$stage_root/app/connectors/blender"
cp -R third_party/dwpose "$stage_root/app/licenses/dwpose"
cp VERSION "$stage_root/app/VERSION"

node tools/stamp-web-cache-version.mjs --root "$stage_root/app/web" --version "$version"
chmod +x "$stage_root/app/backend/canvas-backend/canvas-backend"
chmod +x "$stage_root/app/runtime/kling"/node-*/bin/node

./node_modules/.bin/tauri build --bundles app --config src-tauri/tauri.macos.conf.json
bundle_root="$project_root/src-tauri/target/release/bundle/macos"
app_bundle="$(find "$bundle_root" -maxdepth 1 -type d -name '*.app' -print -quit)"
app_count="$(find "$bundle_root" -maxdepth 1 -type d -name '*.app' | wc -l | tr -d '[:space:]')"
if [[ "$app_count" != "1" || -z "$app_bundle" ]]; then
  echo "Expected exactly one macOS app bundle, found $app_count" >&2
  exit 1
fi
resources="$app_bundle/Contents/Resources"
rm -rf "$resources/app"
cp -R "$stage_root/app" "$resources/app"
cp VERSION LICENSE README.md "$resources/"

codesign --force --deep --sign - "$app_bundle"
codesign --verify --deep --strict "$app_bundle"
python3 tools/smoke-macos-bundle.py --app "$app_bundle"

base="SHIYIN-AI-${version}-macos-${artifact_arch}"
zip_path="$output_root/$base.app.zip"
dmg_path="$output_root/$base.dmg"
rm -f "$zip_path" "$dmg_path" "$zip_path.sha256" "$dmg_path.sha256"
ditto -c -k --sequesterRsrc --keepParent "$app_bundle" "$zip_path"
dmg_stage="$build_root/dmg-stage"
mkdir -p "$dmg_stage"
cp -R "$app_bundle" "$dmg_stage/SHIYIN AI.app"
ln -s /Applications "$dmg_stage/Applications"
hdiutil create -volname "SHIYIN AI" -srcfolder "$dmg_stage" -ov -format UDZO "$dmg_path"
for artifact in "$zip_path" "$dmg_path"; do
  hash="$(shasum -a 256 "$artifact" | awk '{print $1}')"
  printf '%s  %s\n' "$hash" "$(basename "$artifact")" > "$artifact.sha256"
done

python3 - "$output_root/$base.manifest.json" "$version" "$artifact_arch" "$zip_path" "$dmg_path" <<'PY'
import hashlib, json, platform, sys
from pathlib import Path

target, version, arch, *artifacts = sys.argv[1:]
items = []
for raw in artifacts:
    path = Path(raw)
    items.append({
        "name": path.name,
        "size": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    })
Path(target).write_text(json.dumps({
    "version": version,
    "architecture": arch,
    "runner_machine": platform.machine(),
    "artifacts": items,
}, indent=2) + "\n", encoding="utf-8")
PY

echo "macOS artifacts built in $output_root"
