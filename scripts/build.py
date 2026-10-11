"""Build a portable executable and an archive with a credential-free config."""

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', choices=[
        'linux-x86_64', 'windows-x86_64', 'macos-arm64',
        'macos-x86_64', 'fedoraLinux-43-x86_64',
    ])
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    build_dir = root / 'build'
    dist_dir = root / 'dist'
    release_dir = root / 'release'
    build_dir.mkdir(exist_ok=True)
    release_dir.mkdir(exist_ok=True)

    # DdddOcr() with default options only loads common_old.onnx; skipping the
    # unused beta (common.onnx) and detection (common_det.onnx) models saves ~70 MB.
    ocr_model = Path(importlib.util.find_spec('ddddocr').origin).parent / 'common_old.onnx'
    # Stripping symbols is safe on Linux; on macOS it can break code signatures.
    strip = ['--strip'] if 'linux' in args.target.lower() else []

    subprocess.run([
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm', '--clean', '--onefile', '--console', '--noupx',
        *strip,
        # Drop docstrings and asserts from the bundled bytecode.
        '--optimize', '2',
        # Standard-library modules the app never imports at runtime.
        *[arg for module in ('tkinter', 'unittest', 'doctest', 'pydoc_data', 'test', 'lib2to3')
          for arg in ('--exclude-module', module)],
        '--name', 'troNTOU',
        '--paths', str(root / 'troNTOU'),
        '--specpath', str(build_dir),
        '--workpath', str(build_dir / 'pyinstaller'),
        '--distpath', str(dist_dir),
        '--add-data', f'{ocr_model}{os.pathsep}ddddocr',
        '--collect-binaries', 'onnxruntime',
        str(root / 'troNTOU' / 'main.py'),
    ], cwd=root, check=True)

    executable = dist_dir / ('troNTOU.exe' if sys.platform == 'win32' else 'troNTOU')
    # Loads the bundled OCR model and native libraries without signing in or sending messages.
    subprocess.run([str(executable), '--help'], cwd=dist_dir, check=True, timeout=120)

    name = f'troNTOU-{args.target}'
    package_dir = build_dir / 'packages' / name
    package_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, package_dir / executable.name)
    # Never copy the user's config.yaml into a downloadable artifact.
    shutil.copy2(root / 'config.example.yaml', package_dir / 'config.yaml')
    shutil.copy2(root / 'README.md', package_dir / 'README.md')

    archive = Path(shutil.make_archive(
        str(release_dir / name),
        'zip' if sys.platform == 'win32' else 'gztar',
        root_dir=package_dir.parent, base_dir=package_dir.name,
    ))
    with archive.open('rb') as file:
        digest = hashlib.file_digest(file, 'sha256').hexdigest()
    archive.with_name(archive.name + '.sha256').write_text(
        f'{digest}  {archive.name}\n', encoding='utf-8',
    )
    print(f'Created {archive}')


if __name__ == '__main__':
    main()
