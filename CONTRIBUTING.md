# Contributing

Aki's Gif-inator is a Product of Achilleus. Keep changes readable and preserve
the simple drop, trim, export workflow. Contributions are under GPL-3.0-or-later;
retain upstream notices for any adapted code or assets.

Run `python -m unittest discover -s tests -v`, `python tools/check_release.py`
and `python tools/package_release.py` in the configured environment. Tests use
generated clips and temporary folders; do not replace them with private videos.
NVIDIA tests skip on systems without supported hardware. Check live OpenGL
rendering separately from headless fallback tests.

For UI changes, verify playback, timeline dragging, keyboard focus, exact trim
times, quality/fitting, GPU fallback, cancellation, previews and save dialogs.
Maintain contrast in both themes, with live and still glass. Avoid adding network requests
or collecting pointer data. Inputs must remain untouched and partial GIFs must
not be exposed as completed exports.

Do not commit input videos, exports, credentials, local logs, virtual environments,
build outputs, private paths or personal email addresses. Use your public GitHub
noreply address for commits if you want to keep your email private. Crop personal
filenames from screenshots and use synthetic media in bug reports.

Official installers use `tools/build_installer.py` and Inno Setup. Dependency
URLs/hashes belong in the reviewed manifest; obtain hashes from publisher
metadata and validate a clean installation before releasing. Do not embed a
local Qt/FFmpeg build into Setup. Tag the matching source version to run the
installer release workflow. [Distribution requirements](docs/DISTRIBUTION.md).
The source packager keeps its separate explicit allowlist.
