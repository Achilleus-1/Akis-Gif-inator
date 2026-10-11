# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Native Qt desktop UI. No browser, HTML, or local HTTP server."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import traceback

from PySide6.QtCore import Qt, Signal, QObject, QTimer, QUrl, QRectF, QSize, QSettings
from PySide6.QtGui import QColor, QPainter, QPen, QImage, QPixmap, QMovie, QDesktopServices, QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QStackedWidget, QFileDialog, QDoubleSpinBox,
    QComboBox, QProgressBar, QSizePolicy, QMessageBox, QCheckBox,
)

from converter import App, ROOT, CREATE_NO_WINDOW, PROFILES
from glass import AeroBackdrop, GlassPanel

APP_NAME = "Aki's Gif-inator"
VERSION = "1.2.0"
ASSETS = Path(getattr(sys, "_MEIPASS", ROOT)) / "assets"


def time_label(seconds: float) -> str:
    seconds = max(0, seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, rest = divmod(remainder, 60)
    return f"{int(hours)}:{int(minutes):02}:{rest:04.1f}" if hours else f"{int(minutes)}:{rest:04.1f}"


def size_label(size: int) -> str:
    return f"{size / 1_000_000:.2f} MB" if size >= 1_000_000 else f"{size / 1000:.0f} KB"


class Bridge(QObject):
    loaded = Signal(int, object, str)
    thumbs = Signal(int, object)


class TrimBar(QWidget):
    """A genuine range timeline: two trim handles plus an independent playhead."""
    selectionChanged = Signal(float, float)
    seekRequested = Signal(float)

    def __init__(self):
        super().__init__()
        self.duration = self.start = self.end = self.position = 0.0
        self.images = []
        self.dragging = None
        self.active_handle = "start"
        self.setMinimumHeight(115)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Video trim timeline")
        self.setAccessibleDescription("Drag the left and right handles to trim. Click inside to seek. Use left/right arrows to move a handle; press Tab to switch handles. Exact times are available below.")
        self.setToolTip("Drag either blue handle to trim. Click the strip to preview a frame. Arrow keys adjust the focused handle; Tab switches handles.")

    def set_video(self, duration):
        self.duration = max(0, duration)
        self.start, self.end, self.position = 0, self.duration, 0
        self.images = []
        self.update()

    def set_selection(self, start, end, emit=False):
        gap = min(0.05, self.duration)
        self.start = min(max(0, start), max(0, self.duration - gap))
        self.end = min(self.duration, max(self.start + gap, end))
        self.update()
        if emit:
            self.selectionChanged.emit(self.start, self.end)

    def area(self):
        return QRectF(14, 18, max(1, self.width() - 28), 58)

    def x_for(self, seconds):
        rect = self.area()
        return rect.left() + rect.width() * seconds / max(self.duration, 0.001)

    def time_for(self, x):
        rect = self.area()
        return min(self.duration, max(0, (x - rect.left()) / rect.width() * self.duration))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.area()
        p.setPen(Qt.PenStyle.NoPen)
        dark = bool(self.property('dark'))
        p.setBrush(QColor("#193549" if dark else "#d4e7ef"))
        p.drawRoundedRect(rect, 7, 7)
        p.save()
        p.setClipRect(rect)
        for i, image in enumerate(self.images):
            tile = QRectF(rect.left() + i * rect.width() / len(self.images), rect.top(), rect.width() / len(self.images) + 1, rect.height())
            p.drawImage(tile, image)
        left, right = self.x_for(self.start), self.x_for(self.end)
        if self.duration:
            p.fillRect(QRectF(rect.left(), rect.top(), left - rect.left(), rect.height()), QColor(12, 13, 19, 195))
            p.fillRect(QRectF(right, rect.top(), rect.right() - right, rect.height()), QColor(12, 13, 19, 195))
            p.fillRect(QRectF(left, rect.top(), right - left, rect.height()), QColor(30, 177, 207, 22))
        p.restore()
        if self.duration:
            p.setPen(QPen(QColor("#058eb6"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(left, rect.top(), right - left, rect.height()))
            for name, x in (("start", left), ("end", right)):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#b0f1e5" if self.hasFocus() and self.active_handle == name else "#069dc7"))
                p.drawRoundedRect(QRectF(x - 6, rect.top() - 3, 12, rect.height() + 6), 4, 4)
                p.setPen(QPen(QColor("#e8fbff"), 2))
                p.drawLine(int(x), int(rect.top() + 21), int(x), int(rect.bottom() - 21))
            play = self.x_for(self.position)
            p.setPen(QPen(QColor("#ffffff"), 2))
            p.drawLine(int(play), 12, int(play), 83)
        p.setPen(QColor("#b5d9e7" if dark else "#52758a"))
        font = p.font(); font.setPointSize(8); p.setFont(font)
        p.drawText(QRectF(14, 86, 100, 22), Qt.AlignmentFlag.AlignLeft, time_label(0))
        p.drawText(QRectF(14, 86, rect.width(), 22), Qt.AlignmentFlag.AlignRight, time_label(self.duration))
        p.drawText(QRectF(14, 86, rect.width(), 22), Qt.AlignmentFlag.AlignCenter, "Drag the ends to trim" if self.duration else "Your timeline appears here")

    def mousePressEvent(self, event):
        if not self.duration or event.button() != Qt.MouseButton.LeftButton:
            return
        self.setFocus()
        x = event.position().x()
        a, b = abs(x - self.x_for(self.start)), abs(x - self.x_for(self.end))
        if min(a, b) <= 14:
            self.dragging = "start" if a <= b else "end"
            self.active_handle = self.dragging
        else:
            self.dragging = "seek"
        self.move_to(x)

    def move_to(self, x):
        seconds = self.time_for(x)
        if self.dragging == "start":
            self.set_selection(min(seconds, self.end - min(0.05, self.duration)), self.end, True)
            self.seekRequested.emit(self.start)
        elif self.dragging == "end":
            self.set_selection(self.start, max(seconds, self.start + min(0.05, self.duration)), True)
            self.seekRequested.emit(max(self.start, self.end - 0.05))
        else:
            self.position = seconds
            self.seekRequested.emit(seconds)
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move_to(event.position().x())

    def mouseReleaseEvent(self, _event):
        self.dragging = None

    def focusNextPrevChild(self, forward):
        if forward and self.active_handle == "start" and self.hasFocus():
            self.active_handle = "end"; self.update(); return True
        return super().focusNextPrevChild(forward)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right) and self.duration:
            delta = 1 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 0.1
            if event.key() == Qt.Key.Key_Left:
                delta = -delta
            if self.active_handle == "start":
                self.set_selection(min(self.end - 0.05, self.start + delta), self.end, True)
                self.seekRequested.emit(self.start)
            else:
                self.set_selection(self.start, self.end + delta, True)
                self.seekRequested.emit(max(self.start, self.end - 0.05))
        else:
            super().keyPressEvent(event)


class GifPreview(QLabel):
    def __init__(self):
        super().__init__("Your GIF will appear here")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(240, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setObjectName('gifPreview')
        self.animation = None
        self.original = QSize()

    def load(self, path):
        self.clear_preview()
        self.original = QImage(path).size()
        self.animation = QMovie(path)
        self.setMovie(self.animation)
        self.fit()
        self.animation.start()

    def clear_preview(self):
        if self.animation:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None
        self.setText("A good loop is worth sharing.\n\nYour GIF will appear here.")

    def fit(self):
        if self.animation and not self.original.isEmpty():
            self.animation.setScaledSize(self.original.scaled(self.size() - QSize(12, 12), Qt.AspectRatioMode.KeepAspectRatio))

    def resizeEvent(self, event):
        self.fit()
        super().resizeEvent(event)


STYLE = """
QMainWindow { background:#c9e9ef; }
QWidget { font-family:'Segoe UI'; font-size:12px; color:#153d56; }
QFrame#panel, QFrame#glassHeader { background:transparent; border:0; }
QFrame#glassHeader QLabel, QFrame#glassHeader QCheckBox { color:#e9faff; }
QLabel#brand { font-size:27px; font-weight:600; color:white; }
QLabel#brandCredit { font-size:10px; color:#c4ecf5; }
QLabel#headline { font-size:25px; font-weight:600; color:#153e59; }
QLabel#muted { color:#52758a; font-size:11px; }
QLabel#heading { font-size:15px; font-weight:600; color:#174d65; }
QLabel#pill { color:#21627a; font-size:10px; background:rgba(255,255,255,115); border:1px solid rgba(255,255,255,215); border-radius:13px; padding:6px 12px; }
QLabel#notice { color:#6b4c13; background:rgba(255,248,226,235); border:1px solid #dabf83; border-radius:12px; padding:10px; }
QPushButton { border:1px solid rgba(255,255,255,230); background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(255,255,255,230),stop:1 rgba(228,245,251,160)); border-radius:11px; padding:8px 13px; color:#235971; }
QPushButton:hover { border-color:#6fc6dc; background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #ffffff,stop:1 #d5f3f9); }
QPushButton:pressed { background:#c4e9f3; }
QPushButton:focus { border:2px solid #087da6; padding:7px 12px; }
QPushButton:disabled { color:#819ca9; background:rgba(255,255,255,85); border-color:rgba(255,255,255,150); }
QPushButton#primary { background:qlineargradient(x1:0,y1:0,x2:.6,y2:1,stop:0 #24b7d5,stop:.48 #0789b5,stop:1 #046e9a); color:white; font-size:14px; font-weight:600; border:1px solid #76d5e6; padding:12px 22px; }
QPushButton#primary:hover { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #40c9e0,stop:1 #087ba7); }
QPushButton#primary:disabled { background:rgba(84,143,164,85); color:#effaff; border-color:rgba(255,255,255,180); }
QPushButton#drop { border:1px dashed #79b8cc; background:rgba(240,251,255,115); color:#28728c; font-size:16px; border-radius:17px; }
QDoubleSpinBox, QComboBox { color:#1d4a63; background:rgba(255,255,255,185); border:1px solid #b5d6e2; border-radius:9px; padding:7px; min-height:16px; }
QDoubleSpinBox:focus, QComboBox:focus { border:1px solid #087da6; }
QDoubleSpinBox:disabled { color:#819ca9; }
QComboBox QAbstractItemView { color:#17435b; background:#effaff; selection-background-color:#b9e8f2; selection-color:#104564; border:1px solid #9cc8d6; padding:4px; }
QCheckBox { spacing:7px; }
QCheckBox::indicator { width:13px; height:13px; }
QCheckBox::indicator:unchecked { background:rgba(255,255,255,190); border:1px solid #81b0c1; border-radius:4px; }
QCheckBox::indicator:checked { background:#0b91b8; border:2px solid #b0eaf4; border-radius:4px; }
QCheckBox:focus { color:#007ba7; }
QProgressBar { border:0; background:#c9e4ed; border-radius:3px; max-height:6px; }
QProgressBar::chunk { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2ab6d0,stop:1 #91d8b5); border-radius:3px; }
QToolTip { background:#f1fbff; color:#174b65; border:1px solid #8abacb; padding:5px; }
QLabel#gifPreview, QLabel#sourceFallback { background:rgba(242,251,255,150); border:1px solid rgba(255,255,255,220); border-radius:16px; color:#52758a; }
"""

DARK_STYLE = """
QMainWindow { background:#101e30; }
QWidget { color:#dceff7; }
QLabel#headline, QLabel#heading { color:#ecfaff; }
QLabel#muted { color:#b5d0df; }
QLabel#pill { color:#c0e9f5; background:rgba(19,47,68,190); border-color:#426b80; }
QLabel#notice { color:#ffe2a2; background:rgba(67,51,27,240); border-color:#a48a4e; }
QPushButton { color:#def6ff; border-color:#456b80; background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #254b63,stop:1 #172e44); }
QPushButton:hover { border-color:#65cfdf; background:#28536a; }
QPushButton:pressed { background:#102f43; }
QPushButton:disabled { color:#8296a4; background:rgba(25,43,61,140); border-color:#354b5c; }
QPushButton#drop { background:rgba(12,30,47,120); color:#b7dce9; border-color:#426b80; }
QPushButton#primary:disabled { background:#244558; color:#819da9; border-color:#3e6478; }
QDoubleSpinBox, QComboBox { color:#e5f6ff; background:#152b40; border-color:#446b80; }
QDoubleSpinBox:disabled { color:#718c9a; }
QComboBox QAbstractItemView { color:#e5f6ff; background:#152b40; selection-background-color:#27627a; selection-color:white; border-color:#446b80; }
QCheckBox::indicator:unchecked { background:#142b3e; border-color:#6590a3; }
QCheckBox::indicator:checked { background:#0aa9c9; border-color:#68cfdf; }
QCheckBox:focus { color:#76e0ee; }
QProgressBar { background:#253d50; }
QToolTip { background:#153148; color:#e2f4fc; border-color:#537f93; }
QLabel#gifPreview, QLabel#sourceFallback { background:rgba(9,24,40,160); color:#b5d0df; border-color:#426b80; }
"""


class Window(QMainWindow):
    def __init__(self, engine=None, settings=None):
        super().__init__()
        self.engine = engine or App()
        self.source = self.result = None
        self.job_id = None
        self.loading = False
        self.generation = 0
        self.closing = False
        self.preview_primed = False
        self.settings = settings or QSettings('Achilleus', 'Akis-Gif-inator')
        self.bridge = Bridge(self)
        self.bridge.loaded.connect(self.loaded)
        self.bridge.thumbs.connect(self.thumbnails_ready)
        self.setWindowTitle(APP_NAME + " — Video to GIF")
        self.setWindowIcon(app_icon())
        self.setAcceptDrops(True)
        self.setMinimumSize(900, 790)
        self.resize(1100, 850)
        self.setStyleSheet(STYLE)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setMuted(True)
        self.player.setAudioOutput(self.audio)
        self.video = QVideoWidget()
        self.video.setMinimumHeight(80)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.player.setVideoOutput(self.video)
        self.player.positionChanged.connect(self.position_changed)
        self.player.playbackStateChanged.connect(lambda state: self.play_button.setText("Pause" if state == QMediaPlayer.PlaybackState.PlayingState else "Play selection"))
        self.player.errorOccurred.connect(self.preview_error)
        self.player.mediaStatusChanged.connect(self.media_status)
        self.build_ui()
        self.dark_mode.setChecked(self.settings.value('appearance/dark', False, type=bool))
        self.apply_theme(self.dark_mode.isChecked(), persist=False)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(150)
        self.poll_timer.timeout.connect(self.poll)
        self.poll_timer.start()
        self.controls()

    @staticmethod
    def label(text, name="muted"):
        widget = QLabel(text); widget.setObjectName(name); return widget

    def build_ui(self):
        base = AeroBackdrop(); self.backdrop = base; self.setCentralWidget(base)
        outer = QVBoxLayout(base); outer.setContentsMargins(28, 20, 28, 18); outer.setSpacing(14)
        header = GlassPanel(base,dark=True); top = QHBoxLayout(header); top.setContentsMargins(20,13,24,13); top.setSpacing(14)
        logo = QLabel(); logo.setFixedSize(52,52); logo.setPixmap(QPixmap(str(ASSETS / "branding" / "achilleus-white.png")).scaled(52,52,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); top.addWidget(logo)
        wordmark = QVBoxLayout(); wordmark.setSpacing(3); wordmark.addWidget(self.label(APP_NAME,"brand")); wordmark.addWidget(self.label("PRODUCT OF ACHILLEUS  ·  YOUR LOCAL GIF DESK","brandCredit")); top.addLayout(wordmark); top.addStretch()
        self.dark_mode = QCheckBox('Dark mode'); self.dark_mode.setToolTip('Switch between light Aero and dark glass. Saved locally on this computer.')
        self.dark_mode.toggled.connect(self.apply_theme); top.addWidget(self.dark_mode)
        self.live_glass = QCheckBox("Live glass"); self.live_glass.setChecked(True); self.live_glass.setToolTip("Local liquid-glass reflections and ripples. Turn off for a still Aero background. Animation pauses when this window is inactive or minimized.")
        self.live_glass.toggled.connect(base.set_live); base.availabilityChanged.connect(self.glass_available); top.addWidget(self.live_glass); outer.addWidget(header)
        intro = QHBoxLayout(); intro.addWidget(self.label("Drop it. Trim it. GIF it.", "headline")); intro.addStretch(); intro.addWidget(self.label("MP4 / MKV  →  GIF   ·   ALL LOCAL","pill")); outer.addLayout(intro)
        self.notice = self.label("", "notice"); self.notice.setWordWrap(True); self.notice.hide(); outer.addWidget(self.notice)
        columns = QHBoxLayout(); columns.setSpacing(18); outer.addLayout(columns, 1)
        source_panel = GlassPanel(base); sl = QVBoxLayout(source_panel); sl.setContentsMargins(18, 16, 18, 16); sl.setSpacing(10)
        source_header = QHBoxLayout(); source_header.addWidget(self.label("01  Your video", "heading")); source_header.addStretch()
        self.replace = QPushButton("Choose video"); self.replace.clicked.connect(self.choose); source_header.addWidget(self.replace); sl.addLayout(source_header)
        self.source_stack = QStackedWidget()
        self.drop = QPushButton("Drop an MP4 or MKV here\n\nor click to browse"); self.drop.setObjectName("drop"); self.drop.setMinimumHeight(80); self.drop.clicked.connect(self.choose)
        self.source_stack.addWidget(self.drop); self.source_stack.addWidget(self.video)
        self.fallback = QLabel("Preview unavailable. You can still trim and export this video."); self.fallback.setWordWrap(True); self.fallback.setAlignment(Qt.AlignmentFlag.AlignCenter); self.fallback.setObjectName('sourceFallback')
        self.source_stack.addWidget(self.fallback); sl.addWidget(self.source_stack, 1)
        self.file_name = self.label("MP4 / MKV · original files stay untouched"); self.file_name.setWordWrap(True); sl.addWidget(self.file_name)
        preview_controls = QHBoxLayout()
        self.play_button = QPushButton("Play selection"); self.play_button.clicked.connect(self.play_selection); preview_controls.addWidget(self.play_button)
        self.play_time = self.label("0:00.0"); preview_controls.addWidget(self.play_time); preview_controls.addStretch()
        self.first_ten = QPushButton("First 10 sec"); self.first_ten.clicked.connect(self.first_ten_seconds); preview_controls.addWidget(self.first_ten); sl.addLayout(preview_controls)
        self.timeline = TrimBar(); self.timeline.selectionChanged.connect(self.range_changed); self.timeline.seekRequested.connect(self.seek); sl.addWidget(self.timeline)
        trim_controls = QHBoxLayout()
        self.start_time = QDoubleSpinBox(); self.end_time = QDoubleSpinBox()
        for spin, name in ((self.start_time, "Start time in seconds"), (self.end_time, "End time in seconds")):
            spin.setDecimals(2); spin.setSingleStep(0.1); spin.setSuffix(" s"); spin.setAccessibleName(name); spin.setRange(0, 0); spin.setKeyboardTracking(False)
        trim_controls.addWidget(self.label("Start")); trim_controls.addWidget(self.start_time)
        trim_controls.addWidget(self.label("End")); trim_controls.addWidget(self.end_time)
        self.reset_trim = QPushButton("Full video"); self.reset_trim.clicked.connect(self.full_video); trim_controls.addWidget(self.reset_trim); sl.addLayout(trim_controls)
        self.start_time.valueChanged.connect(self.spins_changed); self.end_time.valueChanged.connect(self.spins_changed)
        self.selection_label = self.label("Use the timeline handles to shorten your video."); sl.addWidget(self.selection_label)
        columns.addWidget(source_panel, 1)
        result_panel = GlassPanel(base); rl = QVBoxLayout(result_panel); rl.setContentsMargins(18, 16, 18, 16); rl.setSpacing(12)
        rl.addWidget(self.label("02  Your GIF", "heading"))
        self.gif = GifPreview(); self.gif.clear_preview(); rl.addWidget(self.gif, 1)
        self.result_info = self.label("Infinite loop · smart compression"); self.result_info.setWordWrap(True); rl.addWidget(self.result_info)
        self.progress = QProgressBar(); self.progress.setTextVisible(False); self.progress.hide(); rl.addWidget(self.progress)
        self.status = self.label("GIFs save automatically to the exports folder."); self.status.setWordWrap(True); rl.addWidget(self.status)
        self.shorten = QPushButton("Shorten selection to fit"); self.shorten.hide(); self.shorten.clicked.connect(self.shorten_to_fit); rl.addWidget(self.shorten)
        result_buttons = QHBoxLayout()
        self.save_as = QPushButton("Save a copy…"); self.save_as.clicked.connect(self.save_copy); result_buttons.addWidget(self.save_as)
        self.open_folder = QPushButton("Open folder ↗"); self.open_folder.clicked.connect(self.show_folder); result_buttons.addWidget(self.open_folder)
        self.cancel_button = QPushButton("Cancel"); self.cancel_button.clicked.connect(self.cancel); self.cancel_button.hide(); result_buttons.addWidget(self.cancel_button)
        rl.addLayout(result_buttons); columns.addWidget(result_panel, 1)
        settings = GlassPanel(base); row = QHBoxLayout(settings); row.setContentsMargins(18, 15, 18, 15); row.setSpacing(12)
        target_layout = QVBoxLayout(); target_layout.addWidget(self.label("File size target")); self.targets = QComboBox()
        for size in (4, 8, 10, 25, 50, 100):
            self.targets.addItem(f"{size} MB", size)
        self.targets.setCurrentIndex(3)
        target_layout.addWidget(self.targets); row.addLayout(target_layout)
        detail_layout = QVBoxLayout(); detail_layout.addWidget(self.label("Detail")); self.detail = QComboBox()
        for key, (label, _edge, _fps, _dither) in PROFILES.items():
            self.detail.addItem(label, key)
        self.detail.setCurrentIndex(self.detail.findData("high"))
        detail_layout.addWidget(self.detail); row.addLayout(detail_layout); row.addStretch()
        fit_layout = QVBoxLayout(); self.auto_fit = QCheckBox("Auto-fit size"); self.auto_fit.setChecked(False)
        self.auto_fit.setToolTip("When on, lower frame rate, dimensions and colors as needed to meet the size target. When off, keep your selected detail and flag an oversized GIF.")
        fit_layout.addWidget(self.auto_fit)
        self.quality_hint = self.label("Keep detail; trim to fit."); fit_layout.addWidget(self.quality_hint); row.addLayout(fit_layout)
        self.auto_fit.toggled.connect(lambda checked: self.quality_hint.setText("May reduce detail to fit." if checked else "Keep detail; trim to fit."))
        self.use_gpu = QCheckBox("NVIDIA GPU decoding"); self.use_gpu.setChecked(False)
        self.use_gpu.setToolTip("Try NVIDIA NVDEC on CUDA device 0. Automatically retry on CPU if unsupported. GIF encoding and filters remain on CPU. Compare the export time to see whether your video benefits.")
        self.export_button = QPushButton("Export GIF  ↗"); self.export_button.setObjectName("primary"); self.export_button.clicked.connect(self.export); row.addWidget(self.export_button); outer.addWidget(settings)
        footer = QHBoxLayout(); footer.addWidget(self.use_gpu); footer.addWidget(self.label("Shorter clips keep more detail at the same file size.")); footer.addStretch()
        self.device_info = self.label("Export: CPU decode · CPU GIF encode")
        self.device_info.setToolTip("Shows the actual decoder used for the current or last export. With NVIDIA GPU decoding checked, try NVDEC and fall back to CPU if needed. GIF encoding and filters use CPU. Video preview has its own playback device.")
        footer.addWidget(self.device_info); outer.addLayout(footer)

    def apply_theme(self, dark, persist=True):
        self.setStyleSheet(STYLE + (DARK_STYLE if dark else ''))
        self.backdrop.set_dark(dark); self.timeline.setProperty('dark', dark); self.timeline.update()
        if persist: self.settings.setValue('appearance/dark', bool(dark))

    def glass_available(self, available):
        if not available:
            self.live_glass.setChecked(False); self.live_glass.setEnabled(False)
            self.live_glass.setText("Still glass")
            self.live_glass.setToolTip("Aero styling is active. Live glass is unavailable on this graphics device.")

    def message(self, text=""):
        self.notice.setText(text); self.notice.setVisible(bool(text))

    def controls(self):
        ready = bool(self.source) and not self.loading and not self.job_id
        self.export_button.setEnabled(ready)
        self.export_button.setText("Exporting…" if self.job_id else "Export GIF  ↗")
        for widget in (self.timeline, self.start_time, self.end_time, self.first_ten, self.reset_trim, self.play_button):
            widget.setEnabled(ready)
        for widget in (self.replace, self.drop, self.detail, self.targets, self.auto_fit, self.use_gpu):
            widget.setEnabled(not self.loading and not self.job_id)
        self.save_as.setEnabled(bool(self.result) and not self.job_id)
        self.open_folder.setEnabled(bool(self.result))
        self.cancel_button.setVisible(bool(self.job_id))

    def choose(self):
        if self.job_id or self.loading:
            return
        file, _ = QFileDialog.getOpenFileName(self, "Choose a video", "", "Video files (*.mp4 *.mkv);;All files (*)")
        if file:
            self.load_path(Path(file))

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if not self.job_id and not self.loading and len(urls) == 1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower() in (".mp4", ".mkv"):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.job_id and not self.loading and event.mimeData().hasUrls():
            self.load_path(Path(event.mimeData().urls()[0].toLocalFile())); event.acceptProposedAction()

    def load_path(self, path):
        if self.job_id or self.loading:
            return
        self.generation += 1; generation = self.generation
        self.loading = True; self.source = None; self.result = None; self.preview_primed = False
        self.player.stop(); self.player.setSource(QUrl()); self.gif.clear_preview(); self.shorten.hide(); self.message()
        self.file_name.setText("Reading video…"); self.result_info.setText("Infinite loop · smart compression"); self.status.setText("GIFs save automatically to the exports folder."); self.controls()
        def worker():
            try:
                source = self.engine.load_video(path)
                self.bridge.loaded.emit(generation, source, "")
            except Exception as exc:
                self.bridge.loaded.emit(generation, None, str(exc))
        threading.Thread(target=worker, daemon=True).start()

    def loaded(self, generation, source, error):
        if generation != self.generation or self.closing:
            return
        self.loading = False
        if error:
            self.source_stack.setCurrentIndex(0); self.file_name.setText("Choose an MP4 or MKV video."); self.message(error); self.controls(); return
        self.source = source
        self.file_name.setText(f"{source['name']}  ·  {source['width']} × {source['height']}  ·  {time_label(source['duration'])}")
        self.file_name.setToolTip(str(source["path"]))
        self.replace.setText("Replace")
        self.timeline.set_video(source["duration"])
        for spin in (self.start_time, self.end_time):
            spin.setMaximum(source["duration"])
        self.range_changed(0, source["duration"])
        self.source_stack.setCurrentIndex(1)
        self.player.setSource(QUrl.fromLocalFile(str(source["path"])))
        self.controls()
        if source["duration"] > 20:
            self.message("The full video is selected. Drag the timeline handles to keep a shorter moment, or choose First 10 sec.")
        threading.Thread(target=self.make_thumbnails, args=(generation, source), daemon=True).start()

    def make_thumbnails(self, generation, source):
        frames = []
        for i in range(8):
            if self.closing or generation != self.generation:
                return
            try:
                result = subprocess.run(
                    [self.engine.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", str(source["duration"] * i / 8), "-protocol_whitelist", "file,pipe", "-i", str(source["path"]), "-map", f"0:{source['stream']}", "-frames:v", "1", "-vf", "scale=160:90:force_original_aspect_ratio=decrease,pad=160:90:(ow-iw)/2:(oh-ih)/2", "-f", "image2pipe", "-c:v", "png", "pipe:1"],
                    capture_output=True, timeout=12, creationflags=CREATE_NO_WINDOW,
                )
                if result.returncode == 0 and result.stdout:
                    frames.append(result.stdout)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if not self.closing:
            self.bridge.thumbs.emit(generation, frames)

    def thumbnails_ready(self, generation, frames):
        if generation == self.generation and not self.closing:
            self.timeline.images = [QImage.fromData(data) for data in frames]
            self.timeline.update()

    def range_changed(self, start, end):
        for spin, value in ((self.start_time, start), (self.end_time, end)):
            spin.blockSignals(True); spin.setValue(value); spin.blockSignals(False)
        self.timeline.set_selection(start, end)
        self.selection_label.setText(f"Selected: {time_label(start)} → {time_label(end)}   ·   {end - start:.2f} seconds")

    def spins_changed(self):
        self.timeline.set_selection(self.start_time.value(), self.end_time.value())
        self.range_changed(self.timeline.start, self.timeline.end)
        self.seek(self.timeline.start)

    def first_ten_seconds(self):
        if self.source:
            self.range_changed(0, min(10, self.source["duration"])); self.seek(0); self.message()

    def full_video(self):
        if self.source:
            self.range_changed(0, self.source["duration"]); self.seek(0); self.message()

    def seek(self, seconds):
        self.player.pause(); self.player.setPosition(round(seconds * 1000))
        self.timeline.position = seconds; self.timeline.update(); self.play_time.setText(time_label(seconds))

    def play_selection(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            if not self.timeline.start <= self.player.position() / 1000 < self.timeline.end - 0.05:
                self.player.setPosition(round(self.timeline.start * 1000))
            self.player.play()

    def position_changed(self, position):
        self.timeline.position = position / 1000; self.timeline.update(); self.play_time.setText(time_label(position / 1000))
        if self.source and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState and position / 1000 >= self.timeline.end:
            self.player.pause(); self.player.setPosition(round(self.timeline.start * 1000))

    def media_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and not self.preview_primed:
            self.preview_primed = True
            self.player.setPosition(round(self.timeline.start * 1000))
            self.player.play()
            QTimer.singleShot(120, self.player.pause)

    def preview_error(self, _error, _message):
        if self.source:
            self.source_stack.setCurrentIndex(2)
            self.message("This video cannot play in the preview. Use the timeline thumbnails and times to trim it; FFmpeg can still export it.")

    def export(self):
        if not self.source or self.job_id or self.loading:
            return
        try:
            self.player.pause(); self.message(); self.shorten.hide(); self.gif.clear_preview(); self.result = None
            job = self.engine.start_job({"upload_id": self.source["id"], "start": self.timeline.start, "end": self.timeline.end, "target_mb": self.targets.currentData(), "profile": self.detail.currentData(), "auto_fit": self.auto_fit.isChecked(), "use_gpu": self.use_gpu.isChecked()})
            self.device_info.setText(f"Export: {job['decoder_device']} decode · CPU GIF encode")
            self.job_id = job["id"]; self.progress.setValue(1); self.progress.show(); self.status.setText("Preparing your GIF…"); self.cancel_button.setEnabled(True); self.controls()
        except Exception as exc:
            self.message(str(exc))

    def poll(self):
        if not self.job_id:
            return
        with self.engine.lock:
            job = self.engine.public_job(self.engine.jobs[self.job_id])
        self.progress.setValue(job["progress"]); self.status.setText(job["message"])
        self.device_info.setText(f"Export: {job['decoder_device']} decode · CPU GIF encode")
        if job["status"] == "running":
            return
        self.job_id = None; self.progress.hide()
        if job["status"] == "done":
            self.result = job["result"]
            r = self.result; self.gif.load(r["path"])
            self.result_info.setText(f"{size_label(r['bytes'])}  ·  {r['width']} × {r['height']}  ·  {r['fps']:g} fps  ·  {r['duration']:.2f} sec\nExported in {r['elapsed_seconds']:.2f} s · {r['decoder_device']} decode · CPU GIF encode")
            self.status.setText("Saved to " + r["path"])
            notices = [r["gpu_fallback"]] if r["gpu_fallback"] else []
            if not r["target_met"]:
                reason = "after automatic fitting" if r["auto_fit"] else "with your chosen detail preserved"
                notices.append(f"This GIF is above your {r['target_mb']:g} MB target {reason}. Shorten the selection to keep it shareable.")
                self.shorten.show()
            self.message("\n".join(notices))
        else:
            self.message(job.get("error", "Export cancelled. Adjust your selection and try again."))
        self.controls()

    def shorten_to_fit(self):
        if self.source and self.result:
            suggested = max(0.1, self.result["duration"] * self.result["target_mb"] * 1_000_000 / self.result["bytes"] * 0.85)
            self.range_changed(self.timeline.start, min(self.timeline.end, self.timeline.start + suggested))
            self.seek(self.timeline.start)
            self.message("Selection shortened using the previous GIF's size as an estimate. Review the timeline and click Export GIF. The actual size is checked again.")
            self.shorten.hide()

    def cancel(self):
        if self.job_id:
            self.engine.cancel(self.engine.jobs[self.job_id]); self.cancel_button.setEnabled(False)

    def show_folder(self):
        folder = Path(self.result["path"]).parent if self.result else self.engine.output
        folder.mkdir(parents=True, exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def save_copy(self):
        if not self.result:
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Save GIF copy", str(Path.home() / "Downloads" / self.result["filename"]), "Animated GIF (*.gif)")
        if filename:
            destination = Path(filename)
            if destination.suffix.lower() != ".gif":
                destination = destination.with_suffix(".gif")
            try:
                if destination.resolve() != Path(self.result["path"]).resolve():
                    shutil.copyfile(self.result["path"], destination)
                self.message("Saved a copy to " + str(destination))
            except OSError as exc:
                self.message(str(exc))

    def closeEvent(self, event):
        self.closing = True; self.generation += 1; self.backdrop.close_renderer()
        self.poll_timer.stop(); self.player.stop(); self.player.setSource(QUrl()); self.gif.clear_preview(); self.engine.close(); event.accept()


def app_icon():
    pixmap = QPixmap(64, 64); pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    from PySide6.QtGui import QLinearGradient
    gradient=QLinearGradient(4,2,60,64); gradient.setColorAt(0,QColor("#65dfeb")); gradient.setColorAt(.48,QColor("#0b97c4")); gradient.setColorAt(1,QColor("#087397"))
    painter.setBrush(gradient); painter.setPen(QPen(QColor("#d8fbff"),1)); painter.drawRoundedRect(QRectF(2,2,60,60),17,17)
    painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QColor(255,255,255,230),5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); painter.drawArc(QRectF(16,17,31,30),35*16,280*16)
    painter.drawLine(43,17,48,17); painter.drawLine(48,17,48,24)
    painter.setBrush(QColor("#b2f5d1")); painter.setPen(Qt.PenStyle.NoPen); painter.drawEllipse(QRectF(27,29,11,11)); painter.end(); return QIcon(pixmap)


def smoke_test(output: Path, use_gpu=False):
    """Check the frozen binary with no external Python or FFmpeg on PATH."""
    engine = App(output.parent / "smoke-exports")
    try:
        engine.ready()
        fixture = engine.work / "bundle-sample.mp4"
        subprocess.run([engine.ffmpeg, "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15", "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(fixture)], check=True, capture_output=True, creationflags=CREATE_NO_WINDOW)
        source = engine.load_video(fixture)
        job = engine.start_job({"upload_id": source["id"], "start": 0.2, "end": 0.8, "target_mb": 4, "profile": "very_high", "auto_fit": False, "use_gpu": use_gpu})
        engine.jobs[job["id"]]["thread"].join(60)
        final = engine.public_job(engine.jobs[job["id"]])
        final.update(ffmpeg=engine.ffmpeg, ffprobe=engine.ffprobe, frozen=bool(getattr(sys, "frozen", False)))
        final['version'] = VERSION
        # Exercise the new presets inside the installed/frozen app as well.
        subprocess.run([engine.ffmpeg, "-v", "error", "-nostdin", "-y", "-f", "lavfi", "-i", "testsrc2=size=960x540:rate=24", "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(fixture)], check=True, capture_output=True, creationflags=CREATE_NO_WINDOW)
        source = engine.load_video(fixture)
        final['presets'] = {}
        for profile, expected in [('smooth', (720, 406, 20)), ('sharp', (960, 540, 15))]:
            job = engine.start_job({"upload_id": source["id"], "start": 0, "end": 1, "target_mb": 4, "profile": profile, "auto_fit": False, "use_gpu": use_gpu})
            engine.jobs[job['id']]['thread'].join(60)
            checked = engine.public_job(engine.jobs[job['id']])
            result = checked.get('result', {})
            if checked['status'] != 'done' or (result.get('width'), result.get('height'), result.get('fps')) != expected:
                raise RuntimeError(f'{profile} preset smoke check failed: {checked}')
            measured = engine.probe(Path(result['path']))
            counted = subprocess.run([engine.ffprobe, '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'json', result['path']], check=True, capture_output=True, creationflags=CREATE_NO_WINDOW)
            frames = int(json.loads(counted.stdout)['streams'][0]['nb_read_frames'])
            if frames != expected[2] or abs(measured['duration'] - 1) > 0.1:
                raise RuntimeError(f'{profile} GIF timing smoke check failed: {measured}')
            final['presets'][profile] = result
        # Exercise the packaged Qt OpenGL modules without opening a window.
        from glass import GlassRenderer
        qt = QApplication.instance() or QApplication([])
        renderer = GlassRenderer()
        try:
            available = renderer.initialize()
            frame = renderer.draw(640, 480, 1., [320., 240., 1.], [0., 0., 0., 0.],
                                  [QRectF(20, 20, 600, 70), QRectF(20, 110, 290, 270),
                                   QRectF(330, 110, 290, 270), QRectF(20, 400, 600, 60)]) if available else QImage()
            dark_rendered = False
            if available:
                renderer.dark = True
                dark_frame = renderer.draw(640, 480, 1., [320., 240., 1.], [0., 0., 0., 0.],
                                          [QRectF(20, 20, 600, 70), QRectF(20, 110, 290, 270),
                                           QRectF(330, 110, 290, 270), QRectF(20, 400, 600, 60)])
                dark_rendered = not dark_frame.isNull() and dark_frame.pixelColor(5, 5).lightness() < frame.pixelColor(5, 5).lightness()
                if not dark_rendered: raise RuntimeError('Dark glass shader did not change the rendered pixels.')
            final['glass'] = {'available': available, 'rendered': not frame.isNull(), 'dark_rendered': dark_rendered, 'error': renderer.error}
        finally:
            renderer.close()
        output.write_text(json.dumps(final, indent=2), encoding="utf-8")
        return 0 if final["status"] == "done" else 1
    except Exception:
        output.write_text(json.dumps({"status": "error", "error": traceback.format_exc()}), encoding="utf-8")
        return 1
    finally:
        engine.close()


def main():
    parser = argparse.ArgumentParser(description=APP_NAME + " — native video-to-GIF desktop app")
    parser.add_argument("video", nargs="?")
    parser.add_argument("--smoke-test", type=Path)
    parser.add_argument("--gpu", action="store_true", help="Enable optional NVIDIA GPU decoding")
    args = parser.parse_args()
    if args.smoke_test:
        return smoke_test(args.smoke_test, args.gpu)
    qt = QApplication(sys.argv[:1]); qt.setApplicationName(APP_NAME); qt.setOrganizationName("Achilleus"); qt.setApplicationVersion(VERSION)
    window = Window(); window.use_gpu.setChecked(args.gpu); window.show()
    if args.video:
        QTimer.singleShot(0, lambda: window.load_path(Path(args.video)))
    return qt.exec()


if __name__ == "__main__":
    sys.exit(main())
