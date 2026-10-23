"""Build the standalone Windows executable without bundling personal settings."""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main():
    if sys.platform != 'win32':
        raise SystemExit('Build this Windows application on Windows.')
    subprocess.run([
        sys.executable, '-m', 'PyInstaller',
        '--onefile', '--windowed', '--noupx', '--noconfirm',
        '--name', 'Nightreign auto-timer',
        '--icon', str(ROOT/'assets'/'nightreign-auto-timer.ico'),
        '--add-data', str(ROOT/'assets')+':assets',
        '--add-data', str(ROOT/'gamebar.html')+':.',
        '--distpath', str(ROOT/'dist'),
        '--workpath', str(ROOT/'build'/'work'),
        '--specpath', str(ROOT/'build'),
        str(ROOT/'app.py'),
    ], cwd=ROOT, check=True)
    print(ROOT/'dist'/'Nightreign auto-timer.exe')


if __name__ == '__main__':
    main()
