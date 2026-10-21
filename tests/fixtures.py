"""Synthetic format fixtures: no game save or account data is distributed."""
import hashlib
import struct
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
from engine import Observation,MORNING
from save_reader import KEY,read_clock

INVENTORY_END=0x14+5120*8
MARKER_OFFSET=INVENTORY_END+0x94+64
LOADOUT=INVENTORY_END+0x94+0x5b8+4+3065*14+0x21a
WORLD_START=LOADOUT+8
MAP_OFFSET=WORLD_START+65
CLOCK_OFFSET=MAP_OFFSET+0x2004f


def make_slot(clock=MORNING,active=True,map_id='m60_42_37_00',unloaded=False,play_time=100000):
    length=((CLOCK_OFFSET+80+15)//16)*16
    data=bytearray(length)
    struct.pack_into('<I',data,0,length-16)
    struct.pack_into('<I',data,4,0x134)
    struct.pack_into('<I',data,12,play_time)
    marker=bytearray.fromhex('ffff000000000000000e0e008cc30000')
    marker[10]=14 if active else 0
    data[MARKER_OFFSET:MARKER_OFFSET+16]=marker
    struct.pack_into('<HHI',data,LOADOUT,0xc2,0,0)
    if unloaded:
        data[MAP_OFFSET:MAP_OFFSET+4]=b'\xff'*4
    else:
        parts=[int(part) for part in map_id[1:].split('_')]
        data[MAP_OFFSET:MAP_OFFSET+4]=bytes(reversed(parts))
        struct.pack_into('<3f',data,MAP_OFFSET-12,1,2,3)
        data[MAP_OFFSET+20]=1
    hours,remainder=divmod(clock,3600);minutes,seconds=divmod(remainder,60)
    struct.pack_into('<3I',data,CLOCK_OFFSET,hours,minutes,seconds)
    struct.pack_into('<4I',data,CLOCK_OFFSET+12,0x134,0x134,1,0)
    # Lower bound of the documented owner range, not a player's account.
    struct.pack_into('<Q',data,CLOCK_OFFSET+28,0x0110000100000000)
    data[-28:-12]=hashlib.md5(data[4:-28]).digest()
    data[-12:]=bytes([12])*12
    return bytes(data)


def make_container(slot=None):
    slot=slot or make_slot()
    generic=bytearray(48)
    generic[-28:-12]=hashlib.md5(generic[4:-28]).digest()
    generic[-12:]=bytes([12])*12
    header=bytearray(512);header[:4]=b'BND4'
    struct.pack_into('<I',header,12,14)
    encrypted=[];offset=512
    for index,entry in enumerate([slot]+[bytes(generic)]*13):
        iv=bytes([index])*16
        encryptor=Cipher(algorithms.AES(KEY),modes.CBC(iv)).encryptor()
        payload=iv+encryptor.update(entry)+encryptor.finalize()
        descriptor=64+32*index
        header[descriptor:descriptor+8]=bytes.fromhex('40000000ffffffff')
        struct.pack_into('<iii',header,descriptor+8,len(payload),len(entry),offset)
        encrypted.append(payload);offset+=len(payload)
    return bytes(header)+b''.join(encrypted)


def expedition_samples():
    sequence=[
        (0,MORNING,False,'m10_00_00_00',False),
        (5,MORNING+2,True,'m60_42_37_00',True),
        (20,40000,True,'m60_42_37_00',False),
        (900,86398,True,'m60_42_37_00',False),
        (940,MORNING+2,True,'m60_42_37_00',False),
        (980,50000,True,'m60_42_37_00',False),
        (1820,86398,True,'m60_42_37_00',False),
        (1880,86398,True,'m12_00_00_00',False),
        (1920,86398,True,'m19_00_00_00',False),
        (2000,MORNING,False,'m10_00_00_00',False),
    ]
    for elapsed,clock,active,map_id,unloaded in sequence:
        c=read_clock(make_slot(clock,active,map_id,unloaded,100000+elapsed*1000))
        yield Observation(c['clock_seconds'],10000+elapsed,10000+elapsed+.5,
            c['play_time_ms'],c['expedition_active'],c['map_id'],c['location_unloaded'])
