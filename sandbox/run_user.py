"""Executed as a child of worker. No host Python process loads submitted code."""
import os
import resource
import runpy
import sys

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024, 2 * 1024 * 1024))
resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
os.umask(0o077)
sys.path.insert(0, '/opt')
runpy.run_path('/inputs/program.py', run_name='__main__')
