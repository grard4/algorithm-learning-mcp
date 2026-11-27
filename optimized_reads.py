"""Bounded read-result cache and reversible cursor transport; no database writes.

Only the C2.3 link-only query is cached. Learning progress, L3, single-link
evidence checks and invalidation notifications remain uncached. An unchanged
reply requires an explicit caller version; a cache hit alone never suppresses data.
"""
import base64
import copy
import hashlib
import json
import pathlib
import threading
import time
from collections import OrderedDict

RULE = 'phase-d-read-cache-v1'
PREFIX = 'd1.'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf8')


def pack_cursor(cursor):
    if cursor is None:
        return None
    envelope = json.loads(base64.urlsafe_b64decode(cursor))
    page = json.loads(base64.urlsafe_b64decode(envelope['page']))
    # A single transport envelope; underlying query/state validation is untouched.
    flat = [envelope['kind'], envelope['signature'], envelope['held'], page]
    packed = PREFIX + base64.urlsafe_b64encode(encoded(flat)).decode('ascii').rstrip('=')
    return packed if len(packed) < len(cursor) else cursor


def unpack_cursor(cursor, error):
    if not isinstance(cursor, str) or not cursor.startswith(PREFIX):
        return cursor  # Existing cursors retain their validation and compatibility.
    try:
        if len(cursor) > 8192:
            raise ValueError('oversized cursor')
        part = cursor[len(PREFIX):]
        raw = base64.b64decode(part + '=' * (-len(part) % 4), altchars=b'-_', validate=True)
        flat = json.loads(raw)
        if (not isinstance(flat, list) or len(flat) != 4 or flat[0] != 'c23-compact-r2'
                or not isinstance(flat[1], str) or not isinstance(flat[2], dict)
                or not isinstance(flat[3], dict)
                or set(flat[3]) != {'signature', 'state', 'offsets'}):
            raise ValueError('invalid flat cursor')
        page = {key: flat[3][key] for key in ['signature', 'state', 'offsets']}
        inner = base64.urlsafe_b64encode(json.dumps(page).encode()).decode()
        envelope = {'kind': flat[0], 'signature': flat[1], 'held': flat[2], 'page': inner}
        return base64.urlsafe_b64encode(json.dumps(envelope, separators=(',', ':')).encode()).decode()
    except (ValueError, UnicodeError, TypeError, KeyError) as exc:
        raise error('INVALID_CURSOR') from exc


class ReadCache:
    def __init__(self, search, health, error, implementation_hash,
                 max_entries=128, max_bytes=4 * 1024 * 1024, ttl=60, clock=time.monotonic):
        self.search = search
        self.health = health
        self.error = error
        self.implementation_hash = implementation_hash
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.ttl = ttl
        self.clock = clock
        self.entries = OrderedDict()
        self.bytes = 0
        self.lock = threading.RLock()
        self.hits = self.misses = 0

    def query(self, c, concepts, limit=2, topic_ids=None, cursor=None, known_versions=None):
        # Both health and journal watermark belong to the caller's same read snapshot.
        if not c.in_transaction or c.execute('PRAGMA query_only').fetchone()[0] != 1:
            raise self.error('READ_TRANSACTION_REQUIRED')
        meta = self.health(c)  # Runs even on hits; removed/changed triggers fail closed.
        database = next(row[2] for row in c.execute('PRAGMA database_list') if row[1] == 'main')
        if not database:
            raise self.error('CACHE_FILE_DATABASE_REQUIRED')
        watermark = c.execute('SELECT COALESCE(MAX(seq),0) FROM r3_notices').fetchone()[0]
        cursor = unpack_cursor(cursor, self.error)
        # Never cache course alignment or progress on this key. This query reads only
        # concept/source tables whose changes are covered by the verified R3 triggers.
        # Supported backup restore rotates epoch. A forged same-epoch journal is outside
        # the existing database integrity contract, not silently claimed detectable.
        args = [concepts, limit, topic_ids, cursor, known_versions]
        try:
            key = hashlib.sha256(encoded([RULE, self.implementation_hash,
                str(pathlib.Path(database).resolve()), dict(meta), watermark,
                c.execute('PRAGMA schema_version').fetchone()[0], args])).digest()
        except (ValueError, TypeError):
            return self.search(c, *args)  # Let the existing strict validator reject it.
        now = self.clock()
        with self.lock:
            hit = self.entries.get(key)
            if hit and now - hit[0] < self.ttl:
                self.hits += 1
                self.entries.move_to_end(key)
                return copy.deepcopy(hit[1])
            if hit:
                self.bytes -= self.entries.pop(key)[2]
            self.misses += 1
        # Exceptions are not cached. Do not hold the cache lock during SQL work.
        result = copy.deepcopy(self.search(c, *args))
        result['next_cursor'] = pack_cursor(result.get('next_cursor'))
        size = len(encoded(result))
        if size <= self.max_bytes and self.max_entries > 0 and self.ttl > 0:
            with self.lock:
                if key in self.entries:
                    self.bytes -= self.entries.pop(key)[2]
                self.entries[key] = (now, copy.deepcopy(result), size)
                self.bytes += size
                while len(self.entries) > self.max_entries or self.bytes > self.max_bytes:
                    self.bytes -= self.entries.popitem(last=False)[1][2]
        return result
