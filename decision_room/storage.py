"""Private, local files. Database references are relative, never public URLs."""
import hashlib
import os
import tempfile
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Storage:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.root.chmod(0o700)

    def path(self, business_id, key):
        prefix = str(business_id)
        relative = Path(key)
        if relative.is_absolute() or not relative.parts or relative.parts[0] != prefix:
            raise ValueError('File reference does not belong to this business.')
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root / prefix):
            raise ValueError('File reference escapes the business storage directory.')
        return target

    def capture(self, business_id, source, max_bytes):
        """Hash the exact bytes we copy, avoiding a hash/copy race on uploads."""
        folder = self.path(business_id, f'{business_id}/originals')
        folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        hasher, size = hashlib.sha256(), 0
        fd, tmp = tempfile.mkstemp(prefix='.upload-', dir=folder)
        try:
            with os.fdopen(fd, 'wb') as target, Path(source).open('rb') as incoming:
                while chunk := incoming.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError('File exceeds the configured size limit.')
                    hasher.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            sha = hasher.hexdigest()
            key = f'{business_id}/originals/{sha}.csv'
            destination = self.path(business_id, key)
            if destination.exists():
                if digest(destination) != sha:
                    raise ValueError('An existing original failed its integrity check; refusing to overwrite it.')
            else:
                os.chmod(tmp, 0o400)
                # Exclusive publication: another importer may have captured the same file.
                try:
                    os.link(tmp, destination)
                except FileExistsError:
                    if digest(destination) != sha:
                        raise ValueError('Original file integrity mismatch.')
            return {'sha256': sha, 'byte_count': size, 'original_key': key,
                    'original_names': [Path(source).name]}
        finally:
            Path(tmp).unlink(missing_ok=True)
