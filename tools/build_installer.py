# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Build the Windows installer containing this project's source, not dependencies."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from release_files import ROOT, FILES, VERSION
from check_release import check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iscc', type=Path, help='Inno Setup 6.6+ compiler')
    args = parser.parse_args()
    compiler = args.iscc or shutil.which('iscc')
    if not compiler:
        for directory in ('Program Files (x86)', 'Program Files'):
            candidate = Path('C:/') / directory / 'Inno Setup 6' / 'ISCC.exe'
            if candidate.is_file(): compiler = candidate; break
    if not compiler: raise SystemExit('Install Inno Setup 6.6+ or pass --iscc.')
    issues = check()
    if issues: raise SystemExit('\n'.join(issues))
    payload = ROOT / 'build' / 'installer-payload'
    payload.mkdir(parents=True, exist_ok=True)
    selected = [name for name in FILES if name in ('app.py', 'converter.py', 'desktop.py', 'glass.py', 'LICENSE', 'THIRD-PARTY-NOTICES.txt', 'Start.bat', 'Start Akis Gif-inator.cmd') or name.startswith(('assets/', 'licenses/', 'docs/'))]
    # Refuse stale/unreviewed content from an earlier build rather than sweeping it in.
    launcher = payload / 'Akis-Gif-inator.exe'
    expected = {payload / name for name in selected} | {launcher}
    unexpected = [path for path in payload.rglob('*') if path.is_file() and path not in expected]
    if unexpected: raise SystemExit('Unexpected files in installer payload; use a fresh build folder.')
    for name in selected:
        destination = payload / name; destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    import os
    csc = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(csc), '/nologo', '/target:winexe', '/platform:x64', '/optimize+', '/debug-',
                    '/reference:System.Windows.Forms.dll', '/win32icon:' + str(ROOT / 'assets/gif-inator.ico'),
                    '/out:' + str(launcher), str(ROOT / 'launcher/Launcher.cs')], check=True)
    manifest = json.loads((ROOT / 'installer' / 'dependencies.json').read_text(encoding='utf-8'))
    download_lines = []
    for item in manifest['packages']:
        if item['kind'] == 'ffmpeg':
            download_lines.append("if WizardIsTaskSelected('ffmpeg') and ((ExpandConstant('{param:ForceFFmpeg|0}') = '1') or (FileSearch('ffmpeg.exe', GetEnv('PATH')) = '') or (FileSearch('ffprobe.exe', GetEnv('PATH')) = '')) then")
        fields = [item[key] for key in ('url', 'filename', 'sha256')]
        if any("'" in value or '\n' in value for value in fields): raise SystemExit('Invalid manifest string.')
        if item['kind'] == 'ffmpeg':
            download_lines.append('begin')
        download_lines.append("if DependencyCache <> '' then CopyFile(DependencyCache + '\\" + item['filename'] + "', ExpandConstant('{tmp}\\" + item['filename'] + "'), False);")
        download_lines.append("DownloadPage.Add('" + "', '".join(fields) + "');")
        if item['kind'] == 'ffmpeg':
            download_lines.append('end;')
    (ROOT / 'build' / 'installer-dependencies.iss').write_text('\n'.join(download_lines), encoding='utf-8')
    command = [str(compiler), '/DAppVersion=' + VERSION, '/DPayloadDir=' + str(payload), str(ROOT / 'installer' / 'setup.iss')]
    subprocess.run(command, cwd=ROOT, check=True)
    print(f'Built Akis-Gif-inator-{VERSION}-windows-x64-setup.exe')


if __name__ == '__main__': main()
