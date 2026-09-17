from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import sqlite3
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
from distribution.desktop_settings import startup_enabled, set_startup
from distribution.traffic import Traffic

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = Path(os.environ.get('SHIYIN_DISTRIBUTION_DATA', 'D:/SHIYIN-Distribution'))
ALLOWED_ROOTS = ('app/web', 'app/backend/canvas-backend', 'app/skills')
MAX_SERVICE_LOGS = 1000


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + secrets.token_hex(6) + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    os.replace(temp, path)


def local_ip():
    # UDP connect 只查询路由，不发送数据；优先办公网，避免 VPN 默认路由。
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(('192.168.0.1', 9))
            return probe.getsockname()[0]
        except OSError:
            return socket.gethostbyname(socket.gethostname())


def relative_path(value, hot=False):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('文件路径无效')
    parts = value.split('/')
    if any(p in ('', '.', '..') or p.endswith(('.', ' ')) for p in parts):
        raise ValueError('文件路径越界')
    if hot and value != 'SHIYIN AI.exe' and not any(value.startswith(p + '/') for p in ALLOWED_ROOTS):
        raise ValueError('热更新只能包含应用文件')
    return Path(*parts)


class Center:
    def __init__(self, data, port=3011, admin_port=3013):
        self.data = Path(data).resolve()
        self.data.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.config_path = self.data / 'settings.json'
        self.config = {'port': port, 'auto_start': True, 'address': local_ip(), 'theme': 'system',
                       'background_on_close': True, 'launch_at_login': startup_enabled(), 'start_hidden': True}
        if self.config_path.exists():
            self.config.update(json.loads(self.config_path.read_text('utf-8')))
        self.admin_port = admin_port
        self.server = None
        self.discovery = None
        self.zeroconf = None
        self.job = {'running': False, 'message': '', 'error': ''}
        self.started = time.time()
        self.desktop_action = {'sequence': 0, 'action': ''}
        self.bug_upload_times = {}
        token_path = self.data / 'admin-token'
        if not token_path.exists():
            token_path.write_text(secrets.token_urlsafe(36), 'ascii')
        self.token = token_path.read_text('ascii')
        key_path = self.data / 'signing-key'
        if not key_path.exists():
            key = Ed25519PrivateKey.generate()
            key_path.write_bytes(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
        self.key = Ed25519PrivateKey.from_private_bytes(key_path.read_bytes())
        self.public_key = self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS releases (id TEXT PRIMARY KEY, kind TEXT, version TEXT,
                    manifest TEXT, state TEXT, created REAL);
                CREATE TABLE IF NOT EXISTS clients (ip TEXT PRIMARY KEY, seen REAL, version TEXT);
                CREATE TABLE IF NOT EXISTS logs (created REAL, message TEXT);
                CREATE TABLE IF NOT EXISTS bug_reports (id TEXT PRIMARY KEY, created REAL, client_id TEXT,
                    ip TEXT, kind TEXT, summary TEXT, file TEXT, user_id TEXT);
                CREATE TABLE IF NOT EXISTS bug_devices (user_id TEXT, client_id TEXT, updated REAL,
                    ip TEXT, file TEXT, PRIMARY KEY(user_id,client_id));
            ''')
            if 'user_id' not in [row['name'] for row in db.execute('PRAGMA table_info(bug_reports)')]:
                db.execute('ALTER TABLE bug_reports ADD COLUMN user_id TEXT')
            device_columns = {row['name'] for row in db.execute('PRAGMA table_info(bug_devices)')}
            for column in ('computer_user', 'computer_name'):
                if column not in device_columns:
                    db.execute(f"ALTER TABLE bug_devices ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
            # Keep the service log bounded so long-running installations cannot
            # exhaust disk space. This also trims logs accumulated by older builds.
            db.execute('DELETE FROM logs WHERE rowid NOT IN '
                       '(SELECT rowid FROM logs ORDER BY created DESC, rowid DESC LIMIT ?)',
                       (MAX_SERVICE_LOGS,))
        self.traffic = Traffic(self.db)
        self.blob_labels = None

    def touch_client(self, ip, version=''):
        with self.db() as db:
            db.execute('''INSERT INTO clients VALUES (?,?,?) ON CONFLICT(ip) DO UPDATE SET
                seen=excluded.seen, version=CASE WHEN excluded.version!='' THEN excluded.version ELSE clients.version END''',
                (ip, time.time(), version[:80]))

    def blob_label(self, sha):
        with self.lock:
            if self.blob_labels is None:
                labels = {}
                with self.db() as db:
                    releases = db.execute('SELECT kind,version,manifest FROM releases ORDER BY created').fetchall()
                for release in releases:
                    manifest = json.loads(json.loads(release['manifest'])['payload'])
                    for item in manifest['files']:
                        labels[item['sha256']] = f"{release['kind']} · {release['version']} · {item['path']}"
                    package = manifest.get('package')
                    if package:
                        labels[package['sha256']] = f"{release['kind']} · {release['version']} · {package['name']}"
                self.blob_labels = labels
            return self.blob_labels.get(sha, sha)

    def db(self):
        conn = sqlite3.connect(self.data / 'index.db', timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def log(self, message):
        with self.db() as db:
            db.execute('INSERT INTO logs VALUES (?, ?)', (time.time(), str(message)))
            db.execute('DELETE FROM logs WHERE rowid NOT IN '
                       '(SELECT rowid FROM logs ORDER BY created DESC, rowid DESC LIMIT ?)',
                       (MAX_SERVICE_LOGS,))

    def receive_bug_report(self, body, ip):
        if not isinstance(body, dict):
            raise ValueError('日志格式无效')
        client_id = str(body.get('clientId') or '').strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', client_id):
            raise ValueError('客户端标识无效')
        user_id = str(body.get('userId') or 'admin').strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', user_id):
            raise ValueError('账号标识无效')
        kind = str(body.get('kind') or '')
        if kind not in ('heartbeat', 'error', 'runtime'):
            raise ValueError('日志类型无效')
        with self.lock:
            now = time.time()
            recent = [stamp for stamp in self.bug_upload_times.get(ip, []) if now - stamp < 60]
            if len(recent) >= 120:
                raise ValueError('日志发送过于频繁')
            recent.append(now)
            self.bug_upload_times[ip] = recent
        summary = str(body.get('summary') or '')[:240]
        report_id = f"{time.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(6)}"
        folder = self.data / 'bug-logs' / user_id / client_id
        folder.mkdir(parents=True, exist_ok=True)
        report = {'id': report_id, 'receivedAt': time.time(), 'ip': ip,
                  'clientId': client_id, 'userId': user_id, 'kind': kind, 'summary': summary,
                  'version': str(body.get('version') or '')[:80],
                  'details': body.get('details')}
        machine = body.get('machine')
        if machine is not None:
            if not isinstance(machine, dict) or len(json.dumps(machine, ensure_ascii=False)) > 40000:
                raise ValueError('设备信息格式无效或过大')
        def identity_text(key):
            value = body.get(key)
            return ''.join(c for c in value.strip() if c.isprintable())[:128] if isinstance(value, str) else ''
        computer_user, computer_name = identity_text('computerUser'), identity_text('computerName')
        device_file = folder / 'device.json'
        with self.lock:
            previous = json.loads(device_file.read_text('utf-8')) if device_file.exists() else {}
            atomic_json(device_file, {'userId': user_id, 'clientId': client_id,
                'computerUser': computer_user or previous.get('computerUser', ''),
                'computerName': computer_name or previous.get('computerName', ''),
                'ip': ip, 'updatedAt': report['receivedAt'],
                'machine': machine if machine is not None else previous.get('machine', {})})
            with self.db() as db:
                db.execute('INSERT INTO bug_devices (user_id,client_id,updated,ip,file,computer_user,computer_name) '
                    'VALUES (?,?,?,?,?,?,?) ON CONFLICT(user_id,client_id) '
                    'DO UPDATE SET updated=excluded.updated,ip=excluded.ip,file=excluded.file,'
                    "computer_user=CASE WHEN excluded.computer_user!='' THEN excluded.computer_user ELSE bug_devices.computer_user END,"
                    "computer_name=CASE WHEN excluded.computer_name!='' THEN excluded.computer_name ELSE bug_devices.computer_name END",
                    (user_id, client_id, report['receivedAt'], ip, str(device_file), computer_user, computer_name))
        file = folder / f'{report_id}.json'
        atomic_json(file, report)
        with self.db() as db:
            db.execute('INSERT INTO bug_reports VALUES (?,?,?,?,?,?,?,?)',
                       (report_id, report['receivedAt'], client_id, ip, kind, summary, str(file), user_id))
        self.touch_client(ip, report['version'])
        return {'id': report_id}

    def bug_reports(self, client_id='', limit=100):
        with self.db() as db:
            if client_id:
                rows = db.execute('SELECT id,created,client_id,ip,kind,summary,user_id FROM bug_reports '
                                  'WHERE client_id=? ORDER BY created DESC LIMIT ?', (client_id, limit))
            else:
                rows = db.execute('SELECT id,created,client_id,ip,kind,summary,user_id FROM bug_reports '
                                  'ORDER BY created DESC LIMIT ?', (limit,))
            return [dict(row) for row in rows]

    def bug_report(self, report_id):
        with self.db() as db:
            row = db.execute('SELECT file FROM bug_reports WHERE id=?', (report_id,)).fetchone()
        if not row:
            raise ValueError('日志不存在')
        return json.loads(Path(row['file']).read_text('utf-8'))

    def bug_devices(self):
        with self.db() as db:
            return [dict(row) for row in db.execute('SELECT user_id,client_id,updated,ip,computer_user,computer_name '
                'FROM bug_devices ORDER BY updated DESC')]

    def bug_device(self, user_id, client_id):
        with self.db() as db:
            row = db.execute('SELECT file FROM bug_devices WHERE user_id=? AND client_id=?',
                             (user_id, client_id)).fetchone()
        if not row:
            raise ValueError('设备信息不存在')
        return json.loads(Path(row['file']).read_text('utf-8'))

    def start(self):
        with self.lock:
            if self.server:
                return
            server = ThreadingHTTPServer(('0.0.0.0', int(self.config['port'])), self.handler(False))
            server.daemon_threads = True
            self.server = server
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.advertise()
            self.log('分发服务启动：' + self.url)

    @property
    def url(self):
        return f"http://{self.config['address']}:{self.config['port']}"

    def stop(self):
        with self.lock:
            server, self.server = self.server, None
            if self.discovery:
                self.discovery.close()
                self.discovery = None
            if self.zeroconf:
                self.zeroconf.close()
                self.zeroconf = None
            if server:
                server.shutdown()
                server.server_close()
                self.log('分发服务已停止')
            self.traffic.flush()

    def advertise(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('0.0.0.0', 3012))
            sock.settimeout(1)
            self.discovery = sock
            def respond():
                while self.discovery is sock:
                    try:
                        raw, addr = sock.recvfrom(2048)
                        if raw == b'SHIYIN-DISCOVER-2':
                            sock.sendto(json.dumps({'url': self.url, 'public_key': self.public_key}).encode(), addr)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
            threading.Thread(target=respond, daemon=True).start()
        except OSError as exc:
            self.log('UDP 发现不可用：' + str(exc))
        try:
            from zeroconf import ServiceInfo, Zeroconf
            zc = Zeroconf()
            zc.register_service(ServiceInfo('_shiyin-update._tcp.local.',
                'SHIYIN._shiyin-update._tcp.local.', addresses=[socket.inet_aton(self.config['address'])],
                port=int(self.config['port']), properties={'public_key': self.public_key}))
            self.zeroconf = zc
        except Exception as exc:
            self.log('mDNS 不可用，使用 UDP/IP：' + str(exc))

    def status(self):
        with self.db() as db:
            releases = [dict(r) for r in db.execute('SELECT id,kind,version,state,created,manifest FROM releases ORDER BY created DESC')]
            clients = [dict(r) for r in db.execute('SELECT * FROM clients ORDER BY seen DESC')]
            logs = [dict(r) for r in db.execute('SELECT * FROM logs ORDER BY created DESC LIMIT 100')]
        for release in releases:
            envelope = json.loads(release.pop('manifest'))
            release['notes'] = str(json.loads(envelope['payload']).get('notes') or '')
        target = next((release['version'] for release in releases
            if release['kind'] == 'hot' and release['state'] == 'published'), '')
        for client in clients:
            reported = client['version'].rsplit('/', 1)[-1].strip()
            installed = reported if re.fullmatch(r'\d{14}', reported) else ''
            client.update(target_version=target, update_state=
                'current' if target and installed and installed >= target else
                'outdated' if target and installed else 'unknown')
        return {'running': bool(self.server), 'url': self.url, 'public_key': self.public_key,
                'settings': self.config, 'releases': releases, 'clients': clients, 'logs': logs,
                'job': dict(self.job), 'data': str(self.data), 'uptime': int(time.time() - self.started),
                'desktop_action': dict(self.desktop_action), 'traffic': self.traffic.snapshot(),
                'target_version': target, 'bug_reports': self.bug_reports(),
                'bug_devices': self.bug_devices(),
                'bug_log_root': str(self.data / 'bug-logs')}

    def launch_job(self, action):
        with self.lock:
            if self.job['running']:
                raise ValueError('已有导入任务正在执行')
            self.job = {'running': True, 'message': '正在校验并导入文件…', 'error': ''}
        def run():
            try:
                action()
                self.job['message'] = '校验与发布完成'
            except Exception as exc:
                self.job['error'] = str(exc)
                self.log('导入失败：' + str(exc))
            finally:
                self.job['running'] = False
        threading.Thread(target=run, daemon=True).start()

    def blob(self, path, expected=None):
        sha = digest(path)
        if expected and sha != expected:
            raise ValueError(f'校验失败：{Path(path).name}')
        target = self.data / 'blobs' / sha
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            temp = target.with_suffix('.' + secrets.token_hex(6) + '.part')
            shutil.copyfile(path, temp)
            if digest(temp) != sha:
                temp.unlink()
                raise ValueError('导入过程中源文件发生变化')
            os.replace(temp, target)
        return sha

    def import_release(self, source, kind, notes=''):
        if kind in ('hot-bootstrap', 'hot-updater'):
            raise ValueError('旧更新器发布路线已停用，请发布2.0.0或更高版本的全量基准包')
        source = Path(source).resolve(strict=True)
        files = []
        if kind in ('hot', 'hot-bootstrap', 'hot-updater'):
            manifest = json.loads((source / 'manifest.json').read_text('utf-8-sig'))
            version = str(manifest['version'])
            if not re.fullmatch(r'\d{14}', version):
                raise ValueError('热更新版本必须为14位时间序号')
            if not re.fullmatch(r'\d+\.\d+\.\d+', str(manifest.get('min_desktop_version', ''))):
                raise ValueError('缺少有效的最低桌面基线版本')
            if not isinstance(manifest.get('files'), list) or not 0 < len(manifest['files']) <= 20000:
                raise ValueError('热更新文件数量无效')
            protocol = manifest.get('protocol_version')
            if protocol not in (2, 3) or (kind == 'hot-bootstrap' and protocol != 2) or (kind == 'hot-updater' and protocol != 3):
                raise ValueError('热更新协议版本无效')
            if protocol == 2 and manifest.get('package') is not None:
                raise ValueError('旧协议不能包含增量包字段')
            for item in manifest['files']:
                if not isinstance(item.get('size'), int) or item['size'] < 0 or not re.fullmatch(r'[0-9a-f]{64}', str(item.get('sha256', ''))):
                    raise ValueError('文件大小或 SHA-256 格式无效')
                rel = relative_path(item['path'], hot=True)
                files.append(dict(item))
            roots = manifest.get('prune_roots', [])
            if any(r not in ALLOWED_ROOTS for r in roots):
                raise ValueError('清理目录超出应用白名单')
            if kind == 'hot-bootstrap':
                if roots or len(files) != 1 or files[0]['path'] != 'SHIYIN AI.exe':
                    raise ValueError('更新器引导包只能包含桌面主程序')
            if protocol == 3:
                package = manifest.get('package')
                if not isinstance(package, dict) or not re.fullmatch(r'SHIYIN-Hot-Update-\d{14}\.shiyin-update', str(package.get('name', ''))):
                    raise ValueError('缺少有效的单包信息')
                if not isinstance(package.get('size'), int) or package['size'] <= 0 or not re.fullmatch(r'[0-9a-f]{64}', str(package.get('sha256', ''))):
                    raise ValueError('增量包大小或 SHA-256 无效')
                package_path = (source / package['name']).resolve(strict=True)
                package_path.relative_to(source)
                if package_path.stat().st_size != package['size']:
                    raise ValueError('增量包大小不匹配')
                self.blob(package_path, package['sha256'])
                expected = {item['path']: item for item in files}
                with zipfile.ZipFile(package_path) as archive:
                    entries = [entry for entry in archive.infolist() if not entry.is_dir()]
                    if len(entries) != len(files) or len({entry.filename for entry in entries}) != len(entries):
                        raise ValueError('增量包文件数量或路径重复')
                    for entry in entries:
                        relative_path(entry.filename, hot=True)
                        item = expected.get(entry.filename)
                        if not item or entry.file_size != item['size']:
                            raise ValueError('增量包包含清单外文件或大小不匹配：' + entry.filename)
                        with archive.open(entry) as handle:
                            sha = hashlib.file_digest(handle, 'sha256').hexdigest()
                        if sha != item['sha256']:
                            raise ValueError('增量包文件校验失败：' + entry.filename)
            else:
                for item in files:
                    rel = relative_path(item['path'], hot=True)
                    path = (source / 'files' / rel).resolve(strict=True)
                    path.relative_to((source / 'files').resolve())
                    if path.stat().st_size != item['size']:
                        raise ValueError('文件大小不匹配：' + item['path'])
                    self.blob(path, item['sha256'])
        elif kind == 'video-depth-runtime':
            manifest = json.loads((source / 'manifest.json').read_text('utf-8-sig'))
            if manifest.get('schema_version') != 2 or manifest.get('component') != kind:
                raise ValueError('运行时清单版本或组件名称无效')
            version = str(manifest.get('version') or '')
            if not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?', version):
                raise ValueError('运行时版本无效')
            variants = manifest.get('variants')
            packages = manifest.get('packages')
            if not isinstance(variants, list) or not variants or not isinstance(packages, list) or not packages:
                raise ValueError('运行时清单缺少 variants 或 packages')
            package_ids = set()
            public_packages = []
            for item in packages:
                package_id = str(item.get('id') or '') if isinstance(item, dict) else ''
                file_name = str(item.get('file') or '') if isinstance(item, dict) else ''
                if not re.fullmatch(r'[0-9A-Za-z._-]+', package_id) or package_id in package_ids:
                    raise ValueError('运行时下载包 id 无效或重复')
                rel = relative_path(file_name)
                package_path = (source / rel).resolve(strict=True)
                package_path.relative_to(source)
                size = package_path.stat().st_size
                sha = digest(package_path)
                if int(item.get('size') or 0) != size or str(item.get('sha256') or '').lower() != sha:
                    raise ValueError('运行时下载包大小或 SHA-256 不匹配：' + package_id)
                self.blob(package_path, sha)
                package_ids.add(package_id)
                public_packages.append({
                    'id': package_id, 'size': size, 'sha256': sha,
                    'target_path': str(item.get('target_path') or ''),
                })
                files.append({'path': file_name, 'size': size, 'sha256': sha})
            for variant in variants:
                ids = variant.get('packages') if isinstance(variant, dict) else None
                if not isinstance(ids, list) or not ids or any(str(value) not in package_ids for value in ids):
                    raise ValueError('运行时变体引用了未知下载包')
            manifest = {
                key: manifest[key] for key in (
                    'schema_version', 'component', 'version', 'license_notice', 'variants'
                ) if key in manifest
            }
            manifest.update(protocol_version=2, packages=public_packages)
        elif kind in ('person-depth', 'video-depth'):
            current = source / 'current.json'
            if current.exists():
                current_data = json.loads(current.read_text('utf-8'))
                installation = (source / 'installations' / current_data['installation']).resolve(strict=True)
                installation.relative_to(source / 'installations')
                source = installation
            version = time.strftime('%Y%m%d%H%M%S')
            for path in sorted(source.rglob('*')):
                if path.is_file():
                    path.resolve().relative_to(source)
                    rel = path.relative_to(source).as_posix()
                    relative_path(rel)
                    files.append({'path': rel, 'size': path.stat().st_size, 'sha256': self.blob(path)})
            manifest = {'protocol_version': 1, 'component': kind, 'version': version, 'installation': version}
        elif kind == 'full':
            match = re.fullmatch(r'SHIYIN-AI-Setup-(\d+\.\d+\.\d+)\.exe', source.name)
            if not match:
                raise ValueError('请选择正式全量安装包')
            version = match[1]
            files = [{'path': source.name, 'size': source.stat().st_size, 'sha256': self.blob(source)}]
            manifest = {'version': version}
        else:
            raise ValueError('未知资源类型')
        paths = [f['path'].lower() for f in files]
        if not files or len(set(paths)) != len(paths):
            raise ValueError('文件清单为空或有重复路径')
        manifest.update(files=files, total_bytes=sum(f['size'] for f in files), notes=notes)
        release_id = kind + '-' + version
        raw = json.dumps(manifest, ensure_ascii=False, separators=(',', ':'))
        envelope = json.dumps({'payload': raw, 'signature': self.key.sign(raw.encode()).hex(), 'public_key': self.public_key})
        with self.db() as db:
            if db.execute('SELECT 1 FROM releases WHERE id=?', (release_id,)).fetchone():
                raise ValueError('此版本已存在，请使用新的版本号')
            db.execute("UPDATE releases SET state='archived' WHERE kind=? AND state='published'", (kind,))
            db.execute('INSERT INTO releases VALUES (?,?,?,?,?,?)', (release_id, kind, version, envelope, 'published', time.time()))
        with self.lock:
            self.blob_labels = None
        self.log('已发布 ' + release_id + f'，{len(files)} 个文件')

    def active(self, kind):
        with self.db() as db:
            row = db.execute("SELECT * FROM releases WHERE kind=? AND state='published' ORDER BY created DESC LIMIT 1", (kind,)).fetchone()
        return dict(row) if row else None

    def handler(self, admin):
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def json(self, value, status=200, headers=None):
                raw = json.dumps(value, ensure_ascii=False).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('Cache-Control', 'no-store')
                for name, header_value in (headers or {}).items():
                    self.send_header(name, str(header_value))
                self.end_headers()
                self.wfile.write(raw)

            def authenticated(self):
                return secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + owner.token)

            def do_POST(self):
                path = urlsplit(self.path).path
                if not admin and path == '/v1/bug-reports':
                    try:
                        size = int(self.headers.get('Content-Length', 0))
                        if not 0 < size <= 65536:
                            raise ValueError('日志大小无效')
                        body = json.loads(self.rfile.read(size))
                        return self.json(owner.receive_bug_report(body, self.client_address[0]), 201)
                    except (ValueError, OSError, json.JSONDecodeError) as exc:
                        return self.json({'error': str(exc)}, 400)
                if not admin or not self.authenticated():
                    return self.json({'error': '需要本机管理授权'}, 403)
                try:
                    size = int(self.headers.get('Content-Length', 0))
                    if size > 65536:
                        raise ValueError('请求过大')
                    body = json.loads(self.rfile.read(size) or b'{}')
                    if path == '/api/start': owner.start()
                    elif path == '/api/stop': owner.stop()
                    elif path == '/api/restart':
                        owner.stop()
                        owner.start()
                    elif path == '/api/import':
                        owner.launch_job(lambda: owner.import_release(body['source'], body['kind'], body.get('notes', '')))
                    elif path == '/api/release':
                        with owner.db() as db:
                            row = db.execute('SELECT * FROM releases WHERE id=?', (body['id'],)).fetchone()
                            if not row: raise ValueError('资源不存在')
                            state = body['state']
                            if state not in ('published', 'paused'): raise ValueError('状态无效')
                            if state == 'published':
                                db.execute("UPDATE releases SET state='archived' WHERE kind=? AND state='published'", (row['kind'],))
                            db.execute('UPDATE releases SET state=? WHERE id=?', (state, body['id']))
                        owner.log(body['id'] + ' → ' + state)
                    elif path == '/api/desktop-action':
                        action = body.get('action')
                        if action not in ('show', 'background', 'close'):
                            raise ValueError('桌面操作无效')
                        owner.desktop_action = {'sequence': owner.desktop_action['sequence'] + 1, 'action': action}
                    elif path == '/api/settings':
                        port = int(body.get('port', owner.config['port']))
                        address = str(body.get('address', owner.config['address']))
                        if not 1024 <= port <= 65534 or port in (3012, owner.admin_port): raise ValueError('端口无效或与管理端口冲突')
                        ipaddress.IPv4Address(address)
                        if 'address' in body:
                            with socket.socket() as probe: probe.bind((address, 0))
                        next_config = dict(owner.config, port=port, address=address)
                        theme = body.get('theme', owner.config['theme'])
                        if theme not in ('system', 'dark', 'light'):
                            raise ValueError('主题无效')
                        next_config['theme'] = theme
                        for field in ('auto_start', 'background_on_close', 'launch_at_login', 'start_hidden'):
                            if field in body:
                                if not isinstance(body[field], bool):
                                    raise ValueError('开关参数必须为布尔值')
                                next_config[field] = body[field]
                        if 'launch_at_login' in body:
                            set_startup(next_config['launch_at_login'])
                        atomic_json(owner.config_path, next_config)
                        owner.config = next_config
                    else: return self.json({'error': '接口不存在'}, 404)
                    return self.json(owner.status())
                except Exception as exc:
                    return self.json({'error': str(exc)}, 400)

            def do_GET(self):
                try:
                    path = unquote(urlsplit(self.path).path)
                    if admin:
                        if path == '/api/bug-reports':
                            if not self.authenticated(): return self.json({'error': '需要管理授权'}, 403)
                            return self.json(owner.bug_reports())
                        if path.startswith('/api/bug-devices/'):
                            if not self.authenticated(): return self.json({'error': '需要管理授权'}, 403)
                            parts = path.split('/')
                            if len(parts) != 5: return self.json({'error': '设备标识无效'}, 400)
                            return self.json(owner.bug_device(parts[3], parts[4]))
                        if path.startswith('/api/bug-reports/'):
                            if not self.authenticated(): return self.json({'error': '需要管理授权'}, 403)
                            return self.json(owner.bug_report(path.rsplit('/', 1)[-1]))
                        if path == '/api/status':
                            if not self.authenticated(): return self.json({'error': '需要管理授权'}, 403)
                            return self.json(owner.status())
                        if path in ('/', '/panel.js', '/panel.css'):
                            name = {'/': 'panel.html', '/panel.js': 'panel.js', '/panel.css': 'panel.css'}[path]
                            raw = (Path(__file__).parent / name).read_bytes()
                            self.send_response(200)
                            self.send_header('Content-Type', {'/': 'text/html; charset=utf-8', '/panel.js': 'text/javascript', '/panel.css': 'text/css'}[path])
                            self.send_header('Content-Length', str(len(raw)))
                            self.send_header('Cache-Control', 'no-store')
                            self.end_headers()
                            return self.wfile.write(raw)
                        return self.json({'error': '不存在'}, 404)
                    if path == '/health':
                        return self.json({'ok': True, 'url': owner.url, 'public_key': owner.public_key, 'protocol': 3})
                    if path == '/':
                        full = owner.active('full')
                        download = ('<p><a style="color:#8fe0b4" href="/update/files/SHIYIN-AI-Setup-'
                                    + full['version'] + '.exe">下载 SHIYIN AI ' + full['version'] + ' 基准安装包</a></p>') if full else '<p>基准安装包正在准备，请稍后再试。</p>'
                        raw = ('<!doctype html><meta charset="utf-8"><title>SHIYIN 局域网下载</title>'
                               '<body style="background:#12191f;color:#e5eef5;font:16px sans-serif;padding:60px">'
                               '<h1>SHIYIN 局域网下载</h1><p>首次安装或从1.0.x升级：保存并退出软件，下载基准安装包，选择原安装目录覆盖安装。</p>'
                               + download + '<p>2.0.0及后续版本使用软件内的局域网热更新。原工程和媒体保留在数据目录中。</p>').encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type','text/html; charset=utf-8')
                        self.send_header('Content-Length',str(len(raw)))
                        self.end_headers()
                        return self.wfile.write(raw)
                    if path == '/SHIYIN-Hot-Update.exe':
                        return self.json({'error': '旧迁移工具已停用，请从首页下载2.0.0基准安装包'}, 410)
                    if path == '/hot-update/manifest.json':
                        return self.json({'error': '请从首页下载2.0.0基准安装包覆盖升级'}, 409)
                    if path == '/v1/catalog':
                        owner.touch_client(self.client_address[0], self.headers.get('X-Shiyin-Version', ''))
                        capabilities = {value.strip() for value in self.headers.get('X-Shiyin-Capabilities', '').split(',')}
                        release = None
                        desktop = self.headers.get('X-Shiyin-Version', '').split('/')[0].strip()
                        if re.fullmatch(r'\d+\.\d+\.\d+', desktop) and {'package-v3', 'fast-extract-v1'} <= capabilities:
                            candidate = owner.active('hot')
                            if candidate:
                                manifest = json.loads(json.loads(candidate['manifest'])['payload'])
                                minimum = max((2, 0, 0), tuple(map(int, manifest['min_desktop_version'].split('.'))))
                                if manifest.get('protocol_version') == 3 and tuple(map(int, desktop.split('.'))) >= minimum:
                                    release = candidate
                        target = owner.active('hot')
                        target_version = target['version'] if target else release['version'] if release else ''
                        catalog = json.loads(release['manifest']) if release else {'release': None}
                        if release:
                            plan_payload = json.dumps({'protocol_version': 1, 'target_version': target_version},
                                ensure_ascii=False, separators=(',', ':'))
                            catalog.update(plan_payload=plan_payload,
                                plan_signature=owner.key.sign(plan_payload.encode()).hex())
                        return self.json(catalog,
                            headers={'X-Shiyin-Plan-Target': target_version})
                    if path.startswith('/v1/blobs/'):
                        sha = path.removeprefix('/v1/blobs/')
                        if not re.fullmatch(r'[0-9a-f]{64}', sha): raise ValueError('哈希无效')
                        return self.file(owner.data / 'blobs' / sha, owner.blob_label(sha))
                    for kind in ('person-depth', 'video-depth', 'video-depth-runtime'):
                        if path.startswith('/' + kind + '/'):
                            release = owner.active(kind)
                            if not release: return self.json({'error': '组件尚未发布'}, 404)
                            manifest = json.loads(json.loads(release['manifest'])['payload'])
                            if path == '/' + kind + '/manifest.json':
                                owner.touch_client(self.client_address[0], self.headers.get('X-Shiyin-Version', ''))
                                if kind == 'video-depth-runtime':
                                    return self.json(json.loads(release['manifest']))
                                return self.json(manifest)
                            if kind == 'video-depth-runtime' and path.startswith('/' + kind + '/packages/'):
                                package_id = path.removeprefix('/' + kind + '/packages/')
                                item = next((p for p in manifest.get('packages', []) if p['id'] == package_id), None)
                                if not item: return self.json({'error': '下载包不在发布清单'}, 404)
                                return self.file(owner.data / 'blobs' / item['sha256'])
                            rel = path.removeprefix('/' + kind + '/files/')
                            relative_path(rel)
                            item = next((f for f in manifest['files'] if f['path'] == rel), None)
                            if not item: return self.json({'error': '文件不在发布清单'}, 404)
                            return self.file(owner.data / 'blobs' / item['sha256'])
                    if path == '/update/manifest.json':
                        release = owner.active('full')
                        if not release: return self.json({'error': '暂无全量包'}, 404)
                        manifest = json.loads(json.loads(release['manifest'])['payload'])
                        item = manifest['files'][0]
                        checksum = f"{item['sha256']}  {item['path']}\n"
                        return self.json({'tag_name': 'v' + release['version'], 'draft': False, 'prerelease': False, 'body': manifest.get('notes', ''), 'assets': [
                            {'name': item['path'], 'size': item['size'], 'browser_download_url': owner.url + '/update/files/' + item['path']},
                            {'name': item['path'] + '.sha256', 'size': len(checksum), 'browser_download_url': owner.url + '/update/files/' + item['path'] + '.sha256'}]})
                    if path.startswith('/update/files/'):
                        release = owner.active('full')
                        if not release: return self.json({'error': '暂无全量包'}, 404)
                        item = json.loads(json.loads(release['manifest'])['payload'])['files'][0]
                        name = path.removeprefix('/update/files/')
                        if name == item['path']: return self.file(owner.data / 'blobs' / item['sha256'])
                        if name == item['path'] + '.sha256':
                            raw = f"{item['sha256']}  {item['path']}\n".encode()
                            self.send_response(200)
                            self.send_header('Content-Length', str(len(raw)))
                            self.end_headers()
                            return self.wfile.write(raw)
                    return self.json({'error': '不存在'}, 404)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as exc:
                    self.json({'error': str(exc)}, 400)

            def file(self, path, resource=None):
                if not path.is_file(): return self.json({'error': '文件不存在'}, 404)
                size = path.stat().st_size
                start, end = 0, size - 1
                ranged = self.headers.get('Range', '')
                if ranged:
                    match = re.fullmatch(r'bytes=(\d+)-(\d*)', ranged)
                    if not match or int(match[1]) >= size:
                        return self.json({'error': 'Range 越界'}, 416)
                    start = int(match[1])
                    end = min(int(match[2]) if match[2] else end, end)
                    if end < start: return self.json({'error': 'Range 无效'}, 416)
                self.send_response(206 if ranged else 200)
                self.send_header('Content-Length', str(max(0, end - start + 1)))
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('ETag', '"' + path.name + '"')
                self.send_header('Accept-Ranges', 'bytes')
                if ranged: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                self.end_headers()
                owner.touch_client(self.client_address[0], self.headers.get('X-Shiyin-Version', ''))
                total = max(0, end - start + 1)
                key = owner.traffic.begin(self.client_address[0], resource or unquote(urlsplit(self.path).path), total, start, size)
                remaining = total
                self.connection.settimeout(30)
                try:
                    with path.open('rb') as handle:
                        handle.seek(start)
                        while remaining > 0:
                            chunk = handle.read(min(256 * 1024, remaining))
                            if not chunk: break
                            view = memoryview(chunk)
                            while view:
                                sent = self.connection.send(view)
                                if not sent: raise ConnectionResetError('下载连接关闭')
                                owner.traffic.advance(key, sent)
                                remaining -= sent
                                view = view[sent:]
                except OSError:
                    # 响应头已发送，不再向文件流追加 JSON 错误内容。
                    pass
                finally:
                    owner.traffic.finish(key, remaining == 0)
        return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=DEFAULT_DATA)
    parser.add_argument('--port', type=int, default=3011)
    parser.add_argument('--admin-port', type=int, default=3013)
    args = parser.parse_args()
    center = Center(args.data, args.port, args.admin_port)
    admin = ThreadingHTTPServer(('127.0.0.1', args.admin_port), center.handler(True))
    admin.daemon_threads = True
    if center.config['auto_start']:
        try: center.start()
        except OSError as exc: center.log('启动失败，请检查端口占用：' + str(exc))
    try:
        admin.serve_forever()
    except BaseException as exc:
        atomic_json(center.data / 'service-error.json', {
            'error': f'{type(exc).__name__}: {exc}', 'time': time.time()
        })
        raise
    finally:
        center.stop()
        admin.server_close()


if __name__ == '__main__':
    main()
