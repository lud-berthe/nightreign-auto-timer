"""Portable settings follow the executable, while bundled assets stay internal."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app


class ApplicationPathTests(unittest.TestCase):
    def test_frozen_app_uses_executable_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            executable=Path(folder)/'Portable timer'/'Nightreign auto-timer.exe'
            with patch.object(app.sys,'frozen',True,create=True), patch.object(app.sys,'executable',str(executable)):
                self.assertEqual(app.application_directory(),executable.resolve().parent)
                self.assertNotEqual(app.application_directory(),app.RESOURCES)

    def test_source_run_uses_source_directory(self):
        with patch.object(app.sys,'frozen',False,create=True):
            self.assertEqual(app.application_directory(),Path(app.__file__).resolve().parent)


if __name__ == '__main__':
    unittest.main()
