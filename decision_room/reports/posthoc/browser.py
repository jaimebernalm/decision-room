"""Bounded private Chrome session for a rendered report, without a user profile."""
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time


def chrome_binary():
    for name in ('google-chrome', 'chromium', 'chromium-browser'):
        if path := shutil.which(name):
            return path
    path = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    if path.is_file():
        return str(path)
    raise RuntimeError('A Chrome/Chromium binary is required for rendered report inventory.')


class Browser:
    def __init__(self, binary=None, timeout=30):
        self.timeout = timeout
        self.profile = tempfile.mkdtemp(prefix='report-verification-')
        r, self.writer = os.pipe()
        self.reader, w = os.pipe()
        # Remap in a fresh interpreter, not preexec_fn (the caller may have
        # active HTTP threads). Pass the real descriptors: 3/4 may be closed
        # or belong to unrelated database/network connections in the parent.
        launcher = '''import fcntl, os, sys
r, w = map(int, sys.argv[1:3])
a, b = (fcntl.fcntl(fd, fcntl.F_DUPFD, 5) for fd in (r, w))
os.dup2(a, 3, inheritable=True)
os.dup2(b, 4, inheritable=True)
for fd in {r, w, a, b} - {3, 4}:
    os.close(fd)
os.execv(sys.argv[3], sys.argv[3:])
'''
        try:
            self.process = subprocess.Popen(
                [sys.executable, '-c', launcher, str(r), str(w),
                 binary or chrome_binary(), '--headless=new', '--disable-gpu',
                 '--no-first-run', '--hide-scrollbars', '--remote-debugging-pipe',
                 '--user-data-dir=' + self.profile, 'about:blank'],
                pass_fds=(r, w),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except BaseException:
            os.close(self.writer); os.close(self.reader)
            shutil.rmtree(self.profile, ignore_errors=True)
            raise
        finally:
            os.close(r); os.close(w)
        self.buffer, self.counter = b'', 0

    def call(self, method, params=None, session=None):
        self.counter += 1
        payload = {'id': self.counter, 'method': method, 'params': params or {}}
        if session:
            payload['sessionId'] = session
        pending = memoryview(json.dumps(payload).encode() + b'\0')
        deadline = time.monotonic() + self.timeout
        while pending:
            if not select.select([], [self.writer], [], max(0, deadline-time.monotonic()))[1]:
                raise TimeoutError('Chrome command timed out.')
            count = os.write(self.writer, pending[:65536]); pending = pending[count:]
        while time.monotonic() < deadline:
            while b'\0' in self.buffer:
                raw, self.buffer = self.buffer.split(b'\0', 1)
                reply = json.loads(raw)
                if reply.get('id') == self.counter:
                    if 'error' in reply:
                        raise RuntimeError('Chrome rejected ' + method)
                    return reply['result']
            if not select.select([self.reader], [], [], max(0, deadline-time.monotonic()))[0]:
                break
            chunk = os.read(self.reader, 65536)
            if not chunk:
                raise RuntimeError('Chrome closed its pipe.')
            self.buffer += chunk
            if len(self.buffer) > 32 * 1024 * 1024:
                raise ValueError('Chrome response exceeds the bound.')
        raise TimeoutError('Chrome response timed out.')

    def evaluate(self, expression, session):
        result = self.call('Runtime.evaluate', {'expression': expression,
                           'returnByValue': True, 'awaitPromise': True}, session)
        if result.get('exceptionDetails') or 'value' not in result.get('result', {}):
            raise ValueError('Report DOM could not be inspected.')
        return result['result']['value']

    def open(self, path):
        target = self.call('Target.createTarget', {'url': 'about:blank'})['targetId']
        session = self.call('Target.attachToTarget', {'targetId': target, 'flatten': True})['sessionId']
        self.call('Emulation.setDeviceMetricsOverride', {
            'width': 1280, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False}, session)
        self.call('Page.navigate', {'url': Path(path).resolve().as_uri()}, session)
        deadline = time.monotonic() + self.timeout
        while self.evaluate('document.readyState', session) != 'complete':
            if time.monotonic() > deadline:
                raise TimeoutError('Report did not finish loading.')
            time.sleep(.05)
        self.evaluate('document.fonts.ready.then(() => true)', session)
        return session

    def close(self):
        self.process.kill(); self.process.wait()
        os.close(self.reader); os.close(self.writer)
        shutil.rmtree(self.profile, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
