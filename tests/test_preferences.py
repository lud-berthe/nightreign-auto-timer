"""User overlay preferences survive writing and loading a fresh app instance."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app import Panel,load_settings,SETTINGS_DEFAULTS
from timings import phase_at


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.config=Path(folder.name)/'settings.json'
        config=patch('app.CONFIG',self.config);config.start();self.addCleanup(config.stop)

    def test_first_launch_uses_half_opacity_and_top_alignment(self):
        settings=load_settings()
        self.assertEqual(settings['overlay_background_opacity'],.5)
        self.assertEqual(settings['overlay_anchor_y'],0)
        self.assertEqual(settings['edit_hotkey'],'F10')

    def test_saved_position_opacity_and_visibility_survive_reload(self):
        settings=load_settings()
        settings.update(overlay_anchor_x=.31,overlay_anchor_y=.14,overlay_x=340,
                        overlay_y=150,overlay_hidden=True,overlay_background_opacity=.72)
        Panel.save_settings(SimpleNamespace(ephemeral=False,settings=settings))
        restored=load_settings()
        for name in ('overlay_anchor_x','overlay_anchor_y','overlay_x','overlay_y',
                     'overlay_hidden','overlay_background_opacity'):
            self.assertEqual(restored[name],settings[name])

    def test_explicit_transparency_is_preserved(self):
        settings=load_settings();settings['overlay_background_opacity']=0
        Panel.save_settings(SimpleNamespace(ephemeral=False,settings=settings))
        self.assertEqual(load_settings()['overlay_background_opacity'],0)

    def test_invalid_opacity_restores_the_new_default(self):
        self.config.write_text(json.dumps({'source':'test.sl2','overlay_background_opacity':'invalid'}))
        self.assertEqual(load_settings()['overlay_background_opacity'],.5)

    def test_custom_edit_shortcut_is_saved_and_restored(self):
        settings=load_settings();settings['edit_hotkey']='ctrl + alt + e'
        Panel.save_settings(SimpleNamespace(ephemeral=False,settings=settings))
        self.assertEqual(load_settings()['edit_hotkey'],'Ctrl+Alt+E')

    def test_invalid_edit_shortcut_falls_back_to_f10(self):
        self.config.write_text(json.dumps({'source':'test.sl2','edit_hotkey':'F99'}))
        self.assertEqual(load_settings()['edit_hotkey'],'F10')

    def test_internal_options_cannot_override_calibration_or_detection(self):
        old = dict(first=1,second=2,shrink_first=3,shrink_second=4,day2_shift=50,
                   auto_start=False,auto_day2=False,hdr_mode=False)
        self.config.write_text(json.dumps(old),encoding='utf-8')
        settings=load_settings()
        self.assertTrue(old.keys().isdisjoint(settings))
        self.assertAlmostEqual(phase_at(1,0).remaining,271.75)
        self.assertAlmostEqual(phase_at(2,0).remaining,271.75)

    def test_saving_drops_legacy_and_runtime_fields(self):
        settings=load_settings()
        settings.update(first=10,auto_start=False,hdr_mode=False,elapsed=200,
                        overlay_background=True)
        Panel.save_settings(SimpleNamespace(ephemeral=False,settings=settings))
        saved=json.loads(self.config.read_text(encoding='utf-8'))
        self.assertEqual(set(saved),set(SETTINGS_DEFAULTS))
        self.assertEqual(saved['edit_hotkey'],'F10')

    def test_automatic_source_is_not_saved_as_a_fixed_path(self):
        settings=load_settings()
        Panel.save_settings(SimpleNamespace(ephemeral=False,settings=settings))
        self.assertEqual(json.loads(self.config.read_text())['source'],'')

    def test_custom_save_source_is_preserved(self):
        settings=load_settings();settings['source']='custom.sl2'
        Panel.save_settings(SimpleNamespace(ephemeral=False,settings=settings))
        self.assertEqual(load_settings()['source'],'custom.sl2')

    def test_old_background_switch_migrates_to_opacity(self):
        self.config.write_text(json.dumps({'overlay_background':True}),encoding='utf-8')
        settings=load_settings()
        self.assertEqual(settings['overlay_background_opacity'],1)
        Panel.save_settings(SimpleNamespace(ephemeral=False,settings=settings))
        self.assertNotIn('overlay_background',json.loads(self.config.read_text()))

    def test_non_object_json_uses_default_preferences(self):
        for value in ([],None,'invalid',17):
            with self.subTest(value=value):
                self.config.write_text(json.dumps(value),encoding='utf-8')
                self.assertEqual(load_settings(),SETTINGS_DEFAULTS)


if __name__=='__main__':unittest.main()
