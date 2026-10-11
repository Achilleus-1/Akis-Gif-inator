# Architecture

- `app.py`: desktop entry point.
- `desktop.py`: native PySide6 widgets, playback, draggable range timeline,
  background probing/thumbnails, polling, GIF preview and export controls.
- `converter.py`: validation, subprocess control, palette/GIF passes, size
  fitting, cancellation, actual-device reporting and atomic output staging.
- `glass.py`: separate offscreen OpenGL context for an Aero environment and
  rounded glass lenses, then native painting of the bounded image. No browser
  or WebEngine. The video widget is not placed inside an OpenGL widget.
- `build.py`: local single-file PyInstaller build with the runtime, FFmpeg,
  branding and license notices.
- `tools/package_release.py`: reviewed file allowlist for source ZIPs.
- `tools/check_release.py`: data/credential/path checks on publishable files.

Video is registered by local path instead of copied. A worker thread runs two
FFmpeg passes per quality candidate: generate a palette, then encode a GIF.
This avoids buffering an entire selected clip in a split filter graph. CPU
decoding uses `-hwaccel none`; NVIDIA uses CUDA frames and an explicit hardware
download before CPU filters. That download requires real hardware frames, so a
successful GPU pass is not mislabeled software decoding. A GPU failure restarts
both passes on CPU. Cancellation never starts a fallback retry.

The result is copied to a sibling staging file and renamed atomically. A failed
or cancelled export does not expose a partial GIF. Temporary palettes and
candidate outputs are cleaned. The input video is never rewritten.

The decorative shader has a separate 20 fps limit and bounded framebuffer.
Inactive/minimized windows skip animation. It has no bearing on video device
selection. Pointer/click data are only transient visual state. A graphics failure
stops the renderer and uses ordinary painter gradients. Controls keep native
input handling and readable focus indicators in either mode.

The public repository and 1.0.0 release contain application source and authored
assets only. They exclude binaries, build paths, test outputs and source videos.
See [distribution requirements](DISTRIBUTION.md) before distributing executables.
