"""Trusted host controller. Submitted Python is only executed inside Docker."""
import json
import hashlib
import os
import selectors
import subprocess
import time
from pathlib import Path

from .config import ROOT

INPUT_ROOT = ROOT / '.local/sandbox-inputs'
MAX_TRANSPORT = 6 * 1024**2
LIMITS = {'memory_bytes': 768 * 1024**2, 'cpus': 1, 'pids': 64,
          'tmp_bytes': 128 * 1024**2, 'output_fs_bytes': 32 * 1024**2,
          'file_bytes': 2 * 1024**2, 'artifact_bytes': 4 * 1024**2,
          'artifact_count': 16, 'log_bytes': 64 * 1024,
          'input_bytes': 512 * 1024**2, 'concurrency': 1}


class CleanupPendingError(RuntimeError):
    """Leave the durable execution open so recovery can retry removal."""


class DockerBackend:
    def __init__(self):
        try:
            self.manifest = json.loads((ROOT / '.local/sandbox-runtime.json').read_text())
        except FileNotFoundError:
            raise ValueError('Build the runtime first: .venv/bin/python scripts/dev/local_sandbox.py build') from None
        # Runtime CLI uses an empty private config: no automatic proxy variables,
        # registry credentials or settings inherited from the user's Docker CLI.
        self.cli_env = {key: os.environ[key] for key in ('PATH', 'HOME', 'TMPDIR') if key in os.environ}
        endpoint = subprocess.run(['docker', 'context', 'inspect', self.manifest['context'],
                                   '--format', '{{.Endpoints.docker.Host}}'],
                                  capture_output=True, text=True, timeout=20, env=self.cli_env, check=True).stdout.strip()
        if not endpoint.startswith('unix://'):
            raise ValueError('This backend requires a local Unix Docker socket. Remote execution needs a separate backend.')
        client_config = ROOT / '.local/sandbox-docker-cli'
        client_config.mkdir(mode=0o700, exist_ok=True)
        (client_config / 'config.json').write_text('{}\n')
        self.prefix = ['docker', '--config', str(client_config), '--host', endpoint]
        self.manifest['controller_files'] = {
            name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('docker_backend.py', 'execution.py', 'execution_contract.py')}
        info = json.loads(self.control('image', 'inspect', self.manifest['image']).stdout)[0]
        if info['Id'] != self.manifest['image'] or not info['Id'].startswith('sha256:'):
            raise ValueError('Runtime must reference a locally available immutable image ID.')

    def control(self, *args, check=True):
        result = subprocess.run([*self.prefix, *args], capture_output=True, text=True, timeout=20, env=self.cli_env)
        if check and result.returncode:
            raise ValueError('Docker control failed: ' + result.stderr[-2000:])
        return result

    @staticmethod
    def name(execution_id):
        return 'decision-room-' + execution_id.hex

    def remove(self, execution_id):
        name = self.name(execution_id)
        state = self.control('inspect', name, check=False)
        if state.returncode:
            # Distinguish a missing container from an unreachable daemon.
            self.control('info', '--format', '{{.ID}}')
            return
        info = json.loads(state.stdout)[0]
        if info['Config']['Labels'].get('decision-room.execution') != str(execution_id):
            raise ValueError('Refusing to remove a container without the matching ownership label.')
        self.control('rm', '-f', name)

    def run(self, execution_id, stage, timeout):
        stage = Path(stage).resolve()
        if stage.parent != INPUT_ROOT.resolve() or stage.name != str(execution_id):
            raise ValueError('Invalid input staging directory.')
        name = self.name(execution_id)
        args = ['create', '--pull=never', '--name', name,
                '--label', f'decision-room.execution={execution_id}',
                '--network', 'none', '--read-only', '--user', '10001:10001',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--pids-limit', str(LIMITS['pids']), '--cpus', '1',
                '--memory', str(LIMITS['memory_bytes']), '--memory-swap', str(LIMITS['memory_bytes']),
                '--ulimit', 'nofile=128:128', '--ulimit', 'core=0:0',
                '--ipc', 'private', '--shm-size', '16m', '--log-driver', 'none',
                '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=128m,uid=10001,gid=10001,mode=700',
                '--tmpfs', '/output:rw,noexec,nosuid,nodev,size=32m,uid=10001,gid=10001,mode=700',
                '--mount', f'type=bind,src={stage},dst=/inputs,readonly', self.manifest['image']]
        process = None
        try:
            self.control(*args)
            initial = json.loads(self.control('inspect', name).stdout)[0]
            runtime = {'container_id': initial['Id'], 'host_config': initial['HostConfig'],
                       'mounts': initial['Mounts']}
            process = subprocess.Popen([*self.prefix, 'start', '--attach', name],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.cli_env)
            buffers = {'stdout': bytearray(), 'stderr': bytearray()}
            deadline, forced = time.monotonic() + timeout + 10, None
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
                selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
                while selector.get_map():
                    if time.monotonic() >= deadline:
                        forced = 'timed_out'
                        break
                    for key, _ in selector.select(timeout=min(0.2, max(0, deadline-time.monotonic()))):
                        chunk = key.fileobj.read1(65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        buffer = buffers[key.data]
                        limit = MAX_TRANSPORT if key.data == 'stdout' else LIMITS['log_bytes']
                        if len(buffer) + len(chunk) > limit:
                            forced = 'resource_limit'
                            break
                        buffer.extend(chunk)
                    if forced:
                        break
            if forced:
                self.control('kill', name, check=False)
                process.kill()
            process.wait(timeout=5)
            state = json.loads(self.control('inspect', name).stdout)[0]['State']
            runtime['state'] = state
            if state['OOMKilled']:
                forced = 'resource_limit'
            elif not forced and (state['ExitCode'] != 0 or process.returncode != 0):
                forced = 'failed'
            return {'forced_status': forced, 'payload': bytes(buffers['stdout']),
                    'transport_stderr': bytes(buffers['stderr']).decode('utf-8', errors='replace'),
                    'runtime': runtime}
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                process.stdout.close()
                process.stderr.close()
            try:
                self.remove(execution_id)
            except Exception as error:
                raise CleanupPendingError('Container cleanup unconfirmed; run recover-executions once Docker is available.') from error
