"""Suspension and resume checks using synthetic observations only."""
import struct
import unittest
from engine import TimerEngine,Observation,MORNING
from save_reader import read_clock
from tests.fixtures import make_slot,expedition_samples
from timings import overlay_active


class SaveSessionTests(unittest.TestCase):
    def sample(self,clock=23872,when=100,play=100000,unloaded=True,age=.5):
        return Observation(clock,when-age,when,play,True,None,unloaded)

    def suspend(self,day=1):
        timer=TimerEngine();timer.start(day,90)
        timer.observe(self.sample(),100)
        self.assertEqual(timer.day,day)
        self.assertEqual(timer.observe(self.sample(when=105),105),'save_session_suspended')
        return timer

    def test_empty_location_is_distinct_from_loaded_and_unknown_layouts(self):
        self.assertTrue(read_clock(make_slot(unloaded=True))['location_unloaded'])
        self.assertFalse(read_clock(make_slot(map_id='m10_00_00_00'))['location_unloaded'])
        data=bytearray(make_slot(unloaded=True));struct.pack_into('<I',data,4,0x135)
        self.assertIsNone(read_clock(data)['location_unloaded'])

    def test_repeated_unloaded_checkpoints_suspend_all_days(self):
        for day in (1,2,3):
            with self.subTest(day=day):
                timer=self.suspend(day)
                self.assertEqual(timer.day,0)
                self.assertIsNone(timer.started_at)
                self.assertFalse(overlay_active(timer.day))
                self.assertIsNotNone(timer.suspended_run)

    def test_initial_loading_with_advancing_playtime_never_suspends(self):
        timer=TimerEngine();timer.start(1,90)
        timer.observe(self.sample(),100)
        timer.observe(self.sample(when=105,play=105000),105)
        self.assertEqual(timer.day,1)
        self.assertIsNone(timer.suspended_run)

    def test_frozen_boss_clock_with_loaded_location_does_not_suspend(self):
        timer=TimerEngine();timer.start(2,90)
        timer.observe(self.sample(clock=86398,unloaded=False),100)
        timer.observe(self.sample(clock=86398,when=105,unloaded=False),105)
        self.assertEqual(timer.day,2)

    def test_unknown_location_stale_data_and_duplicate_save_are_not_exit_signals(self):
        for second in (self.sample(when=105,unloaded=None),self.sample(when=150,age=60),
                       self.sample(when=105,age=5.5),self.sample(when=130)):
            with self.subTest(sample=second):
                timer=TimerEngine();timer.start(1,90)
                timer.observe(self.sample(),100)
                timer.observe(second,second.observed_at)
                self.assertEqual(timer.day,1)

    def test_resume_excludes_time_outside_the_session(self):
        timer=self.suspend(2)
        self.assertIsNone(timer.observe(self.sample(when=110),110))
        self.assertEqual(timer.observe(self.sample(when=300,play=105000),300),'save_session_resumed')
        self.assertEqual(timer.day,2)
        self.assertAlmostEqual(timer.elapsed(300),20)
        self.assertIsNone(timer.suspended_run)

    def test_bastion_clears_suspension_and_rearms_the_next_expedition(self):
        timer=self.suspend()
        timer.observe(Observation(MORNING,299,300,130000,False,'m10_00_00_00',False),300)
        self.assertIsNone(timer.suspended_run)
        self.assertEqual(timer.day,0)
        self.assertEqual(timer.observe(Observation(MORNING+2,304,305,135000,True,None,True),305),'auto_day1')

    def test_saved_day2_and_day3_transitions_take_priority_when_resuming(self):
        timer=TimerEngine();timer.start(1,90)
        timer.observe(self.sample(clock=86398),100)
        timer.observe(self.sample(clock=86398,when=105),105)
        self.assertEqual(timer.observe(self.sample(clock=MORNING+20,when=300,play=105000),300),'auto_day2')
        timer=self.suspend(2)
        sample=Observation(86398,299,300,105000,True,'m12_00_00_00',False)
        self.assertEqual(timer.observe(sample,300),'auto_day3')
        self.assertIsNone(timer.suspended_run)

    def test_complete_expedition_has_no_spurious_suspension(self):
        timer=TimerEngine();events=[]
        for sample in expedition_samples():
            event=timer.observe(sample,sample.observed_at)
            if event:events.append(event)
        self.assertEqual(events,['auto_day1','auto_day2','auto_day3','auto_lobby'])

    def test_repeated_exit_writes_suspend_only_once(self):
        timer=TimerEngine();timer.start(1,90)
        events=[]
        for when in (100,105,110):
            event=timer.observe(self.sample(when=when),when)
            if event:events.append(event)
        self.assertEqual(events,['save_session_suspended'])
        self.assertEqual(timer.day,0)


if __name__=='__main__':unittest.main()
