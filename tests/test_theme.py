import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Mock external dependencies
sys.modules['caldav'] = MagicMock()
sys.modules['flask'] = MagicMock()
sys.modules['dateutil'] = MagicMock()
sys.modules['dateutil.tz'] = MagicMock()
sys.modules['dateutil.parser'] = MagicMock()
sys.modules['astral'] = MagicMock()
sys.modules['astral.sun'] = MagicMock()
sys.modules['babel'] = MagicMock()
sys.modules['babel.dates'] = MagicMock()

# Add app to path
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'app'))

from app import main

class TestTheme(unittest.TestCase):
    
    def test_force_light(self):
        with patch('app.main.THEME', 'light'):
            self.assertEqual(main.get_theme_mode(), 'light')

    def test_force_dark(self):
        with patch('app.main.THEME', 'dark'):
            self.assertEqual(main.get_theme_mode(), 'dark')

    def test_auto_default(self):
        # Assuming LATITUDE/LONGITUDE are not set in the environment where test runs
        # It should default to 'dark' if lat/long are missing
        with patch('app.main.THEME', 'auto'):
            # Ensure lat/long are None for this test to hit the default fallback
            with patch('app.main.LATITUDE', None):
                self.assertEqual(main.get_theme_mode(), 'dark')

if __name__ == '__main__':
    unittest.main()
