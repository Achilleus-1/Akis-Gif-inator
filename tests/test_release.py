# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Check publication boundaries with private fixtures outside the allowlist."""
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_release import check_text, check
from release_files import FILES, ROOT
from package_release import package


class PublicationTests(unittest.TestCase):
    def test_detects_credentials_and_personal_paths(self):
        self.assertTrue(check_text('gh' + 'p_' + 'x'*36, 'sample.py'))
        self.assertTrue(check_text('C:/' + 'Users/' + 'Example/private.mp4', 'sample.py'))
        self.assertTrue(check_text('https://' + 'user:password' + '@' + 'host.example', 'sample.py'))

    def test_public_source_passes_review(self): self.assertEqual(check(), [])

    def test_staged_review_checks_index_instead_of_only_working_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); sample = root / 'sample.py'
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            sample.write_text('gh' + 'p_' + 'x'*36)
            subprocess.run(['git', 'add', 'sample.py'], cwd=root, check=True)
            sample.write_text('clean working copy')
            self.assertEqual(check(root, ('sample.py',)), [])
            self.assertTrue(check(root, ('sample.py',), staged=True))

    def test_source_archive_omits_local_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in FILES:
                destination = root / name; destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((ROOT / name).read_bytes())
            (root / 'private-video.mp4').write_bytes(b'private')
            (root / '.env').write_text('private credential')
            (root / 'local.exe').write_bytes(b'binary')
            archive = package(root)
            with zipfile.ZipFile(archive) as source:
                self.assertEqual(set(source.namelist()), {'Akis-Gif-inator/'+name for name in FILES})
