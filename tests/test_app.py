# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Real conversion checks and native timeline checks. No network or browser."""
import json
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from converter import App, CREATE_NO_WINDOW, find_binary

@unittest.skipUnless(find_binary('ffmpeg') and find_binary('ffprobe'), 'FFmpeg required')
class ConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory(prefix='loop-fixtures-')
        cls.root = Path(cls.fixtures.name)
        cls.mp4 = cls.root / 'sample.mp4'
        cls.mkv = cls.root / 'sample.mkv'
        cls.noise = cls.root / 'noise.mp4'
        cls.hd = cls.root / 'hd.mp4'
        cls.software_only = cls.root / 'software-only.mkv'
        cls.hevc = cls.root / '10bit-hevc.mp4'
        def ffmpeg(*args):
            subprocess.run([find_binary('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y', *args], check=True, capture_output=True, creationflags=CREATE_NO_WINDOW)
        ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=960x540:rate=24', '-t', '3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(cls.mp4))
        ffmpeg('-i', str(cls.mp4), '-c', 'copy', str(cls.mkv))
        ffmpeg('-f', 'lavfi', '-i', 'nullsrc=s=640x360:r=20,noise=alls=100:allf=t+u', '-t', '3', '-c:v', 'libx264', '-crf', '8', '-pix_fmt', 'yuv420p', str(cls.noise))
        ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=30', '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(cls.hd))
        ffmpeg('-i', str(cls.mp4), '-t', '0.6', '-c:v', 'ffv1', str(cls.software_only))
        ffmpeg('-i', str(cls.mp4), '-t', '0.6', '-c:v', 'libx265', '-preset', 'ultrafast', '-x265-params', 'log-level=error:pools=4', '-pix_fmt', 'yuv420p10le', str(cls.hevc))
    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()
    def setUp(self):
        self.output = tempfile.TemporaryDirectory(prefix='loop-output-')
        self.engine = App(Path(self.output.name))
    def tearDown(self):
        self.engine.close()
        self.output.cleanup()
    def export(self, source, **settings):
        job = self.engine.start_job({'upload_id': source['id'], 'start': 0.5, 'end': 2, 'target_mb': 8, 'edge': 720, **settings})
        self.engine.jobs[job['id']]['thread'].join(60)
        job = self.engine.public_job(self.engine.jobs[job['id']])
        self.assertNotEqual(job['status'], 'running')
        return job
    def test_mp4_trim_size_animation_and_loop(self):
        source = self.engine.load_video(self.mp4)
        job = self.export(source)
        self.assertEqual(job['status'], 'done', job)
        r = job['result']
        self.assertTrue(r['target_met'])
        self.assertLessEqual(r['bytes'], 8_000_000)
        self.assertEqual((r['width'], r['height'], r['fps']), (720, 406, 15))
        gif = Path(r['path']).read_bytes()
        self.assertEqual(gif[:6], b'GIF89a')
        self.assertIn(b'NETSCAPE2.0', gif)
        self.assertAlmostEqual(self.engine.probe(Path(r['path']))['duration'], 1.5, delta=0.15)
        subprocess.run([self.engine.ffmpeg, '-v', 'error', '-i', r['path'], '-f', 'null', '-'], check=True, capture_output=True, creationflags=CREATE_NO_WINDOW)
    def test_mkv(self):
        job = self.export(self.engine.load_video(self.mkv), edge=480)
        self.assertEqual(job['status'], 'done', job)
        self.assertEqual(job['result']['width'], 480)
    def test_nvidia_actual_hardware_export_h264_and_10bit_hevc(self):
        check = subprocess.run([self.engine.ffmpeg, '-v', 'error', '-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda', '-i', str(self.mp4), '-frames:v', '1', '-vf', 'hwdownload,format=nv12', '-f', 'null', '-'], capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=20)
        if check.returncode:
            self.skipTest('NVIDIA hardware decoder unavailable on this machine')
        for fixture in (self.mp4,self.hevc):
            with self.subTest(codec=fixture.name):
                job = self.export(self.engine.load_video(fixture), start=0, end=0.6, use_gpu=True, profile='high', auto_fit=False)
                self.assertEqual(job['status'],'done',job)
                r = job['result']
                self.assertEqual(r['decoder_device'],'NVIDIA GPU')
                self.assertEqual(r['encoder_device'],'CPU')
                self.assertEqual(r['gpu_fallback'],'')
                self.assertGreater(r['elapsed_seconds'],0)
                self.assertEqual((r['width'],r['height'],r['fps']),(960,540,24))
                self.assertAlmostEqual(self.engine.probe(Path(r['path']))['duration'],0.6,delta=0.1)
                subprocess.run([self.engine.ffmpeg,'-v','error','-i',r['path'],'-f','null','-'],check=True,capture_output=True,creationflags=CREATE_NO_WINDOW)
    def test_unsupported_gpu_codec_automatically_exports_with_cpu(self):
        job = self.export(self.engine.load_video(self.software_only), start=0, end=0.6, use_gpu=True)
        self.assertEqual(job['status'],'done',job)
        r=job['result']
        self.assertTrue(r['gpu_requested'])
        self.assertEqual(r['decoder_device'],'CPU')
        self.assertTrue(r['gpu_fallback'])
        self.assertAlmostEqual(self.engine.probe(Path(r['path']))['duration'],0.6,delta=0.1)
    def test_gpu_failure_during_encoding_restarts_entire_export_on_cpu(self):
        source = self.engine.load_video(self.mp4)
        original = self.engine.run_ffmpeg
        calls=[]
        def interrupted_gpu(job,args,base,span):
            gpu = args[args.index('-hwaccel')+1] == 'cuda'
            calls.append((gpu,'-filter_complex' in args))
            if gpu and '-filter_complex' in args:
                raise RuntimeError('Simulated driver failure during the second GPU pass')
            if gpu:
                # Run the initial palette on CPU so failure recovery is tested
                # even on CI computers without an NVIDIA GPU.
                args = [arg.replace('hwdownload,format=nv12,','') for arg in args]
                index=args.index('-hwaccel'); args[index:index+6]=['-hwaccel','none']
            original(job,args,base,span)
        with patch.object(self.engine,'run_ffmpeg',side_effect=interrupted_gpu):
            job = self.export(source, use_gpu=True)
        self.assertEqual(job['status'],'done',job)
        self.assertEqual(calls,[(True,False),(True,True),(False,False),(False,True)])
        self.assertEqual(job['result']['decoder_device'],'CPU')
        self.assertTrue(job['result']['gpu_fallback'])
        self.assertAlmostEqual(self.engine.probe(Path(job['result']['path']))['duration'],1.5,delta=0.15)
    def test_gpu_cancellation_does_not_retry_on_cpu(self):
        source = self.engine.load_video(self.hd)
        public = self.engine.start_job({'upload_id':source['id'],'end':1,'profile':'very_high','auto_fit':False,'use_gpu':True})
        job=self.engine.jobs[public['id']]
        self.engine.cancel(job); job['thread'].join(10)
        self.assertEqual(job['status'],'cancelled',job)
        self.assertEqual(job['gpu_fallback'],'')
        self.assertFalse(list(Path(self.output.name).glob('*.gif')))
    def test_high_and_much_higher_preserve_detail_even_above_target(self):
        source = self.engine.load_video(self.hd)
        for profile, dimensions, fps in [('high', (1280,720), 24), ('very_high', (1920,1080), 30)]:
            with self.subTest(profile=profile):
                job = self.export(source, start=0, end=0.6, profile=profile, auto_fit=False, target_mb=0.25)
                self.assertEqual(job['status'], 'done', job)
                r = job['result']
                self.assertEqual((r['width'],r['height']), dimensions)
                self.assertEqual(r['fps'], fps)
                self.assertEqual(r['colors'],256)
                self.assertGreater(r['bytes'],250_000)
                self.assertFalse(r['target_met'])
                self.assertEqual((r['decoder_device'],r['encoder_device']),('CPU','CPU'))
                self.assertAlmostEqual(self.engine.probe(Path(r['path']))['duration'],0.6,delta=0.1)
                subprocess.run([self.engine.ffmpeg, '-v', 'error', '-i', r['path'], '-f', 'null', '-'], check=True, capture_output=True, creationflags=CREATE_NO_WINDOW)
    def test_high_quality_does_not_upscale_or_add_source_frames(self):
        source = self.engine.load_video(self.mp4)
        job = self.export(source, profile='very_high', auto_fit=False)
        self.assertEqual(job['status'],'done',job)
        self.assertEqual((job['result']['width'],job['result']['height'],job['result']['fps']),(960,540,24))
    def test_high_quality_explicit_auto_fit_reduces_detail_truthfully(self):
        source = self.engine.load_video(self.hd)
        job = self.export(source, start=0, end=0.6, profile='high', auto_fit=True, target_mb=0.25)
        self.assertEqual(job['status'],'done',job)
        r = job['result']
        self.assertTrue(r['width'] < 1280 or r['fps'] < 24)
        self.assertEqual(r['target_met'],r['bytes'] <= 250_000)
        self.assertAlmostEqual(self.engine.probe(Path(r['path']))['duration'],0.6,delta=0.15)
    def test_fitting_flags_actual_oversize_and_keeps_duration(self):
        job = self.export(self.engine.load_video(self.noise), start=0, end=3, target_mb=0.25)
        self.assertEqual(job['status'], 'done', job)
        r = job['result']
        self.assertLess(r['fps'], 15)
        self.assertEqual(r['target_met'], r['bytes'] <= 250_000)
        if not r['target_met']:
            self.assertEqual((r['width'], r['fps']), (320, 8))
        self.assertAlmostEqual(self.engine.probe(Path(r['path']))['duration'], 3, delta=0.2)
    def test_cancel_then_retry(self):
        source = self.engine.load_video(self.noise)
        public = self.engine.start_job({'upload_id': source['id'], 'start': 0, 'end': 3, 'target_mb': 0.25, 'edge': 960})
        job = self.engine.jobs[public['id']]
        self.engine.cancel(job)
        job['thread'].join(10)
        self.assertEqual(job['status'], 'cancelled', job)
        self.assertIsNone(self.engine.active)
        self.assertFalse(list(Path(self.output.name).glob('*.gif')))
        self.assertEqual(self.export(source, end=0.8)['status'], 'done')
    def test_invalid_files_and_selections(self):
        bad = self.root / 'bad.mp4'; bad.write_text('not video')
        with self.assertRaises(ValueError): self.engine.load_video(bad)
        with self.assertRaises(ValueError): self.engine.load_video(self.root / 'bad.exe')
        source = self.engine.load_video(self.mp4)
        for settings in ({'start': 2, 'end': 1}, {'end': 10}, {'target_mb': -1}, {'start': float('nan')}, {'edge': 123}, {'profile':'unknown'}, {'auto_fit':'yes'}, {'use_gpu':'yes'}):
            with self.assertRaises(ValueError):
                self.engine.start_job({'upload_id': source['id'], 'start': 0, 'end': 2, 'target_mb': 8, 'edge': 720, **settings})
    def test_original_unchanged_no_copy_no_upscale_unique_exports(self):
        before = self.noise.read_bytes()
        source = self.engine.load_video(self.noise)
        self.assertEqual(source['path'], self.noise.resolve())
        first = self.export(source, end=0.7, edge=960)
        second = self.export(source, end=0.7, edge=960)
        self.assertEqual(first['status'], 'done', first)
        self.assertEqual(second['status'], 'done', second)
        self.assertEqual(first['result']['width'], 640)
        self.assertNotEqual(first['result']['filename'], second['result']['filename'])
        self.assertEqual(before, self.noise.read_bytes())
        self.engine.load_video(self.mkv)
        self.assertEqual(before, self.noise.read_bytes())

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QCoreApplication, QEvent
from PySide6.QtTest import QTest
from desktop import TrimBar, Window

class TimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])
    def setUp(self):
        self.bar = TrimBar(); self.bar.resize(600, 115); self.bar.set_video(120); self.bar.show(); self.qt.processEvents()
    def tearDown(self):
        self.bar.close()
    def test_full_video_initial_selection_and_clamps(self):
        self.assertEqual((self.bar.start, self.bar.end), (0, 120))
        self.bar.set_selection(-9, 999)
        self.assertEqual((self.bar.start, self.bar.end), (0, 120))
        self.bar.set_selection(110, 50)
        self.assertGreater(self.bar.end, self.bar.start)
    def test_drag_start_handle_changes_range(self):
        emitted = []; self.bar.selectionChanged.connect(lambda a,b: emitted.append((a,b)))
        QTest.mousePress(self.bar, Qt.MouseButton.LeftButton, pos=QPoint(14,40))
        QTest.mouseMove(self.bar, QPoint(157,40))
        QTest.mouseRelease(self.bar, Qt.MouseButton.LeftButton, pos=QPoint(157,40))
        self.assertAlmostEqual(self.bar.start, 30, delta=1)
        self.assertEqual(self.bar.end,120)
        self.assertTrue(emitted)
    def test_drag_end_handle_changes_range(self):
        QTest.mousePress(self.bar, Qt.MouseButton.LeftButton, pos=QPoint(586,40))
        QTest.mouseMove(self.bar, QPoint(443,40))
        QTest.mouseRelease(self.bar, Qt.MouseButton.LeftButton, pos=QPoint(443,40))
        self.assertEqual(self.bar.start,0)
        self.assertAlmostEqual(self.bar.end,90,delta=1)
    def test_click_seeks_without_changing_selection(self):
        positions = []; self.bar.seekRequested.connect(positions.append)
        QTest.mouseClick(self.bar, Qt.MouseButton.LeftButton, pos=QPoint(300,40))
        self.assertAlmostEqual(positions[-1],60,delta=1)
        self.assertEqual((self.bar.start,self.bar.end),(0,120))
    def test_keyboard_precise_trim(self):
        self.bar.set_selection(5,20); self.bar.setFocus(); self.bar.active_handle='start'
        QTest.keyClick(self.bar,Qt.Key.Key_Right)
        self.assertAlmostEqual(self.bar.start,5.1)
        self.bar.active_handle='end'
        QTest.keyClick(self.bar,Qt.Key.Key_Left,Qt.KeyboardModifier.ShiftModifier)
        self.assertAlmostEqual(self.bar.end,19)
    @unittest.skipUnless(find_binary('ffmpeg') and find_binary('ffprobe'),'FFmpeg required')
    def test_gpu_checkbox_export_and_fallback_display(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); fixture=root/'software-only.mkv'
            subprocess.run([find_binary('ffmpeg'),'-v','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=24','-t','0.6','-c:v','ffv1',str(fixture)],check=True,capture_output=True,creationflags=CREATE_NO_WINDOW)
            window=Window(App(root/'exports'))
            try:
                self.assertFalse(window.use_gpu.isChecked())
                window.source=window.engine.load_video(fixture)
                window.timeline.set_video(window.source['duration'])
                for spin in (window.start_time,window.end_time):
                    spin.setMaximum(window.source['duration'])
                window.range_changed(0,window.source['duration']); window.controls()
                window.show(); self.qt.processEvents()
                QTest.mouseClick(window.use_gpu,Qt.MouseButton.LeftButton)
                self.assertTrue(window.use_gpu.isChecked())
                QTest.mouseClick(window.export_button,Qt.MouseButton.LeftButton)
                job=window.engine.jobs[window.job_id]; job['thread'].join(20)
                self.assertEqual(job['status'],'done',window.engine.public_job(job))
                window.poll()
                self.assertTrue(window.result['gpu_requested'])
                self.assertEqual(window.result['decoder_device'],'CPU')
                self.assertIn('CPU decode',window.device_info.text())
                self.assertIn('Exported in',window.result_info.text())
                self.assertIn('CPU decoding instead',window.notice.text())
                self.assertTrue(window.use_gpu.isEnabled())
            finally:
                window.close()
                QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    def test_shortening_estimate_changes_selection_and_full_reset(self):
        output = tempfile.TemporaryDirectory(); window = Window(App(Path(output.name)))
        window.source={'duration':120}; window.timeline.set_video(120); window.range_changed(10,30)
        window.result={'duration':20,'target_mb':4,'bytes':8_000_000}
        window.shorten_to_fit()
        self.assertAlmostEqual(window.timeline.start,10)
        self.assertAlmostEqual(window.timeline.end,18.5)
        window.full_video()
        self.assertEqual((window.timeline.start,window.timeline.end),(0,120))
        window.close(); output.cleanup()

if __name__ == '__main__': unittest.main()
