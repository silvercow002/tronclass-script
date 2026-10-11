"""Build a portable executable and an archive with a credential-free config."""

import argparse
import hashlib
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

    subprocess.run([
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm', '--clean', '--onefile', '--console', '--noupx',
        '--name', 'troNTOU',
        '--paths', str(root / 'troNTOU'),
        '--specpath', str(build_dir),
        '--workpath', str(build_dir / 'pyinstaller'),
        '--distpath', str(dist_dir),
        '--collect-data', 'ddddocr',
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
