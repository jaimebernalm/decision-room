"""Bounded transport for outputs before tmpfs disappears on container exit.

All output from this worker is treated as untrusted by the external controller.
It is a convenience supervisor, not an independent verifier or security boundary.
"""
import base64
import json
import os
import signal
import stat
import subprocess
from pathlib import Path

MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 4 * 1024 * 1024
MAX_LOG = 64 * 1024
MAX_ARTIFACTS = 16


def main():
    request = json.loads(Path('/inputs/request.json').read_text())
    environment = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/tmp',
                   'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1',
                   'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
                   'MPLBACKEND': 'Agg', 'MPLCONFIGDIR': '/tmp/matplotlib'}
    state = 'completed'
    with open('/tmp/stdout', 'wb') as out, open('/tmp/stderr', 'wb') as err:
        child = subprocess.Popen(['python', '-I', '-B', '-u', '/opt/run_user.py'],
                                 stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                 env=environment, start_new_session=True)
        try:
            code = child.wait(timeout=request['timeout_seconds'])
            if code != 0:
                state = 'failed'
        except subprocess.TimeoutExpired:
            state, code = 'timed_out', None
        finally:
            # Stop ordinary descendants before reading output; Docker stops any
            # detached descendants when PID 1 exits. Never reuse the container.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
    logs = {}
    for key in ('stdout', 'stderr'):
        with open('/tmp/' + key, 'rb') as stream:
            raw = stream.read(MAX_LOG + 1)
        logs[key] = raw[:MAX_LOG].decode('utf-8', errors='replace')
        logs[key + '_truncated'] = len(raw) > MAX_LOG
    files, total = [], 0
    try:
        # Flat outputs only. Refuse symlinks, directories, sockets and FIFOs.
        entries = list(Path('/output').iterdir())
        if len(entries) > MAX_ARTIFACTS:
            raise ValueError('Too many output files.')
        for path in sorted(entries):
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE:
                raise ValueError('Output must be a bounded regular file.')
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError('Output type changed.')
                raw = stream.read(MAX_FILE + 1)
            total += len(raw)
            if len(raw) > MAX_FILE or total > MAX_TOTAL:
                raise ValueError('Output exceeds the configured limit.')
            files.append({'name': path.name, 'base64': base64.b64encode(raw).decode('ascii')})
    except (ValueError, OSError) as error:
        state, files = 'invalid_output', []
        logs['stderr'] += '\n' + str(error)
    print(json.dumps({'protocol': 1, 'status': state, 'exit_code': code, 'logs': logs, 'files': files}, allow_nan=False))


if __name__ == '__main__':
    main()
