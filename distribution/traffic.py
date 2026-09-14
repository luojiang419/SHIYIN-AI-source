"""服务端文件响应统计；字节表示成功写入 socket，不代表客户端安装完成。"""
from collections import deque
import secrets
import sqlite3
import threading
import time


class Traffic:
    def __init__(self, db, clock=time.time):
        self.db, self.clock = db, clock
        self.lock = threading.RLock()
        self.active = {}
        self.recent = deque(maxlen=40)
        self.buckets = {}
        self.pending = {}
        self.last_flush = 0
        self.persistence_error = ''
        with db() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS traffic_daily (
                day TEXT, ip TEXT, bytes INTEGER NOT NULL, peak REAL NOT NULL,
                PRIMARY KEY(day, ip))''')

    @staticmethod
    def day(stamp):
        return time.strftime('%Y-%m-%d', time.localtime(stamp))

    def begin(self, ip, resource, total, offset=0, file_size=0):
        with self.lock:
            key = secrets.token_hex(12)
            self.active[key] = dict(id=key, ip=ip, resource=resource, total=total,
                                    offset=offset, file_size=file_size, sent=0,
                                    started=self.clock(), state='downloading')
            return key

    def advance(self, key, count):
        with self.lock:
            now = self.clock()
            item = self.active[key]
            item['sent'] += count
            second, day = int(now), self.day(now)
            for ip in ('*', item['ip']):
                bucket = self.buckets.setdefault(second, {})
                bucket[ip] = bucket.get(ip, 0) + count
                row = self.pending.setdefault((day, ip), [0, 0])
                row[0] += count
                row[1] = max(row[1], bucket[ip])
            self._prune(now)
            if now - self.last_flush >= 1:
                self.flush()

    def _prune(self, now):
        for second in list(self.buckets):
            if second < int(now) - 120:
                del self.buckets[second]

    def flush(self):
        with self.lock:
            try:
                if self.pending:
                    with self.db() as conn:
                        conn.executemany('''INSERT INTO traffic_daily VALUES (?,?,?,?)
                            ON CONFLICT(day,ip) DO UPDATE SET
                            bytes=bytes+excluded.bytes, peak=MAX(peak,excluded.peak)''',
                            [(day, ip, value[0], value[1]) for (day, ip), value in self.pending.items()])
                    self.pending.clear()
                self.persistence_error = ''
            except sqlite3.Error as exc:
                # 统计存储故障不能打断正在进行的文件下载，待下次采样重试。
                self.persistence_error = str(exc)
            self.last_flush = self.clock()

    def finish(self, key, completed):
        with self.lock:
            item = self.active.pop(key)
            item.update(state='completed' if completed else 'interrupted', ended=self.clock())
            self.recent.appendleft(item)
            self.flush()

    def snapshot(self):
        with self.lock:
            now = self.clock()
            self._prune(now)
            self.flush()
            day = self.day(now)
            with self.db() as conn:
                rows = {r['ip']: dict(r) for r in conn.execute('SELECT * FROM traffic_daily WHERE day=?', (day,))}
            for (pending_day, ip), values in self.pending.items():
                if pending_day == day:
                    row = rows.setdefault(ip, {'bytes': 0, 'peak': 0})
                    row['bytes'] += values[0]
                    row['peak'] = max(row['peak'], values[1])
            def speed(ip):
                return sum(self.buckets.get(s, {}).get(ip, 0) for s in range(int(now)-3, int(now))) / 3
            clients = {ip: dict(today_bytes=r['bytes'], peak_bps=r['peak'], speed_bps=speed(ip))
                       for ip, r in rows.items() if ip != '*'}
            for item in self.active.values():
                clients.setdefault(item['ip'], dict(today_bytes=0, peak_bps=0, speed_bps=speed(item['ip'])))
            total = rows.get('*', {})
            return dict(day=day, active_count=len(self.active), downloading_clients=len({t['ip'] for t in self.active.values()}),
                        speed_bps=speed('*'), today_bytes=total.get('bytes', 0), peak_bps=total.get('peak', 0),
                        clients=clients, active=[dict(t) for t in self.active.values()], recent=list(self.recent),
                        history=[dict(time=s, speed_bps=self.buckets.get(s, {}).get('*', 0))
                                 for s in range(int(now)-60, int(now))], persistence_error=self.persistence_error)
