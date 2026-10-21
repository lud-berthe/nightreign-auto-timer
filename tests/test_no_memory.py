"""Runtime safety and automatic transition regressions."""
import ast
from pathlib import Path
import unittest

from engine import TimerEngine,Observation,MORNING
from save_reader import read_clock
from tests.fixtures import make_slot,MARKER_OFFSET
from timings import phase_at,overlay_active,compact_text

ROOT=Path(__file__).resolve().parents[1]


class SaveOnlyTests(unittest.TestCase):
    def test_runtime_dependency_tree_has_no_memory_reader(self):
        pending,seen=['app'],set()
        while pending:
            name=pending.pop()
            if name in seen:continue
            seen.add(name)
            path=ROOT/(name+'.py')
            tree=ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.Attribute):
                    self.assertNotIn(node.attr.lower(),{'openprocess','readprocessmemory','writeprocessmemory'})
                if isinstance(node,ast.Constant) and isinstance(node.value,str):
                    self.assertNotIn(node.value.lower(),{'kernel32','kernel32.dll'})
                imports=[]
                if isinstance(node,ast.Import):imports=[alias.name for alias in node.names]
                elif isinstance(node,ast.ImportFrom) and node.module:imports=[node.module]
                for imported in imports:
                    self.assertFalse(imported.startswith(('research','live_game')),imported)
                    local=imported.split('.')[0]
                    if (ROOT/(local+'.py')).exists():pending.append(local)
        self.assertIn('save_reader',seen)
        self.assertIn('game_window',seen)

    def test_saved_bastion_marker_stops_and_rearms_the_next_expedition(self):
        timer=TimerEngine();timer.start(2,0)
        timer.observe(Observation(86399,99,100,100000,True),100)
        result=timer.observe(Observation(MORNING,199,200,200000,False),200)
        self.assertEqual(result,'auto_lobby')
        self.assertEqual(timer.day,0)
        self.assertFalse(overlay_active(timer.day))
        result=timer.observe(Observation(MORNING+2,204,205,205000,True),205)
        self.assertEqual(result,'auto_day1')
        self.assertEqual(timer.day,1)

    def test_active_day2_morning_is_not_confused_with_the_bastion(self):
        timer=TimerEngine();timer.start(1,0)
        timer.observe(Observation(86399,99,100,100000,True),100)
        result=timer.observe(Observation(MORNING,199,200,200000,True),200)
        self.assertEqual(result,'auto_day2')
        timer.observe(Observation(MORNING+73,200,201,201000,True),201)
        self.assertEqual(timer.day,2)

    def test_stale_lobby_snapshot_cannot_stop_a_running_day(self):
        timer=TimerEngine();timer.start(1,0)
        timer.observe(Observation(70000,99,100,100000,True),100)
        timer.observe(Observation(MORNING,150,210,200000,False),210)
        self.assertEqual(timer.day,1)

    def test_window_loss_has_a_grace_period_and_clears_the_timer(self):
        timer=TimerEngine();timer.start(2,0)
        timer.observe_window(True,100)
        timer.observe_window(False,101)
        timer.observe_window(False,102)
        self.assertEqual(timer.day,2)
        timer.observe_window(True,102.5)
        timer.observe_window(False,103)
        self.assertEqual(timer.observe_window(False,105),'game_window_closed')
        self.assertEqual(timer.day,0)

    def test_activity_marker_rejects_unknown_envelopes(self):
        lobby=make_slot(clock=MORNING,active=False,map_id='m10_00_00_00')
        late=make_slot(clock=86398,active=True)
        self.assertIs(read_clock(lobby)['expedition_active'],False)
        self.assertIs(read_clock(late)['expedition_active'],True)
        cleared=bytearray(lobby);cleared[MARKER_OFFSET:MARKER_OFFSET+2]=bytes(2)
        self.assertIs(read_clock(cleared)['expedition_active'],False)
        cleared[MARKER_OFFSET:MARKER_OFFSET+2]=b'xx'
        self.assertIsNone(read_clock(cleared)['expedition_active'])

    def test_day3_display_and_overlay_visibility_remain_available(self):
        settings=dict(first=271.75,second=662.1,shrink_first=180.35,shrink_second=177.1,day2_shift=0)
        self.assertEqual(compact_text(phase_at(3,0,settings)),('Day 3',''))
        self.assertFalse(overlay_active(3))
        self.assertFalse(overlay_active(0))
        for day in (1,2):
            self.assertEqual(phase_at(day,662.1,settings).key,'second_shrink')


if __name__=='__main__':unittest.main()
