from __future__ import annotations

import argparse
import asyncio
import base64
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import requests
import websockets


class DevTools:
    def __init__(self, socket):
        self.socket = socket
        self.next_id = 1
        self.exceptions: list[str] = []

    async def call(self, method: str, params: dict | None = None) -> dict:
        request_id = self.next_id
        self.next_id += 1
        await self.socket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(await self.socket.recv())
            if message.get("method") == "Runtime.exceptionThrown":
                details = message.get("params", {}).get("exceptionDetails", {})
                self.exceptions.append(str(details.get("text") or details.get("exception", {}).get("description") or "JavaScript exception"))
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error']}")
            return message.get("result") or {}

    async def evaluate(self, expression: str):
        result = await self.call("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
        })
        if result.get("exceptionDetails"):
            raise RuntimeError(str(result["exceptionDetails"]))
        return result.get("result", {}).get("value")


async def wait_for_page(devtools: DevTools, predicate: str, timeout: float = 15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if await devtools.evaluate(predicate):
            return
        await asyncio.sleep(0.1)
    try:
        diagnostic = await devtools.evaluate("({href:location.href,title:document.title,readyState:document.readyState,body:(document.body?.innerText||'').slice(0,240)})")
    except Exception as exc:
        diagnostic = {"error": str(exc)}
    raise TimeoutError(f"Browser predicate timed out: {predicate}; page={diagnostic}")


async def run(args) -> dict:
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = output_dir / "chrome-profile-cdp"
    if profile.exists():
        shutil.rmtree(profile)
    chrome_log = output_dir / "chrome-cdp.log"
    bootstrap_url = f"http://127.0.0.1:{args.port}/api/auth/bootstrap?token={args.token}"
    browser = subprocess.Popen(
        [
            args.chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--remote-allow-origins=*",
            f"--remote-debugging-port={args.debug_port}",
            f"--user-data-dir={profile}",
            "--window-size=1440,1000",
            bootstrap_url,
        ],
        stdout=chrome_log.open("wb"),
        stderr=subprocess.STDOUT,
    )
    try:
        target = None
        for _ in range(150):
            if browser.poll() is not None:
                raise RuntimeError(f"Chrome exited early with code {browser.returncode}")
            try:
                targets = requests.get(f"http://127.0.0.1:{args.debug_port}/json", timeout=0.5).json()
                target = next((item for item in targets if item.get("type") == "page" and f"127.0.0.1:{args.port}" in str(item.get("url") or "")), None)
                if target:
                    break
            except Exception:
                pass
            await asyncio.sleep(0.1)
        if not target:
            raise TimeoutError("Chrome DevTools did not expose the local application page")
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=16 * 1024 * 1024) as socket:
            devtools = DevTools(socket)
            await devtools.call("Runtime.enable")
            await devtools.call("Page.enable")

            await wait_for_page(devtools, "document.readyState === 'complete' && !!document.getElementById('frame-ecommerce') && !!window.RuntimeSync")
            await devtools.evaluate("document.querySelector('[onclick*=\"ecommerce\"]')?.click(); true")
            await wait_for_page(devtools, "!!document.getElementById('frame-ecommerce')?.contentWindow?.EcommerceStudio?.state?.capabilities")
            await devtools.evaluate("""
                (() => {
                    const frame = document.getElementById('frame-ecommerce');
                    const doc = frame.contentDocument;
                    const input = doc.querySelector('.ec-universal-instruction');
                    input.focus();
                    input.value = '';
                    input.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward'}));
                    return doc.activeElement === input;
                })()
            """)
            await devtools.call("Input.insertText", {"text": "A"})
            await asyncio.sleep(0.45)
            continuous_input_step1 = await devtools.evaluate("""
                (() => {
                    const frame = document.getElementById('frame-ecommerce');
                    const doc = frame.contentDocument;
                    const input = doc.querySelector('.ec-universal-instruction');
                    return {
                        value: input.value,
                        stateValue: frame.contentWindow.EcommerceStudio.state.options.universal.instruction,
                        active: doc.activeElement === input,
                    };
                })()
            """)
            await devtools.call("Input.insertText", {"text": "B"})
            await asyncio.sleep(0.45)
            continuous_input_step2 = await devtools.evaluate("""
                (() => {
                    const frame = document.getElementById('frame-ecommerce');
                    const doc = frame.contentDocument;
                    const input = doc.querySelector('.ec-universal-instruction');
                    return {
                        value: input.value,
                        stateValue: frame.contentWindow.EcommerceStudio.state.options.universal.instruction,
                        active: doc.activeElement === input,
                    };
                })()
            """)
            main_upload = await devtools.evaluate("""
                (async () => {
                    const frame = document.getElementById('frame-ecommerce');
                    const studio = frame.contentWindow.EcommerceStudio;
                    const doc = frame.contentDocument;
                    const bytes = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP8zwACTGCSAQANHQEDgslx/wAAAABJRU5ErkJggg=='), char => char.charCodeAt(0));
                    const file = new frame.contentWindow.File([bytes], 'drag-persistence.png', {type:'image/png'});
                    const defaultOperation = studio.state.operation;
                    const defaultActiveOperations = [...doc.querySelectorAll('[data-operation].active')].map(item => item.dataset.operation);
                    doc.querySelector('[data-operation="try_on"]').click();
                    const sourceSlotDeadline = Date.now() + 5000;
                    while((studio.state.operation !== 'try_on' || !doc.querySelector('.ec-upload-slot[data-role="source"]')) && Date.now() < sourceSlotDeadline) {
                        await new Promise(resolve=>setTimeout(resolve,50));
                    }
                    for (const [id,value] of Object.entries({ratioSelect:'4:5',resolutionSelect:'2k',qualitySelect:'high',countSelect:'3'})) {
                        const select=doc.getElementById(id);
                        select.value=value;
                        select.dispatchEvent(new Event('change',{bubbles:true}));
                    }
                    await studio.uploadInput(file, 'source');
                    const deadline = Date.now() + 10000;
                    while(!studio.state.inputs.source?.url && Date.now() < deadline) await new Promise(resolve=>setTimeout(resolve,50));
                    if(!studio.state.inputs.source?.url) throw new Error('drag upload did not persist a source URL');
                    const sourceUrl = studio.state.inputs.source.url;
                    doc.querySelector('[data-operation="universal"]').click();
                    await new Promise(resolve=>setTimeout(resolve,150));
                    doc.querySelector('[data-operation="try_on"]').click();
                    await new Promise(resolve=>setTimeout(resolve,150));
                    const operationRestored = studio.state.inputs.source?.url === sourceUrl;
                    let preferences = await fetch('/api/preferences').then(response=>response.json());
                    const preferenceDeadline = Date.now() + 5000;
                    while(!String(preferences.values?.ecommerce_settings || '').includes('"operation":"try_on"') && Date.now() < preferenceDeadline) {
                        await new Promise(resolve=>setTimeout(resolve,100));
                        preferences = await fetch('/api/preferences').then(response=>response.json());
                    }
                    return {
                        defaultOperation,
                        defaultActiveOperations,
                        sourceUrl,
                        operationRestored,
                        generationParameters:{aspectRatio:studio.state.aspectRatio,resolution:studio.state.resolution,quality:studio.state.quality,count:studio.state.count},
                        preferenceHasSource:String(preferences.values?.ecommerce_settings || '').includes(sourceUrl),
                        themeMode:window.StudioTheme.getMode(),
                        productIdentity:document.getElementById('product-identity')?.textContent.trim() || '',
                        documentTitle:document.title,
                        worksBelowAssets:[...document.querySelectorAll('.nav-item')].findIndex(item=>item.textContent.includes('作品管理')) > [...document.querySelectorAll('.nav-item')].findIndex(item=>item.textContent.includes('素材库')),
                    };
                })()
            """)
            source_url_json = json.dumps(main_upload["sourceUrl"])
            await wait_for_page(devtools, f"fetch('/api/preferences').then(r=>r.json()).then(d=>String(d.values?.ecommerce_settings||'').includes({source_url_json}))")
            main_preference = await devtools.evaluate(f"fetch('/api/preferences').then(r=>r.json()).then(d=>String(d.values?.ecommerce_settings||'').includes({source_url_json}))")
            await devtools.evaluate("localStorage.removeItem('studio_ecommerce_settings_v2'); location.reload(); true")
            await wait_for_page(devtools, "document.readyState === 'complete' && !!document.getElementById('frame-ecommerce')?.contentWindow?.EcommerceStudio?.state?.capabilities")
            await wait_for_page(devtools, "!!document.getElementById('frame-ecommerce').contentWindow.EcommerceStudio.state.workspaces.try_on?.inputs?.source?.url")
            main_persistence = await devtools.evaluate("""
                (() => {
                    const frame=document.getElementById('frame-ecommerce');
                    const studio=frame.contentWindow.EcommerceStudio;
                    const sourceUrl=studio.state.workspaces.try_on?.inputs?.source?.url || '';
                    const generationParameters={aspectRatio:studio.state.aspectRatio,resolution:studio.state.resolution,quality:studio.state.quality,count:studio.state.count};
                    document.querySelector('[onclick*="works"]')?.click();
                    return {sourceUrl,generationParameters,activeOperation:studio.state.operation,activePage:localStorage.getItem('studio_active_page'),themeMode:window.StudioTheme.getMode()};
                })()
            """)
            await wait_for_page(devtools, "!!document.getElementById('frame-works')?.contentWindow?.WorksManager?.state?.compareViewer")
            main_works = await devtools.evaluate("""
                (() => {
                    const frame=document.getElementById('frame-works');
                    const doc=frame.contentDocument;
                    doc.getElementById('worksQuickCompare').click();
                    const result={
                        tabs:[...doc.querySelectorAll('#worksTabs [data-tab]')].map(item=>item.dataset.tab),
                        freeCompareOpen:doc.getElementById('worksCompareDialog').open,
                        localTargetPicker:!!doc.getElementById('compareTargetFile'),
                        localBasePicker:!!doc.getElementById('compareBaseFile'),
                    };
                    doc.getElementById('closeWorksCompare').click();
                    document.querySelector('[onclick*="ecommerce"]')?.click();
                    window.broadcastTheme('system');
                    return result;
                })()
            """)
            await wait_for_page(devtools, "document.getElementById('frame-ecommerce').classList.contains('active')")
            main_return = await devtools.evaluate("""
                (() => ({
                    sourceStillPresent:!!document.getElementById('frame-ecommerce').contentWindow.EcommerceStudio.state.workspaces.try_on?.inputs?.source?.url,
                    themeMode:window.StudioTheme.getMode(),
                    iframeTheme:document.getElementById('frame-ecommerce').contentWindow.StudioTheme.get(),
                    mainTheme:window.StudioTheme.get(),
                }))()
            """)

            await devtools.call("Page.navigate", {"url": f"http://127.0.0.1:{args.port}/static/ecommerce.html"})
            await wait_for_page(devtools, "document.readyState === 'complete' && !!window.EcommerceStudio && !!window.EcommerceStudio.state.capabilities")

            runtime = await devtools.evaluate("""
                (() => {
                    const tabs = [...document.querySelectorAll('[data-operation]')];
                    const tabOrder = tabs.map(tab => tab.dataset.operation);
                    const operationSlots = {};
                    for (const tab of tabs) {
                        tab.click();
                        operationSlots[tab.dataset.operation] = document.querySelectorAll('#inputSlots .ec-upload-slot').length;
                    }
                    document.querySelector('[data-operation="try_on"]').click();
                    const workspace = document.getElementById('resultWorkspace');
                    workspace.classList.remove('hidden');
                    document.getElementById('compareHandle').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
                    const keyboardValue = window.EcommerceStudio.state.compareValue;
                    const stage = document.getElementById('compareStage');
                    const rect = stage.getBoundingClientRect();
                    stage.dispatchEvent(new PointerEvent('pointerdown',{clientX:rect.left + rect.width * .25,clientY:rect.top + 20,pointerId:7,bubbles:true}));
                    const pointerValue = Math.round(window.EcommerceStudio.state.compareValue);
                    window.EcommerceStudio.state.compareViewer.setZoom(2);
                    stage.dispatchEvent(new PointerEvent('pointerdown',{button:1,clientX:100,clientY:100,pointerId:8,bubbles:true}));
                    stage.dispatchEvent(new PointerEvent('pointermove',{button:1,clientX:135,clientY:124,pointerId:8,bubbles:true}));
                    stage.dispatchEvent(new PointerEvent('pointerup',{button:1,clientX:135,clientY:124,pointerId:8,bubbles:true}));
                    const viewerState = window.EcommerceStudio.state.compareViewer.state();
                    window.EcommerceStudio.state.compareViewer.reset();
                    workspace.classList.add('hidden');
                    const modelPanel = document.getElementById('advancedSettings');
                    const modelToggle = document.getElementById('modelPanelToggle');
                    const parameterValues = {ratio:'4:5', resolution:'2k', quality:'high', count:'3'};
                    for (const [name, value] of Object.entries(parameterValues)) {
                        const select = document.getElementById(name === 'ratio' ? 'ratioSelect' : `${name}Select`);
                        select.value = value;
                        select.dispatchEvent(new Event('change',{bubbles:true}));
                    }
                    modelToggle.click();
                    const modelPanelCollapsed = modelPanel.classList.contains('collapsed') && modelToggle.getAttribute('aria-expanded') === 'false';
                    modelToggle.click();
                    document.querySelector('[data-operation="universal"]').click();
                    const dock = document.getElementById('universalDock').getBoundingClientRect();
                    const dockStyle = getComputedStyle(document.getElementById('universalDock'));
                    const generate = document.getElementById('generateButton').getBoundingClientRect();
                    const add = document.getElementById('addUniversalReference').getBoundingClientRect();
                    const slots = document.getElementById('inputSlots').getBoundingClientRect();
                    const universalCards = [...document.querySelectorAll('.ec-universal-reference')];
                    const firstSix = universalCards.slice(0, 6).map(card => card.getBoundingClientRect());
                    const firstSixTop = firstSix.map(rect => Math.round(rect.top));
                    const firstSixOneRow = new Set(firstSixTop).size === 1;
                    const firstSixVisible = firstSix.length === 6 && firstSix.every(rect => rect.left >= slots.left - 1 && rect.right <= slots.right + 1);
                    document.getElementById('addUniversalReference').click();
                    const cardsAfterAdd = [...document.querySelectorAll('.ec-universal-reference')];
                    const rowsAfterAdd = new Set(cardsAfterAdd.map(card => Math.round(card.getBoundingClientRect().top))).size;
                    cardsAfterAdd.at(-1)?.querySelector('[data-remove-reference]')?.click();
                    document.getElementById('emptyResult').classList.add('hidden');
                    workspace.classList.remove('hidden');
                    const pixel = 'data:image/gif;base64,R0lGODlhAQABAAAAACw=';
                    const posePixel = 'data:image/gif;base64,R0lGODlhAQABAIAAAP8AAP///ywAAAAAAQABAAACAUwAOw==';
                    const generatedPixel = 'data:image/gif;base64,R0lGODlhAQABAIAAAAD/AP///ywAAAAAAQABAAACAUwAOw==';
                    const comparison = window.EcommerceStudio.syncComparisonReference({
                        inputs:[
                            {role:'subject',reference_type:'subject',url:pixel},
                            {role:'pose',reference_type:'pose',url:posePixel},
                        ],
                        comparison_reference_url:posePixel,
                    });
                    const poseComparison = {
                        returnedPose:Boolean(comparison?.isPose),
                        returnedUrl:comparison?.url || '',
                        imageUrl:document.getElementById('beforeImage').getAttribute('src') || '',
                        label:document.getElementById('compareBeforeLabel').textContent.trim(),
                        ariaLabel:document.getElementById('compareHandle').getAttribute('aria-label') || '',
                    };
                    window.EcommerceStudio.renderTaskResult({
                        id:'visual-background-smoke',
                        operation:'universal',
                        status:'succeeded',
                        inputs:[{role:'pose',reference_type:'pose',url:posePixel}],
                        result:{images:[generatedPixel],image_items:[],provider_id:'shiying',model:'gemini-3-pro-image-preview'},
                    });
                    const unifiedGeneratedBackdrop = document.getElementById('beforeBackdrop').getAttribute('src') === generatedPixel
                        && document.getElementById('afterBackdrop').getAttribute('src') === generatedPixel
                        && document.getElementById('beforeImage').getAttribute('src') === posePixel;
                    const beforeBackdropStyle = getComputedStyle(document.getElementById('beforeBackdrop'));
                    const afterBackdropStyle = getComputedStyle(document.getElementById('afterBackdrop'));
                    const foregroundLayersTransparent = [
                        document.getElementById('beforeImage'),
                        document.getElementById('afterClip'),
                    ].every(layer=>getComputedStyle(layer).backgroundColor === 'rgba(0, 0, 0, 0)');
                    const backdropStylesMatch = beforeBackdropStyle.filter === afterBackdropStyle.filter
                        && beforeBackdropStyle.objectFit === afterBackdropStyle.objectFit
                        && beforeBackdropStyle.objectPosition === afterBackdropStyle.objectPosition;
                    document.getElementById('beforeImage').src = pixel;
                    document.getElementById('beforeBackdrop').src = pixel;
                    document.getElementById('afterImage').src = pixel;
                    document.getElementById('afterBackdrop').src = pixel;
                    document.getElementById('resultMeta').innerHTML = '<span>平台 <strong>shiying</strong></span><span>模型 <strong>gemini-3-pro-image-preview</strong></span>';
                    document.getElementById('candidateList').innerHTML = '<button class="ec-candidate active" type="button"><img src="'+pixel+'" alt="结果 1"><span>1</span></button><button class="ec-candidate" type="button"><img src="'+pixel+'" alt="结果 2"><span>2</span></button>';
                    const resultFrameRect = document.querySelector('.ec-result-frame').getBoundingClientRect();
                    const resultMetaRect = document.getElementById('resultMeta').getBoundingClientRect();
                    const resultStageRect = document.getElementById('compareStage').getBoundingClientRect();
                    const resultCandidatesRect = document.getElementById('candidateList').getBoundingClientRect();
                    const resultFooter = document.querySelector('.ec-result-footer');
                    const backdropFilter = getComputedStyle(document.getElementById('beforeBackdrop')).filter;
                    const backdropBrightness = Number(backdropFilter.match(/brightness\\(([\d.]+)\\)/)?.[1] || 1);
                    const backdropBlur = Number(backdropFilter.match(/blur\\(([\d.]+)px\\)/)?.[1] || 0);
                    const resultFrame = {
                        width:Math.round(resultFrameRect.width),
                        height:Math.round(resultFrameRect.height),
                        stageRatioDelta:Math.abs(resultStageRect.width / resultStageRect.height - 16 / 9),
                        wideStage:resultStageRect.width > resultStageRect.height,
                        backdropCount:document.querySelectorAll('.ec-compare-backdrop').length,
                        backdropBlurred:backdropFilter.includes('blur'),
                        backdropBrightness,
                        backdropBlur,
                        unifiedGeneratedBackdrop,
                        foregroundLayersTransparent,
                        backdropStylesMatch,
                        metaOverlaysImage:resultMetaRect.left >= resultStageRect.left && resultMetaRect.right <= resultStageRect.right && resultMetaRect.top >= resultStageRect.top,
                        candidatesOverlayImage:resultCandidatesRect.left >= resultStageRect.left && resultCandidatesRect.right <= resultStageRect.right && resultCandidatesRect.bottom <= resultStageRect.bottom,
                        candidatesInsideFrame:resultCandidatesRect.left >= resultFrameRect.left && resultCandidatesRect.right <= resultFrameRect.right && resultCandidatesRect.top >= resultFrameRect.top && resultCandidatesRect.bottom <= resultFrameRect.bottom,
                        candidateCount:document.querySelectorAll('#candidateList .ec-candidate').length,
                        removedActions:['downloadPreview','qualityReview','exportFinal','saveAsset'].every(id=>!document.getElementById(id)) && !resultFooter?.querySelector('.ec-result-actions'),
                    };
                    return {
                        title: document.querySelector('h1')?.textContent.trim(),
                        routingStatusRemoved:!document.getElementById('capabilityStatus') && !document.getElementById('routeSummary'),
                        operations: tabs.length,
                        tabOrder,
                        operationSlots,
                        mode: window.EcommerceStudio.state.mode,
                        keyboardValue,
                        pointerValue,
                        providers: window.EcommerceStudio.state.capabilities?.providers?.length || 0,
                        providerIds: (window.EcommerceStudio.state.capabilities?.providers || []).map(item => item.id),
                        selectedProvider: document.getElementById('providerSelect')?.value,
                        models: window.EcommerceStudio.state.capabilities?.models?.length || 0,
                        selectedModels: [...document.getElementById('modelSelect').options].map(item => item.value),
                        autoModelLabel: document.getElementById('modelSelect')?.options?.[0]?.textContent || '',
                        generationParameters: {
                            aspectRatio: window.EcommerceStudio.state.aspectRatio,
                            resolution: window.EcommerceStudio.state.resolution,
                            quality: window.EcommerceStudio.state.quality,
                            count: window.EcommerceStudio.state.count,
                        },
                        ratioOptions: [...document.getElementById('ratioSelect').options].map(item => item.value),
                        modelPanelCollapsed,
                        universalLayout: {
                            presetRoles:universalCards.map(card => card.dataset.referenceRole),
                            cardCountBeforeAdd:universalCards.length,
                            cardCountAfterAdd:cardsAfterAdd.length,
                            firstSixOneRow,
                            firstSixVisible,
                            rowsAfterAdd,
                            activeOperations:tabs.filter(tab => tab.classList.contains('active')).map(tab => tab.dataset.operation),
                            dockVisible:dock.width > 0 && dock.height > 0,
                            dockFixed:dockStyle.position === 'fixed',
                            dockCentered:Math.abs((dock.left + dock.width / 2) - innerWidth / 2) <= 2,
                            dockAtBottom:dock.bottom <= innerHeight + 1 && dock.top > innerHeight / 2,
                            generateInsideDock:generate.left >= dock.left && generate.right <= dock.right && generate.bottom <= dock.bottom,
                            addInsideDock:add.left >= dock.left && add.right <= dock.right && add.bottom <= dock.bottom,
                            addBesideGenerate:add.right <= generate.left - 6 && Math.abs((add.top + add.height / 2) - (generate.top + generate.height / 2)) <= 2,
                            pageMode:document.getElementById('ecommercePage').classList.contains('is-universal'),
                        },
                        poseComparison,
                        resultFrame,
                        viewerState,
                        hasFullscreen: !!document.getElementById('compareFullscreen'),
                    };
                })()
            """)
            desktop_image = await devtools.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            (output_dir / "ecommerce-desktop.png").write_bytes(base64.b64decode(desktop_image["data"]))
            await devtools.evaluate("""
                (() => {
                    const instruction = document.querySelector('.ec-universal-instruction');
                    instruction.focus();
                    instruction.value = '';
                    instruction.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward'}));
                    return true;
                })()
            """)
            await devtools.call("Input.insertText", {"text": "中文输入正常"})
            await asyncio.sleep(0.1)
            await devtools.evaluate("""
                (() => {
                    const label = document.querySelector('[data-reference-field="label"]');
                    label.scrollIntoView({block:'center',inline:'center'});
                    label.click();
                    label.focus();
                    label.value = '';
                    label.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward'}));
                    if(document.activeElement !== label) throw new Error('reference label did not receive focus');
                    label.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:''}));
                    label.value = '白色连衣裙';
                    label.dispatchEvent(new InputEvent('input',{bubbles:true,data:'白色连衣裙',inputType:'insertCompositionText',isComposing:true}));
                    label.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'白色连衣裙'}));
                    return true;
                })()
            """)
            await asyncio.sleep(0.1)
            chinese_input = await devtools.evaluate("""
                (() => {
                    const instruction = document.querySelector('.ec-universal-instruction');
                    const label = document.querySelector('[data-reference-field="label"]');
                    const firstKey = document.querySelector('[data-reference-field="label"]')?.dataset.referenceKey;
                    return {
                        instructionValue:instruction?.value || '',
                        instructionState:window.EcommerceStudio.state.options.universal.instruction || '',
                        referenceLabelValue:label?.value || '',
                        referenceLabelState:firstKey ? (window.EcommerceStudio.state.inputs[firstKey]?.label || '') : '',
                    };
                })()
            """)
            await devtools.evaluate("""
                (() => {
                    const instruction = document.querySelector('.ec-universal-instruction');
                    instruction.scrollIntoView({block:'center',inline:'center'});
                    instruction.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId:11}));
                    instruction.click();
                    instruction.focus();
                    instruction.value = '';
                    instruction.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward'}));
                    if(document.activeElement !== instruction) throw new Error('universal instruction did not receive focus');
                    return true;
                })()
            """)
            await devtools.call("Input.insertText", {"text": "delayed-focus"})
            await asyncio.sleep(1.0)
            delayed_instruction_input = await devtools.evaluate("""
                (() => {
                    const instruction = document.querySelector('.ec-universal-instruction');
                    const localSnapshot = localStorage.getItem('studio_ecommerce_settings_v2') || '';
                    return {
                        value:instruction?.value || '',
                        stateValue:window.EcommerceStudio.state.options.universal.instruction || '',
                        active:document.activeElement === instruction,
                        localStorageHasValue:localSnapshot.includes('delayed-focus'),
                    };
                })()
            """)
            await devtools.evaluate("""
                (() => {
                    const instruction = document.querySelector('.ec-universal-instruction');
                    instruction.focus();
                    instruction.value = 'rerender-focus';
                    instruction.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:'rerender-focus'}));
                    return document.activeElement === instruction;
                })()
            """)
            await asyncio.sleep(0.4)
            await devtools.evaluate("window.dispatchEvent(new Event('studio-lang-change')); true")
            await asyncio.sleep(0.1)
            rerender_instruction_input = await devtools.evaluate("""
                (() => {
                    const instruction = document.querySelector('.ec-universal-instruction');
                    return {
                        value:instruction?.value || '',
                        stateValue:window.EcommerceStudio.state.options.universal.instruction || '',
                        active:document.activeElement === instruction,
                    };
                })()
            """)
            await devtools.evaluate("document.getElementById('advancedSettings').scrollIntoView({block:'center'}); true")
            await asyncio.sleep(0.15)
            model_panel_image = await devtools.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            (output_dir / "ecommerce-model-panel.png").write_bytes(base64.b64decode(model_panel_image["data"]))

            await devtools.call("Emulation.setDeviceMetricsOverride", {
                "width": 390,
                "height": 844,
                "deviceScaleFactor": 1,
                "mobile": True,
            })
            await asyncio.sleep(0.25)
            mobile_layout = await devtools.evaluate("""
                (() => {
                    const control = document.querySelector('.ec-control-panel').getBoundingClientRect();
                    const result = document.querySelector('.ec-result-panel').getBoundingClientRect();
                    const workspace = getComputedStyle(document.querySelector('.ec-workspace'));
                    const generateStyle=getComputedStyle(document.getElementById('generateActions'));
                    const generate=document.getElementById('generateButton').getBoundingClientRect();
                    const dock=document.getElementById('universalDock').getBoundingClientRect();
                    const dockStyle=getComputedStyle(document.getElementById('universalDock'));
                    const generateInsideDock=generate.left >= dock.left && generate.right <= dock.right && generate.bottom <= dock.bottom;
                    return {
                        columns:workspace.gridTemplateColumns,
                        resultBelowControl:result.top >= control.bottom - 1,
                        viewport:innerWidth,
                        generatePinned:generateStyle.position === 'fixed' || (dockStyle.position === 'fixed' && generateInsideDock),
                        generateVisible:generate.bottom <= innerHeight && generate.top >= 0,
                        dockFixed:dockStyle.position === 'fixed',
                        dockCentered:Math.abs((dock.left + dock.width / 2) - innerWidth / 2) <= 2,
                        generateInsideDock,
                        generateReachable:innerHeight - generate.bottom <= 36,
                    };
                })()
            """)
            mobile_image = await devtools.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            (output_dir / "ecommerce-mobile.png").write_bytes(base64.b64decode(mobile_image["data"]))
            dark_background = await devtools.evaluate("""
                document.documentElement.classList.add('studio-theme-dark');
                getComputedStyle(document.body).backgroundColor;
            """)

            await devtools.call("Emulation.clearDeviceMetricsOverride")
            crop_setup = await devtools.evaluate("""
                (async () => {
                    const studio=window.EcommerceStudio;
                    const firstKey=Object.keys(studio.state.inputs).find(key=>key.startsWith('ref_'));
                    if(!firstKey) throw new Error('universal reference key is missing');
                    const canvas=document.createElement('canvas');
                    canvas.width=120;
                    canvas.height=80;
                    const context=canvas.getContext('2d');
                    context.fillStyle='#ef4444';
                    context.fillRect(0,0,60,80);
                    context.fillStyle='#2563eb';
                    context.fillRect(60,0,60,80);
                    const blob=await new Promise((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('source canvas blob failed')),'image/png'));
                    const file=new File([blob],'reference-crop-source.png',{type:'image/png'});
                    await studio.uploadInput(file,firstKey);
                    const item=studio.state.inputs[firstKey];
                    if(!item?.url) throw new Error('reference upload failed');
                    document.querySelector(`[data-preview-reference="${firstKey}"]`)?.click();
                    const image=document.getElementById('referenceCropImage');
                    if(!image.complete || !image.naturalWidth) await new Promise((resolve,reject)=>{
                        const timer=setTimeout(()=>reject(new Error('reference preview image timeout')),5000);
                        image.addEventListener('load',()=>{clearTimeout(timer);resolve();},{once:true});
                    });
                    document.getElementById('referenceCropMode').click();
                    document.querySelector('[data-crop-ratio="4:5"]').click();
                    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
                    return {
                        firstKey,
                        originalUrl:item.url,
                        dialogOpen:document.getElementById('referencePreview').open,
                        mode:studio.state.referencePreview.mode,
                        ratio:studio.state.referencePreview.ratio,
                        naturalSize:[image.naturalWidth,image.naturalHeight],
                        cropRect:{...studio.state.referencePreview.cropRect},
                    };
                })()
            """)
            crop_image = await devtools.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            (output_dir / "reference-crop.png").write_bytes(base64.b64decode(crop_image["data"]))
            crop_runtime = await devtools.evaluate("""
                (async () => {
                    const studio=window.EcommerceStudio;
                    const firstKey=studio.state.referencePreview.key;
                    const originalUrl=studio.state.inputs[firstKey].url;
                    document.getElementById('applyReferenceCrop').click();
                    const deadline=Date.now()+10000;
                    while((studio.state.inputs[firstKey]?.crop_history?.length || 0)<1 && Date.now()<deadline) await new Promise(resolve=>setTimeout(resolve,50));
                    const item=studio.state.inputs[firstKey];
                    if(!item?.crop_history?.length) throw new Error('crop history was not created');
                    const croppedUrl=item.url;
                    const versionCount=document.querySelectorAll('[data-reference-version]').length;
                    document.querySelector('[data-reference-version="0"]').click();
                    document.getElementById('useReferenceVersion').click();
                    const originalApplied=studio.state.inputs[firstKey].url===originalUrl;
                    document.querySelector('[data-reference-version="1"]').click();
                    document.getElementById('useReferenceVersion').click();
                    const cropApplied=studio.state.inputs[firstKey].url===croppedUrl;
                    document.getElementById('referencePreview').close();
                    while(Object.keys(studio.state.inputs).filter(key=>key.startsWith('ref_')).length>1){
                        const remove=[...document.querySelectorAll('[data-remove-reference]')].find(button=>button.dataset.removeReference!==firstKey);
                        if(!remove) throw new Error('unable to reduce reference slots');
                        remove.click();
                        await new Promise(resolve=>setTimeout(resolve,10));
                    }
                    await studio.state.preferenceWriteChain;
                    return {
                        firstKey,
                        originalUrl,
                        croppedUrl,
                        cropHistory:item.crop_history.map(version=>({...version})),
                        cropSize:[item.width,item.height],
                        versionCount,
                        originalApplied,
                        cropApplied,
                        referenceCount:Object.keys(studio.state.inputs).filter(key=>key.startsWith('ref_')).length,
                    };
                })()
            """)
            await devtools.call("Page.navigate", {"url": f"http://127.0.0.1:{args.port}/static/ecommerce.html"})
            await wait_for_page(devtools, "document.readyState === 'complete' && !!window.EcommerceStudio?.state?.capabilities")
            await wait_for_page(devtools, "Object.keys(window.EcommerceStudio.state.inputs).filter(key=>key.startsWith('ref_')).length === 1")
            crop_persistence = await devtools.evaluate("""
                (() => {
                    const studio=window.EcommerceStudio;
                    const keys=Object.keys(studio.state.inputs).filter(key=>key.startsWith('ref_'));
                    const item=studio.state.inputs[keys[0]];
                    document.querySelector(`[data-preview-reference="${keys[0]}"]`)?.click();
                    const result={
                        referenceCount:keys.length,
                        url:item?.url || '',
                        originalUrl:item?.original_url || '',
                        cropHistoryCount:item?.crop_history?.length || 0,
                        versionCount:document.querySelectorAll('[data-reference-version]').length,
                        dialogOpen:document.getElementById('referencePreview').open,
                        generationParameters:{
                            aspectRatio:studio.state.aspectRatio,
                            resolution:studio.state.resolution,
                            quality:studio.state.quality,
                            count:studio.state.count,
                        },
                    };
                    document.getElementById('referencePreview').close();
                    return result;
                })()
            """)
            await devtools.call("Page.navigate", {"url": f"http://127.0.0.1:{args.port}/static/works.html"})
            await wait_for_page(devtools, "document.readyState === 'complete' && !!window.WorksManager && !!window.WorksManager.state.compareViewer")
            works_runtime = await devtools.evaluate("""
                (() => {
                    const pixel = 'data:image/gif;base64,R0lGODlhAQABAAAAACw=';
                    const work = {
                        id:'browser-smoke-work', name:'浏览器验证作品', kind:'ecommerce', operation:'universal',
                        url:pixel, source_url:pixel, favorite:false, prompt:'验证作品管理共享划像组件',
                        model:'gemini-3-pro-image-preview', created_at:1, width:2048, height:2048
                    };
                    window.WorksManager.state.works = [work];
                    window.WorksManager.openCompare(work.id);
                    const viewer = window.WorksManager.state.compareViewer;
                    viewer.setZoom(2);
                    const stage = document.getElementById('worksCompareStage');
                    stage.dispatchEvent(new PointerEvent('pointerdown',{button:1,clientX:90,clientY:80,pointerId:18,bubbles:true}));
                    stage.dispatchEvent(new PointerEvent('pointermove',{button:1,clientX:122,clientY:101,pointerId:18,bubbles:true}));
                    stage.dispatchEvent(new PointerEvent('pointerup',{button:1,clientX:122,clientY:101,pointerId:18,bubbles:true}));
                    return {
                        title:document.querySelector('h1')?.textContent.trim(),
                        tabs:[...document.querySelectorAll('#worksTabs [data-tab]')].map(item=>item.dataset.tab),
                        emptyCount:document.getElementById('worksCount')?.textContent,
                        dialogOpen:document.getElementById('worksCompareDialog')?.open,
                        favoriteButton:!!document.getElementById('compareFavorite'),
                        fullscreenButton:!!document.getElementById('worksFullscreen'),
                        viewerState:viewer.state(),
                    };
                })()
            """)
            await asyncio.sleep(0.15)
            works_image = await devtools.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            (output_dir / "works-comparison.png").write_bytes(base64.b64decode(works_image["data"]))

            await devtools.call("Page.navigate", {"url": f"http://127.0.0.1:{args.port}/static/ecommerce.html"})
            await wait_for_page(devtools, "document.readyState === 'complete' && !!window.EcommerceStudio?.state?.capabilities && !!document.getElementById('universalDock')")
            drag_drop_setup = await devtools.evaluate("""
                (async () => {
                    document.querySelector('[data-operation="universal"]')?.click();
                    await new Promise(resolve=>setTimeout(resolve,100));
                    const state = window.EcommerceStudio.state;
                    Object.entries(state.inputs).forEach(([key,item]) => {
                        if(key.startsWith('ref_') && !item?.url) delete state.inputs[key];
                    });
                    window.EcommerceStudio.renderInputs();
                    document.getElementById('addUniversalReference')?.click();
                    await new Promise(resolve=>setTimeout(resolve,50));
                    const beforeKeys = Object.entries(state.inputs).filter(([,item])=>item?.url).map(([key])=>key);
                    const beforeReferenceCount = Object.keys(state.inputs).filter(key=>key.startsWith('ref_')).length;
                    const bytes = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP8zwACTGCSAQANHQEDgslx/wAAAABJRU5ErkJggg=='), char=>char.charCodeAt(0));
                    const transfer = new DataTransfer();
                    transfer.items.add(new File([bytes], 'direct-drop-1.png', {type:'image/png'}));
                    transfer.items.add(new File([bytes], 'direct-drop-2.png'));
                    const dock = document.getElementById('universalDock');
                    const dropTarget = [...dock.querySelectorAll('.ec-upload-slot')].find(slot=>!state.inputs[slot.dataset.role]?.url);
                    if(!dropTarget) throw new Error('no empty universal reference slot for direct drop smoke');
                    dropTarget.dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true,dataTransfer:transfer}));
                    const highlighted = dock.classList.contains('is-file-dragover');
                    const slotHighlighted = dropTarget.classList.contains('dragover');
                    const overlayHidden = getComputedStyle(dock,'::after').content === 'none';
                    const exactTargetKey = dropTarget.dataset.role;
                    dropTarget.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
                    const highlightClearedAfterSlotDrop = !dock.classList.contains('is-file-dragover');
                    return {
                        beforeKeys,
                        beforeCount:beforeKeys.length,
                        beforeReferenceCount,
                        highlighted,
                        slotHighlighted,
                        overlayHidden,
                        exactTargetKey,
                        highlightClearedAfterSlotDrop,
                    };
                })()
            """)
            await wait_for_page(devtools, f"Object.values(window.EcommerceStudio.state.inputs).filter(item=>item?.url).length >= {drag_drop_setup['beforeCount'] + 2}")
            drag_drop_runtime = await devtools.evaluate(f"""
                (() => {{
                    const state = window.EcommerceStudio.state;
                    const before = new Set({json.dumps(drag_drop_setup['beforeKeys'])});
                    const uploadedKeys = Object.entries(state.inputs).filter(([key,item])=>item?.url && !before.has(key)).map(([key])=>key);
                    const select = document.querySelector(`[data-reference-type="${{uploadedKeys[0]}}"]`);
                    select.value = 'pose';
                    select.dispatchEvent(new Event('change',{{bubbles:true}}));
                    return {{
                        uploadedCount:uploadedKeys.length,
                        uploadedKeys,
                        urls:uploadedKeys.map(key=>state.inputs[key]?.url || ''),
                        manualRole:state.inputs[uploadedKeys[0]]?.reference_type || '',
                        exactTargetKey:{json.dumps(drag_drop_setup['exactTargetKey'])},
                        exactTargetName:state.inputs[{json.dumps(drag_drop_setup['exactTargetKey'])}]?.name || '',
                        referenceCount:Object.keys(state.inputs).filter(key=>key.startsWith('ref_')).length,
                        dropHighlightCleared:!document.getElementById('universalDock').classList.contains('is-file-dragover'),
                    }};
                }})()
            """)
            blank_drop_setup = await devtools.evaluate("""
                (async () => {
                    const studio=window.EcommerceStudio;
                    document.getElementById('addUniversalReference')?.click();
                    document.getElementById('addUniversalReference')?.click();
                    await new Promise(resolve=>setTimeout(resolve,50));
                    const state=studio.state;
                    const emptySlots=[...document.querySelectorAll('.ec-upload-slot')].filter(slot=>!state.inputs[slot.dataset.role]?.url);
                    if(emptySlots.length<2) throw new Error('not enough empty slots for blank-area drop smoke');
                    const otherKey=emptySlots[0].dataset.role;
                    const nearestKey=emptySlots[1].dataset.role;
                    const otherRect=emptySlots[0].getBoundingClientRect();
                    const nearestRect=emptySlots[1].getBoundingClientRect();
                    const clientX=Math.max(otherRect.right+1,nearestRect.left-1);
                    const clientY=nearestRect.top+(nearestRect.height/2);
                    const bytes=Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP8zwACTGCSAQANHQEDgslx/wAAAABJRU5ErkJggg=='),char=>char.charCodeAt(0));
                    const transfer=new DataTransfer();
                    transfer.items.add(new File([bytes],'blank-nearest-drop.png',{type:'image/png'}));
                    const blankArea=document.getElementById('inputSlots');
                    const dock=document.getElementById('universalDock');
                    blankArea.dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true,dataTransfer:transfer,clientX,clientY}));
                    const dockHighlighted=dock.classList.contains('is-file-dragover');
                    const overlayHidden=getComputedStyle(dock,'::after').content==='none';
                    blankArea.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer,clientX,clientY}));
                    return {nearestKey,otherKey,dockHighlighted,overlayHidden};
                })()
            """)
            await wait_for_page(devtools, f"window.EcommerceStudio.state.inputs[{json.dumps(blank_drop_setup['nearestKey'])}]?.name === 'blank-nearest-drop.png'")
            blank_drop_runtime = await devtools.evaluate(f"""
                (() => {{
                    const state=window.EcommerceStudio.state;
                    return {{
                        nearestName:state.inputs[{json.dumps(blank_drop_setup['nearestKey'])}]?.name || '',
                        otherStillEmpty:!state.inputs[{json.dumps(blank_drop_setup['otherKey'])}]?.url,
                        dropHighlightCleared:!document.getElementById('universalDock').classList.contains('is-file-dragover'),
                    }};
                }})()
            """)

            await devtools.call("Page.navigate", {"url": f"http://127.0.0.1:{args.port}/static/app-settings.html"})
            await wait_for_page(devtools, "document.readyState === 'complete' && !document.getElementById('closeBehaviorOptions')?.disabled && !!document.querySelector('input[name=closeBehavior]:checked')")
            app_settings_runtime = await devtools.evaluate("""
                (async() => {
                    const choose = value => {
                        const input = document.querySelector(`input[name="closeBehavior"][value="${value}"]`);
                        input.checked = true;
                        input.dispatchEvent(new Event('change',{bubbles:true}));
                    };
                    const waitFor = async value => {
                        const deadline = Date.now() + 4000;
                        while(Date.now() < deadline) {
                            const data = await fetch('/api/app-settings',{cache:'no-store'}).then(response=>response.json());
                            if(data.close_behavior === value && !document.getElementById('closeBehaviorOptions').disabled) return data;
                            await new Promise(resolve=>setTimeout(resolve,60));
                        }
                        throw new Error(`close behavior did not persist: ${value}`);
                    };
                    const initial = document.querySelector('input[name="closeBehavior"]:checked')?.value || '';
                    choose('exit');
                    const exitSaved = await waitFor('exit');
                    location.reload();
                    return {initial, exitSaved:exitSaved.close_behavior};
                })()
            """)
            await wait_for_page(devtools, "document.readyState === 'complete' && !document.getElementById('closeBehaviorOptions')?.disabled && document.querySelector('input[name=closeBehavior]:checked')?.value === 'exit'")
            app_settings_runtime.update(await devtools.evaluate("""
                (async() => {
                    const restored = document.querySelector('input[name="closeBehavior"]:checked')?.value || '';
                    const input = document.querySelector('input[name="closeBehavior"][value="minimize_to_tray"]');
                    input.checked = true;
                    input.dispatchEvent(new Event('change',{bubbles:true}));
                    const deadline = Date.now() + 4000;
                    let saved = '';
                    while(Date.now() < deadline) {
                        const data = await fetch('/api/app-settings',{cache:'no-store'}).then(response=>response.json());
                        saved = data.close_behavior || '';
                        if(saved === 'minimize_to_tray' && !document.getElementById('closeBehaviorOptions').disabled) break;
                        await new Promise(resolve=>setTimeout(resolve,60));
                    }
                    return {
                        restored,
                        finalSaved:saved,
                        optionCount:document.querySelectorAll('input[name="closeBehavior"]').length,
                        title:document.querySelector('h1')?.textContent.trim() || '',
                        outputPathVisible:!!document.getElementById('generatedOutputDir')?.value,
                        chooseOutputVisible:!!document.getElementById('chooseGeneratedOutput'),
                        resetDefaultDisabled:document.getElementById('resetGeneratedOutput')?.disabled === true,
                        outputNaming:document.body.innerText.includes('SHIYIN-000001-YYYYMMDD'),
                    };
                })()
            """))
            app_settings_image = await devtools.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            (output_dir / "app-settings.png").write_bytes(base64.b64decode(app_settings_image["data"]))

            await devtools.call("Page.navigate", {"url": f"http://127.0.0.1:{args.port}/static/api-settings.html"})
            await wait_for_page(devtools, "document.readyState === 'complete' && [...document.querySelectorAll('#providerList .provider-card')].some(item=>item.textContent.includes('VISION'))")
            api_settings_runtime = await devtools.evaluate("""
                (() => {
                    selectProvider('local-vision');
                    const base = document.getElementById('baseInput');
                    base.value = '127.0.0.1:9000';
                    base.dispatchEvent(new Event('blur',{bubbles:true}));
                    const localNormalized = base.value;
                    base.value = 'vision.example.com:8443';
                    base.dispatchEvent(new Event('blur',{bubbles:true}));
                    const domainNormalized = base.value;
                    const imageBlock = document.querySelector('.api-image-model-block');
                    const chatBlock = document.querySelector('.api-chat-model-block');
                    const videoBlock = document.querySelector('.api-video-model-block');
                    const activeCard = [...document.querySelectorAll('#providerList .provider-card')].find(item=>item.classList.contains('active'));
                    return {
                        bodyMode:document.body.classList.contains('show-local-vision'),
                        activeCardText:activeCard?.textContent || '',
                        editorTitle:document.getElementById('editorTitle')?.textContent.trim() || '',
                        modelsTitle:document.getElementById('modelsTitle')?.textContent.trim() || '',
                        chatModelsTitle:document.getElementById('chatModelsTitle')?.textContent.trim() || '',
                        chatModels:[...document.querySelectorAll('#chatModelList input')].map(input=>input.value),
                        localNormalized,
                        domainNormalized,
                        keyConfigured:document.getElementById('keyHint')?.textContent.includes('已保存') || false,
                        imageHidden:getComputedStyle(imageBlock).display === 'none',
                        chatVisible:getComputedStyle(chatBlock).display !== 'none',
                        videoHidden:getComputedStyle(videoBlock).display === 'none',
                        topSaveRemoved:!document.querySelector('.api-page-save-btn'),
                        keyConfirmRemoved:!document.querySelector('.api-standard-key-row .key-btn:not(.key-clear)'),
                    };
                })()
            """)
            await wait_for_page(devtools, "fetch('/api/providers',{cache:'no-store'}).then(r=>r.json()).then(d=>d.providers?.find(item=>item.id==='local-vision')?.base_url === 'https://vision.example.com:8443/v1')")
            api_settings_runtime["autoSaved"] = True
            await asyncio.sleep(0.15)
            api_settings_image = await devtools.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            (output_dir / "api-settings-vision.png").write_bytes(base64.b64decode(api_settings_image["data"]))

            expected_slots = {"try_on": 7, "pose_transfer": 2, "prop_replace": 2, "angle_change": 1, "background_change": 2, "universal": 6}
            expected_order = ["universal", "try_on", "pose_transfer", "prop_replace", "angle_change", "background_change"]
            if main_upload["defaultOperation"] != "universal" or main_upload["defaultActiveOperations"] != ["universal"]:
                raise AssertionError(f"Ecommerce default entry should be universal: {main_upload}")
            if continuous_input_step1 != {"value": "A", "stateValue": "A", "active": True} or continuous_input_step2 != {"value": "AB", "stateValue": "AB", "active": True}:
                raise AssertionError(f"Continuous text input lost focus or state: {continuous_input_step1} / {continuous_input_step2}")
            if not main_upload["operationRestored"] or not main_preference or not main_upload["worksBelowAssets"]:
                raise AssertionError(f"Main-shell upload/persistence/navigation failed: {main_upload}")
            if not re.fullmatch(r"SHIYIN AI V\d+\.\d+\.\d+", main_upload["productIdentity"]) or main_upload["documentTitle"] != main_upload["productIdentity"]:
                raise AssertionError(f"SHIYIN product identity/title failed: {main_upload}")
            if not main_persistence["sourceUrl"] or not main_return["sourceStillPresent"] or main_persistence["generationParameters"] != {"aspectRatio": "4:5", "resolution": "2k", "quality": "high", "count": 3}:
                raise AssertionError(f"Database-backed reload persistence failed: {main_persistence} / {main_return}")
            if main_works["tabs"] != ["all", "favorite", "trash"] or not main_works["freeCompareOpen"] or not main_works["localTargetPicker"] or not main_works["localBasePicker"]:
                raise AssertionError(f"Main-shell works manager failed: {main_works}")
            if main_return["themeMode"] != "system" or main_return["iframeTheme"] != main_return["mainTheme"]:
                raise AssertionError(f"System theme synchronization failed: {main_return}")
            if runtime["operations"] != 6 or runtime["tabOrder"] != expected_order or runtime["operationSlots"] != expected_slots:
                raise AssertionError(f"Operation tabs/slots mismatch: {runtime}")
            if runtime["mode"] != "standard" or runtime["keyboardValue"] != 52 or runtime["pointerValue"] != 25:
                raise AssertionError(f"Mode or comparison controls failed: {runtime}")
            pose_comparison = runtime["poseComparison"]
            if not pose_comparison["returnedPose"] or pose_comparison["returnedUrl"] != pose_comparison["imageUrl"] or pose_comparison["label"] != "姿势参考" or pose_comparison["ariaLabel"] != "姿势参考图与生成图对比":
                raise AssertionError(f"Pose reference was not used as comparison base: {pose_comparison}")
            if not runtime["hasFullscreen"] or runtime["viewerState"]["scale"] != 2 or runtime["viewerState"]["panX"] != 35 or runtime["viewerState"]["panY"] != 24:
                raise AssertionError(f"Fullscreen/zoom/middle-pan comparison failed: {runtime}")
            if runtime["providerIds"] != ["shiying"] or runtime["selectedProvider"] != "shiying":
                raise AssertionError(f"Only configured shiying should be selectable: {runtime}")
            if runtime["models"] < 1 or runtime["providers"] != 1 or "gemini-3-pro-image-preview" not in runtime["selectedModels"]:
                raise AssertionError(f"Capabilities did not load: {runtime}")
            if not runtime["routingStatusRemoved"]:
                raise AssertionError(f"Internal routing status is still visible: {runtime}")
            if "gemini-3-pro-image-preview" not in runtime["autoModelLabel"]:
                raise AssertionError(f"Recommended model label did not refresh: {runtime}")
            if not runtime["modelPanelCollapsed"]:
                raise AssertionError(f"Model panel did not collapse accessibly: {runtime}")
            result_frame = runtime["resultFrame"]
            if result_frame["width"] <= 0 or result_frame["height"] <= 0 or not result_frame["wideStage"] or result_frame["backdropCount"] != 2 or not result_frame["backdropBlurred"] or result_frame["backdropBrightness"] < 0.72 or result_frame["backdropBlur"] > 22 or not result_frame["unifiedGeneratedBackdrop"] or not result_frame["foregroundLayersTransparent"] or not result_frame["backdropStylesMatch"] or result_frame["candidateCount"] != 2 or not result_frame["metaOverlaysImage"] or not result_frame["candidatesInsideFrame"] or not result_frame["removedActions"]:
                raise AssertionError(f"Universal result frame is not wide, layered, or has overlapping bands: {result_frame}")
            universal_layout = runtime["universalLayout"]
            if universal_layout["presetRoles"] != ["subject", "full_garment", "shoes", "accessory", "pose", "scene"] or universal_layout["activeOperations"] != ["universal"] or not all((universal_layout["dockVisible"], universal_layout["dockFixed"], universal_layout["dockCentered"], universal_layout["dockAtBottom"], universal_layout["generateInsideDock"], universal_layout["addInsideDock"], universal_layout["addBesideGenerate"], universal_layout["firstSixOneRow"], universal_layout["firstSixVisible"], universal_layout["pageMode"])) or universal_layout["cardCountBeforeAdd"] != 6 or universal_layout["cardCountAfterAdd"] != 7 or universal_layout["rowsAfterAdd"] != 2:
                raise AssertionError(f"Universal bottom dock layout failed: {runtime}")
            if chinese_input["instructionValue"] != "中文输入正常" or chinese_input["instructionState"] != "中文输入正常" or chinese_input["referenceLabelValue"] != "白色连衣裙" or chinese_input["referenceLabelState"] != "白色连衣裙":
                raise AssertionError(f"Chinese text input failed: {chinese_input}")
            if delayed_instruction_input != {"value": "delayed-focus", "stateValue": "delayed-focus", "active": True, "localStorageHasValue": True}:
                raise AssertionError(f"Universal instruction input lost focus or state after delayed sync: {delayed_instruction_input}")
            if rerender_instruction_input != {"value": "rerender-focus", "stateValue": "rerender-focus", "active": True}:
                raise AssertionError(f"Universal instruction input lost focus after control rerender: {rerender_instruction_input}")
            if runtime["generationParameters"] != {"aspectRatio": "4:5", "resolution": "2k", "quality": "high", "count": 3}:
                raise AssertionError(f"Generation parameters did not update: {runtime}")
            if "4:5" not in runtime["ratioOptions"]:
                raise AssertionError(f"4:5 ratio is missing: {runtime}")
            if mobile_layout["viewport"] != 390 or not mobile_layout["resultBelowControl"] or not mobile_layout["generatePinned"] or not mobile_layout["generateVisible"] or not mobile_layout["dockFixed"] or not mobile_layout["dockCentered"] or not mobile_layout["generateInsideDock"] or not mobile_layout["generateReachable"]:
                raise AssertionError(f"Narrow layout failed: {mobile_layout}")
            if crop_setup["naturalSize"] != [120, 80] or not crop_setup["dialogOpen"] or crop_setup["mode"] != "crop" or crop_setup["ratio"] != "4:5":
                raise AssertionError(f"Reference preview/crop setup failed: {crop_setup}")
            if crop_runtime["versionCount"] != 2 or not crop_runtime["originalApplied"] or not crop_runtime["cropApplied"] or crop_runtime["referenceCount"] != 1:
                raise AssertionError(f"Reference crop/version switching failed: {crop_runtime}")
            if crop_persistence["referenceCount"] != 1 or crop_persistence["url"] != crop_runtime["croppedUrl"] or crop_persistence["originalUrl"] != crop_runtime["originalUrl"] or crop_persistence["cropHistoryCount"] != 1 or crop_persistence["versionCount"] != 2 or not crop_persistence["dialogOpen"]:
                raise AssertionError(f"Reference crop persistence failed: {crop_persistence} / {crop_runtime}")
            if crop_persistence["generationParameters"] != {"aspectRatio": "4:5", "resolution": "2k", "quality": "high", "count": 3}:
                raise AssertionError(f"Generation parameter reload persistence failed: {crop_persistence}")
            if works_runtime["title"] != "作品管理" or works_runtime["tabs"] != ["all", "favorite", "trash"]:
                raise AssertionError(f"Works tabs failed: {works_runtime}")
            if not works_runtime["dialogOpen"] or not works_runtime["favoriteButton"] or not works_runtime["fullscreenButton"]:
                raise AssertionError(f"Works comparison actions failed: {works_runtime}")
            if works_runtime["viewerState"]["scale"] != 2 or works_runtime["viewerState"]["panX"] != 32 or works_runtime["viewerState"]["panY"] != 21:
                raise AssertionError(f"Works zoom/middle-pan failed: {works_runtime}")
            if not drag_drop_setup["highlighted"] or not drag_drop_setup["slotHighlighted"] or not drag_drop_setup["overlayHidden"] or not drag_drop_setup["highlightClearedAfterSlotDrop"]:
                raise AssertionError(f"Universal exact-slot drag feedback failed: {drag_drop_setup}")
            if drag_drop_runtime["uploadedCount"] != 2 or not all(drag_drop_runtime["urls"]) or drag_drop_runtime["manualRole"] != "pose" or drag_drop_runtime["exactTargetName"] != "direct-drop-1.png" or drag_drop_runtime["referenceCount"] <= drag_drop_setup["beforeReferenceCount"] or not drag_drop_runtime["dropHighlightCleared"]:
                raise AssertionError(f"Universal exact-slot drag/drop allocation failed: {drag_drop_setup} / {drag_drop_runtime}")
            if not blank_drop_setup["dockHighlighted"] or not blank_drop_setup["overlayHidden"] or blank_drop_runtime["nearestName"] != "blank-nearest-drop.png" or not blank_drop_runtime["otherStillEmpty"] or not blank_drop_runtime["dropHighlightCleared"]:
                raise AssertionError(f"Universal blank-area nearest-slot drag/drop failed: {blank_drop_setup} / {blank_drop_runtime}")
            if app_settings_runtime != {"initial": "minimize_to_tray", "exitSaved": "exit", "restored": "exit", "finalSaved": "minimize_to_tray", "optionCount": 2, "title": "软件设置", "outputPathVisible": True, "chooseOutputVisible": True, "resetDefaultDisabled": True, "outputNaming": True}:
                raise AssertionError(f"App close behavior settings failed: {app_settings_runtime}")
            if not api_settings_runtime["bodyMode"] or "VISION" not in api_settings_runtime["activeCardText"] or api_settings_runtime["editorTitle"] != "本地视觉模型":
                raise AssertionError(f"Local vision provider did not render: {api_settings_runtime}")
            if api_settings_runtime["modelsTitle"] != "视觉模型配置" or api_settings_runtime["chatModelsTitle"] != "视觉模型" or "qwen3.5-9b-vlm" not in api_settings_runtime["chatModels"]:
                raise AssertionError(f"Local vision model section is incomplete: {api_settings_runtime}")
            if api_settings_runtime["localNormalized"] != "http://127.0.0.1:9000/v1" or api_settings_runtime["domainNormalized"] != "https://vision.example.com:8443/v1":
                raise AssertionError(f"OpenAI-compatible URL completion failed: {api_settings_runtime}")
            if not api_settings_runtime["keyConfigured"] or not api_settings_runtime["imageHidden"] or not api_settings_runtime["chatVisible"] or not api_settings_runtime["videoHidden"] or not api_settings_runtime["topSaveRemoved"] or not api_settings_runtime["keyConfirmRemoved"] or not api_settings_runtime["autoSaved"]:
                raise AssertionError(f"Local vision visibility/key state failed: {api_settings_runtime}")
            if devtools.exceptions:
                raise AssertionError(f"Browser JavaScript exceptions: {devtools.exceptions}")
            return {
                "runtime": runtime,
                "main_upload": main_upload,
                "continuous_input": [continuous_input_step1, continuous_input_step2],
                "main_preference": main_preference,
                "main_persistence": main_persistence,
                "main_works": main_works,
                "main_return": main_return,
                "mobile_layout": mobile_layout,
                "crop_setup": crop_setup,
                "crop_runtime": crop_runtime,
                "crop_persistence": crop_persistence,
                "chinese_input": chinese_input,
                "delayed_instruction_input": delayed_instruction_input,
                "dark_background": dark_background,
                "works_runtime": works_runtime,
                "drag_drop_setup": drag_drop_setup,
                "drag_drop_runtime": drag_drop_runtime,
                "blank_drop_setup": blank_drop_setup,
                "blank_drop_runtime": blank_drop_runtime,
                "app_settings_runtime": app_settings_runtime,
                "api_settings_runtime": api_settings_runtime,
                "javascript_exceptions": devtools.exceptions,
                "screenshots": [
                    str(output_dir / "ecommerce-desktop.png"),
                    str(output_dir / "ecommerce-model-panel.png"),
                    str(output_dir / "ecommerce-mobile.png"),
                    str(output_dir / "reference-crop.png"),
                    str(output_dir / "works-comparison.png"),
                    str(output_dir / "app-settings.png"),
                    str(output_dir / "api-settings-vision.png"),
                ],
                "status": "ok",
            }
    finally:
        browser.terminate()
        try:
            browser.wait(timeout=5)
        except subprocess.TimeoutExpired:
            browser.kill()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--debug-port", type=int, default=9337)
    parser.add_argument("--chrome", default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    parser.add_argument("--result-path", default="")
    args = parser.parse_args()
    serialized = json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2)
    if args.result_path:
        Path(args.result_path).write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
