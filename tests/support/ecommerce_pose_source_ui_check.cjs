const assert = require('node:assert/strict');
const {chromium} = require('playwright');

(async () => {
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage();
        await page.route('**/api/**', route => {
            const pathname = new URL(route.request().url()).pathname;
            if(pathname === '/api/ecommerce/capabilities') {
                return route.fulfill({json:{models:[],providers:[],routes:{},pose_presets:[{id:'standing_front',name:'正面站立'},{id:'walking',name:'自然行走'}],reference_slot_types:[]}});
            }
            if(pathname === '/api/ecommerce/tasks') return route.fulfill({json:{tasks:[]}});
            return route.fulfill({json:{}});
        });
        await page.goto(`${process.env.POSE_TEST_BASE_URL || 'http://127.0.0.1:8877'}/static/ecommerce.html`);
        await page.locator('[data-operation="pose_transfer"]').click();
        await page.locator('[data-option-button="pose_source"][data-value="preset"]').click();
        assert.equal(await page.locator('#posePresetGrid').count(), 1);
        await page.locator('[data-option-button="pose_source"][data-value="reference"]').click();
        assert.equal(await page.locator('#posePresetGrid').count(), 0);
        await page.locator('[data-option-button="pose_source"][data-value="preset"]').click();
        assert.equal(await page.locator('#posePresetGrid').count(), 1);
        console.log('pose source controls passed');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
