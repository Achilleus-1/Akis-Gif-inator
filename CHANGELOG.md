# Changelog

## 1.2.0 — 2026-10-11

- Add Smooth (720px / 20 fps) and Sharp (960px / 15 fps) detail presets with Sierra dithering.
- Preserve the existing presets, High default, source limits and optional size fitting.
- Verify both presets with real GIF exports and include them in packaged smoke checks.

## 1.1.0 — 2026-10-10

- Add remembered Dark mode for native controls, previews, timeline and live/still glass.
- Correct scalar OpenGL uniform binding for the animation clock and theme.
- Add a normal per-user Windows setup EXE, shortcuts and uninstall support.
- Download a private Python/Qt runtime and optional FFmpeg directly from publishers,
  using pinned versions, SHA-256 verification and safe archive paths.
- Add installation/export/uninstall CI and versioned release assets with checksums.
- Present end-user downloads first, with source/development and dependencies documented separately.

## 1.0.0 — 2026-10-10

- Establish Aki's Gif-inator as a Product of Achilleus.
- Native Frutiger Aero interface with local OpenGL liquid glass, pointer
  reflections, click ripples, a still fallback and inactive-window pause.
- MP4/MKV drag-and-drop, native preview, thumbnail range timeline and exact times.
- Detail options through 1920px/30 fps, optional size fitting and trim-to-fit.
- Optional NVIDIA NVDEC, automatic CPU fallback and actual device/export timing.
- Animated GIF previews, unique atomic saves, save-copy and cancellation.
- Source-only public release with GPL licensing, third-party notices, privacy
  checks, documentation, issue templates and CI. Local self-contained build tool.
