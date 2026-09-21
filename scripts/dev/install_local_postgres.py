"""Download the official Postgres.app binary bundle into this repo (macOS).

No system installation, Xcode licence changes, login items or global PATH edits.
"""
import hashlib
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / '.tools/postgres'
RELEASE = 'v2.9.6'
ASSET = 'Postgres-2.9.6-18.dmg'


def main():
    binary = DEST / 'Postgres.app/Contents/Versions/18/bin/postgres'
    if binary.exists():
        subprocess.run([str(binary), '--version'], check=True)
        return
    DEST.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(f'https://api.github.com/repos/PostgresApp/PostgresApp/releases/tags/{RELEASE}') as response:
        release = json.load(response)
    asset = next(a for a in release['assets'] if a['name'] == ASSET)
    dmg = DEST / ASSET
    digest = asset.get('digest', '')
    if not digest.startswith('sha256:'):
        raise RuntimeError('Publisher SHA-256 is missing; cannot verify the binary download.')
    if not dmg.exists() or hashlib.file_digest(dmg.open('rb'), 'sha256').hexdigest() != digest[7:]:
        urllib.request.urlretrieve(asset['browser_download_url'], dmg)
    with dmg.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != digest[7:]:
        raise RuntimeError('Downloaded PostgreSQL digest does not match the publisher.')
    mount = DEST / 'mount'
    subprocess.run(['hdiutil', 'attach', str(dmg), '-nobrowse', '-readonly', '-mountpoint', str(mount)], check=True)
    try:
        subprocess.run(['ditto', str(mount / 'Postgres.app'), str(DEST / 'Postgres.app')], check=True)
    finally:
        subprocess.run(['hdiutil', 'detach', str(mount)], check=True)
    (DEST / 'provenance.json').write_text(json.dumps({'release': RELEASE, 'url': asset['browser_download_url'], 'sha256': actual}, indent=2) + '\n')
    subprocess.run([str(binary), '--version'], check=True)


if __name__ == '__main__':
    main()
