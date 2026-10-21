"""Location parsing and automatic transitions, without private save files."""
import struct
import unittest
from engine import TimerEngine,Observation
from save_reader import read_clock
from tests.fixtures import make_slot,MAP_OFFSET
from timings import overlay_active


class SavedLocationTests(unittest.TestCase):
    def observation(self,map_id,when=100,age=.5):
        clock=23400 if map_id=='m10_00_00_00' else 86398
        active=map_id!='m10_00_00_00'
        c=read_clock(make_slot(clock,active,map_id))
        return Observation(c['clock_seconds'],when-age,when,c['play_time_ms'],
                           c['expedition_active'],c['map_id'],c['location_unloaded'])

    def test_known_locations_are_parsed(self):
        for map_id in ('m60_44_37_00','m12_00_00_00','m19_00_00_00','m10_00_00_00'):
            with self.subTest(map=map_id):
                self.assertEqual(read_clock(make_slot(map_id=map_id))['map_id'],map_id)

    def test_day3_and_lobby_are_distinguished_with_a_frozen_clock(self):
        timer=TimerEngine();timer.start(2,0)
        before=self.observation('m60_44_37_00',100)
        timer.observe(before,100)
        arrived=self.observation('m12_00_00_00',110)
        self.assertEqual(before.clock_seconds,arrived.clock_seconds)
        self.assertEqual(timer.observe(arrived,110),'auto_day3')
        self.assertFalse(overlay_active(timer.day))
        timer.observe(self.observation('m19_00_00_00',120),120)
        self.assertEqual(timer.day,3)
        self.assertEqual(timer.observe(self.observation('m10_00_00_00',130),130),'auto_lobby')
        self.assertEqual(timer.day,0)

    def test_fresh_final_area_can_identify_day3_on_startup(self):
        timer=TimerEngine()
        self.assertEqual(timer.observe(self.observation('m12_00_00_00'),100),'auto_day3')

    def test_stale_final_area_and_skyboxes_do_not_change_day(self):
        timer=TimerEngine();timer.start(2,0)
        timer.observe(self.observation('m12_00_00_00',100,60),100)
        timer.observe(Observation(86398,199,200,200000,True,'m12_00_00_99'),200)
        self.assertEqual(timer.day,2)

    def test_unknown_layout_and_invalid_location_padding_fail_closed(self):
        data=bytearray(make_slot(map_id='m12_00_00_00'))
        data[MAP_OFFSET+4]=1
        self.assertIsNone(read_clock(data)['map_id'])
        data=bytearray(make_slot(map_id='m12_00_00_00'))
        struct.pack_into('<I',data,4,0x135)
        self.assertIsNone(read_clock(data)['map_id'])


if __name__=='__main__':unittest.main()
