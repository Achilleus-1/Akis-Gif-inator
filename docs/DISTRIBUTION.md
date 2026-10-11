# Installation, dependencies and distribution

## Official Windows releases

The normal end-user download is `Akis-Gif-inator-VERSION-windows-x64-setup.exe`
in GitHub Releases, alongside a source ZIP and `SHA256SUMS.txt`. The repository
stores source, documentation and build recipes; executables, environments,
media, logs and dependency downloads stay out of Git.

Setup uses Inno Setup, installs per user without elevation, adds a Start menu
shortcut and optional desktop shortcut, and registers an uninstall entry. The
default app folder is `%LOCALAPPDATA%/Programs/Akis-Gif-inator`. Uninstall removes
installed program/dependency files while retaining user-created exports.
Upgrades use the same product ID and folder. Close the running app before upgrading.

## What is installed

| Component | Where it comes from | How it is used |
| --- | --- | --- |
| This app and branding | Embedded project source in Setup | Native UI and conversion orchestration |
| Python 3.13.16 x64 | Python.org embeddable ZIP | Private runtime; does not replace system Python |
| PySide6 / Qt / Shiboken6 6.10.2 | Exact Windows wheels from PyPI | Native widgets, video preview and OpenGL glass |
| FFmpeg / FFprobe | Existing PATH installation, or Gyan 9.0.2 essentials | Separate processes for probing and GIF export |
| NVIDIA driver | Installed by the user | Optional decoding; never installed or redistributed here |

Installation needs internet and approximately 250 MB of runtime downloads, plus
about 109 MB when FFmpeg needs downloading. The private runtime takes more disk
space after extraction. Use the setup download progress/cancel controls; no video
is uploaded. The installed application runs offline, with no background update service.

URLs, exact versions and publisher SHA-256 hashes are pinned in
`installer/dependencies.json`. Python's hash comes from its publisher Sigstore
metadata; Qt wheel hashes come from PyPI; FFmpeg's hash comes from Gyan's
checksum file. Setup checks hashes natively, and the runtime script checks them
again before extracting. Archive paths must stay inside the staging directory.
A failure stops before copying installed files or creating shortcuts.

The runtime script expands the published wheels directly into private
`Lib/site-packages`, retaining upstream `.dist-info` license files. The embedded
Python path file points only at its runtime, installed wheels and app source.
No pip invocation, system Python installation, PATH edit or security-setting
change is needed. FFmpeg's publisher README/license/docs are retained separately.

## Licenses and sources

Original code is GPL-3.0-or-later. Adapted glass formulas retain their MIT notice.
The Inno Setup engine retains its own license and attribution. Setup does not
embed or mirror Python, Qt or FFmpeg binaries: recipients obtain those directly
from their publishers at installation time. Upstream license texts/notices remain
in the installed dependency packages. See `THIRD-PARTY-NOTICES.txt` for links.

This release design avoids treating a dependency-heavy local FFmpeg/Qt bundle
as an audited public artifact. `build.py` remains available for personal,
self-contained builds. Anyone redistributing that different bundle must inventory
its exact libraries and meet their license/corresponding-source requirements;
adding a generic FFmpeg link is insufficient.

## Release process

1. Update app/source version, changelog and `docs/releases/VERSION.md`.
2. Review dependency URLs, hashes, third-party notices and source privacy.
3. Run the native tests and both theme previews. Build Setup with Inno Setup 6.6+.
4. Verify a clean install, actual GIF export without external runtime on PATH,
   and uninstall preserving generated exports.
5. Tag the matching version `vVERSION`. The release workflow repeats the install
   checks, generates checksums and publishes Setup/source/checksums after success.

The first 1.0.0 release was source-only. Starting with 1.1.0 the end-user download
is the setup EXE. The installer is currently unsigned; checksums establish file
integrity, not a commercial publisher signature. No Windows security bypass is
performed. [Troubleshooting](TROUBLESHOOTING.md).

References: [ScreenToGif releases](https://github.com/NickeManarin/ScreenToGif/releases),
[FFmpeg licensing](https://ffmpeg.org/legal.html),
[Qt licensing](https://doc.qt.io/qtforpython-6/licenses.html),
[Python embedded distribution](https://docs.python.org/3/using/windows.html#the-embeddable-package),
and [Inno Setup](https://jrsoftware.org/isinfo.php).
