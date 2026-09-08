import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

import main
from canvas_core.ecommerce import build_prompt
from canvas_core.lookbook_styles import (
    FASHION_EDITORIAL_PROMPT, load_styles, save_styles, shiying_cover_route,
)


ROOT = Path(__file__).resolve().parents[1]


class LookbookStyleStoreTests(unittest.TestCase):
    def test_restart_migration_and_account_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            save_styles(first, [{"id": "fw-cream-cyan-film", "cover": "/assets/new.png"}])
            save_styles(first, [{"id": "fw-cream-cyan-film", "cover": "/assets/stale.png"},
                                {"id": "github-one", "name": "旧技能"}], only_missing=True)
            # 再次从磁盘构造读取，不依赖进程或浏览器缓存。
            self.assertEqual(load_styles(first)[0]["cover"], "/assets/new.png")
            self.assertEqual(len(load_styles(first)), 2)
            self.assertEqual(load_styles(second), [])
            save_styles(second, [{"id": "fw-cream-cyan-film", "cover": "/assets/other.png"}])
            self.assertEqual(load_styles(first)[0]["cover"], "/assets/new.png")

    def test_concurrent_updates_do_not_lose_other_styles(self):
        with tempfile.TemporaryDirectory() as directory:
            with ThreadPoolExecutor(max_workers=6) as executor:
                list(executor.map(lambda i: save_styles(Path(directory), [{"id": f"style-{i}", "cover": f"/assets/{i}.png"}]), range(12)))
            self.assertEqual(len(load_styles(Path(directory))), 12)

    def test_failed_atomic_write_preserves_original_and_corruption_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_styles(root, [{"id": "style", "cover": "/assets/old.png"}])
            with patch("canvas_core.lookbook_styles.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    save_styles(root, [{"id": "style", "cover": "/assets/new.png"}])
            self.assertEqual(load_styles(root)[0]["cover"], "/assets/old.png")
            path = root / "config/lookbook-styles.json"
            path.write_text("broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                save_styles(root, [{"id": "style"}])
            self.assertEqual(path.read_text(), "broken")

    def test_api_save_validation_and_partial_cover_update(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "DATA_DIR", Path(directory)):
            for cover in ("blob:temporary", "data:image/png;base64,aaa", "https://host/a.png", "/assets/../secret"):
                with self.assertRaises(HTTPException) as caught:
                    main.put_lookbook_styles(main.LookbookStylesSaveRequest(styles=[{"id": "one", "cover": cover}]))
                self.assertEqual(caught.exception.status_code, 400)
            main.put_lookbook_styles(main.LookbookStylesSaveRequest(styles=[{"id": "github-one", "name": "风格", "source": "github", "prompt": "direction"}]))
            main.put_lookbook_styles(main.LookbookStylesSaveRequest(styles=[{"id": "github-one", "cover": "/assets/upload.png"}]))
            result = main.get_lookbook_styles()
            self.assertEqual(result["styles"][0]["prompt"], "direction")
            self.assertEqual(result["styles"][0]["cover"], "/assets/upload.png")
            self.assertEqual(result["builtin_styles"][0]["name"], "时尚广告")


class LookbookCoverRouteTests(unittest.TestCase):
    def test_route_is_shiying_image_model_and_never_chat_model(self):
        providers = [{"id": "ecommerce-vision", "chat_models": ["vision-chat"]},
                     {"id": "shiying", "image_models": ["image-other", "gemini-3-pro-image-preview"], "chat_models": ["wrong-chat"]}]
        self.assertEqual(shiying_cover_route(providers), {"provider_id": "shiying", "model": "gemini-3-pro-image-preview"})
        for values in ([], [{"id": "shiying", "enabled": False, "image_models": ["image"]}], [{"id": "shiying", "chat_models": ["chat"]}]):
            with self.assertRaises(ValueError):
                shiying_cover_route(values)

    def test_cover_api_executes_image_route_and_handles_empty_result(self):
        providers = [{"id": "shiying", "image_models": ["gemini-3-pro-image-preview"]}]
        generation = AsyncMock(return_value={"image_items": [{"url": "/assets/generated/cover.png"}]})
        with patch.object(main, "configured_ecommerce_providers", return_value=providers), patch.object(main, "execute_ai_image_batch", generation):
            result = asyncio.run(main.generate_lookbook_skill_cover(main.LookbookSkillCoverRequest(prompt="monochrome fashion")))
            self.assertEqual(result["provider_id"], "shiying")
            self.assertEqual(generation.call_args.kwargs["count"], 1)
            self.assertEqual(generation.call_args.kwargs["model"], "gemini-3-pro-image-preview")
            generation.return_value = {}
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.generate_lookbook_skill_cover(main.LookbookSkillCoverRequest(prompt="fashion")))
            self.assertEqual(caught.exception.status_code, 502)

    def test_fashion_skill_is_applied_without_frontend_prompt(self):
        prompt = build_prompt("universal", [], {"prompt_policy": "lookbook", "lookbook_style": {"id": "fashion-advertising"}, "lookbook_mode": "story-campaign", "lookbook_count": 6})
        self.assertIn(FASHION_EDITORIAL_PROMPT, prompt)
        for phrase in ("REFERENCE ROUTER", "ENVIRONMENT ENGINE", "EVENT AND CONTINUITY LEDGER", "20-28mm", "the grid serves the frame"):
            self.assertIn(phrase.lower(), prompt.lower())
        self.assertNotIn("CAMERA BEHAVIOR: favor a lightly handheld", prompt)
        self.assertNotIn("NATURAL SUNLIGHT AND SOFT-FILM LOCK:", prompt)
        self.assertNotIn("MATERIAL PORTRAIT LIGHT LOCK:", prompt)
        self.assertNotIn("AUTO LOOKBOOK MODE", prompt)


class LookbookStyleFrontendRuntimeTests(unittest.TestCase):
    def test_cache_migration_restart_default_cover_and_failed_save(self):
        script = r"""
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const source=fs.readFileSync('static/js/canvas-lookbook-node.js','utf8').replace('window.CanvasLookbookNode={','window.CanvasLookbookNode={styles,loadStyles,saveStored,');
let disk=[{id:'standard-advertising',cover:'/assets/server.png'}],failSave=false;
function boot(legacy){
  let cache=legacy?JSON.stringify(legacy):null;
  const c={window:{},document:{addEventListener:()=>{}},localStorage:{getItem:()=>cache,removeItem:()=>{cache=null;}}};
  c.fetch=async(url,opts)=>{
    if(opts?.method==='PUT'){
      if(failSave)return {ok:false,json:async()=>({detail:'磁盘空间不足'})};
      const body=JSON.parse(opts.body);
      for(const item of body.styles){const old=disk.find(x=>x.id===item.id);if(!old)disk.push(item);else if(!body.only_missing)Object.assign(old,item);}
    }
    return {ok:true,json:async()=>({styles:JSON.parse(JSON.stringify(disk)),builtin_styles:[]})};
  };
  vm.runInNewContext(source,c);return c.window.CanvasLookbookNode;
}
(async()=>{
  let ui=boot([{id:'fw-cream-cyan-film',cover:'/assets/upload.png',prompt:'stale builtin prompt'},{id:'standard-advertising',cover:'/assets/old-browser.png'}]);
  await Promise.all([ui.loadStyles(),ui.loadStyles()]);
  assert.equal(ui.styles().find(x=>x.id==='standard-advertising').cover,'/assets/server.png');
  assert.equal(ui.styles().find(x=>x.id==='fw-cream-cyan-film').cover,'/assets/upload.png');
  assert.notEqual(ui.styles().find(x=>x.id==='fw-cream-cyan-film').prompt,'stale builtin prompt');
  await ui.saveStored([{id:'fashion-advertising',cover:'/assets/manual.png'}]);
  ui=boot();await ui.loadStyles();
  assert.equal(ui.styles().find(x=>x.id==='fashion-advertising').cover,'/assets/manual.png');
  assert.equal(ui.styles().find(x=>x.id==='levis-black-white').cover,'/static/img/lookbook-covers/levis-black-white.webp');
  const node=ui.createNode({});node.lookbookStyleId='fashion-advertising';ui.normalize(node);
  assert.equal(node.lookbookStyleCover,'/assets/manual.png');
  failSave=true;
  await assert.rejects(ui.saveStored([{id:'fashion-advertising',cover:'/assets/failed.png'}]),/磁盘空间不足/);
  assert.equal(ui.styles().find(x=>x.id==='fashion-advertising').cover,'/assets/manual.png');
})().catch(e=>{console.error(e);process.exit(1)});
"""
        subprocess.run(["node", "-e", script], cwd=ROOT, check=True, capture_output=True, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
