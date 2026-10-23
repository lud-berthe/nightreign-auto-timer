import json
import unittest
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from engine import Observation, TimerEngine, MORNING
from timings import phase_at, countdown_color
from gamebar_view import GameBarView
from game_window import GameWindow, anchored_position, relative_position



def sample(clock, when=100, age=1):
    return Observation(clock,when-age,when,int(when*1000))


class TimerTests(unittest.TestCase):
    def test_day1_starts_from_lobby_clock_without_a_keypress(self):
        timer = TimerEngine()
        timer.observe(sample(MORNING,100),100)
        timer.observe(sample(MORNING,110),110)
        self.assertEqual(timer.day,0)
        self.assertEqual(timer.observe(sample(MORNING+2,120),120),'auto_day1')
        self.assertEqual(timer.day,1)
        self.assertAlmostEqual(timer.elapsed(120),1+2/72.86)

    def test_fresh_single_checkpoint_does_not_start_a_run(self):
        timer = TimerEngine()
        timer.observe(sample(MORNING+2,100),100)
        self.assertEqual(timer.day,0)

    def test_stale_day1_checkpoint_does_not_start_a_run(self):
        timer = TimerEngine()
        timer.observe(sample(MORNING,100),100)
        timer.observe(sample(MORNING+2,200,60),200)
        self.assertEqual(timer.day,0)

    def test_clock_change_without_play_time_change_is_not_a_departure(self):
        timer = TimerEngine()
        timer.observe(sample(MORNING,100),100)
        timer.observe(Observation(MORNING+2,199,200,100000),200)
        self.assertEqual(timer.day,0)

    def test_new_expedition_resets_the_previous_timer_automatically(self):
        timer = TimerEngine()
        timer.start(2,0)
        timer.observe(sample(15*3600,100),100)
        timer.observe(sample(MORNING,200),200)
        self.assertEqual(timer.observe(sample(MORNING+1,205),205),'auto_day1')
        self.assertEqual(timer.day,1)
        self.assertLess(timer.elapsed(205),2)

    def test_old_save_cannot_start_a_timer(self):
        timer = TimerEngine()
        timer.observe(sample(23*3600,100),100)
        timer.observe(sample(MORNING+365,200),200)
        self.assertEqual(timer.day,0)

    def test_fresh_morning_recales_day2_and_counts_already_elapsed_time(self):
        timer = TimerEngine()
        timer.start(1,0)
        timer.observe(sample(23*3600),100)
        result = timer.observe(sample(MORNING+365,200),200)
        self.assertEqual(result,'auto_day2')
        self.assertEqual(timer.day,2)
        self.assertGreater(timer.elapsed(200),5)
        self.assertLess(timer.elapsed(200),8)

    def test_return_to_lobby_then_departure_starts_a_new_day1(self):
        timer = TimerEngine()
        timer.start(1,0)
        timer.observe(sample(23*3600),100)
        self.assertEqual(timer.observe(sample(MORNING,200),200),'ambiguous_morning')
        self.assertEqual(timer.observe(sample(MORNING+1,201),201),'auto_day1')
        self.assertEqual(timer.day,1)
        self.assertFalse(timer.transition_pending)
        self.assertLess(timer.elapsed(201),2)

    def test_auto_start_can_be_disabled(self):
        timer = TimerEngine()
        timer.auto_start = False
        timer.observe(sample(MORNING,100),100)
        timer.observe(sample(MORNING+1,101),101)
        self.assertEqual(timer.day,0)

    def test_stale_checkpoint_never_changes_the_day(self):
        timer = TimerEngine()
        timer.start(1,0)
        timer.observe(sample(23*3600),100)
        timer.observe(sample(MORNING+365,200,90),200)
        self.assertEqual(timer.day,1)

    def test_stopping_blocks_a_later_false_morning(self):
        timer = TimerEngine()
        timer.start(1,0)
        timer.observe(sample(23*3600),100)
        timer.stop()
        timer.observe(sample(MORNING+365,200),200)
        self.assertEqual(timer.day,0)

    def test_time_alone_does_not_change_days(self):
        timer = TimerEngine()
        timer.start(1,0)
        self.assertEqual(timer.elapsed(10000),10000)
        self.assertEqual(timer.day,1)

    def test_save_only_day3_is_not_guessed(self):
        timer = TimerEngine()
        timer.start(2,0)
        timer.observe(sample(23*3600),100)
        timer.observe(sample(MORNING+365,200),200)
        self.assertEqual(timer.day,2)

    def test_auto_can_be_disabled(self):
        timer = TimerEngine()
        timer.start(1,0)
        timer.auto_day2 = False
        timer.observe(sample(23*3600),100)
        timer.observe(sample(MORNING+365,200),200)
        self.assertEqual(timer.day,1)

    def test_changing_source_clears_the_detector(self):
        timer = TimerEngine()
        timer.start(1,0)
        timer.observe(sample(23*3600),100)
        timer.reset_source()
        timer.observe(sample(MORNING+365,200),200)
        self.assertEqual(timer.day,0)


class PhaseTests(unittest.TestCase):

    def test_closures_switch_from_waiting_to_shrinking_then_to_boss(self):
        for elapsed,key,remaining in [(0,'first_wait',271.75),(271.75,'first_shrink',180.35),
                (452.1,'second_wait',210),(662.1,'second_shrink',177.1),(839.2,'boss',None)]:
            with self.subTest(elapsed=elapsed):
                phase = phase_at(1,elapsed)
                self.assertEqual(phase.key,key)
                if remaining is None:self.assertIsNone(phase.remaining)
                else:self.assertAlmostEqual(phase.remaining,remaining)

    def test_second_day_restarts_its_sequence_from_the_observed_start(self):
        self.assertEqual(phase_at(2,0).remaining,271.75)
        self.assertEqual(phase_at(2,662.1).key,'second_shrink')
        self.assertEqual(phase_at(2,839.2).key,'boss')

    def test_boss_duration_is_unbounded_and_never_creates_a_new_day(self):
        timer = TimerEngine()
        timer.start(1,0)
        self.assertEqual(phase_at(timer.day,timer.elapsed(5000)).key,'boss')
        self.assertEqual(timer.day,1)
        timer.start(2,5000)
        self.assertEqual(phase_at(timer.day,timer.elapsed(5000)).key,'first_wait')

    def test_idle_and_final_do_not_show_a_storm_countdown(self):
        self.assertIsNone(phase_at(0,0).remaining)
        self.assertEqual(phase_at(3,100).key,'final')

    def test_last_minute_warning_resets_when_the_next_phase_begins(self):
        self.assertEqual(countdown_color(phase_at(1,211.75)),'#ffffff')
        self.assertEqual(countdown_color(phase_at(1,212.75)),'#ff766b')
        self.assertEqual(countdown_color(phase_at(1,271.75)),'#ffffff')


class GameBarTests(unittest.TestCase):
    def test_local_view_shares_the_phase_and_does_not_serve_local_files(self):
        view = GameBarView(port=0)
        try:
            settings={'overlay_background_opacity':0.35}
            view.publish(1,phase_at(1,212.75),'Save file read',settings)
            with urlopen(view.url+'state',timeout=2) as response:
                state = json.load(response)
            self.assertEqual((state['day'],state['phase'],state['remaining']),(1,'first_wait',59))
            self.assertTrue(state['visible'])
            self.assertEqual(state['background_opacity'],0.35)
            self.assertNotIn('source',state)
            view.publish(1,phase_at(1,212.75),'',dict(settings,overlay_hidden=True))
            with urlopen(view.url+'state',timeout=2) as response:hidden=json.load(response)
            self.assertFalse(hidden['visible'])
            for day in (3,0):
                view.publish(day,phase_at(day,0),'',{})
                with urlopen(view.url+'state',timeout=2) as response:hidden = json.load(response)
                self.assertFalse(hidden['visible'])
                self.assertEqual((hidden['title'],hidden['clock']),('',''))
            with urlopen(view.url,timeout=2) as response:
                self.assertIn('role="timer"',response.read().decode('utf-8'))
            with self.assertRaises(HTTPError) as missing:
                urlopen(view.url+'settings.json',timeout=2)
            self.assertEqual(missing.exception.code,404)
            with self.assertRaises(HTTPError) as host:
                urlopen(Request(view.url+'state',headers={'Host':'other.example'}),timeout=2)
            self.assertEqual(host.exception.code,403)
        finally:view.close()


class WindowFollowingTests(unittest.TestCase):
    def test_overlay_moves_with_the_client_area_and_stays_centered_on_resize(self):
        game = GameWindow(1,1,100,120,1200,800)
        self.assertEqual(anchored_position(game,(200,80)),(600,120))
        moved = GameWindow(1,1,350,200,1600,900)
        self.assertEqual(anchored_position(moved,(200,80)),(1050,200))

    def test_dragged_anchor_is_preserved_on_a_monitor_left_of_the_primary(self):
        game = GameWindow(1,1,-1920,100,1600,900)
        position = (-1700,190)
        anchor = relative_position(game,position,(200,80))
        self.assertEqual(anchored_position(game,(200,80),*anchor),position)

    def test_anchor_is_clamped_inside_a_smaller_game_window(self):
        game = GameWindow(1,1,10,30,500,400)
        self.assertEqual(anchored_position(game,(200,80),1,1),(310,350))


if __name__=='__main__':
    unittest.main()
