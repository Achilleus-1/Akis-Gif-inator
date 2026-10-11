# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Achilleus
"""Build the portable single-file Windows app, including FFmpeg and its DLLs."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ffmpeg-dir", type=Path)
    args = parser.parse_args()
    binary = shutil.which("ffmpeg")
    ffmpeg_dir = args.ffmpeg_dir or (Path(binary).parent if binary else ROOT / "bin")
    for filename in ("ffmpeg.exe", "ffprobe.exe"):
        if not (ffmpeg_dir / filename).is_file():
            raise SystemExit(f"Missing {filename} in {ffmpeg_dir}")
    from PySide6.QtWidgets import QApplication
    from desktop import app_icon
    qt = QApplication([])
    assets = ROOT / "assets"; assets.mkdir(exist_ok=True)
    app_icon().pixmap(128, 128).save(str(assets / "gif-inator.ico"))
    datas = []
    for file in sorted(ffmpeg_dir.iterdir()):
        if file.name in ("ffmpeg.exe", "ffprobe.exe") or file.suffix.lower() == ".dll":
            datas.append((str(file), "bin"))
    datas.append((str(ROOT / 'THIRD-PARTY-NOTICES.txt'), "licenses"))
    datas.append((str(ROOT / 'LICENSE'), "licenses"))
    datas.append((str(ROOT / 'licenses'), "licenses"))
    datas.append((str(assets / 'branding'), "assets/branding"))
    ffmpeg_license = ffmpeg_dir.parent / "LICENSE.txt"
    if ffmpeg_license.is_file():
        shutil.copyfile(ffmpeg_license, assets / "FFmpeg-LICENSE.txt")
        datas.append((str(assets / 'FFmpeg-LICENSE.txt'), "licenses"))
    # Dependency scanning also adds FFmpeg's DLLs at the archive root. Keep
    # only the copies beside ffmpeg.exe; Qt has its own different DLL versions.
    spec = ROOT / "build" / "Akis-Gif-inator.spec"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text(f'''from pathlib import Path
a = Analysis([{str(ROOT / 'app.py')!r}], pathex=[{str(ROOT)!r}],
             binaries=[], datas={datas!r}, hiddenimports=[],
             excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets'])
ffmpeg_folder = Path({str(ffmpeg_dir)!r}).resolve()
a.binaries = [entry for entry in a.binaries
              if entry[0].lower() != 'icuuc.dll'
              and not (Path(entry[1]).parent.resolve() == ffmpeg_folder
                      and not entry[0].replace('\\\\', '/').startswith('bin/'))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Akis-Gif-inator',
          debug=False, strip=False, upx=False, console=False,
          icon={str(assets / 'gif-inator.ico')!r})
''', encoding="utf-8")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(ROOT), "--workpath", str(ROOT / "build"), str(spec)]
    # Qt uses Windows' ICU API. An unrelated ICU DLL on PATH can have the same
    # filename with incompatible symbols; never collect it into the app.
    build_environment = os.environ.copy()
    windows = Path(os.environ.get("SystemRoot", "C:/Windows"))
    build_environment["PATH"] = os.pathsep.join([str(ffmpeg_dir), str(windows / "System32"), str(windows)])
    subprocess.run(command, cwd=ROOT, env=build_environment, check=True)
    print(f"Ready: {ROOT / 'Akis-Gif-inator.exe'}")


if __name__ == "__main__":
    main()
