"""Split the Python suite into balanced shards for parallel CI jobs.

  python scripts/checks/test_shards.py list N I   modules of shard I (0-based) out of N
  python scripts/checks/test_shards.py time       time every module alone and rewrite the timings

Every tests/test_*.py module goes to exactly one shard. Modules are placed
heaviest first on the lightest shard, by the recorded seconds; a module without
a recorded time counts as the median, so a new test file is never dropped.
"""
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIMINGS = Path(__file__).with_name('test_timings.json')


def modules():
    return sorted(f'tests.{p.stem}' for p in (ROOT / 'tests').glob('test_*.py'))


def shards(count):
    names = modules()
    recorded = json.loads(TIMINGS.read_text()) if TIMINGS.exists() else {}
    known = [recorded[n] for n in names if n in recorded]
    default = statistics.median(known) if known else 1.0
    loads, groups = [0.0] * count, [[] for _ in range(count)]
    for name in sorted(names, key=lambda n: (-recorded.get(n, default), n)):
        lightest = loads.index(min(loads))
        groups[lightest].append(name)
        loads[lightest] += recorded.get(name, default)
    return groups, loads


def record():
    seconds = {}
    for name in modules():
        started = time.monotonic()
        subprocess.run([sys.executable, '-m', 'unittest', name], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        seconds[name] = round(time.monotonic() - started, 1)
        print(f'{seconds[name]:8.1f}  {name}', flush=True)
    TIMINGS.write_text(json.dumps(seconds, indent=2, sort_keys=True) + '\n')


def main():
    if sys.argv[1:2] == ['time']:
        record()
    elif sys.argv[1:2] == ['list'] and len(sys.argv) == 4:
        count, index = int(sys.argv[2]), int(sys.argv[3])
        if not 0 <= index < count:
            raise SystemExit('Shard index out of range.')
        groups, loads = shards(count)
        print(f'Shard {index + 1} of {count}: {len(groups[index])} modules, about {loads[index]:.0f} s', file=sys.stderr)
        print(' '.join(groups[index]))
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
