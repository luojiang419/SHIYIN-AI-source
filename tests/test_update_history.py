import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from tools.update_history import make_record, merge_history, read_history, stage_record, commit_record, write_history

ROOT = Path(__file__).resolve().parents[1]

class UpdateHistoryTests(unittest.TestCase):
    def test_same_version_different_baselines_and_components_are_retained(self):
        a = make_record('baseline', '3.0.0', '首次基线', baseline='20260923090000')
        b = make_record('baseline', '3.0.0', '重建基线', baseline='20260923100000')
        component = {'id':'component:3.0.0','version':'3.0.0','kind':'component','items':[]}
        merged = merge_history({'history':[]}, [a,b,component,a])
        self.assertEqual(len(merged['history']),3)
        self.assertEqual(len(next(x for x in merged['history'] if x['id']==a['id'])['items']),2)

    def test_published_status_cannot_be_downgraded_by_rebuild(self):
        a = make_record('web','20260923100000','修复',status='published')
        b = make_record('web','20260923100000','补充说明')
        result = merge_history({'history':[a]},[b])['history'][0]
        self.assertEqual(result['record_status'],'published')
        self.assertEqual([x['text'] for x in result['items']],['修复','补充说明'])

    def test_staging_does_not_change_source_until_build_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'static/update-history.json'; target=root/'package/update-history.json'
            write_history(source,{'history':[{'version':'1.0.0','items':[]}]})
            record=make_record('web','20260923100000','新功能')
            before=source.read_bytes()
            stage_record(root,target,record)
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual(len(read_history(target)['history']),2)
            commit_record(root,record)
            self.assertEqual(read_history(source),read_history(target))

    def test_corrupt_archive_fails_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/'static/update-history.json'; path.parent.mkdir();path.write_text('{broken')
            with self.assertRaises(ValueError):commit_record(root,make_record('hot','20260923100000','测试'))
            self.assertEqual(path.read_text(),'{broken')

    def test_web_package_manifest_covers_history_and_preserves_old_records(self):
        spec=importlib.util.spec_from_file_location('hot_history_build',ROOT/'tools/build-hot-update.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'static').mkdir();(root/'.build').mkdir()
            (root/'static/index.html').write_text('<html></html>')
            write_history(root/'static/update-history.json',{'history':[{'version':'1.0.0','items':[]}]})
            with patch.object(module,'ROOT',root),patch.object(module,'run'),patch('sys.argv',['build','--web-only','--version','20260923120000','--notes','时间轴验证']):module.main()
            snapshot=root/'dist/hot-update/20260923120000'
            manifest=json.loads((snapshot/'manifest.json').read_text(encoding='utf-8'))
            history=next(x for x in manifest['files'] if x['path']=='app/web/update-history.json')
            self.assertEqual(history['sha256'],module.digest(snapshot/'files'/history['path']))
            with zipfile.ZipFile(snapshot/manifest['package']['name']) as archive:
                packaged=json.loads(archive.read(history['path']))
            self.assertEqual(len(packaged['history']),2)
            self.assertEqual(read_history(root/'static/update-history.json'),packaged)

    def test_installer_stages_baseline_without_old_markdown_history(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for folder in ['src-tauri','release-notes','static']:(root/folder).mkdir()
            (root/'VERSION').write_text('3.0.0',encoding='utf-8')
            (root/'src-tauri/distribution-baseline.txt').write_text('20260923130000',encoding='utf-8')
            (root/'release-notes/current.md').write_text('# v3.0.0\n- 新基线功能\n## 历史版本记录\n- 旧说明',encoding='utf-8')
            write_history(root/'static/update-history.json',{'history':[{'version':'2.0.5','items':[]}]})
            target=root/'stage/update-history.json'
            subprocess.run([sys.executable,str(ROOT/'tools/update_history.py'),'--root',str(root),'--stage',str(target)],check=True)
            history=read_history(target)['history']
            self.assertEqual(len(history),2)
            self.assertEqual(history[0]['kind'],'baseline')
            self.assertIn('新基线功能',str(history[0]))
            self.assertNotIn('旧说明',str(history[0]))
            subprocess.run([sys.executable,str(ROOT/'tools/update_history.py'),'--root',str(root),'--commit-stage',str(target)],check=True)
            self.assertEqual(read_history(root/'static/update-history.json')['history'],history)

    def test_archive_retains_failed_baseline_and_all_event_kinds(self):
        entries=read_history(ROOT/'static/update-history.json')['history']
        self.assertEqual(len({x.get('id') or 'release:'+x['version'] for x in entries}),len(entries))
        self.assertTrue({'baseline','web','hot','component'}.issubset({x.get('kind') for x in entries}))
        failed=next(x for x in entries if x.get('id')=='baseline-attempt:2.0.2')
        self.assertEqual(failed['record_status'],'failed')
        for version in ['2.0.0','2.0.1','2.0.3','2.0.4','2.0.5']:
            self.assertTrue(any(x['version']==version and x.get('kind')=='baseline' for x in entries))

if __name__=='__main__':unittest.main()
