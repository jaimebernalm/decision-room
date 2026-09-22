"""Start the local database and open the Decision Room web workspace."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default=os.environ.get('DECISION_ROOM_AGENT_MODEL', 'qwen3.8-27b-splash'),
                        help='Installed LM Studio model; defaults to the model used by this project.')
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    os.chdir(ROOT)
    subprocess.run([sys.executable, 'scripts/dev/local_postgres.py', 'start'], check=True)
    os.environ['DECISION_ROOM_AGENT_MODEL'] = args.model
    os.environ.setdefault('DECISION_ROOM_AGENT_TIMEOUT', '300')
    command = [sys.executable, '-m', 'decision_room.web', '--port', str(args.port)]
    if not args.no_open:
        command.append('--open')
    os.execv(sys.executable, command)


if __name__ == '__main__':
    main()
