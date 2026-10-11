# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Local FFmpeg conversion engine used by the native desktop app."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
OUTPUT = ROOT / "exports"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PROFILES = {
    "compact": ("Compact · 480px · 15 fps", 480, 15, "bayer"),
    "balanced": ("Balanced · 720px · 15 fps", 720, 15, "bayer"),
    "smooth": ("Smooth · 720px · 20 fps", 720, 20, "sierra2_4a"),
    "sharp": ("Sharp · 960px · 15 fps", 960, 15, "sierra2_4a"),
    "detail": ("Extra detail · 960px · 20 fps", 960, 20, "sierra2_4a"),
    "high": ("High · 1280px · 24 fps", 1280, 24, "sierra2_4a"),
    "very_high": ("Much higher · 1920px · 30 fps", 1920, 30, "sierra2_4a"),
}


def find_binary(name: str) -> str | None:
    local = Path(getattr(sys, "_MEIPASS", ROOT)) / "bin" / (name + (".exe" if os.name == "nt" else ""))
    return str(local) if local.is_file() else shutil.which(name)


class Cancelled(Exception):
    pass


class App:
    def __init__(self, output: Path = OUTPUT):
        self.output = output
        self.ffmpeg = find_binary("ffmpeg")
        self.ffprobe = find_binary("ffprobe")
        self.temp = tempfile.TemporaryDirectory(prefix="mp4-to-gif-")
        self.work = Path(self.temp.name)
        self.lock = threading.RLock()
        self.uploads: dict[str, dict] = {}
        self.jobs: dict[str, dict] = {}
        self.active: str | None = None

    def ready(self):
        if not self.ffmpeg or not self.ffprobe:
            raise ValueError("FFmpeg and FFprobe are required. Add them to PATH or place both executables in this app's bin folder, then restart the app.")

    def load_video(self, path: Path) -> dict:
        path = path.resolve()
        if path.suffix.lower() not in (".mp4", ".mkv") or not path.is_file():
            raise ValueError("Choose an MP4 or MKV video.")
        if not path.stat().st_size:
            raise ValueError("This video is empty.")
        info = self.probe(path)
        source = {**info, "id": uuid.uuid4().hex, "path": path, "name": path.name, "bytes": path.stat().st_size}
        with self.lock:
            if self.active:
                raise ValueError("Wait for the current export or cancel it first.")
            self.uploads.clear()
            self.uploads[source["id"]] = source
        return source

    def close(self):
        with self.lock:
            for job in self.jobs.values():
                job["cancel"].set()
                process = job.get("process")
                if process and process.poll() is None:
                    process.kill()
        # Allow workers to close their files before removing the temporary directory.
        for job in list(self.jobs.values()):
            thread = job.get("thread")
            if thread and thread is not threading.current_thread():
                thread.join(timeout=5)
        self.temp.cleanup()

    def probe(self, path: Path) -> dict:
        self.ready()
        result = subprocess.run(
            [self.ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams", "-of", "json", str(path)],
            capture_output=True, timeout=60, creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode:
            raise ValueError("This file could not be read as a video. Try another MP4 or MKV file.")
        data = json.loads(result.stdout)
        stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
        if not stream:
            raise ValueError("This file does not contain a video track.")
        duration = float(data.get("format", {}).get("duration") or stream.get("duration") or 0)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("The video's duration could not be read. Try remuxing it to MP4 first.")
        width, height = int(stream["width"]), int(stream["height"])
        for side in stream.get("side_data_list", []):
            if abs(float(side.get("rotation", 0))) % 180 == 90:
                width, height = height, width
                break
        fps = 0
        for rate in (stream.get("avg_frame_rate"), stream.get("r_frame_rate")):
            try:
                numerator, denominator = str(rate).split("/")
                fps = float(numerator) / float(denominator)
                if math.isfinite(fps) and fps > 0:
                    break
            except (ValueError, ZeroDivisionError):
                pass
            fps = 0
        return {"duration": duration, "width": width, "height": height, "stream": stream["index"], "fps": fps,
                "pixel_format": stream.get("pix_fmt", ""), "codec": stream.get("codec_name", "")}

    def start_job(self, payload: dict) -> dict:
        self.ready()
        upload_id = payload.get("upload_id")
        with self.lock:
            source = self.uploads.get(upload_id)
            if not source:
                raise ValueError("Choose a video first.")
            if self.active:
                raise ValueError("An export is already running. Wait for it or cancel it first.")
            profile = payload.get("profile")
            if profile is not None and profile not in PROFILES:
                raise ValueError("Choose a valid detail preset.")
            auto_fit = payload.get("auto_fit", True)
            if not isinstance(auto_fit, bool):
                raise ValueError("Auto-fit size must be on or off.")
            use_gpu = payload.get("use_gpu", False)
            if not isinstance(use_gpu, bool):
                raise ValueError("GPU decoding must be on or off.")
            try:
                start = float(payload.get("start", 0))
                end = float(payload.get("end", source["duration"]))
                target_mb = float(payload.get("target_mb", 8))
                edge = int(payload.get("edge", 720))
                fps, dither = 15, "bayer"
                if profile is not None:
                    _, edge, fps, dither = PROFILES[profile]
            except (TypeError, ValueError, OverflowError):
                raise ValueError("Enter valid clip times and a file size target.") from None
            if not all(math.isfinite(x) for x in (start, end, target_mb)):
                raise ValueError("Enter valid clip times and a file size target.")
            if start < 0 or end <= start or end > source["duration"] + 0.05:
                raise ValueError("The clip must start at or after zero and end within the video.")
            end = min(end, source["duration"])
            if not 0.25 <= target_mb <= 100 or edge not in (480, 720, 960, 1280, 1920):
                raise ValueError("Choose a size target from 0.25 to 100 MB and a valid detail preset.")
            job_id = uuid.uuid4().hex
            job = {
                "id": job_id, "status": "running", "progress": 1,
                "message": "Preparing your GIF…", "cancel": threading.Event(),
                "source": source, "start": start, "duration": end - start,
                "target_mb": target_mb, "edge": edge, "fps": fps, "dither": dither,
                "auto_fit": auto_fit, "profile": profile, "process": None,
                "gpu_requested": use_gpu, "gpu_fallback": "",
                "decoder_device": "Checking NVIDIA GPU" if use_gpu else "CPU", "encoder_device": "CPU",
            }
            self.jobs[job_id] = job
            self.active = job_id
            thread = threading.Thread(target=self.convert, args=(job,), daemon=True)
            job["thread"] = thread
            thread.start()
            return self.public_job(job)

    def public_job(self, job: dict) -> dict:
        return {k: job[k] for k in ("id", "status", "progress", "message", "result", "error", "decoder_device", "encoder_device", "gpu_fallback") if k in job}

    def update(self, job: dict, **values):
        with self.lock:
            job.update(values)

    def run_ffmpeg(self, job: dict, args: list[str], base: float, span: float):
        if job["cancel"].is_set():
            raise Cancelled()
        with tempfile.TemporaryFile() as errors:
            with self.lock:
                if job["cancel"].is_set():
                    raise Cancelled()
                process = subprocess.Popen(
                    [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-progress", "pipe:1", *args],
                    stdout=subprocess.PIPE, stderr=errors, text=True, creationflags=CREATE_NO_WINDOW,
                )
                job["process"] = process
            try:
                for line in process.stdout:
                    if job["cancel"].is_set():
                        process.kill()
                        raise Cancelled()
                    if line.startswith("out_time_us="):
                        try:
                            fraction = min(1, max(0, int(line.split("=", 1)[1]) / 1e6 / job["duration"]))
                            self.update(job, progress=round(base + span * fraction))
                        except ValueError:
                            pass
                process.wait()
                if job["cancel"].is_set():
                    raise Cancelled()
                if process.returncode:
                    errors.seek(0)
                    detail = errors.read().decode("utf-8", errors="replace")[-1800:]
                    raise RuntimeError("FFmpeg could not export this clip. " + detail.strip())
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
                process.stdout.close()
                with self.lock:
                    job["process"] = None

    @staticmethod
    def candidates(edge: int, fps: float = 15, auto_fit: bool = True):
        # Lower frame rate before dimensions so text remains readable longer.
        options = [(edge, fps, 256)]
        if not auto_fit:
            return options
        options += [(edge, min(fps, 20), 256), (edge, min(fps, 15), 256),
                   (edge, 12, 256), (edge, 10, 256),
                   (min(edge, 1280), 15, 256), (min(edge, 960), 12, 256),
                   (min(edge, 720), 10, 256),
                   (min(edge, 576), 10, 256), (480, 10, 256),
                   (480, 10, 128), (384, 10, 128), (320, 8, 128)]
        return list(dict.fromkeys((min(edge, w), min(fps, rate), colors) for w, rate, colors in options))

    @staticmethod
    def cuda_download_format(pixel_format: str) -> str | None:
        # NVDEC surfaces differ from the input's planar pixel format. Preserve
        # bit depth when downloading for the existing software GIF filters.
        return {
            "yuv420p": "nv12", "yuvj420p": "nv12", "nv12": "nv12",
            "yuv420p10le": "p010le", "p010le": "p010le",
            "yuv422p": "nv16", "yuvj422p": "nv16", "nv16": "nv16",
            "yuv422p10le": "p210le", "p210le": "p210le",
            "yuv444p": "yuv444p", "yuvj444p": "yuv444p",
        }.get(pixel_format)

    def encode_candidates(self, job: dict, folder: Path, use_gpu: bool):
        source = job["source"]
        prefix = ""
        hardware = ["-hwaccel", "none"]
        if use_gpu:
            download_format = self.cuda_download_format(source["pixel_format"])
            if not download_format:
                raise RuntimeError("This source pixel format requires software decoding.")
            hardware = ["-hwaccel", "cuda", "-hwaccel_device", "0", "-hwaccel_output_format", "cuda"]
            # Requiring hardware frames here ensures a successful run really
            # used NVDEC, even if FFmpeg tries a software decoder internally.
            prefix = f"hwdownload,format={download_format},"
        fps = min(job["fps"], source["fps"]) if source["fps"] > 0 else job["fps"]
        edge = min(job["edge"], max(source["width"], source["height"]))
        options = self.candidates(edge, fps, job["auto_fit"])
        target = int(job["target_mb"] * 1_000_000)
        best = None
        device = "NVIDIA GPU" if use_gpu else "CPU"
        for index, (edge, fps, colors) in enumerate(options):
            if job["cancel"].is_set():
                raise Cancelled()
            base = 3 + index * 90 / len(options)
            span = 90 / len(options)
            self.update(job, progress=round(base), message=(f"Building palette · {device} decoding…" if index == 0 else f"Fitting your {job['target_mb']:g} MB target · pass {index + 1}…"))
            # Two passes avoid buffering an entire clip in a split filter graph.
            scale = prefix + f"fps={fps},scale=w='if(gte(iw,ih),min({edge},iw),-2)':h='if(gte(iw,ih),-2,min({edge},ih))':flags=lanczos,setsar=1"
            input_args = [*hardware, "-ss", str(job["start"]), "-t", str(job["duration"]), "-protocol_whitelist", "file,pipe", "-i", str(source["path"])]
            palette = folder / "palette.png"
            candidate = folder / f"attempt-{index}.gif"
            self.run_ffmpeg(job, [*input_args, "-map", f"0:{source['stream']}", "-vf", f"{scale},palettegen=max_colors={colors}:stats_mode=full", "-frames:v", "1", "-update", "1", str(palette)], base, span * 0.4)
            self.update(job, decoder_device=device, message=f"{device} decode · CPU encode · {edge}px · {fps:g} fps…")
            dither = "bayer:bayer_scale=3" if job["dither"] == "bayer" else job["dither"]
            self.run_ffmpeg(job, [*input_args, "-i", str(palette), "-filter_complex", f"[0:{source['stream']}]{scale}[v];[v][1:v]paletteuse=dither={dither}:diff_mode=rectangle[out]", "-map", "[out]", "-an", "-c:v", "gif", "-loop", "0", str(candidate)], base + span * 0.4, span * 0.6)
            size = candidate.stat().st_size
            if best is None or size < best[0]:
                best = (size, candidate, edge, fps, colors)
            if size <= target:
                break
        return best

    def convert(self, job: dict):
        folder = self.work / job["id"]
        folder.mkdir()
        started = time.perf_counter()
        try:
            source = job["source"]
            target = int(job["target_mb"] * 1_000_000)
            try:
                best = self.encode_candidates(job, folder, job["gpu_requested"])
            except RuntimeError as exc:
                if not job["gpu_requested"]:
                    raise
                if job["cancel"].is_set():
                    raise Cancelled()
                # Restart both palette and GIF passes so the saved result is
                # entirely CPU-decoded after a GPU failure. Never retry cancel.
                self.update(job, decoder_device="CPU", gpu_fallback="GPU decoding could not be used for this video. Exported with CPU decoding instead.",
                            gpu_error=str(exc), message="GPU unavailable for this video · retrying on CPU…")
                best = self.encode_candidates(job, folder, False)
            if job["cancel"].is_set():
                raise Cancelled()
            size, candidate, edge, fps, colors = best
            self.update(job, progress=96, message="Saving your GIF…")
            metadata = self.probe(candidate)
            self.output.mkdir(parents=True, exist_ok=True)
            stem = re.sub(r"[^\w .-]", "_", Path(source["name"]).stem)[:70].strip(" .") or "video"
            filename = f"{stem}-{time.strftime('%Y%m%d-%H%M%S')}-{job['id'][:6]}.gif"
            destination = self.output / filename
            # Copy to a sibling staging file so exports never exposes a partial GIF.
            staging = destination.with_suffix(".gif.partial")
            try:
                shutil.copyfile(candidate, staging)
                with self.lock:
                    if job["cancel"].is_set():
                        raise Cancelled()
                    staging.replace(destination)
                    result = {
                        "filename": filename, "bytes": size, "width": metadata["width"],
                        "height": metadata["height"], "fps": fps, "colors": colors,
                        "duration": job["duration"], "target_met": size <= target,
                        "target_mb": job["target_mb"], "path": str(destination),
                        "auto_fit": job["auto_fit"], "profile": job["profile"],
                        "dither": job["dither"], "decoder_device": job["decoder_device"], "encoder_device": "CPU",
                        "gpu_requested": job["gpu_requested"], "gpu_fallback": job["gpu_fallback"],
                        "elapsed_seconds": round(time.perf_counter() - started, 3),
                    }
                    job.update(status="done", progress=100, message="Your GIF is ready.", result=result)
                    self.active = None
            finally:
                staging.unlink(missing_ok=True)
        except Cancelled:
            self.update(job, status="cancelled", message="Export cancelled.")
        except Exception as exc:
            self.update(job, status="error", error=str(exc), message="Export failed.")
        finally:
            shutil.rmtree(folder, ignore_errors=True)
            with self.lock:
                if self.active == job["id"]:
                    self.active = None

    def cancel(self, job: dict):
        with self.lock:
            if job["status"] != "running":
                return
            job["cancel"].set()
            process = job.get("process")
            if process and process.poll() is None:
                process.kill()
