"""Start the local database and open the Decision Room web workspace."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    sys.path.insert(0, str(ROOT))
    from decision_room.local_env import load_env
    load_env(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default=os.environ.get('DECISION_ROOM_AGENT_MODEL', 'qwen3.8-27b-splash'),
                        help='Model identifier; defaults to the local .env or the project local model.')
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
