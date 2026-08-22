# 562 - Film input connection status

生成时间：2026-08-22 13:52:58

## 已完成内容

Film node input rows now show a green status dot and connected text when image input exists; disconnected rows keep optional input; added regression assertions; version bumped from 1.0.239 to 1.0.240.

## 当前模块

Film node input status

## 当前 Git 状态

```text
M VERSION
 M main.py
 M package-lock.json
 M package.json
 M src-tauri/Cargo.lock
 M src-tauri/Cargo.toml
 M src-tauri/tauri.conf.json
 M static/css/canvas-film-nodes.css
 M static/js/canvas-film-nodes.js
 M static/js/canvas.js
 M static/js/smart-canvas.js
 M static/update-notes.json
 M tests/test_canvas_film_nodes.py
?? "\345\275\223\345\211\215\351\241\271\347\233\256\346\200\247\350\203\275\344\270\216\351\225\277\346\234\237\347\274\223\345\255\230\345\210\206\346\236\220\346\212\245\345\221\212.md"
```

## 代码前后对比 / Diff

```diff
diff --git a/VERSION b/VERSION
index f5f769a..9191d21 100644
--- a/VERSION
+++ b/VERSION
@@ -1 +1 @@
-1.0.239
+1.0.240
diff --git a/main.py b/main.py
index 625cec2..38bbe01 100644
--- a/main.py
+++ b/main.py
@@ -406,7 +406,7 @@ STARTUP_MAINTENANCE_STATE = {
 }
 ACTIVE_CANVAS_BY_ACCOUNT: dict[str, str] = {}
 ACTIVE_CANVAS_ID = ""
-APP_VERSION = "1.0.239"
+APP_VERSION = "1.0.240"
 GITHUB_REPO_URL = "https://github.com/luojiang419/SHIYIN-AI-source"
 GITHUB_VERSION_URL = "https://raw.githubusercontent.com/luojiang419/SHIYIN-AI-source/main/VERSION"
 GITHUB_TREE_URL = "https://api.github.com/repos/luojiang419/SHIYIN-AI-source/git/trees/main?recursive=1"
diff --git a/package-lock.json b/package-lock.json
index a459771..af1c4cf 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,12 +1,12 @@
 {
   "name": "shiyin-ai-windows-desktop",
-  "version": "1.0.239",
+  "version": "1.0.240",
   "lockfileVersion": 3,
   "requires": true,
   "packages": {
     "": {
       "name": "shiyin-ai-windows-desktop",
-      "version": "1.0.239",
+      "version": "1.0.240",
       "devDependencies": {
         "@tauri-apps/cli": "2.11.4",
         "tailwindcss": "3.4.17"
diff --git a/package.json b/package.json
index 2e1e1c7..cb0138a 100644
--- a/package.json
+++ b/package.json
@@ -1,7 +1,7 @@
 {
   "name": "shiyin-ai-windows-desktop",
   "private": true,
-  "version": "1.0.239",
+  "version": "1.0.240",
   "scripts": {
     "css:build": "node ./node_modules/tailwindcss/lib/cli.js -c tailwind.config.cjs -i ./static/css/tailwind-input.css -o ./static/vendor/css/tailwind.generated.css --minify",
     "desktop:dev": "npm run css:build && tauri dev",
diff --git a/src-tauri/Cargo.lock b/src-tauri/Cargo.lock
index 7b07638..bf9984b 100644
--- a/src-tauri/Cargo.lock
+++ b/src-tauri/Cargo.lock
@@ -449,7 +449,7 @@ dependencies = [
 
 [[package]]
 name = "canvas-desktop"
-version = "1.0.239"
+version = "1.0.240"
 dependencies = [
  "arboard",
  "open",
diff --git a/src-tauri/Cargo.toml b/src-tauri/Cargo.toml
index 6ef2276..4a12c97 100644
--- a/src-tauri/Cargo.toml
+++ b/src-tauri/Cargo.toml
@@ -1,6 +1,6 @@
 [package]
 name = "canvas-desktop"
-version = "1.0.239"
+version = "1.0.240"
 description = "SHIYIN AI Windows portable desktop host"
 authors = ["SHIYIN AI contributors"]
 edition = "2021"
diff --git a/src-tauri/tauri.conf.json b/src-tauri/tauri.conf.json
index 32c39ef..4cb308d 100644
--- a/src-tauri/tauri.conf.json
+++ b/src-tauri/tauri.conf.json
@@ -1,7 +1,7 @@
 {
   "$schema": "../node_modules/@tauri-apps/cli/config.schema.json",
   "productName": "SHIYIN AI",
-  "version": "1.0.239",
+  "version": "1.0.240",
   "identifier": "com.hero8152.canvas.desktop",
   "build": {
     "frontendDist": "../desktop-placeholder"
diff --git a/static/css/canvas-film-nodes.css b/static/css/canvas-film-nodes.css
index df172fa..ef9a36e 100644
--- a/static/css/canvas-film-nodes.css
+++ b/static/css/canvas-film-nodes.css
@@ -128,8 +128,20 @@
     white-space:nowrap;
 }
 .film-input-row b.has-input {
+    display:inline-flex;
+    align-items:center;
+    gap:4px;
     color:#258a57;
 }
+.film-input-status-dot {
+    display:inline-block;
+    width:6px;
+    height:6px;
+    flex:0 0 auto;
+    border-radius:50%;
+    background:#2fbf71;
+    box-shadow:0 0 0 2px color-mix(in srgb, #2fbf71 18%, transparent), 0 0 7px color-mix(in srgb, #2fbf71 55%, transparent);
+}
 .film-prompt-field,
 .film-image-settings label,
 .film-video-settings label {
diff --git a/static/js/canvas-film-nodes.js b/static/js/canvas-film-nodes.js
index 55d38dd..6487987 100644
--- a/static/js/canvas-film-nodes.js
+++ b/static/js/canvas-film-nodes.js
@@ -156,8 +156,9 @@
     function inputSlotHtml(node, port, options={}){
         const assets = options.assets?.(node) || [];
         const count = assets.filter(item => String(item?.role || item?.inputRole || '') === port.role && item?.url).length;
-        const state = count ? `${count} 张已连接` : '可选输入';
-        return `<div class="film-input-row" data-input-role="${esc(port.role)}" data-port-index="${Number(options.index || 0)}"><span><i data-lucide="${count ? 'circle-check' : 'circle-dashed'}"></i><strong>${esc(port.label)}</strong></span><b class="${count ? 'has-input' : ''}">${esc(state)}</b></div>`;
+        const state = count ? '已连接' : '可选输入';
+        const stateHtml = count ? '<span class="film-input-status-dot" aria-hidden="true"></span>已连接' : state;
+        return `<div class="film-input-row" data-input-role="${esc(port.role)}" data-port-index="${Number(options.index || 0)}"><span><i data-lucide="${count ? 'circle-check' : 'circle-dashed'}"></i><strong>${esc(port.label)}</strong></span><b class="${count ? 'has-input' : ''}">${stateHtml}</b></div>`;
     }
     function bodyHtml(node, options={}){
         normalize(node);
diff --git a/static/js/canvas.js b/static/js/canvas.js
index 6285ff0..0236b57 100644
--- a/static/js/canvas.js
+++ b/static/js/canvas.js
@@ -8262,6 +8262,7 @@ function filmNodeProviderOptions(node){
     return videoProviderOptions(node.apiProvider || videoApiProviders()[0]?.id || 'comfly');
 }
 function filmNodeModelOptions(node){
+    if(isKlingVideoNode(node)) ensureKlingCapabilities();
     return videoModelOptionsForNode(node);
 }
 function filmNodeImageProviderOptions(node){
diff --git a/static/js/smart-canvas.js b/static/js/smart-canvas.js
index b3dd9b8..c0d0d2e 100644
--- a/static/js/smart-canvas.js
+++ b/static/js/smart-canvas.js
@@ -1469,6 +1469,12 @@ function filmSmartAssets(node){
         return imagesForNode(source).map(ref => ({ref,role:connection.inputRole || ''}));
     });
 }
+function filmSmartImageProviderId(node){
+    const providers=imageProviders();
+    return providers.some(provider => provider.id === node?.apiProvider)
+        ? node.apiProvider
+        : (providers[0]?.id || '');
+}
 function filmSmartProviderOptions(node){
     const providers=videoApiProviders();
     const selected=node.apiProvider || providers[0]?.id || 'comfly';
@@ -1480,10 +1486,10 @@ function filmSmartModelOptions(node){
     return [...new Set([selected,...models].filter(Boolean))].map(model => `<option value="${escapeAttr(model)}" ${model===selected?'selected':''}>${escapeHtml(model)}</option>`).join('');
 }
 function filmSmartImageProviderOptions(node){
-    return smartMultiViewProviderOptions(node.apiProvider || imageProviders()[0]?.id || '');
+    return smartMultiViewProviderOptions(filmSmartImageProviderId(node));
 }
 function filmSmartImageModelOptions(node){
-    const providerId=node.apiProvider || imageProviders()[0]?.id || '';
+    const providerId=filmSmartImageProviderId(node);
     return smartMultiViewModelOptions(providerId,node.model || '');
 }
 function createFilmNode(type, point){
@@ -1515,7 +1521,7 @@ async function runSmartFilmNode(node){
     node.running=true; node.runError=''; render();
     try {
         if(node.specialType === 'film-storyboard'){
-            const imageProvider=node.apiProvider || settingsForNodeRun.provider_id || imageProviders()[0]?.id || '';
+            const imageProvider=filmSmartImageProviderId(node) || settingsForNodeRun.provider_id || imageProviders()[0]?.id || '';
             const imageModels=providerImageModels(imageProvider);
             const imageSettings={...settingsForNodeRun,engine:'api',apiKind:'image',ratio:node.aspectRatio || settingsForNodeRun.ratio || '16:9',resolution:node.resolution || settingsForNodeRun.resolution || '2k',quality:node.quality || settingsForNodeRun.quality || 'high',count:1,provider_id:imageProvider,model:node.model || settingsForNodeRun.model || imageModels[0] || ''};
             const created=await runApiGeneration(built.prompt,built.refs,imageSettings);
@@ -8148,7 +8154,7 @@ function smartGroupBodyHtml(node){
     </div>`;
 }
 function nodeBodyHtml(node, layout){
-    if(node.specialType === 'film-storyboard' || node.specialType === 'film-video') return window.CanvasFilmNodes?.bodyHtml(node,{providerOptions:filmSmartProviderOptions,modelOptions:filmSmartModelOptions,assets:filmSmartAssets}) || '<div class="smart-group-empty">影视节点加载失败</div>';
+    if(node.specialType === 'film-storyboard' || node.specialType === 'film-video') return window.CanvasFilmNodes?.bodyHtml(node,{providerOptions:filmSmartProviderOptions,modelOptions:filmSmartModelOptions,imageProviderOptions:filmSmartImageProviderOptions,imageModelOptions:filmSmartImageModelOptions,assets:filmSmartAssets}) || '<div class="smart-group-empty">影视节点加载失败</div>';
     if(node.specialType === 'panorama') return window.CanvasSpecialNodes?.panoramaBodyHtml(node) || '<div class="smart-group-empty">720°取景器加载失败</div>';
     if(node.specialType === 'dwpose') return window.CanvasSpecialNodes?.poseBodyHtml(node) || '<div class="smart-group-empty">动作提取节点加载失败</div>';
     if(node.specialType === 'pose-reference') return window.CanvasSpecialNodes?.poseReferenceBodyHtml?.(node) || '<div class="smart-group-empty">姿势参考节点加载失败</div>';
diff --git a/static/update-notes.json b/static/update-notes.json
index 050db00..821f0b1 100644
--- a/static/update-notes.json
+++ b/static/update-notes.json
@@ -1,5 +1,5 @@
 {
-  "version": "1.0.239",
+  "version": "1.0.240",
   "updated_at": "2026-08-22T09:21:25+08:00",
   "items": [
     {
diff --git a/tests/test_canvas_film_nodes.py b/tests/test_canvas_film_nodes.py
index 5897c5d..bc1d796 100644
--- a/tests/test_canvas_film_nodes.py
+++ b/tests/test_canvas_film_nodes.py
@@ -58,3 +58,17 @@ def test_film_input_slots_match_three_view_layout_and_keep_labels_inside_content
     assert "rgba(124,58,237" not in FILM_CSS
     assert "rgba(139,92,246" not in FILM_CSS
     assert "rgba(124,58,237" not in SMART_CSS
+
+
+def test_film_variants_use_their_parent_generation_model_sources():
+    assert "imageProviderOptions:filmSmartImageProviderOptions" in SMART
+    assert "imageModelOptions:filmSmartImageModelOptions" in SMART
+    assert "const imageProvider=filmSmartImageProviderId(node)" in SMART
+    assert "if(isKlingVideoNode(node)) ensureKlingCapabilities();" in CLASSIC
+
+
+def test_film_connected_input_status_has_a_green_indicator_and_connected_label():
+    assert "film-input-status-dot" in FILM
+    assert "'<span class=\"film-input-status-dot\" aria-hidden=\"true\"></span>已连接'" in FILM
+    assert ".film-input-status-dot" in FILM_CSS
+    assert "background:#2fbf71" in FILM_CSS
```

## 验证结果

- `python -m pytest tests/test_canvas_film_nodes.py tests/test_canvas_multi_view.py tests/test_unified_video_node_frontend.py tests/test_kling_canvas_video.py tests/test_kling_cli.py -q`：46 passed，4 个 FastAPI 弃用警告。
- `node --check static/js/canvas-film-nodes.js`：通过。
- `node --check static/js/canvas.js`：通过。
- `node --check static/js/smart-canvas.js`：通过。
- `git diff --check`：通过。

## 待办清单

Run full related tests, JS syntax checks, source backup, pitfall record, and GitHub push.

## 下一步

Run canvas, smart-canvas, Kling, and multi-view tests plus Node syntax checks; then create the large-module backup and clean temporary caches.

## 避坑记录

Windows PowerShell 5.1 直接向 Python 快照脚本传递长中文参数时可能发生 argv 编码乱码；本次改用 ASCII 参数生成快照，并将经验记录到 `避坑指南/Windows PowerShell调用Python快照脚本中文参数编码.md`。
