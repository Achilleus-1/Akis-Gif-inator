# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Exercise shader fallback and lifecycle without requiring a GPU on CI."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from glass import AeroBackdrop


class GlassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.backdrop = AeroBackdrop(); self.backdrop.show(); self.qt.processEvents()

    def tearDown(self): self.backdrop.close_renderer(); self.backdrop.close()

    def test_headless_device_failure_keeps_still_background(self):
        self.assertFalse(self.backdrop.available)
        self.assertFalse(self.backdrop.timer.isActive())
        self.assertFalse(self.backdrop.grab().isNull())

    def test_live_toggle_stops_rendering_and_can_resume(self):
        self.backdrop.renderer = Mock(); self.backdrop.renderer.draw.return_value = QImage(20, 20, QImage.Format.Format_RGB32)
        self.backdrop.available = True; self.backdrop.set_live(True)
        self.assertTrue(self.backdrop.timer.isActive())
        self.backdrop.set_live(False); self.backdrop.renderer.draw.reset_mock()
        self.backdrop.tick(force=True)
        self.assertFalse(self.backdrop.timer.isActive()); self.backdrop.renderer.draw.assert_not_called()
        self.backdrop.set_live(True); self.backdrop.renderer.draw.assert_called_once()

    def test_shader_exception_returns_to_still_style(self):
        self.backdrop.renderer = Mock(); self.backdrop.renderer.draw.side_effect = RuntimeError('Context lost')
        self.backdrop.available = True; availability = []
        self.backdrop.availabilityChanged.connect(availability.append)
        self.backdrop.tick(force=True)
        self.assertEqual(availability, [False]); self.assertFalse(self.backdrop.available)
        self.assertFalse(self.backdrop.timer.isActive()); self.backdrop.renderer.close.assert_called_once()

    def test_hidden_window_does_not_render(self):
        self.backdrop.renderer = Mock(); self.backdrop.available = True; self.backdrop.hide()
        self.backdrop.tick(force=True); self.backdrop.renderer.draw.assert_not_called()
