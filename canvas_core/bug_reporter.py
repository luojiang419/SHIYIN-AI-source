"""Persist bounded diagnostic reports and deliver them to the trusted LAN center."""
from __future__ import annotations

import json
import getpass
import logging
import os
from pathlib import Path
import platform
import subprocess
import threading
import time
import urllib.request
import uuid

from canvas_core.distribution_client import distribution_status


def _run_diagnostic(command: list[str], timeout: int = 12) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return result.stdout.strip()[:20000] if result.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def hardware_diagnostics() -> dict:
    snapshot = {'system': {'name': platform.system(), 'release': platform.release(),
                           'version': platform.version(), 'architecture': platform.machine()},
                'cpu': [], 'memory': {}, 'disks': [], 'displayAdapters': [], 'nvidiaGpus': []}
    if os.name == 'nt':
        script = (
            "$os=Get-CimInstance Win32_OperatingSystem;"
            "$cs=Get-CimInstance Win32_ComputerSystem;"
            "$cpu=Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors;"
            "$disk=Get-CimInstance Win32_DiskDrive | Select-Object Model,Size,InterfaceType;"
            "$gpu=Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM;"
            "@{os=@{caption=$os.Caption;build=$os.BuildNumber};"
            "memory=@{totalBytes=$cs.TotalPhysicalMemory};cpu=@($cpu);"
            "disks=@($disk);displayAdapters=@($gpu)} | ConvertTo-Json -Depth 5 -Compress"
        )
        raw = _run_diagnostic(['powershell', '-NoProfile', '-NonInteractive', '-Command', script])
        if raw:
            try:
                snapshot.update(json.loads(raw))
            except ValueError:
                snapshot['windowsDiagnostics'] = 'unavailable'
    gpu = _run_diagnostic(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,compute_cap',
                           '--format=csv,noheader,nounits'], 5)
    if not gpu:
        gpu = _run_diagnostic(['nvidia-smi', '--query-gpu=name,driver_version,memory.total',
                               '--format=csv,noheader,nounits'], 5)
    for row in gpu.splitlines():
        values = [part.strip() for part in row.split(',')]
        if len(values) >= 3:
            item = {'name': values[0], 'driverVersion': values[1], 'memoryMiB': values[2]}
            if len(values) >= 4:
                item['computeCapability'] = values[3]
            snapshot['nvidiaGpus'].append(item)
    return snapshot


class BugReporter:
    def __init__(self, data_root: str | Path, source: str = 'http://192.168.0.24:3011'):
        self.root = Path(data_root) / 'bug-reports'
        self.pending = self.root / 'pending'
        self.pending.mkdir(parents=True, exist_ok=True)
        identity = self.root / 'client-id'
        if identity.exists():
            self.client_id = identity.read_text('ascii').strip()
        else:
            self.client_id = uuid.uuid4().hex
            identity.write_text(self.client_id, encoding='ascii')
        self.source = source
        self._hardware = None
        self._hardware_at = 0.0
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._user_seen: dict[str, float] = {}
        threading.Thread(target=self._deliver, daemon=True, name='bug-report-delivery').start()

    def report(self, kind: str, summary: str, details: dict | None = None, user_id: str = 'admin', machine: dict | None = None):
        if len(list(self.pending.glob('*.json'))) >= 1000:
            return
        payload = {'clientId': self.client_id, 'kind': kind, 'summary': str(summary)[:240],
                   'userId': str(user_id)[:64],
                   'computerUser': getpass.getuser(), 'computerName': platform.node(),
                   'version': os.getenv('SHIYIN_HOT_UPDATE_VERSION', ''),
                   'details': details or {}}
        if machine is not None:
            payload['machine'] = machine
        elif kind in ('error', 'runtime') and self._hardware is not None:
            payload['machine'] = self._hardware
        path = self.pending / f'{time.time_ns()}-{uuid.uuid4().hex[:8]}.json'
        raw = json.dumps(payload, ensure_ascii=False, default=str)
        if len(raw.encode('utf-8')) > 60000:
            payload['details'] = {'truncated': True, 'summary': str(details)[:10000]}
            raw = json.dumps(payload, ensure_ascii=False)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(raw, encoding='utf-8')
        os.replace(temporary, path)
        self._wake.set()

    def mark_user_active(self, user_id: str):
        now = time.time()
        with self._lock:
            if now - self._user_seen.get(user_id, 0) < 60:
                return
            self._user_seen[user_id] = now
        self.report('heartbeat', '账号运行中', {'pid': os.getpid()},
                    user_id=user_id, machine=self._hardware)

    def _deliver(self):
        last_heartbeat = 0.0
        while True:
            if time.time() - last_heartbeat >= 60:
                now = time.time()
                if self._hardware is None or now - self._hardware_at >= 1800:
                    self._hardware = hardware_diagnostics()
                    self._hardware_at = now
                self.report('heartbeat', '客户端运行中', {'pid': os.getpid()}, machine=self._hardware)
                last_heartbeat = time.time()
            with self._lock:
                queued = sorted(self.pending.glob('*.json'))[:20]
            if queued:
                state = distribution_status(self.source)
                if state['connected']:
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    for path in queued:
                        try:
                            request = urllib.request.Request(state['url'] + '/v1/bug-reports',
                                data=path.read_bytes(), headers={'Content-Type': 'application/json'}, method='POST')
                            with opener.open(request, timeout=3) as response:
                                if response.status != 201:
                                    break
                            path.unlink()
                        except (OSError, ValueError):
                            break
            self._wake.wait(15)
            self._wake.clear()


class BugLogHandler(logging.Handler):
    def __init__(self, reporter: BugReporter):
        super().__init__(logging.WARNING)
        self.reporter = reporter

    def emit(self, record):
        try:
            from canvas_core.account_storage import current_account_id
            self.reporter.report('runtime', record.getMessage()[:200], {
                'logger': record.name, 'level': record.levelname,
                'message': record.getMessage()[:3000],
                'exception': self.format(record)[-5000:] if record.exc_info else '',
            }, user_id=current_account_id())
        except (OSError, ValueError):
            self.handleError(record)


def gpu_diagnostics():
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,compute_cap',
            '--format=csv,noheader'], capture_output=True, text=True, timeout=4,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return {'nvidiaSmi': result.stdout.strip()[:500] if result.returncode == 0 else ''}
    except (OSError, subprocess.TimeoutExpired):
        return {'nvidiaSmi': 'unavailable'}
