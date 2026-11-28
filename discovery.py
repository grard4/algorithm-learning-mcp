"""Persistent first-observation boundary; never interpret ctime/mtime as birth.

Without birthtime, a stable file identity absent from the initial inventory is
eligible for manual review only, never automatic import. Arrival-after-inventory
is not proof of physical creation time.
Existing paths and identities remain excluded even after rename/replacement.
"""
import json
import math
import os
import tempfile
import time

from kb import KBError, digest

MAX_FILES = 50000
MAX_BYTES = 8 * 1024 * 1024


def identity(stat):
    dev, ino = getattr(stat, 'st_dev', None), getattr(stat, 'st_ino', None)
    if not isinstance(dev, int) or not isinstance(ino, int) or ino <= 0:
        return None
    return digest([dev, ino])


class Boundary:
    def __init__(self, config, home, paths, cutoff):
        home = home.resolve()
        root_id = identity(home.stat())
        if not root_id:
            raise KBError('INVALID_DISCOVERY_BOUNDARY', '无法确认发现目录身份；需显式登记')
        self.path = config / ('discovery-baseline-' + digest(str(home)) + '.json')
        if not self.path.exists():
            started = time.time()
            names, identities = set(), set()
            for p in paths:
                if len(names) >= MAX_FILES:
                    raise KBError('TOO_LARGE', '发现文件清单超过预算')
                names.add(digest(str(p.resolve())))
                try:
                    key = identity(p.stat())
                except FileNotFoundError:
                    key = None  # Retain the name tombstone for a vanished source.
                except OSError as exc:
                    # A partial initial inventory cannot prove which files are old.
                    raise KBError('INVALID_DISCOVERY_BOUNDARY', '初始发现清单不可完整读取') from exc
                if key:
                    identities.add(key)
            raw = json.dumps({'version': 1, 'root': root_id, 'since': max(cutoff, started),
                              'paths': sorted(names), 'identities': sorted(identities)}).encode()
            if len(raw) > MAX_BYTES:
                raise KBError('TOO_LARGE', '发现清单超过字节预算')
            config.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix='.discovery-', dir=config)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(temp, self.path)
                except FileExistsError:
                    pass  # Concurrent initializer wins; read its complete snapshot.
            finally:
                os.unlink(temp)
        try:
            with self.path.open('rb') as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('oversized')
            data = json.loads(raw)
            if data['version'] != 1 or data['root'] != root_id:
                raise ValueError('identity')
            self.since = data['since']
            if not math.isfinite(self.since) or self.since < 0:
                raise ValueError('timestamp')
            for field in ('paths', 'identities'):
                values = data[field]
                if not isinstance(values, list) or len(values) > MAX_FILES or any(
                    not isinstance(x, str) or len(x) != 64 or any(c not in '0123456789abcdef' for c in x)
                    for x in values):
                    raise ValueError('inventory')
            self.paths, self.identities = set(data['paths']), set(data['identities'])
        except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
            raise KBError('INVALID_DISCOVERY_BOUNDARY', '发现快照无效；保留现场并显式登记') from exc

    def allows(self, path, stat):
        """Allow inspection of a new arrival; absent birthtime still needs consent."""
        key = identity(stat)
        if not key or path.is_symlink() or digest(str(path.resolve())) in self.paths or key in self.identities:
            return False
        if hasattr(stat, 'st_birthtime'):
            birth = stat.st_birthtime
            return isinstance(birth, (int, float)) and math.isfinite(birth) and self.since < birth <= time.time()
        return True
