import fcntl
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from decision_room.reports.posthoc.browser import Browser, chrome_binary


class BrowserDescriptorTests(unittest.TestCase):
    def test_chrome_uses_real_pipe_descriptors_after_other_runtime_work(self):
        try:
            chrome_binary()
        except RuntimeError:
            self.skipTest('Chrome not installed')
        real_pipe = os.pipe

        def high_pipe():
            pair = real_pipe()
            high = tuple(fcntl.fcntl(fd, fcntl.F_DUPFD, 64) for fd in pair)
            for fd in high:
                os.set_inheritable(fd, False)
            for fd in pair:
                os.close(fd)
            return high

        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'report.html'
            report.write_text('<p>Total 42</p>')
            # Deterministically exercise the descriptor layout that previously
            # raised EBADF before Chrome started, without any provider calls.
            with patch('decision_room.reports.posthoc.browser.os.pipe', high_pipe):
                for _ in range(2):
                    with Browser() as browser:
                        session = browser.open(report)
                        self.assertEqual(browser.evaluate('document.body.innerText', session), 'Total 42')
