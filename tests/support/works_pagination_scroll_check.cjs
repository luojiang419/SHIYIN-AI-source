// 隔离服务：canvas_startup_fixture.py --port 3064；所有作品请求由内存 fixture 提供。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseline = process.argv.includes('--baseline');
const output = '.codex-artifacts/works-pagination';
const pixel = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jEOsAAAAASUVORK5CYII=';

(async()=>{
    fs.mkdirSync(output,{recursive:true});
    const browser = await chromium.launch({headless:true,channel:'msedge'});
    try {
        const page = await browser.newPage({viewport:{width:1920,height:1008}});
        const requests = [], errors = [], seen = new Set();
        let scenario = 'normal', failedOnce = false;
        let maxDom = 0;
        page.on('pageerror', error=>errors.push(error.message));
        await page.route('**/api/works?**',async route=>{
            const params = new URL(route.request().url()).searchParams;
            const mode = scenario;
            const start = Number((params.get('cursor') || 'works#0').split('#')[1]);
            requests.push(start);
            if(mode==='error' && start===120 && !failedOnce){
                failedOnce = true;
                return route.fulfill({status:503,json:{detail:'分页暂时不可用'}});
            }
            const video = params.get('media_type') === 'video';
            const total = video ? 1 : mode==='short' ? 12 : 2059;
            const pageSize = mode==='short' ? 3 : 120;
            const works = Array.from({length:Math.min(pageSize,total-start)},(_,i)=>({
                id:video?'only-video':`work-${start+i}`,name:`work-${start+i}.png`,url:pixel,preview_url:pixel,
                kind:'image',media_type:'image',created_at:1800000000-start-i,
            }));
            await new Promise(resolve=>setTimeout(resolve,mode==='slow' && start===120 ? 800 : 80));
            const next = mode==='repeat' && start===120 ? 'works#120' : start+works.length<total?`works#${start+works.length}`:'';
            await route.fulfill({json:{works,total,next_cursor:next}}).catch(()=>{});
        });
        await page.goto('http://127.0.0.1:3064/static/works.html');
        await page.waitForSelector('.works-card');
        const initial = await page.locator('#worksGrid').evaluate(grid=>({height:grid.scrollHeight,viewport:grid.clientHeight}));
        await page.locator('#worksGrid').evaluate(grid=>{grid.scrollTop=6400;});
        await page.waitForTimeout(450);
        const firstBoundary = await page.locator('#worksGrid').evaluate(grid=>({
            scrollTop:grid.scrollTop,height:grid.scrollHeight,cards:grid.querySelectorAll('.works-card').length,
            visible:[...grid.querySelectorAll('.works-card')].filter(card=>{
                const r=card.getBoundingClientRect(),g=grid.getBoundingClientRect();return r.bottom>g.top && r.top<g.bottom;
            }).length,
        }));
        if(baseline){
            assert.equal(requests.length,1); assert.equal(firstBoundary.visible,0);
            fs.writeFileSync(`${output}/baseline.json`,JSON.stringify({initial,firstBoundary,requests},null,2));
            console.log(JSON.stringify({initial,firstBoundary,requests}));
            return;
        }
        assert.ok(requests.length>=2,'next page must load at the first page boundary');
        assert.ok(firstBoundary.visible>0,'loaded page boundary must contain visible cards');
        await page.locator('#worksGrid').evaluate(grid=>{grid.scrollTop=0;});
        for(let step=0;step<400;step++){
            const info = await page.locator('#worksGrid').evaluate(grid=>({
                ids:[...grid.querySelectorAll('.works-card')].map(card=>card.dataset.workId),
                top:grid.scrollTop,height:grid.scrollHeight,viewport:grid.clientHeight,
            }));
            info.ids.forEach(id=>seen.add(id)); maxDom=Math.max(maxDom,info.ids.length);
            if(seen.size===2059) break;
            await page.locator('#worksGrid').evaluate(grid=>{grid.scrollTop+=500;});
            await page.waitForTimeout(35);
        }
        assert.equal(seen.size,2059,'all works must be reachable through sequential scrolling');
        assert.deepEqual(requests,Array.from({length:18},(_,i)=>i*120));
        assert.ok(maxDom<100,`virtual DOM must stay bounded: ${maxDom}`);
        assert.deepEqual(errors,[]);
        await page.locator('#worksGrid').evaluate(grid=>{grid.scrollTop=grid.scrollHeight;});
        await page.waitForTimeout(80);
        assert.ok(await page.locator('[data-work-id="work-2058"]').evaluate(card=>{
            const r=card.getBoundingClientRect(),g=document.getElementById('worksGrid').getBoundingClientRect();
            return r.top>=g.top && r.bottom<=g.bottom;
        }),'the final work must be visible inside the scrolling viewport');
        await page.screenshot({path:`${output}/last-page.png`});
        fs.writeFileSync(`${output}/current.json`,JSON.stringify({initial,firstBoundary,seen:seen.size,maxDom,requests,errors},null,2));
        console.log(JSON.stringify({seen:seen.size,maxDom,pages:requests.length}));

        const cases = ['2059 件完整遍历、18 页、最多 63 张 DOM 卡片'];
        const reset = async mode => {
            scenario=mode; requests.length=0;
            await page.locator('#worksRefresh').click();
            await page.waitForSelector('[data-work-id="work-0"]');
        };
        const bottom = () => page.locator('#worksGrid').evaluate(grid=>{grid.scrollTop=grid.scrollHeight;});
        await reset('error'); await bottom();
        await page.getByRole('button',{name:'分页暂时不可用 · 点击重试',exact:true}).waitFor();
        assert.deepEqual(requests,[0,120]);
        await page.locator('#worksGrid').evaluate(grid=>{grid.scrollTop-=100;});
        await bottom(); await page.waitForTimeout(250);
        assert.deepEqual(requests,[0,120],'failure must not create an automatic retry storm');
        await page.getByRole('button',{name:'分页暂时不可用 · 点击重试',exact:true}).click();
        await page.waitForFunction(()=>document.querySelector('.works-virtual-spacer').offsetHeight>10000);
        assert.deepEqual(requests,[0,120,120]);
        cases.push('分页错误保留已加载作品、停止自动重试、按钮重试恢复');

        await reset('short');
        await page.waitForFunction(()=>document.querySelectorAll('.works-card').length===12);
        assert.deepEqual(requests,[0,3,6,9]);
        assert.equal(await page.locator('[data-works-load-more]').count(),0);
        cases.push('短页不足视口时自动续取到末页，无需额外滚动事件');

        await reset('repeat'); await bottom();
        await page.getByRole('button',{name:/作品分页未前进/}).waitFor();
        await page.waitForTimeout(250);
        assert.deepEqual(requests,[0,120]);
        cases.push('服务端重复游标明确报错并停止，避免无限请求');

        await reset('slow'); await bottom();
        await page.getByRole('status').filter({hasText:'加载中'}).waitFor();
        const slow = await page.locator('#worksGrid').evaluate(grid=>({
            height:grid.scrollHeight,visible:[...grid.querySelectorAll('.works-card')].filter(card=>{
                const r=card.getBoundingClientRect(),g=grid.getBoundingClientRect();return r.bottom>g.top && r.top<g.bottom;
            }).length,
        }));
        assert.ok(slow.visible>0); assert.ok(slow.height<10000);
        await page.locator('#worksMediaFilter [data-media-type="video"]').click();
        await page.waitForSelector('[data-work-id="only-video"]');
        await page.waitForTimeout(900);
        assert.equal(await page.locator('.works-card').count(),1);
        assert.equal(await page.locator('#worksCount').textContent(),'1');
        assert.equal(await page.locator('#worksGrid').evaluate(grid=>grid.scrollTop),0);
        cases.push('慢分页有可见状态和已有卡片；切换筛选后旧分页不能覆盖新结果');
        assert.deepEqual(errors,[]);
        fs.writeFileSync(`${output}/scenarios.json`,JSON.stringify({cases,slow,errors},null,2));
        console.log(`${cases.length} pagination scenarios passed`);
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
