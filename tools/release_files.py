# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Explicit public source allowlist. Local media and binaries are never swept in."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.0"
FILES = (
    '.gitignore', '.gitattributes', 'app.py', 'converter.py', 'desktop.py',
    'glass.py', 'build.py', 'requirements.txt', 'Start.bat',
    'Start Akis Gif-inator.cmd', 'README.md', 'LICENSE',
    'THIRD-PARTY-NOTICES.txt', 'CHANGELOG.md', 'CONTRIBUTING.md',
    'SECURITY.md', 'CODE_OF_CONDUCT.md', 'GPU-BENCHMARK.md',
    'assets/branding/achilleus-black.png', 'assets/branding/achilleus-white.png',
    'assets/gif-inator.ico', 'licenses/Rockbox-Scrobbler-MIT.txt',
    'licenses/Python-LICENSE.txt', 'licenses/PyInstaller-COPYING.txt',
    'docs/USER_GUIDE.md', 'docs/TROUBLESHOOTING.md', 'docs/ARCHITECTURE.md',
    'docs/PRIVACY.md', 'docs/DISTRIBUTION.md', 'docs/images/preview.png',
    'tests/test_app.py', 'tests/test_glass.py', 'tests/test_release.py',
    'tools/release_files.py', 'tools/check_release.py',
    'tools/package_release.py', 'tools/render_preview.py',
    '.github/PULL_REQUEST_TEMPLATE.md', '.github/ISSUE_TEMPLATE/bug_report.yml',
    '.github/ISSUE_TEMPLATE/feature_request.yml', '.github/ISSUE_TEMPLATE/config.yml',
    '.github/workflows/checks.yml',
)
