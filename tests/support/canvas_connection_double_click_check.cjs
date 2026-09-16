const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async()=>{
    const base = process.argv[2] || 'http://127.0.0.1:3022';
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1280,height:900}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${base}/static/canvas.html?id=connection-double-click-check${process.argv[3] === 'legacy' ? '&canvasEngine=legacy' : ''}`);
        await page.waitForSelector('.image-node[data-id="image"]');
        await page.waitForFunction(()=>!window.canvasEntryOverlay);
        assert.equal(await page.evaluate(()=>!!window.CanvasEngine?.active),process.argv[3]!=='legacy');
        await page.evaluate(() => {
            connections.splice(0, connections.length,
                {id:'disconnect-me',from:'prompt',to:'generator'},
                {id:'keep-me',from:'image',to:'generator'}
            );
            markClassicConnectionStructureDirty();
            render();
        });
        await page.waitForSelector('.link-hit[data-connection-id="disconnect-me"]');
        assert.equal(await page.locator('.link-hit[data-connection-id]').count(), 2);

        await page.locator('#board').dispatchEvent('dblclick', {button:0,detail:2,bubbles:true});
        assert.equal(await page.evaluate(() => connections.length), 2, 'double-clicking canvas background must not remove connections');

        await page.locator('.link-hit[data-connection-id="disconnect-me"]').dispatchEvent('dblclick', {button:0,detail:2,bubbles:true});
        await page.waitForFunction(() => connections.length === 1);
        assert.deepEqual(await page.evaluate(() => connections.map(connection => connection.id)), ['keep-me']);

        await page.evaluate(() => performUndo());
        await page.waitForFunction(() => connections.length === 2);
        assert.deepEqual((await page.evaluate(() => connections.map(connection => connection.id))).sort(), ['disconnect-me','keep-me']);
        const output=await page.locator('.prompt-node .port.out').first().boundingBox();
        const input=await page.locator('.video-node .port.in').first().boundingBox();
        assert(output && input,'source and target ports must be visible');
        await page.mouse.move(output.x+output.width/2,output.y+output.height/2);
        await page.mouse.down();
        await page.mouse.move(input.x+input.width/2,input.y+input.height/2,{steps:8});
        await page.mouse.up();
        await page.waitForTimeout(150);
        const linkState=await page.evaluate(({output,input})=>({
            connections:connections.map(connection=>({id:connection.id,from:connection.from,to:connection.to,inputRole:connection.inputRole})),
            tempLink:!!tempLink,
            outputHit:document.elementFromPoint(output.x+output.width/2,output.y+output.height/2)?.outerHTML.slice(0,180),
            inputHit:document.elementFromPoint(input.x+input.width/2,input.y+input.height/2)?.outerHTML.slice(0,180),
        }),{output,input});
        assert(linkState.connections.some(connection=>connection.from==='prompt'&&connection.to==='video'),JSON.stringify(linkState));
        assert.deepEqual(errors, []);
        console.log('classic canvas connection drag, double-click disconnect and undo passed');
    } finally {
        await browser.close();
    }
})().catch(error=>{console.error(error);process.exitCode=1;});
