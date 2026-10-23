"""PC Nightreign save reader. Source files are only ever opened with 'rb'.

Format facts: Hapfel1/er-save-manager, games/NR/parser.py.
No save writer, game hook or process-memory API is present.
"""
from pathlib import Path
import hashlib
import struct
from math import isfinite

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY = bytes.fromhex('18f6326605bd178a5524523ac0a0c609')


def decode_slot(path):
    path = Path(path)
    before = path.stat()
    slot,spans = None,[]
    with path.open('rb') as stream:
        header = stream.read(512)
        if len(header)!=512 or header[:4]!=b'BND4' or struct.unpack_from('<I',header,12)[0]!=14:
            raise ValueError('Unrecognized save format')
        for index in range(14):
            descriptor = 64+32*index
            if header[descriptor:descriptor+8]!=bytes.fromhex('40000000ffffffff'):
                raise ValueError('Unrecognized save structure')
            size,_,offset = struct.unpack_from('<iii',header,descriptor+8)
            if offset<512 or size<48 or (size-16)%16 or offset+size>before.st_size:
                raise ValueError('Incomplete save file')
            if any(offset<end and offset+size>start for start,end in spans):
                raise ValueError('Inconsistent save structure')
            spans.append((offset,offset+size))
            stream.seek(offset)
            payload = stream.read(size)
            if len(payload)!=size:raise ValueError('Incomplete save file')
            decoder = Cipher(algorithms.AES(KEY),modes.CBC(payload[:16])).decryptor()
            plain = decoder.update(memoryview(payload)[16:])+decoder.finalize()
            if plain[-12:]!=bytes([12])*12 or hashlib.md5(memoryview(plain)[4:-28]).digest()!=plain[-28:-12]:
                raise ValueError('Save write in progress or checksum mismatch')
            if index==0:slot = plain
    after = path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('Save write in progress')
    return slot,before.st_mtime_ns/1e9


def owned_clock_offsets(data, first, limit):
    """Find PC owner tails in native code; validate all candidates afterwards."""
    suffix = b'\x01\x00\x10\x01'
    position = data.find(suffix,first+20,limit+23)
    while position!=-1:
        offset = position-20
        if (offset-first)%4==0:yield offset
        position = data.find(suffix,position+1,limit+23)


def read_clock(data):
    cursor = 0x14
    for _ in range(5120):
        if cursor+8 > len(data)-28:
            raise ValueError('Unrecognized inventory format')
        handle = struct.unpack_from('<I',data,cursor)[0]
        cursor += {0x80000000:88,0x90000000:16,0xC0000000:80}.get(handle&0xF0000000,8)
    loadout = cursor+0x94+0x5B8+4+3065*14+0x21A
    if loadout+8 > len(data)-28:
        raise ValueError('Unrecognized character structure')
    tag, _, size = struct.unpack_from('<HHI',data,loadout)
    start = loadout+8+size
    if tag != 0xC2 or start >= len(data)-28:
        raise ValueError('Unrecognized character structure')
    version = struct.unpack_from('<I',data,4)[0]
    first,limit = start+28,len(data)-28-23
    found = []
    # Owned PC clocks take precedence. If none validates, preserve the complete
    # zero-owner/PS-layout scan and its ambiguity checks.
    for offsets in (owned_clock_offsets(data,first,limit),range(first,limit,4)):
        found = []
        for offset in offsets:
            a,b,current,pad = struct.unpack_from('<4I',data,offset)
            if pad or current>1 or not (0<a<=version and 0<b<=version):continue
            h,m,s = struct.unpack_from('<3I',data,offset-12)
            if h>23 or m>59 or s>59 or struct.unpack_from('<I',data,offset-16)[0]:continue
            owner = struct.unpack_from('<Q',data,offset+16)[0]
            if owner and not 0x0110000100000000<=owner<=0x01100001FFFFFFFF:continue
            found.append((owner,{'hour':h,'minute':m,'second':s,'clock_seconds':h*3600+m*60+s,
                                 'play_time_ms':struct.unpack_from('<I',data,12)[0],
                                 '_clock_offset':offset-12}))
        owned = [item for item in found if item[0]]
        if owned:
            found = owned
            break
    if len(found) != 1:
        raise ValueError('Save clock not found or ambiguous')
    clock = found[0][1]
    clock_offset = clock.pop('_clock_offset')
    clock['map_id'] = saved_map(data,clock_offset,start)
    clock['location_unloaded'] = saved_location_unloaded(data,clock_offset,start)
    # Character-relative activity marker observed in both recorded expeditions:
    # ...0e 00... in the Bastion, ...0e 0e... throughout Days 1 and 2.
    # Require the complete known envelope; unknown layouts stay undecided.
    name_offset = cursor+0x94
    marker = data[name_offset+64:name_offset+80]
    clock['expedition_active'] = None
    if (len(marker)==16 and marker[:2] in (b'\xff\xff',b'\x00\x00')
            and marker[2:10]==bytes.fromhex('000000000000000e')
            and marker[11:]==bytes.fromhex('008cc30000')):
        if marker[10]==14:clock['expedition_active'] = True
        elif marker[10]==0 and clock['clock_seconds']==6*3600+30*60:
            clock['expedition_active'] = False
    return clock


def saved_map(data,clock_offset,world_start):
    """Validated character location before the fixed world-state block, v0x134.

    Located relative to the verified clock/owner tail, never a fixed file offset.
    Unknown versions or inconsistent surrounding fields return no location.
    """
    if struct.unpack_from('<I',data,4)[0]!=0x134:return None
    offset=clock_offset-0x2004f
    if offset-12<world_start or offset+24>clock_offset:return None
    if data[offset+4:offset+8]!=bytes(4) or data[offset+12:offset+20]!=bytes(8):return None
    if data[offset+20]!=1:return None
    position=struct.unpack_from('<3f',data,offset-12)
    yaw=struct.unpack_from('<f',data,offset+8)[0]
    if any(not isfinite(value) or abs(value)>1e6 for value in (*position,yaw)):return None
    area,block,region,variant=reversed(data[offset:offset+4])
    if not 0<area<=99 or any(value>99 for value in (block,region,variant)):return None
    return f'm{area:02}_{block:02}_{region:02}_{variant:02}'


def saved_location_unloaded(data,clock_offset,world_start):
    """Recognize the empty location envelope, not arbitrary unknown map data."""
    if struct.unpack_from('<I',data,4)[0]!=0x134:return None
    offset=clock_offset-0x2004f
    if offset-12<world_start or offset+24>clock_offset:return None
    empty=bytes(12)+b'\xff'*4+bytes(20)
    return data[offset-12:offset+24]==empty


def read_observation(path):
    data,saved_at = decode_slot(path)
    return {**read_clock(data),'saved_at':saved_at}
