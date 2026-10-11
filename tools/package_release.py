# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Create a source-only archive using the reviewed, explicit allowlist."""
import hashlib
import zipfile
from check_release import check
from release_files import FILES, ROOT, VERSION


def package(root=ROOT, destination=None):
    problems = check(root)
    if problems:
        raise ValueError('\n'.join(problems))
    destination = destination or root / 'dist' / f'Akis-Gif-inator-{VERSION}-source.zip'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in FILES:
            info = zipfile.ZipInfo('Akis-Gif-inator/' + name, (2026, 10, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (root / name).read_bytes())
    return destination


if __name__ == '__main__':
    result = package()
    print(result.name)
    print('SHA256: ' + hashlib.sha256(result.read_bytes()).hexdigest())
