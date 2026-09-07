// 运行 linkfox_unified_fixture.py 后执行；所有生成请求在浏览器中拦截。
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
    const base=process.argv[2] || 'http://127.0.0.1:3021';
    const output=process.argv[3] || '.codex-artifacts/linkfox-unified';
    fs.mkdirSync(output,{recursive:true});
    const browser=await chromium.launch({headless:true,channel:'chrome'});
    const page=await browser.newPage({viewport:{width:1600,height:1100}});
    const captured=[],errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/api/canvas-video',async route=>{
        const payload=route.request().postDataJSON();captured.push(payload);
        await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({videos:['/fixture.mp4'],request:{...payload,prompt:`${payload.model}已解析的实际提示词`,original_prompt:payload.prompt,prompt_adaptation:{status:'adapted'}}})});
    });
    try{
        await page.goto(base+'/static/canvas.html?id=linkfox-unified');
        const classic=page.locator('.video-node');
        const film=page.locator('.film-node-panel.film-video');
        await classic.locator('.video-provider').selectOption('linkfox');
        await classic.locator('.video-model').selectOption('海螺2.3');
        assert.equal(await classic.locator('[data-linkfox-unified="duration"]').inputValue(),'6');
        await film.locator('[data-film-field="apiProvider"]').selectOption('linkfox');
        await film.locator('[data-film-field="model"]').selectOption('HappyHorse');
        assert(await film.locator('[data-linkfox-unified="generateAudio"]').isChecked());
        assert(await film.locator('[data-linkfox-unified="generateAudio"]').isDisabled());
        assert.equal(await film.locator('[data-film-field="model"] option').count(),7);
        await page.screenshot({path:path.join(output,'two-nodes.png'),fullPage:true});
        await classic.locator('.gen-btn').click();
        await page.waitForFunction(()=>nodes.find(node=>node.id==='video').runStatus==='done');
        await classic.locator('.video-model').selectOption('seedance2.0fast');
        await classic.locator('.gen-btn').click();
        await page.waitForFunction(()=>nodes.find(node=>node.id==='video').runStatus==='done');
        // 模态错误框可由正常页面关闭；不让其遮住下一节点。
        await page.keyboard.press('Escape');
        await page.evaluate(()=>runFilmNode('film'));
        assert.equal(captured.length,3);
        assert(captured.every(item=>item.provider_id==='linkfox' && item.auto_adapt_prompt));
        assert.equal(captured[0].model,'海螺2.3');
        assert.equal(captured[0].duration,6);
        assert.equal(captured[1].model,'seedance2.0fast');
        assert.equal(captured[1].prompt,'海螺2.3已解析的实际提示词');
        assert.equal(captured[1].prompt_source_model,'海螺2.3');
        assert.equal(captured[1].auto_parse_media,false);
        assert.equal(captured[2].model,'HappyHorse');
        assert.equal(captured[2].generate_audio,true);
        assert(captured.every(item=>item.images.length===1));
        assert.equal(await page.evaluate(()=>nodes.find(node=>node.id==='video').prompt),'女子向左走，无配乐。');
        assert.deepEqual(errors,[]);
        fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({captured,errors},null,2));
        console.log('LinkFox双节点浏览器验证通过：模型切换使用上一模型实际提示词，关闭重复解析，保留编辑原词。');
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
