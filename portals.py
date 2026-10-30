"""Read-only portal reader for committed Valheim 1.0 chunked saves (v40-42).

Reads the generation index and dedicated portal chunk only. Never opens a
world file for writing. Binary format notes and validation: PORTALS.md.
"""
import hashlib
import math
import struct
from pathlib import Path
from datetime import datetime, timezone

MAX_BYTES = 16 * 1024 * 1024

class Reader:
    def __init__(self, raw):
        self.raw, self.offset = raw, 0
    def take(self, n):
        if n < 0 or self.offset + n > len(self.raw):
            raise ValueError('Truncated save data')
        start = self.offset
        self.offset += n
        return self.raw[start:self.offset]
    def unpack(self, fmt):
        return struct.unpack('<' + fmt, self.take(struct.calcsize('<' + fmt)))
    def num(self):
        b = self.unpack('B')[0]
        return ((b & 127) << 8) | self.unpack('B')[0] if b & 128 else b
    def string(self):
        size = 0
        for shift in range(0, 35, 7):
            b = self.unpack('B')[0]
            size |= (b & 127) << shift
            if not b & 128:
                if size > 65536: raise ValueError('Oversized string')
                return self.take(size).decode('utf-8', errors='strict')
        raise ValueError('Invalid string length')
    def end(self):
        if self.offset != len(self.raw): raise ValueError('Unrecognised trailing data')

def read_small(path):
    with path.open('rb') as f:
        raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES: raise ValueError('Portal data exceeds size limit')
    return raw

def version(r):
    value = r.unpack('H')[0]
    if value not in (40, 41, 42): raise ValueError('Unsupported world-save version')
    return value

def count(r, maximum=100000):
    n = r.unpack('i')[0]
    if not 0 <= n <= maximum: raise ValueError('Invalid record count')
    return n

def portal_index(raw):
    r = Reader(raw)
    v = version(r)
    count(r, 50000000)
    found = []
    for _ in range(count(r)):
        chunk, size, revision, n = r.unpack('HBIi')
        if n < 0: raise ValueError('Invalid chunk count')
        if chunk == 1 and size == 0: found.append((f'00_01__0_{revision}.chunk', n))
    r.end()
    if len(found) > 1: raise ValueError('Duplicate portal chunk')
    return v, found[0] if found else None

def parse_portals(raw, expected):
    r = Reader(raw)
    version(r)
    n = count(r)
    if n != expected: raise ValueError('Portal index and chunk counts differ')
    portals = []
    for i in range(n):
        flags = r.unpack('H')[0]
        if flags & 0x2000:
            x, z = r.unpack('hh'); y = 0.0
        else: x, y, z = r.unpack('fff')
        if not all(math.isfinite(v) for v in (x,y,z)): raise ValueError('Invalid coordinates')
        prefab = r.unpack('i')[0]
        if flags & 0x1000:
            rotation = r.unpack('H')[0]
            if not rotation & 0x8000: r.take(2)
        connection = r.unpack('Bi') if flags & 1 else None
        for mask, size in ((2,8),(4,16),(8,20),(16,8),(32,12)):
            if flags & mask: r.take(r.num() * size)
        tag = ''
        if flags & 64:
            for _ in range(r.num()):
                key = r.unpack('i')[0]
                value = r.string()
                if key == 696029674: tag = value
        if flags & 128:
            for _ in range(r.num()):
                r.take(4)
                r.take(count(r, MAX_BYTES))
        identity = hashlib.sha256(struct.pack('<ifff',prefab,x,y,z)).hexdigest()[:16]
        portals.append(dict(id=identity, tag=tag, x=x, y=y, z=z, prefab=prefab,
                            connection=list(connection) if connection else None))
    r.end()
    return portals

def classify(portals):
    """Saved portal links share a hash with opposite Portal/Portal|Target types.
    Tag matches alone are candidates, never evidence of a saved connection.
    """
    for p in portals:
        p['status'], p['target'] = 'unpaired', None
        conn = p['connection']
        if conn and conn[0] in (1, 17) and conn[1]:
            matches = [q for q in portals if q is not p and q['connection'] == [conn[0] ^ 16, conn[1]]]
            if len(matches) == 1 and sum(q['connection'] == conn for q in portals) == 1:
                p['status'], p['target'] = 'linked', matches[0]['id']
            else: p['status'] = 'unresolved'
        elif conn and conn[0] not in (1,17): p['status'] = 'unknown'
        p['same_tag_count'] = sum(q['tag'] == p['tag'] for q in portals)
    return portals

def committed(world):
    generations = []
    for p in world.glob('_main.*.ok'):
        parts = p.name.split('.')
        if len(parts) == 3 and parts[1].isdigit():
            n = int(parts[1])
            if all((world / f'_main.{n}.{ext}').is_file() for ext in ('db2','fwl2','chunks')):
                generations.append(n)
    if not generations: raise ValueError('No committed world save available')
    return max(generations)

def scan(world):
    world = Path(world)
    for attempt in range(2):
        generation = committed(world)
        try:
            index = world / f'_main.{generation}.chunks'
            raw = read_small(index)
            v, record = portal_index(raw)
            portals = classify(parse_portals(read_small(world / record[0]), record[1])) if record else []
            if committed(world) != generation: continue
            saved = datetime.fromtimestamp(index.stat().st_mtime, timezone.utc).isoformat()
            return dict(generation=generation, save_version=v, saved_at=saved, portals=portals)
        except (OSError,ValueError):
            if attempt == 0 and committed(world) != generation: continue
            raise
    raise ValueError('World save changed during both reads')

def world_path(container):
    env = dict(e.split('=',1) for e in container['Config']['Env'] if '=' in e)
    name = env.get('WORLD_NAME','')
    if not name or name in ('.','..') or '/' in name or '\\' in name:
        raise ValueError('Invalid world name')
    mounts = [m for m in container['Mounts'] if m['Destination'] == '/config']
    if len(mounts) != 1: raise ValueError('World configuration mount unavailable')
    return Path(mounts[0]['Source']) / 'worlds_local' / name

_CACHE = {}
def snapshot(container):
    key = container['Name']
    previous = None
    try:
        path = world_path(container)
        cached = _CACHE.get(key)
        previous = cached if cached and cached.get('_path') == str(path) else None
        generation = committed(path)
        if previous and previous.get('_path') == str(path) and previous['generation'] == generation:
            return {k:v for k,v in previous.items() if k != '_path'} | {'error':None}
        result = scan(path) | {'error':None, '_path':str(path)}
        _CACHE[key] = result
        return {k:v for k,v in result.items() if k != '_path'}
    except (OSError,ValueError,KeyError,struct.error) as exc:
        # Do not expose host paths to the dashboard.
        error = str(exc) if isinstance(exc,ValueError) else 'World save could not be read'
        result = {k:v for k,v in (previous or {}).items() if k != '_path'}
        return result | {'error':error, 'stale':True, 'portals':result.get('portals',[])}
