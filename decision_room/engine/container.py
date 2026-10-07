"""One isolated, recoverable OpenCode container per job runtime generation.

Only dedicated named volumes cross restarts. The controller persists identity
before calling create(); uncertain Docker mutations are inspected by that exact
name/label, never repeated with a fresh identity. No provider credential enters
this container. Checkpoints are taken only after Docker confirms it is stopped.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from uuid import UUID

from . import checkpoint
from .client import Client, ProtocolError
from .transport import DockerHTTPTransport

MAX_BYTES = 256 * 1024 * 1024
MAX_FILES = 8192


def _sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, ensure_ascii=False)
        stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o600)


def _unpack(raw, folder):
    """Docker tar is untrusted agent output. Never call extract()/extractall()."""
    if len(raw) > MAX_BYTES:
        raise ValueError('Runtime archive exceeds the byte limit.')
    total = count = 0
    seen = set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for item in archive:
            name = PurePosixPath(item.name)
            if name.is_absolute() or '..' in name.parts or '\\' in item.name:
                raise ValueError('Unsafe runtime archive path.')
            if str(name) == '.':
                if not item.isdir():
                    raise ValueError('Invalid archive root.')
                continue
            if str(name) in seen or not (item.isfile() or item.isdir()):
                raise ValueError('Links, devices and duplicate paths are not checkpointable.')
            seen.add(str(name)); count += 1; total += item.size
            if count > MAX_FILES or total > MAX_BYTES or item.size < 0:
                raise ValueError('Runtime archive exceeds its limits.')
            target = folder.joinpath(*name.parts)
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=0o700)
            else:
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                source = archive.extractfile(item)
                with target.open('xb') as out:
                    shutil.copyfileobj(source, out)
                target.chmod(0o600)


def inspect_snapshot(folder, *, run_id, image):
    """Validate every regular file, including work files and all session state."""
    folder = Path(folder)
    manifest_path = folder / 'runtime.json'
    if folder.is_symlink() or manifest_path.is_symlink() or manifest_path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Invalid runtime checkpoint.')
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('version') != 1 or manifest.get('run_id') != str(UUID(str(run_id)))
            or manifest.get('image') != image or not isinstance(manifest.get('files'), dict)
            or len(manifest['files']) > MAX_FILES):
        raise ValueError('Runtime checkpoint identity differs.')
    files = {}
    total = 0
    for path in folder.rglob('*'):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError('Invalid checkpoint member.')
        if path.is_file() and path != manifest_path:
            total += path.stat().st_size
            if total > MAX_BYTES:
                raise ValueError('Runtime checkpoint exceeds its byte limit.')
            files[path.relative_to(folder).as_posix()] = {'sha256': _sha(path), 'bytes': path.stat().st_size}
    if files != manifest['files']:
        raise ValueError('Runtime checkpoint failed its integrity check.')
    checkpoint.inspect(folder)
    if _sha(folder / 'state/opencode/opencode.db') != _sha(folder / 'opencode.db'):
        raise ValueError('Runtime SQLite differs from the consistent backup.')
    return manifest


class Runtime:
    def __init__(self, backend, *, run_id, instance_id, image, password, token, model):
        self.backend = backend
        self.run_id, self.instance_id = str(UUID(str(run_id))), str(UUID(str(instance_id)))
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
            raise ValueError('An immutable local engine image is required.')
        if not password or not token:
            raise ValueError('Private runtime credentials are required.')
        self.image, self.password, self.token, self.model = image, password, token, model
        self.name = 'dr-agent-' + self.instance_id
        self.volumes = {part: self.name + '-' + part for part in ('state', 'work', 'inputs')}
        self.container_id = None
        self.label = 'decision-room.engine-instance'

    def _docker(self, *args, data=None, env=None, check=True, timeout=60):
        try:
            result = subprocess.run([*self.backend.prefix, *args], input=data, capture_output=True,
                                    env={**self.backend.cli_env, **(env or {})}, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            raise ProtocolError('Docker operation uncertain; reconcile the runtime identity.') from None
        if check and result.returncode:
            raise ProtocolError('Docker runtime operation failed; retained state requires reconciliation.')
        return result

    def _inspect(self):
        result = self._docker('container', 'inspect', self.name, check=False)
        if result.returncode:
            # Do not interpret daemon failure as proof that the container is absent.
            self._docker('info', '--format', '{{.ID}}')
            return None
        info = json.loads(result.stdout)[0]
        if (info['Config']['Labels'].get(self.label) != self.instance_id or info['Image'] != self.image
                or info['Config']['Labels'].get('decision-room.engine-run') != self.run_id):
            raise ProtocolError('Runtime identity is not owned by this job.')
        self.container_id = info['Id']
        return info

    def create(self):
        info = self._inspect()
        if info:
            return self.container_id
        for volume in self.volumes.values():
            existing = self._docker('volume', 'inspect', volume, check=False)
            if existing.returncode == 0:
                labels = json.loads(existing.stdout)[0].get('Labels') or {}
                if labels.get(self.label) != self.instance_id:
                    raise ProtocolError('Runtime volume is not owned by this job.')
            else:
                self._docker('volume', 'create', '--label', self.label + '=' + self.instance_id, volume)
        config = {'autoupdate': False, 'share': 'disabled', 'snapshot': False,
                  'model': 'openai/' + self.model, 'small_model': 'openai/' + self.model,
                  'provider': {'openai': {'options': {'baseURL': f'http://127.0.0.1:8080/jobs/{self.run_id}/v1',
                                                    'apiKey': self.token}}},
                  'mcp': {'decision_room': {'type': 'remote', 'url': f'http://127.0.0.1:8080/jobs/{self.run_id}/mcp',
                                           'headers': {'Authorization': 'Bearer ' + self.token}, 'oauth': False}},
                  'permission': {'*': 'allow', 'external_directory': {'*': 'deny', '/inputs/*': 'allow'}, 'webfetch': 'deny',
                                 'websearch': 'deny', 'question': 'deny'}}
        env = {'OPENCODE_SERVER_PASSWORD': self.password, 'OPENCODE_CONFIG_CONTENT': json.dumps(config)}
        result = self._docker('create', '--pull=never', '--name', self.name,
            '--label', self.label + '=' + self.instance_id, '--label', 'decision-room.engine-run=' + self.run_id,
            '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--pids-limit', '512', '--memory', '2g', '--memory-swap', '2g', '--cpus', '2',
            '--user', '10001:10001', '--log-driver', 'none',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=268435456',
            '--tmpfs', '/home/agent:rw,nosuid,nodev,uid=10001,gid=10001',
            '--mount', f'type=volume,src={self.volumes["state"]},dst=/state',
            '--mount', f'type=volume,src={self.volumes["work"]},dst=/work',
            '--mount', f'type=volume,src={self.volumes["inputs"]},dst=/inputs,readonly',
            '-e', 'OPENCODE_SERVER_PASSWORD', '-e', 'OPENCODE_CONFIG_CONTENT', self.image,
            'serve', '--hostname', '127.0.0.1', '--port', '4096', env=env)
        self.container_id = result.stdout.decode().strip()
        return self.container_id

    def start(self):
        if not self._inspect():
            raise ProtocolError('Create the runtime before starting.')
        self._docker('start', self.container_id)
        client = Client('http://127.0.0.1:4096', self.password,
                        transport=DockerHTTPTransport(self.backend, self.container_id, timeout=3))
        for _ in range(30):
            try:
                client.health()
                return client
            except ProtocolError:
                time.sleep(0.5)
        client.close()
        raise ProtocolError('Runtime did not become healthy.')

    def stop(self):
        info = self._inspect()
        if info and info['State']['Running']:
            self._docker('stop', '--time', '5', self.container_id)
        info = self._inspect()
        if info and info['State']['Running']:
            raise ProtocolError('Runtime has not stopped.')

    def _copy_archive(self, part):
        process = subprocess.Popen([*self.backend.prefix, 'cp', self.container_id + ':/' + part + '/.', '-'],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=self.backend.cli_env)
        try:
            # Bound bytes while receiving, not after buffering an agent-sized file.
            import selectors
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            try:
                deadline = time.monotonic() + 60
                raw = bytearray()
                while time.monotonic() < deadline:
                    if not selector.select(timeout=min(1, max(0, deadline-time.monotonic()))):
                        continue
                    chunk = os.read(process.stdout.fileno(), min(1024*1024, MAX_BYTES + 1 - len(raw)))
                    if not chunk:
                        if process.wait(timeout=5):
                            raise ProtocolError('Runtime archive copy failed.')
                        return bytes(raw)
                    raw.extend(chunk)
                    if len(raw) > MAX_BYTES:
                        raise ValueError('Runtime archive exceeds the byte limit.')
                raise ProtocolError('Runtime archive copy timed out.')
            finally:
                selector.close()
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            process.stdout.close()

    def capture(self, destination):
        """Stop all processes, copy volumes, recover WAL and publish hashes last."""
        self.stop()
        if not self.container_id:
            raise ProtocolError('Runtime is unavailable for checkpointing.')
        destination = Path(destination)
        if destination.exists():
            raise ValueError('Checkpoint destination must be new.')
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix='.runtime-', dir=destination.parent) as temporary:
            staging = Path(temporary)
            for part in ('state', 'work', 'inputs'):
                folder = staging / part; folder.mkdir(mode=0o700)
                raw = self._copy_archive(part)
                _unpack(raw, folder)
            # The copied WAL and DB are from a stopped process. Use SQLite backup
            # rather than publishing the possibly stale main DB alone.
            checkpoint.capture(staging / 'state/opencode/opencode.db', staging / 'consistent')
            for name in ('opencode.db', 'manifest.json'):
                shutil.move(staging / 'consistent' / name, staging / name)
            (staging / 'consistent').rmdir()
            db = staging / 'state/opencode/opencode.db'
            db.unlink(); shutil.copyfile(staging / 'opencode.db', db)
            for suffix in ('-wal', '-shm'):
                Path(str(db) + suffix).unlink(missing_ok=True)
            files = {p.relative_to(staging).as_posix(): {'sha256': _sha(p), 'bytes': p.stat().st_size}
                     for p in staging.rglob('*') if p.is_file()}
            manifest = {'version': 1, 'run_id': self.run_id, 'image': self.image, 'files': files}
            _json(staging / 'runtime.json', manifest)
            inspect_snapshot(staging, run_id=self.run_id, image=self.image)
            destination.mkdir(mode=0o700)  # Exclusive reservation, never overwrite a checkpoint.
            for part in ('state', 'work', 'inputs', 'opencode.db', 'manifest.json', 'runtime.json'):
                shutil.move(staging / part, destination / part)
            for path in destination.rglob('*'):
                if path.is_file():
                    with path.open('rb') as stream:
                        os.fsync(stream.fileno())
            checkpoint._sync_dir(destination)
            checkpoint._sync_dir(destination.parent)
            return manifest

    def restore(self, snapshot):
        """Restore only into a new, unstarted generation; never overlay live files."""
        snapshot = Path(snapshot)
        inspect_snapshot(snapshot, run_id=self.run_id, image=self.image)
        if self._inspect():
            raise ValueError('Restore requires a new runtime generation.')
        for volume in self.volumes.values():
            if self._docker('volume', 'inspect', volume, check=False).returncode == 0:
                raise ValueError('Restore requires fresh volumes; reconcile a partial restore.')
        self.create()
        for part in ('state', 'work', 'inputs'):
            self.install_files(part, {p.relative_to(snapshot / part).as_posix(): p.read_bytes()
                                      for p in (snapshot / part).rglob('*') if p.is_file()})

    def install_files(self, part, files):
        info = self._inspect()
        if not info or info['State']['Status'] != 'created' or part not in self.volumes:
            raise ValueError('Only install files before the first runtime start.')
        if len(files) > MAX_FILES or sum(len(data) for data in files.values()) > MAX_BYTES:
            raise ValueError('Runtime inputs exceed limits.')
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            directories = set()
            for name, raw in files.items():
                path = PurePosixPath(name)
                if path.is_absolute() or '..' in path.parts or str(path) == '.' or '\\' in name:
                    raise ValueError('Invalid runtime input name.')
                for parent in reversed(path.parents):
                    if str(parent) != '.' and str(parent) not in directories:
                        directory = tarfile.TarInfo(str(parent)); directory.type = tarfile.DIRTYPE
                        directory.mode = 0o700; directory.uid = directory.gid = 10001
                        archive.addfile(directory); directories.add(str(parent))
                item = tarfile.TarInfo(str(path)); item.size = len(raw); item.mode = 0o600
                item.uid = item.gid = 10001
                archive.addfile(item, io.BytesIO(raw))
        if part == 'inputs':
            # The agent mount is read-only even before start. A short-lived,
            # networkless loader writes only that dedicated volume.
            script = """import os,sys,tarfile
from pathlib import Path,PurePosixPath
root=Path('/inputs'); root.chmod(0o755)
total=count=0
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
 for item in archive:
  name=PurePosixPath(item.name); count+=1; total+=item.size
  if name.is_absolute() or '..' in name.parts or not (item.isfile() or item.isdir()) or count>8192 or total>268435456: raise ValueError('Invalid input archive')
  path=root.joinpath(*name.parts)
  if item.isdir(): path.mkdir(parents=True,exist_ok=True,mode=0o755)
  else:
   path.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
   with path.open('xb') as out:
    source=archive.extractfile(item)
    while data:=source.read(1048576): out.write(data)
    out.flush(); os.fsync(out.fileno())
   path.chmod(0o444)
"""
            self._docker('run', '--rm', '-i', '--pull=never', '--network', 'none', '--read-only',
                         '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '0:0',
                         '--memory', '512m', '--pids-limit', '32', '--log-driver', 'none',
                         '--mount', f'type=volume,src={self.volumes["inputs"]},dst=/inputs',
                         '--entrypoint', 'python', self.image, '-I', '-S', '-c', script, data=stream.getvalue())
        else:
            self._docker('cp', '-a', '-', self.container_id + ':/' + part, data=stream.getvalue())

    def remove(self):
        """Release only this generation, after needed checkpoints are durable."""
        if self._inspect():
            self._docker('rm', '-f', self.container_id)
        for volume in self.volumes.values():
            found = self._docker('volume', 'inspect', volume, check=False)
            if found.returncode == 0:
                if (json.loads(found.stdout)[0].get('Labels') or {}).get(self.label) != self.instance_id:
                    raise ProtocolError('Refusing to remove an unrelated volume.')
                self._docker('volume', 'rm', volume)
