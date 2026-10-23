"""Game lifecycle, opt-in startup registration and instance coordination."""
from pathlib import Path
from types import SimpleNamespace
import json
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import app
import lifecycle
from lifecycle import GameLifecycle,InstanceLock,instance_running


class GameLifecycleTests(unittest.TestCase):
    def test_game_exit_during_timer_startup_still_closes_an_auto_started_timer(self):
        session=GameLifecycle(initially_running=True)
        self.assertEqual(session.observe(False,0),'closed')

    def test_default_closes_on_first_missing_window_observation(self):
        session=GameLifecycle()
        self.assertEqual(session.observe(True,10),'opened')
        self.assertEqual(session.observe(False,10.1),'closed')

    def test_no_close_before_a_game_has_been_seen(self):
        session=GameLifecycle()
        self.assertIsNone(session.observe(False,0))
        self.assertIsNone(session.observe(False,100))

    def test_optional_grace_period(self):
        session=GameLifecycle(close_delay=5)
        self.assertEqual(session.observe(True,0),'opened')
        self.assertIsNone(session.observe(False,1))
        self.assertIsNone(session.observe(False,5.9))
        self.assertEqual(session.observe(False,6),'closed')
        self.assertIsNone(session.observe(False,7))
        self.assertEqual(session.observe(True,8),'opened')

    def test_a_temporary_window_loss_with_explicit_grace(self):
        session=GameLifecycle(close_delay=5)
        session.observe(True,0);session.observe(False,1)
        self.assertIsNone(session.observe(True,3))
        self.assertIsNone(session.observe(False,4))
        self.assertIsNone(session.observe(False,8))
        self.assertEqual(session.observe(False,9),'closed')

    def test_watcher_launches_once_per_game_run_not_after_manual_timer_close(self):
        tracker=MagicMock()
        tracker.current.side_effect=[object(),object(),None,None,object()]
        settings=[{'open_with_game':True}]*5+[{'open_with_game':False}]
        with patch('app.GameWindowTracker',return_value=tracker), patch('app.load_settings',side_effect=settings), \
             patch('app.time.monotonic',side_effect=[0,1,2,7,8]), patch('app.time.sleep'), \
             patch('app.instance_running',return_value=False), patch('app.launch_process') as launch:
            app.watch_game()
        self.assertEqual(launch.call_count,2)

    def test_existing_window_prevents_an_automatic_duplicate(self):
        tracker=MagicMock();tracker.current.side_effect=[object(),object()]
        with patch('app.GameWindowTracker',return_value=tracker), \
             patch('app.load_settings',side_effect=[{'open_with_game':True}]*2+[{'open_with_game':False}]), \
             patch('app.time.monotonic',side_effect=[0,1]), patch('app.time.sleep'), \
             patch('app.instance_running',side_effect=[True]), patch('app.launch_process') as launch:
            app.watch_game()
        launch.assert_not_called()

    def test_disabled_watcher_does_not_open_a_window(self):
        with patch('app.load_settings',return_value={'open_with_game':False}), \
             patch('app.GameWindowTracker'), patch('app.launch_process') as launch:
            app.watch_game()
        launch.assert_not_called()


class InstanceTests(unittest.TestCase):
    def test_coordination_does_not_create_files_beside_the_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            lock=InstanceLock(folder,'window')
            self.assertTrue(lock.acquire())
            try:self.assertEqual(list(Path(folder).iterdir()),[])
            finally:lock.release()

    def test_installations_do_not_share_the_same_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertNotEqual(InstanceLock(Path(folder)/'a','window').path,
                                InstanceLock(Path(folder)/'b','window').path)

    def test_window_and_watcher_are_independent_and_released(self):
        with tempfile.TemporaryDirectory() as folder:
            window=InstanceLock(folder,'window');watcher=InstanceLock(folder,'watcher')
            try:
                self.assertTrue(window.acquire())
                self.assertTrue(instance_running(folder,'window'))
                self.assertFalse(instance_running(folder,'watcher'))
                self.assertTrue(watcher.acquire())
                self.assertTrue(instance_running(folder,'watcher'))
            finally:window.release();watcher.release()
            self.assertFalse(instance_running(folder,'window'))
            self.assertFalse(instance_running(folder,'watcher'))


class StartupTests(unittest.TestCase):
    def test_startup_command_is_quoted_and_scoped_to_current_user(self):
        registry=MagicMock()
        command=[r'C:\Portable apps\Nightreign auto-timer.exe']
        with patch.dict('sys.modules',{'winreg':registry}):
            lifecycle.configure_startup(True,command)
        registry.CreateKeyEx.assert_called_once_with(registry.HKEY_CURRENT_USER,lifecycle.RUN_KEY,0,registry.KEY_SET_VALUE)
        value=registry.SetValueEx.call_args.args[-1]
        self.assertEqual(value,subprocess.list2cmdline([*command,'--watch']))

    def test_disabling_removes_only_the_apps_startup_value(self):
        registry=MagicMock()
        with patch.dict('sys.modules',{'winreg':registry}):
            lifecycle.configure_startup(False,['timer.exe'])
        self.assertEqual(registry.DeleteValue.call_args.args[-1],lifecycle.RUN_VALUE)
        registry.SetValueEx.assert_not_called()

    def test_independent_child_does_not_share_the_parents_extracted_runtime(self):
        with patch('lifecycle.subprocess.Popen') as launch:
            lifecycle.launch_process(['timer.exe','--watch'],Path('.'))
        self.assertEqual(launch.call_args.kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'],'1')


class CheckboxTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.config=Path(folder.name)/'settings.json'
        config=patch('app.CONFIG',self.config);config.start();self.addCleanup(config.stop)
        startup=patch('app.configure_startup');self.startup=startup.start();self.addCleanup(startup.stop)
        watcher=patch('app.ensure_watcher');self.watcher=watcher.start();self.addCleanup(watcher.stop)

    def panel(self,opened=False,closed=False):
        settings=app.SETTINGS_DEFAULTS.copy();settings.update(open_with_game=opened,close_with_game=closed)
        return SimpleNamespace(settings=settings,ephemeral=False,
            open_with_game=MagicMock(get=MagicMock(return_value=opened)),
            close_with_game=MagicMock(get=MagicMock(return_value=closed)),hint_label=MagicMock())

    def test_open_checkbox_enables_startup_and_starts_the_watcher(self):
        panel=self.panel();panel.open_with_game.get.return_value=True
        app.Panel.update_automation(panel)
        self.assertTrue(json.loads(self.config.read_text())['open_with_game'])
        self.assertTrue(self.startup.call_args.args[0]);self.watcher.assert_called_once()

    def test_close_checkbox_is_independent_of_startup(self):
        panel=self.panel();panel.close_with_game.get.return_value=True
        app.Panel.update_automation(panel)
        self.assertTrue(json.loads(self.config.read_text())['close_with_game'])
        self.startup.assert_not_called();self.watcher.assert_not_called()

    def test_unchecking_open_keeps_close_preference_and_removes_startup(self):
        panel=self.panel(opened=True,closed=True);panel.open_with_game.get.return_value=False
        app.Panel.update_automation(panel)
        self.startup.assert_called_once_with(False,app.application_command())
        self.watcher.assert_not_called()
        saved=json.loads(self.config.read_text())
        self.assertFalse(saved['open_with_game']);self.assertTrue(saved['close_with_game'])

    def test_failed_registration_restores_checkbox_and_saved_settings(self):
        panel=self.panel();panel.open_with_game.get.return_value=True
        self.startup.side_effect=[PermissionError('denied'),None]
        app.Panel.update_automation(panel)
        self.assertFalse(panel.settings['open_with_game'])
        self.assertFalse(json.loads(self.config.read_text())['open_with_game'])
        panel.open_with_game.set.assert_called_with(False)
        self.watcher.assert_not_called()


if __name__=='__main__':unittest.main()
