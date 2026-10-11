# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Check the explicit publication list for missing files and likely private data."""
import re
import struct
import subprocess
from pathlib import Path
from release_files import FILES, ROOT

PATTERNS = (
    ("personal home path", re.compile(r"(?:[A-Z]:[/\\]" + "Users" + r"[/\\][^/\\\s]+|/" + "Users" + r"/[^/\s]+|/" + "home" + r"/[^/\s]+)", re.I)),
    ("access token", re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{24,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{30,})")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----")),
    ("credential URL", re.compile(r"https?://[^\s/]+:[^\s/]+@")),
)


def check_text(text, name):
    errors = [f'{name}: {label}' for label, pattern in PATTERNS if pattern.search(text)]
    # Legal texts retain their original attribution; project files use public contact links.
    if name != 'LICENSE' and not name.startswith('licenses/'):
        emails = re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', text)
        if any(not address.endswith('@users.noreply.github.com') for address in emails):
            errors.append(f'{name}: email address requires review')
    return errors


def check_png(data, name):
    errors = []
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        return [f'{name}: invalid PNG']
    offset = 8
    while offset + 12 <= len(data):
        size = struct.unpack('>I', data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]
        if kind in (b'tEXt', b'zTXt', b'iTXt', b'eXIf'):
            errors.append(f'{name}: metadata chunk requires review')
        offset += size + 12
    return errors


def check_data(data, name):
    suffix = Path(name).suffix.lower()
    if suffix in ('.exe', '.dll', '.mp4', '.mkv', '.gif', '.zip'):
        return [f'{name}: binary or personal media cannot be published']
    if suffix == '.png':
        return check_png(data, name)
    if suffix == '.ico':
        return []
    return check_text(data.decode('utf-8'), name)


def check(root=ROOT, files=FILES, staged=False):
    errors = []
    for name in files:
        path = root / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            errors.append(f'{name}: missing, symlink or outside project'); continue
        errors.extend(check_data(path.read_bytes(), name))
    if staged:
        result = subprocess.run(['git', 'ls-files', '-z'], cwd=root, capture_output=True, check=True)
        names = set(result.stdout.decode().rstrip('\0').split('\0')) - {''}
        for name in sorted(names - set(files)):
            errors.append(f'{name}: staged outside publication allowlist')
        for name in sorted(names & set(files)):
            blob = subprocess.run(['git', 'show', ':' + name], cwd=root, capture_output=True, check=True)
            errors.extend(check_data(blob.stdout, name))
    return errors


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    problems = check(staged=args.staged)
    if problems:
        raise SystemExit('\n'.join(problems))
    print(f'Reviewed {len(FILES)} source files: no detected private paths, tokens, media or metadata.')
