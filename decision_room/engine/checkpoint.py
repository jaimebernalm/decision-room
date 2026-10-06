"""Consistent SQLite backup primitive; not a complete OpenCode job checkpoint.

Run next to the private state database (inside the trusted container/controller).
The orchestrator must also checkpoint work files and publish its PostgreSQL
pointer only after this function returns. Never restore into a running server.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path


def _hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _sync_dir(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _check(path):
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite integrity check failed.')


def capture(source, destination, *, timeout=30):
    source, destination = Path(source).resolve(), Path(destination).absolute()
    if not source.is_file() or destination.exists() or destination.is_symlink():
        raise ValueError('Snapshot source must exist and destination must be new.')
    if not 0 < timeout <= 300:
        raise ValueError('Invalid backup timeout.')
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = Path(tempfile.mkdtemp(prefix='.checkpoint-', dir=destination.parent))
    deadline = time.monotonic() + timeout
    try:
        target = temporary / 'opencode.db'
        def progress(status, remaining, total):
            if time.monotonic() >= deadline:
                raise TimeoutError('SQLite backup deadline exceeded.')
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as incoming:
            with sqlite3.connect(target) as outgoing:
                incoming.backup(outgoing, pages=128, progress=progress, sleep=0.01)
        # The backup API includes committed WAL content; copying the main file does not.
        _check(target)
        target.chmod(0o400)
        with target.open('rb') as stream:
            os.fsync(stream.fileno())
        manifest = {'format_version': 1, 'database': 'opencode.db', 'sha256': _hash(target),
                    'byte_count': target.stat().st_size}
        file = temporary / 'manifest.json'
        file.write_text(json.dumps(manifest, sort_keys=True) + '\n')
        file.chmod(0o400)
        with file.open('rb') as stream:
            os.fsync(stream.fileno())
        _sync_dir(temporary)
        # mkdir reserves the public name exclusively. Readers require manifest + DB
        # digest; the controller publishes its durable pointer only after return.
        destination.mkdir(mode=0o700)
        os.replace(target, destination / target.name)
        os.replace(file, destination / file.name)
        _sync_dir(destination)
        _sync_dir(destination.parent)
        return manifest
    finally:
        shutil.rmtree(temporary)


def restore(snapshot, destination):
    """Validate before exclusive publication; caller guarantees the server is stopped."""
    snapshot, destination = Path(snapshot).resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Restore destination must be new; never overwrite live SQLite.')
    try:
        manifest = json.loads((snapshot / 'manifest.json').read_text())
        if (not isinstance(manifest, dict) or manifest.get('format_version') != 1 or manifest.get('database') != 'opencode.db'
                or not isinstance(manifest.get('sha256'), str)):
            raise ValueError('Invalid checkpoint manifest.')
        source = snapshot / 'opencode.db'
        if source.is_symlink() or source.stat().st_size != manifest['byte_count'] or _hash(source) != manifest['sha256']:
            raise ValueError('Checkpoint failed its integrity check.')
        _check(source)
    except (OSError, KeyError, TypeError, sqlite3.DatabaseError, json.JSONDecodeError):
        raise ValueError('Checkpoint is missing, corrupt or incomplete.') from None
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix='.restore-', dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as outgoing, source.open('rb') as incoming:
            shutil.copyfileobj(incoming, outgoing)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if _hash(temporary) != manifest['sha256']:
            raise ValueError('Checkpoint changed during restore.')
        # Hard-link publication refuses even a destination created concurrently.
        os.link(temporary, destination)
        _sync_dir(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest
