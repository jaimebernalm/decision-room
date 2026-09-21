"""Manage the dedicated local Linux runtime. Run with the repository .venv."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = 'python@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e'
CONTEXT = 'colima-decision-room'


def docker(*args, capture=False):
    return subprocess.run(['docker', '--context', CONTEXT, *args], check=True,
                          text=True, capture_output=capture)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop', 'status', 'build'])
    args = parser.parse_args()
    inputs = ROOT / '.local/sandbox-inputs'
    inputs.mkdir(parents=True, mode=0o700, exist_ok=True)
    if args.action == 'start':
        subprocess.run(['colima', 'start', 'decision-room', '--runtime', 'docker',
                        '--vm-type', 'vz', '--cpus', '2', '--memory', '3', '--disk', '20',
                        '--mount', str(inputs), '--ssh-agent=false', '--ssh-config=false',
                        '--activate=false', '--port-forwarder=none'], check=True)
    elif args.action == 'stop':
        subprocess.run(['colima', 'stop', 'decision-room'], check=True)
    elif args.action == 'status':
        subprocess.run(['colima', 'status', 'decision-room'], check=True)
        docker('info', '--format', '{{json .SecurityOptions}}')
    else:
        docker('build', '--build-arg', f'BASE_IMAGE={BASE}', '-t', 'decision-room-python:local', str(ROOT / 'sandbox'))
        info = json.loads(docker('image', 'inspect', 'decision-room-python:local', capture=True).stdout)[0]
        environment = json.loads(docker('run', '--rm', '--network', 'none', '--read-only',
                                       '--entrypoint', 'cat', info['Id'], '/opt/environment.json', capture=True).stdout)
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((ROOT / 'sandbox').iterdir()) if p.is_file()}
        runtime = {'context': CONTEXT, 'image': info['Id'], 'architecture': info['Architecture'],
                   'base': BASE, 'environment': environment, 'build_files': hashes}
        (ROOT / '.local/sandbox-runtime.json').write_text(json.dumps(runtime, indent=2) + '\n')
        print(json.dumps(runtime, indent=2))


if __name__ == '__main__':
    main()
