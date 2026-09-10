"""有界账号快照：数据库变化立即失效，外部文件变化最多滞后 TTL。"""
from __future__ import annotations

import copy
import os
import threading
import time
from collections import OrderedDict


def database_stamp(path) -> tuple:
    result = []
    for filename in (os.fspath(path), os.fspath(path) + "-wal"):
        try:
            stat = os.stat(filename)
            result.append((stat.st_mtime_ns, stat.st_size))
        except OSError:
            result.append(None)
    return tuple(result)


class WorksSnapshotCache:
    def __init__(self, capacity=8, ttl=10.0):
        self.capacity, self.ttl = capacity, ttl
        self._entries = OrderedDict()
        self._lock = threading.Lock()
        # 固定数量的锁避免账号增长导致无界锁表；不同账号可并行重建。
        self._build_locks = [threading.Lock() for _ in range(32)]

    def get(self, key, stamp, build):
        with self._build_locks[hash(key) % len(self._build_locks)]:
            version = stamp()
            with self._lock:
                entry = self._entries.get(key)
                if entry and entry[0] == version and time.monotonic() - entry[1] < self.ttl:
                    self._entries.move_to_end(key)
                    return copy.deepcopy(entry[2])
            value = build()
            # 构建期间若有新提交，不能把旧快照标成新版本。
            if stamp() == version:
                with self._lock:
                    self._entries[key] = (version, time.monotonic(), value)
                    self._entries.move_to_end(key)
                    while len(self._entries) > self.capacity:
                        self._entries.popitem(last=False)
            return copy.deepcopy(value)

    def clear(self):
        with self._lock:
            self._entries.clear()
