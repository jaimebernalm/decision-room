"""Fetch and verify pinned Linux ARM64 tools; downloaded archives stay outside Git."""
import argparse
import base64
import hashlib
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

PACKAGES = (
    {'file': 'opencode-linux-arm64-1.18.34.tgz',
     'url': 'https://registry.npmjs.org/opencode-linux-arm64/-/opencode-linux-arm64-1.18.34.tgz',
     'algorithm': 'sha512',
     'digest': 'ZSjqcH0MEbAzLEmkRC9Aop1PbWZxe2NuKONAE/x8MRQdjKdOepX7M50UpjbsNoiLMkP584Z98Mg4a42fJhouvA==',
     'member': 'package/bin/opencode', 'binary': 'opencode'},
    {'file': 'ripgrep-15.1.0-aarch64-unknown-linux-gnu.tar.gz',
     'url': 'https://github.com/BurntSushi/ripgrep/releases/download/15.1.0/ripgrep-15.1.0-aarch64-unknown-linux-gnu.tar.gz',
     'algorithm': 'sha256',
     'digest': '2b661c6ef508e902f388e9098d9c4c5aca72c87b55922d94abdba830b4dc885e',
     'member': 'ripgrep-15.1.0-aarch64-unknown-linux-gnu/rg', 'binary': 'rg',
     'notices': ['ripgrep-15.1.0-aarch64-unknown-linux-gnu/'+n for n in ('UNLICENSE','LICENSE-MIT','COPYING')]},
)


def verify(path, package):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, package['algorithm'])
    value = base64.b64encode(digest.digest()).decode() if package['algorithm'] == 'sha512' else digest.hexdigest()
    if value != package['digest']:
        raise ValueError('Vendor archive hash mismatch: ' + package['file'])


def fetch(folder):
    folder.mkdir(parents=True, exist_ok=True)
    for package in PACKAGES:
        destination = folder / package['file']
        if destination.exists():
            verify(destination, package)
            continue
        with tempfile.TemporaryDirectory(dir=folder) as temporary:
            path = Path(temporary) / 'download'
            with urllib.request.urlopen(package['url'], timeout=60) as incoming, path.open('wb') as outgoing:
                size = 0
                while chunk := incoming.read(1024*1024):
                    size += len(chunk)
                    if size > 512*1024*1024:
                        raise ValueError('Vendor download exceeds size limit.')
                    outgoing.write(chunk)
            verify(path, package)
            path.replace(destination)


def install(folder, target):
    target.mkdir(parents=True, exist_ok=True)
    for package in PACKAGES:
        path = folder / package['file']
        verify(path, package)
        with tarfile.open(path) as archive:
            member = archive.getmember(package['member'])
            if not member.isfile() or member.size > 512*1024*1024:
                raise ValueError('Expected one bounded regular binary.')
            with archive.extractfile(member) as incoming, (target / package['binary']).open('wb') as outgoing:
                shutil.copyfileobj(incoming, outgoing)
            for notice in package.get('notices', []):
                member = archive.getmember(notice)
                if not member.isfile() or member.size > 64*1024:
                    raise ValueError('Unexpected vendor notice.')
                notice_folder = target.parent / 'share/licenses' / package['binary']
                notice_folder.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as incoming:
                    (notice_folder / Path(notice).name).write_bytes(incoming.read())
        (target / package['binary']).chmod(0o755)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['fetch', 'verify', 'install'])
    parser.add_argument('--folder', type=Path, default=Path(__file__).parent / 'vendor')
    parser.add_argument('--target', type=Path, default=Path('/usr/local/bin'))
    args = parser.parse_args()
    if args.action == 'fetch':
        fetch(args.folder)
    elif args.action == 'install':
        install(args.folder, args.target)
    else:
        for package in PACKAGES:
            verify(args.folder / package['file'], package)
