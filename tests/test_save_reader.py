"""Encrypted container validation using generated, non-game fixtures."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from save_reader import decode_slot,read_observation,read_clock
from tests.fixtures import make_slot,make_container,WORLD_START


class SaveReaderTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.path=Path(folder.name)/'synthetic.sl2'

    def test_encrypted_file_is_decoded_without_modifying_it(self):
        slot=make_slot(clock=40000)
        self.path.write_bytes(make_container(slot))
        before=hashlib.sha256(self.path.read_bytes()).digest()
        decoded,stamp=decode_slot(self.path)
        self.assertEqual(decoded,slot)
        self.assertEqual(read_observation(self.path)['clock_seconds'],40000)
        self.assertGreater(stamp,0)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).digest(),before)

    def test_unknown_or_truncated_containers_are_rejected(self):
        for raw in (b'not a save',make_container()[:-1]):
            self.path.write_bytes(raw)
            with self.assertRaises(ValueError):decode_slot(self.path)

    def test_corruption_in_an_unused_entry_is_still_rejected(self):
        raw=bytearray(make_container());raw[-1]^=1
        self.path.write_bytes(raw)
        with self.assertRaises(ValueError):decode_slot(self.path)

    def test_overlapping_entries_are_rejected(self):
        raw=bytearray(make_container())
        first_offset=struct.unpack_from('<i',raw,64+16)[0]
        struct.pack_into('<i',raw,64+32+16,first_offset)
        self.path.write_bytes(raw)
        with self.assertRaises(ValueError):decode_slot(self.path)

    def test_owned_tail_takes_priority_over_a_zero_owner_clock_lookalike(self):
        data=bytearray(make_slot())
        offset=WORLD_START+200
        offset+=(WORLD_START+28-offset)%4
        struct.pack_into('<3I',data,offset-12,1,1,1)
        struct.pack_into('<4I',data,offset,0x134,0x134,1,0)
        self.assertEqual(read_clock(data)['clock_seconds'],23400)


if __name__=='__main__':unittest.main()
