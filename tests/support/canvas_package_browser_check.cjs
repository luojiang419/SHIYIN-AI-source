// 真实隔离后端与 Chromium：发送故事板、列表刷新、下载 ZIP、重新导入、导出错误。
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');

(async () => {
    const root = path.resolve(__dirname, '../..');
    const work = fs.mkdtempSync(path.join(os.tmpdir(), 'canvas-package-browser-'));
    const port = Number(process.env.CANVAS_TEST_PORT || 13097);
    const base = `http://127.0.0.1:${port}`;
    const packagedBackend = process.env.CANVAS_TEST_BACKEND;
    const server = spawn(packagedBackend || process.env.PYTHON || 'python', packagedBackend
        ? ['--app-root',process.env.CANVAS_TEST_APP_ROOT,'--host','127.0.0.1','--port',String(port)]
        : ['-m','uvicorn','main:app','--host','127.0.0.1','--port',String(port)], {
        cwd:root, windowsHide:true, env:{...process.env, CANVAS_DATA_DIR:path.join(work,'data'), CANVAS_PORT:String(port), PYTHONUTF8:'1', CANVAS_DWPOSE_AUTO_DOWNLOAD:'0', CANVAS_DEPTH_AUTO_DOWNLOAD:'0'},
        stdio:['ignore','pipe','pipe'],
    });
    let logs = '';
    server.stdout.on('data', data => logs += data);
    server.stderr.on('data', data => logs += data);
    let browser;
    try {
        for(let n=0; n<100; n++){
            if(server.exitCode !== null) throw new Error(logs);
            try { if((await fetch(`${base}/api/health`)).ok) break; } catch(_) {}
            if(n===99) throw new Error(`Server timeout: ${logs}`);
            await new Promise(resolve => setTimeout(resolve,200));
        }
        browser = await chromium.launch({headless:true, channel:'chrome'});
        const page = await browser.newPage({viewport:{width:1440,height:960}, acceptDownloads:true});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const login = await page.request.post(`${base}/api/account/login`, {data:{account:'jiang',password:'jiang'}});
        assert.equal(login.status(),200, await login.text());
        // 由 Pillow 创建真实 PNG，避免测试资源不符合接收端的图片校验。
        const imageFile = path.join(work,'frame.png');
        const imageProcess = spawn(process.env.PYTHON || 'python', ['-c', 'from PIL import Image; import sys; Image.new("RGB", (160,90), "orange").save(sys.argv[1])',imageFile], {windowsHide:true});
        await new Promise((resolve,reject) => imageProcess.on('exit',code => code===0 ? resolve() : reject(new Error('PNG fixture failed'))));
        async function sendBoard(board){
            const manifest = {schema:'shiyin-film-bridge',schema_version:2,bridge_id:`film:test:${board}`,direction:'film-to-shiyin',source:{app:'filmstoryboard',board_id:board},storyboard:{board_name:board,selected_variant:'original',variants:['original'],frames:[{stable_id:`frame:${board}:0:original`,slot_index:0,shot_number:1,frame_index:0,timestamp_ms:0,relative_path:'images/original/0.png',upload_name:'frame.png',width:160,height:90,variant:'original'}]},shots:[]};
            const response = await page.request.post(`${base}/api/canvas-bridges/film/receive-direct`, {multipart:{manifest:JSON.stringify(manifest),canvas_title:board,frames:{name:'frame.png',mimeType:'image/png',buffer:fs.readFileSync(imageFile)}}});
            assert.equal(response.status(),200,await response.text());
            return response.json();
        }
        const first = await sendBoard('board-A');
        await page.goto(`${base}/static/canvas-list.html`);
        await page.locator(`[data-canvas-id="${first.canvas_id}"]`).waitFor();
        const second = await sendBoard('board-B');
        await page.locator(`[data-canvas-id="${second.canvas_id}"]`).waitFor();
        assert.notEqual(first.canvas_id,second.canvas_id);
        const repeated = await sendBoard('board-A');
        assert.equal(repeated.canvas_id,first.canvas_id);
        // 下载路径使用真实菜单点击，而非直接调用导出函数。
        await page.locator(`[data-canvas-id="${first.canvas_id}"] .ws-card-menu`).click();
        const downloaded = page.waitForEvent('download');
        await page.locator('[data-act="export"]').click();
        const download = await downloaded;
        const archive = path.join(work,download.suggestedFilename());
        await download.saveAs(archive);
        assert.equal(fs.readFileSync(archive).subarray(0,2).toString(),'PK');
        await page.locator('.ws-package-progress-close').click();
        await page.locator('#importCanvasPackageInput').setInputFiles(archive);
        await page.waitForURL(/canvas\.html\?id=/);
        const importedId = new URL(page.url()).searchParams.get('id');
        assert.notEqual(importedId, first.canvas_id);
        const restoredResponse = await page.request.get(`${base}/api/canvases/${importedId}`);
        const restored = (await restoredResponse.json()).canvas;
        const imageNode = restored.nodes.find(node => node.type==='image');
        const media = await page.request.get(`${base}${imageNode.url}`);
        assert.deepEqual(await media.body(), fs.readFileSync(imageFile));
        await page.goto(`${base}/static/canvas-list.html`);
        await page.route('**/export-package?**', route => route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'测试打包失败'})}));
        await page.locator(`[data-canvas-id="${first.canvas_id}"] .ws-card-menu`).click();
        await page.locator('[data-act="export-assets"]').click();
        await page.locator('.ws-package-progress-backdrop[data-state="error"]').waitFor();
        assert.match(await page.locator('.ws-package-progress-message').innerText(),/测试打包失败/);
        await page.screenshot({path:path.join(work,'export-error.png')});
        await page.locator('.ws-package-progress-close').click();
        await page.unroute('**/export-package?**');
        const settings = await page.request.put(`${base}/api/app-settings`, {data:{quick_save_mode:'silent',quick_save_dir:path.join(work,'saved')}});
        assert.equal(settings.status(),200,await settings.text());
        await page.reload();
        await page.locator(`[data-canvas-id="${first.canvas_id}"] .ws-card-menu`).click();
        await page.locator('[data-act="export-assets"]').click();
        await page.locator('.ws-package-progress-backdrop[data-state="success"]').waitFor();
        const savedFiles = fs.readdirSync(path.join(work,'saved'));
        assert.equal(savedFiles.length,1);
        assert.equal(fs.readFileSync(path.join(work,'saved',savedFiles[0])).subarray(0,2).toString(),'PK');
        await page.locator('.ws-package-progress-close').click();
        await page.locator('#importCanvasPackageInput').setInputFiles({name:'invalid.zip',mimeType:'application/zip',buffer:Buffer.from('invalid')});
        await page.locator('.ws-package-progress-backdrop[data-state="error"]').waitFor();
        assert.deepEqual(errors,[]);
        console.log(JSON.stringify({ok:true,checks:['board-per-project','repeated-board-sync','live-list-refresh','menu-export-download','ZIP-import-navigation','restored-media-bytes','visible-export-error','silent-export-file','invalid-import-error'],artifacts:work}));
    } finally {
        if(browser) await browser.close();
        server.kill();
    }
})().catch(error => {console.error(error); process.exitCode=1;});
