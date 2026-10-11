# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Check complete theme switching, persistence and headless glass fallback."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from converter import App
from desktop import Window


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.qt = QApplication.instance() or QApplication([])

    def test_switches_glass_timeline_and_controls_without_changing_export_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); settings = QSettings(str(root / 'settings.ini'), QSettings.Format.IniFormat)
            window = Window(App(root / 'exports'), settings=settings)
            try:
                detail, target = window.detail.currentData(), window.targets.currentData()
                window.dark_mode.setChecked(True)
                self.assertTrue(window.backdrop.dark); self.assertTrue(window.backdrop.renderer.dark)
                self.assertTrue(window.timeline.property('dark')); self.assertIn('#101e30', window.styleSheet())
                self.assertEqual((window.detail.currentData(), window.targets.currentData()), (detail, target))
                window.dark_mode.setChecked(False)
                self.assertFalse(window.backdrop.dark); self.assertFalse(window.timeline.property('dark'))
                self.assertNotIn('#101e30', window.styleSheet())
            finally: window.close()

    def test_dark_choice_survives_restart_and_is_readable_without_gl(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); filename = str(root / 'settings.ini')
            settings = QSettings(filename, QSettings.Format.IniFormat)
            window = Window(App(root / 'exports'), settings=settings)
            window.dark_mode.setChecked(True); settings.sync(); window.close()
            reopened = Window(App(root / 'exports'), settings=QSettings(filename, QSettings.Format.IniFormat))
            try:
                reopened.show(); self.qt.processEvents()
                self.assertTrue(reopened.dark_mode.isChecked()); self.assertFalse(reopened.backdrop.available)
                frame = reopened.backdrop.grab().toImage()
                self.assertFalse(frame.isNull())
                self.assertLess(frame.pixelColor(5, 5).lightness(), 100)
            finally: reopened.close()
