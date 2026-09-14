"""客户端只发现和读取分发中心，不启动监听服务。"""
import json
import socket
import urllib.request
from pathlib import Path


def trusted_key():
    return Path(__file__).with_name('distribution-public-key.hex').read_text('ascii').strip()


def discover_source(fallback='http://192.168.0.24:3011'):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(.7)
            sock.sendto(b'SHIYIN-DISCOVER-2', ('255.255.255.255', 3012))
            raw, _ = sock.recvfrom(2048)
            value = json.loads(raw)
            if value.get('public_key') == trusted_key() and str(value.get('url', '')).startswith('http://'):
                return value['url'].rstrip('/')
    except (OSError, ValueError):
        pass
    return fallback


def distribution_status(source):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for url in dict.fromkeys([source, discover_source(source)]):
        try:
            with opener.open(url.rstrip('/') + '/health', timeout=2) as response:
                health = json.loads(response.read(16384))
            if health.get('public_key') != trusted_key():
                raise ValueError('分发中心公钥不匹配')
            return {'role': 'client', 'connected': True, 'url': url}
        except (OSError, ValueError):
            continue
    return {'role': 'client', 'connected': False, 'url': source, 'error': '暂时无法连接分发中心，请确认管理员电脑服务已启动。'}
