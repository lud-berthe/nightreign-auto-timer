import unittest
from hotkeys import parse_edit_hotkey


class HotkeyTests(unittest.TestCase):
    def test_function_keys_use_the_windows_virtual_key_codes(self):
        self.assertEqual(parse_edit_hotkey('F10'),('F10',0,0x79))
        self.assertEqual(parse_edit_hotkey('f1'),('F1',0,0x70))
        self.assertEqual(parse_edit_hotkey('F24'),('F24',0,0x87))

    def test_optional_modifiers_are_normalized(self):
        self.assertEqual(parse_edit_hotkey(' shift + control + e '),('Ctrl+Shift+E',6,0x45))
        self.assertEqual(parse_edit_hotkey('Ctrl+Alt+F10'),('Ctrl+Alt+F10',3,0x79))

    def test_named_keys_and_digits(self):
        self.assertEqual(parse_edit_hotkey('Alt+Home'),('Alt+Home',1,0x24))
        self.assertEqual(parse_edit_hotkey('Ctrl+1'),('Ctrl+1',2,0x31))

    def test_invalid_shortcuts_are_rejected(self):
        for value in ('','F0','F25','Ctrl+','Ctrl+Ctrl+E','Win+E','F10+F11',None,5):
            with self.subTest(value=value),self.assertRaises(ValueError):parse_edit_hotkey(value)


if __name__=='__main__':unittest.main()
