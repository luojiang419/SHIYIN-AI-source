"""只读审计所有账号作品引用；不输出 URL 查询串、提示词或账号凭据。"""
import collections
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

def audit(root):
    scopes = [root, *sorted((root / 'accounts').glob('*'))]
    report = []
    for scope in scopes:
        db = scope / 'database/canvas.db'
        if not db.is_file():
            continue
        connection = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
        rows = connection.execute('SELECT url FROM work_items').fetchall()
        def urls(value):
            if isinstance(value, dict):
                for entry in value.values():
                    yield from urls(entry)
            elif isinstance(value, list):
                for entry in value:
                    yield from urls(entry)
            elif isinstance(value, str) and value.startswith(('http://','https://','/assets/','/output/')) and '\n' not in value:
                yield value
        canvas_urls = set()
        for raw, in connection.execute('SELECT payload_json FROM canvases'):
            canvas_urls.update(urls(json.loads(raw)))
        rows += [(url,) for url in canvas_urls if url not in {row[0] for row in rows}]
        counts = collections.Counter()
        suspicious = []
        for row in rows:
            url = urlsplit(str(row[0] or ''))
            mappings = {'/assets/output/':'media/generated', '/assets/input/':'media/input', '/assets/uploads/':'media/uploads', '/assets/library/':'media/library', '/output/':'exports'}
            local = not url.netloc or url.hostname in {'localhost','127.0.0.1','::1'}
            path = next((scope / directory / unquote(url.path[len(prefix):]) for prefix, directory in mappings.items() if local and url.path.startswith(prefix)), None)
            state = 'local_found' if path and path.is_file() else 'local_missing' if local else 'remote'
            counts[state] += 1
            if state == 'local_missing':
                counts['missing_with_same_basename_in_other_scope'] += any((other / 'media/generated' / Path(url.path).name).is_file() for other in scopes if other != scope)
            ext = Path(unquote(url.path)).suffix.lower()
            if ext in {'.html','.htm','.png_x','.jpg_x','.jpeg_x'}:
                counts['unusual_extension'] += 1
                suspicious.append({'name':Path(unquote(url.path)).name,'host':url.hostname,'state':state})
        connection.close()
        report.append({'scope':str(scope.relative_to(root)), 'counts':dict(counts),'unusual':suspicious[:20]})
    return report

if __name__ == '__main__':
    print(json.dumps(audit(Path(sys.argv[1]).resolve()),ensure_ascii=False,indent=2))
