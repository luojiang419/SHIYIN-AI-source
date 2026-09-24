const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const browser = await chromium.launch({headless: true, channel: 'msedge'});
  try {
    const context = await browser.newContext({viewport: {width: 1400, height: 380}});
    await context.addCookies(input.cookies.map(c => ({...c, url: input.base})));
    const page = await context.newPage();
    await page.goto(input.base + '/static/probe.html');
    const playback = await page.evaluate(async ({source, outputs, expected}) => {
      document.body.style.cssText = 'background:#16181e;color:white;font:20px sans-serif';
      const results = [];
      for (const [index, url] of [source, ...outputs].entries()) {
        const label = document.createElement('p');
        label.textContent = ['原视频', '自动档深度', '小模型深度'][index];
        const video = document.createElement('video');
        video.style.cssText = 'width:440px;display:block';
        const section = document.createElement('section');
        section.style.cssText = 'display:inline-block;margin:8px;vertical-align:top';
        section.append(label, video); document.body.append(section);
        video.muted = true; video.controls = true; video.src = url;
        await video.play();
        await new Promise((resolve, reject) => {
          video.addEventListener('timeupdate', () => { if (video.currentTime > .1) resolve(); });
          video.addEventListener('error', () => reject(new Error('video decode error')), {once:true});
        });
        video.pause();
        await new Promise(resolve => {video.addEventListener('seeked', resolve, {once:true}); video.currentTime = Math.min(6, expected.duration / 2);});
        results.push({width:video.videoWidth, height:video.videoHeight, duration:video.duration, seek:video.currentTime});
      }
      return results;
    }, input);
    for (const video of playback) {
      assert.equal(video.width, input.expected.width); assert.equal(video.height, input.expected.height);
      assert(Math.abs(video.duration - input.expected.duration) < .1);
      assert(Math.abs(video.seek - Math.min(6, input.expected.duration / 2)) < .1);
    }
    await page.screenshot({path:input.screenshot});
    console.log(JSON.stringify({playback, realBrowserDecode:true}));
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
