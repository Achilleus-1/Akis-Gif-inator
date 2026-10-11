# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Render the documentation preview using original, generated demonstration media."""
import math
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt, QRectF, QCoreApplication, QEvent, QSettings
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication
from converter import App, CREATE_NO_WINDOW
from desktop import Window, size_label


def demonstration(index):
    image = QImage(1280, 720, QImage.Format.Format_RGB32)
    painter = QPainter(image); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    background = QLinearGradient(0, 0, 1280, 720)
    background.setColorAt(0, QColor('#1e87ab')); background.setColorAt(.55, QColor('#96dfdf')); background.setColorAt(1, QColor('#d5f4bf'))
    painter.fillRect(image.rect(), background)
    for x, y, radius in ((1100, 100, 240), (210, 620, 280), (1010, 600, 160)):
        y += math.sin(index / 12 + x) * 28
        painter.setPen(QPen(QColor(255, 255, 255, 110), 3)); painter.setBrush(QColor(255, 255, 255, 35))
        painter.drawEllipse(QRectF(x-radius, y-radius, radius*2, radius*2))
        painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawArc(QRectF(x-radius+18, y-radius+18, radius*2-36, radius*2-36), 35*16, 100*16)
    painter.setPen(QColor('#124961')); painter.setFont(QFont('Segoe UI', 20, QFont.Weight.DemiBold))
    painter.drawText(85, 215, 'A LITTLE MOMENT')
    painter.setFont(QFont('Segoe UI', 66, QFont.Weight.Bold)); painter.drawText(80, 315, 'Worth looping.')
    painter.setFont(QFont('Segoe UI', 22)); painter.drawText(85, 386, 'Keep the detail. Share the feeling.')
    painter.setPen(QColor('#f0ffff')); painter.setFont(QFont('Segoe UI', 16)); painter.drawText(85, 645, 'GENERATED DEMO  /  NO PERSONAL MEDIA')
    painter.end(); return image


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--dark', action='store_true'); args = parser.parse_args()
    qt = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='gif-inator-preview-') as temp:
        root = Path(temp); engine = App(root / 'exports'); window = None
        try:
            engine.ready()
            for index in range(72):
                demonstration(index).save(str(root / f'frame-{index:03}.png'))
            source_path = root / 'Aero-demo.mp4'
            subprocess.run([engine.ffmpeg, '-v', 'error', '-y', '-framerate', '24', '-i', str(root / 'frame-%03d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(source_path)], capture_output=True, check=True, creationflags=CREATE_NO_WINDOW)
            source = engine.load_video(source_path)
            job = engine.start_job({'upload_id': source['id'], 'start': .3, 'end': 2.3, 'profile': 'high', 'auto_fit': False, 'target_mb': 25})
            engine.jobs[job['id']]['thread'].join(60)
            final = engine.public_job(engine.jobs[job['id']])
            if final['status'] != 'done':
                raise RuntimeError(final.get('error', final['status']))
            result = final['result']
            preferences = QSettings(str(root / 'appearance.ini'), QSettings.Format.IniFormat)
            window = Window(engine, settings=preferences); window.dark_mode.setChecked(args.dark); window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
            window.resize(1100, 850); window.source = source; window.result = result
            window.timeline.set_video(source['duration'])
            window.timeline.images = [demonstration(i).scaled(160, 90) for i in range(0, 72, 9)]
            for spin in (window.start_time, window.end_time): spin.setMaximum(source['duration'])
            window.range_changed(.3, 2.3); window.timeline.position = .6
            window.file_name.setText('Aero-demo.mp4  ·  1280 × 720  ·  0:03.0')
            window.replace.setText('Replace'); window.play_time.setText('0:00.6')
            window.fallback.setPixmap(QPixmap.fromImage(demonstration(15)).scaled(460, 259, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            window.source_stack.setCurrentIndex(2); window.gif.load(result['path'])
            window.result_info.setText(f"{size_label(result['bytes'])}  ·  1280 × 720  ·  24 fps  ·  2.00 sec\nCPU decode · CPU GIF encode")
            window.status.setText('Saved locally to exports/'); window.controls(); window.show(); qt.processEvents()
            window.backdrop.elapsed = 5.; window.backdrop.pointer = [820., 220., 1.]
            window.backdrop.tick(force=True); qt.processEvents()
            destination = Path(__file__).resolve().parents[1] / 'docs' / 'images' / ('preview-dark.png' if args.dark else 'preview.png')
            destination.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(destination))
            print(f'Preview rendered; live shader: {window.backdrop.available}')
        finally:
            if window:
                window.close()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            else: engine.close()


if __name__ == '__main__': main()
