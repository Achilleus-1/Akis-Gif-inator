# Distribution and licensing

## Public 1.0.0 package

The Git repository and official release ZIP contain application SOURCE ONLY.
They do not contain Python, Qt, FFmpeg, executables, DLLs, codecs or NVIDIA
drivers. Users obtain runtime dependencies separately, or build locally using
`build.py`. This follows the companion scrobbler's source-release structure.

Original application code is GPL-3.0-or-later, Copyright (c) 2026 Achilleus. See
`LICENSE`. The adapted Rockbox Scrobbler shader formulas keep their MIT notice.
Achilleus branding identifies the project; the code license grants no trademark
rights. Apple artwork, fonts and proprietary shader code are not supplied.

## Local standalone builds

`build.py` packages an installed FFmpeg/FFprobe build and local Qt/Python
dependencies. It records no credentials in source and does not upload anything.
Its output is useful for local personal use. A successful build is not itself
a complete public binary-distribution audit.

The local FFmpeg build has GPL components and many enabled external libraries.
Bundled Qt wheels also contain native dependencies, including their own FFmpeg
libraries. Their terms and exact source versions must be inventoried separately.
Do not infer that a single FFmpeg source link covers all these components.

## Before publishing an executable

For each exact dependency build, retain applicable copyright and license texts,
complete corresponding source (including enabled libraries, patches and build
scripts), and installation/rebuild information required by its license. Make
that source available by a valid distribution method alongside the binary.
Respect any library-replacement or relinking requirements under the selected
terms. Check the generated binary, archive, debug paths and metadata for local
personal information. Use a clean build environment and record hashes/versions.

The source-only packager deliberately refuses binaries and personal media.
No GitHub workflow in this project publishes a bundled executable automatically.
Publishing one is a separate release task that must complete the above review;
renaming it or adding a license badge is insufficient.

References: [FFmpeg licensing](https://ffmpeg.org/legal.html),
[Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html),
[GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.html), and
[PyInstaller licensing](https://pyinstaller.org/en/stable/license.html).

Licensing obligations can depend on the final artifact and jurisdiction. This
document describes the project's distribution policy, not a guarantee of legal
clearance or a substitute for reviewing the actual dependency licenses.
