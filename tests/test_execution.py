"""Real Docker + PostgreSQL acceptance tests, with disposable business data."""
import base64
import json
import os
import subprocess
import tempfile
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from psycopg import sql
from psycopg.conninfo import make_conninfo

from decision_room.config import Config, ROOT
from decision_room.database import connect, migrate
from decision_room.docker_backend import DockerBackend, INPUT_ROOT
from decision_room.execution import execute, get_execution, recover_executions
from decision_room.execution_contract import strict_json, validate_payload, validate_result
from decision_room.service import create_business, import_batch
from decision_room.storage import Storage, digest

CALC = '''from dr_runtime import connect, write_result
sql = 'SELECT sum(CAST(sales_ex_tax AS DECIMAL(18,2))) FROM sales'
with connect() as db:
    total = db.execute(sql).fetchone()[0]
write_result({'sales_ex_tax': str(total)}, evidence=[
    {'metric':'sales_ex_tax', 'tables':['sales'], 'operation':sql}])
'''


class ContractTests(unittest.TestCase):
    def test_reject_duplicate_and_nonfinite_json(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '[' * 2000):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                strict_json(raw)

    def test_reject_unsubstantiated_or_foreign_metrics(self):
        base = {'schema_version': 1, 'metrics': {'total': 1}, 'evidence': [], 'notes': []}
        with self.assertRaises(ValueError):
            validate_result(json.dumps(base), {'sales': {'row_count': 24}})
        base['evidence'] = [{'metric':'total', 'tables':['foreign'], 'operation':'count'}]
        with self.assertRaises(ValueError):
            validate_result(json.dumps(base), {'sales': {'row_count':24}})
        base['evidence'][0].update(tables=['sales'], source_records={'sales':[25]})
        with self.assertRaises(ValueError):
            validate_result(json.dumps(base), {'sales': {'row_count':24}})

    def test_host_rejects_traversal_and_artifact_disguises(self):
        payload = {'protocol':1, 'status':'failed', 'exit_code':1,
                   'logs':{'stdout':'','stderr':'','stdout_truncated':False,'stderr_truncated':False}, 'files':[]}
        for name, content in [('../escape.json', b'{}'), ('test.py', b'pass'), ('test.png', b'not PNG'),
                              ('test.parquet', b'not parquet'), ('report.html', b'<script/>')]:
            payload['files'] = [{'name':name,'base64':base64.b64encode(content).decode()}]
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_payload(json.dumps(payload), {})


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.database = 'dr_execution_test_' + uuid.uuid4().hex
        cls.temp = tempfile.TemporaryDirectory(prefix='dr-execution-tests-')
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.config = replace(cls.base, dsn=make_conninfo(cls.base.dsn, dbname=cls.database),
                             storage=Path(cls.temp.name) / 'storage')
        migrate(cls.config)
        cls.business = create_business(cls.config, 'Sandbox test')['id']
        cls.report = import_batch(cls.config, cls.business, [ROOT / 'data/reference-cases/01-daily-sales/input/sales.csv'])
        cls.analysis = cls.report['analysis']['id']
        cls.tables = {'sales': cls.report['files'][0]['table_id']}
        cls.backend = DockerBackend()

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))
        cls.temp.cleanup()

    def run_code(self, code=CALC, **kwargs):
        return execute(self.config, self.business, self.analysis, code=code,
                       tables=self.tables, request_key=kwargs.pop('request_key', uuid.uuid4().hex), **kwargs)

    def assert_clean(self, report):
        self.assertFalse((INPUT_ROOT / str(report['id'])).exists())
        check = self.backend.control('ps', '-a', '--filter', f'label=decision-room.execution={report["id"]}', '--format', '{{.ID}}')
        self.assertEqual(check.stdout.strip(), '')

    def test_reference_persistence_idempotency_and_controls(self):
        key = uuid.uuid4().hex
        first = self.run_code(request_key=key, definitions={'amount':'excluding tax'})
        self.assertEqual(first['status'], 'completed', first.get('issue') or first['logs'])
        self.assertEqual(first['result']['metrics']['sales_ex_tax'], '73784.10')
        self.assertEqual(first['result']['verification'], 'pending')
        second = self.run_code(request_key=key, definitions={'amount':'excluding tax'})
        self.assertEqual(first['id'], second['id'])
        with self.assertRaises(ValueError):
            self.run_code(code=CALC+'\n# changed', request_key=key, definitions={'amount':'excluding tax'})
        fresh = get_execution(self.config, self.business, first['id'])
        storage = Storage(self.config.storage)
        self.assertEqual(digest(storage.path(self.business, fresh['code_key'])), fresh['code_sha256'])
        for artifact in fresh['artifacts']:
            self.assertEqual(digest(storage.path(self.business, artifact['storage_key'])), artifact['sha256'])
        host = fresh['runtime']['host_config']
        self.assertTrue(host['ReadonlyRootfs'])
        self.assertEqual(host['NetworkMode'], 'none')
        self.assertEqual(host['Memory'], 768*1024**2)
        self.assertEqual(host['MemorySwap'], host['Memory'])
        self.assertEqual(host['PidsLimit'], 64)
        self.assertFalse(host['Privileged'])
        self.assertEqual(host['CapDrop'], ['ALL'])
        self.assertIn('no-new-privileges', host['SecurityOpt'])
        self.assertEqual(len(fresh['runtime']['mounts']), 1)
        self.assertFalse(fresh['runtime']['mounts'][0]['RW'])
        self.assert_clean(first)

    def test_isolation_and_all_libraries(self):
        code = '''import os, socket, pathlib
import pandas, numpy, scipy, matplotlib, openpyxl, pyarrow, duckdb
import seaborn, statsmodels.formula.api as smf
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt
from dr_runtime import table_path
assert os.getuid() == 10001
assert 'DR_HOST_SECRET_SENTINEL' not in os.environ
assert not pathlib.Path('/var/run/docker.sock').exists()
assert not pathlib.Path(HOST_REPO_README).exists()
status = pathlib.Path('/proc/self/status').read_text()
assert 'NoNewPrivs:\\t1' in status and 'Seccomp:\\t2' in status
assert 'CapEff:\\t0000000000000000' in status
for filename in (table_path('sales'), '/inputs/program.py', '/opt/environment.json', '/unauthorized'):
    try:
        with open(filename, 'ab') as stream: stream.write(b'bad')
    except OSError: pass
    else: raise AssertionError('write escaped: '+filename)
with socket.socket() as s:
    s.settimeout(1)
    try: s.connect(('192.0.2.1', 443))
    except OSError: pass
    else: raise AssertionError('network accessible')
# Exercise native numerical dependencies and PNG rendering under the same
# limits as real computations; these synthetic values only test compatibility.
frame = pandas.DataFrame({'x': [0., 1., 2., 3., 4.], 'y': [1., 3., 5., 7., 9.]})
fit = smf.ols('y ~ x', data=frame).fit()
numpy.testing.assert_allclose(fit.params[['Intercept', 'x']], [1., 2.], atol=1e-10)
model = make_pipeline(StandardScaler(), LinearRegression())
model.fit(frame[['x']], frame['y'])
numpy.testing.assert_allclose(model.predict(pandas.DataFrame({'x': [5.]})), [11.], atol=1e-10)
seaborn.set_theme(style='whitegrid')
ax = seaborn.barplot(data=frame, x='x', y='y', errorbar=None)
ax.set(title='Library compatibility check', xlabel='x', ylabel='y')
ax.figure.savefig('/output/library_check.png', dpi=100, bbox_inches='tight')
plt.close('all')
'''.replace('HOST_REPO_README', repr(str(ROOT / 'README.md')))+CALC
        with patch.dict(os.environ, {'DR_HOST_SECRET_SENTINEL':'must-not-be-forwarded'}):
            report = self.run_code(code)
        self.assertEqual(report['status'], 'completed', report.get('issue') or report['logs'])
        chart = next(a for a in report['artifacts'] if a['name'] == 'library_check.png')
        self.assertGreater(chart['byte_count'], 1000)
        self.assert_clean(report)

    def test_failures_timeouts_memory_and_output_bounds(self):
        cases = [('syntax', 'this is not Python !!!', 'failed', 10),
                 ('timeout', 'while True: pass', 'timed_out', 1),
                 ('memory', 'x=bytearray(2*1024**3)', 'resource_limit', 10),
                 ('missing_result', 'print("hello")', 'invalid_output', 10),
                 ('link', 'import os; os.symlink("/etc/passwd", "/output/leak.json")', 'invalid_output', 10),
                 ('files', 'from pathlib import Path\nfor i in range(17): Path(f"/output/{i}.csv").write_text("a")', 'invalid_output', 10),
                 ('largefile', 'open("/output/large.csv","wb").write(b"x"*(3*1024**2))', 'failed', 10)]
        for label, code, expected, timeout in cases:
            with self.subTest(case=label):
                report = self.run_code(code, timeout=timeout)
                self.assertEqual(report['status'], expected, report.get('issue') or report['logs'])
                self.assertIsNone(report['result'])
                self.assert_clean(report)

    def test_process_and_disk_limits(self):
        code = '''import subprocess, pathlib, errno
children=[]
try:
    for i in range(80):
        try: children.append(subprocess.Popen(['sleep','20']))
        except OSError as e:
            assert e.errno == errno.EAGAIN
            break
    else: raise AssertionError('process limit not enforced')
finally:
    for child in children: child.kill(); child.wait()
try:
    for i in range(24): pathlib.Path(f'/output/fill{i}.csv').write_bytes(b'x'*(1900*1024))
except OSError as e:
    assert e.errno == errno.ENOSPC
else: raise AssertionError('output tmpfs limit not enforced')
finally:
    for path in pathlib.Path('/output').iterdir(): path.unlink()
'''+CALC
        report = self.run_code(code)
        self.assertEqual(report['status'], 'completed', report.get('issue') or report['logs'])
        self.assert_clean(report)

    def test_transport_limit_and_external_deadline(self):
        # Bypass the helper and write directly to PID 1's transport. The trusted
        # host still limits output even if sandbox-side supervision is bypassed.
        code = 'open("/proc/1/fd/1", "wb", buffering=0).write(b"x"*(7*1024**2))'
        report = self.run_code(code, timeout=2)
        self.assertEqual(report['status'], 'resource_limit', report)
        self.assert_clean(report)
        # Replace the worker's log with a FIFO: host deadline must stop a stuck
        # supervisor even though the user process itself has already exited.
        code = 'import os\nos.unlink("/tmp/stdout")\nos.mkfifo("/tmp/stdout")'
        report = self.run_code(code, timeout=1)
        self.assertEqual(report['status'], 'timed_out', report)
        self.assertLess(report['duration_seconds'], 20)
        self.assert_clean(report)

    def test_cleanup_failure_remains_recoverable(self):
        backend = DockerBackend()
        with patch.object(backend, 'remove', side_effect=ValueError('simulated daemon unavailable')):
            report = self.run_code(backend=backend)
        self.assertEqual(report['status'], 'running')
        self.assertIsNone(report['result'])
        self.assertIsNone(report['finished_at'])
        self.assertIn(report['id'], recover_executions(self.config, self.business))
        self.assert_clean(report)

    def test_interrupt_persists_state(self):
        backend = DockerBackend()
        with patch.object(backend, 'run', side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                self.run_code(backend=backend, request_key='interrupt-test')
        with connect(self.config) as db:
            report = db.execute('SELECT id,status,result FROM executions WHERE request_key=%s', ('interrupt-test',)).fetchone()
        self.assertEqual(report['status'], 'interrupted')
        self.assertIsNone(report['result'])
        self.assert_clean(report)

    def test_scope_integrity_and_recovery(self):
        other = create_business(self.config, 'Other tenant')['id']
        with self.assertRaises(ValueError):
            execute(self.config, other, self.analysis, code=CALC, tables=self.tables, request_key='foreign')
        foreign = import_batch(self.config, other, [ROOT / 'data/reference-cases/01-daily-sales/input/sales.csv'])
        with self.assertRaises(ValueError):
            execute(self.config, self.business, self.analysis, code=CALC,
                    tables={'sales':foreign['files'][0]['table_id']}, request_key='foreign-table')
        report = self.run_code()
        with self.assertRaises(ValueError):
            get_execution(self.config, other, report['id'])
        path = Storage(self.config.storage).path(self.business, self.report['files'][0]['parquet_key'])
        original = path.read_bytes()
        path.chmod(0o600)
        try:
            path.write_bytes(b'tampered')
            broken = self.run_code()
            self.assertEqual(broken['status'], 'failed')
            self.assertIn('integrity', broken['issue'])
            self.assertEqual(broken['runtime'], {})
        finally:
            path.write_bytes(original)
            path.chmod(0o400)
        # Simulate an abandoned durable row plus an owned orphan container.
        with connect(self.config) as db:
            db.execute("UPDATE executions SET status='running',result=NULL WHERE id=%s", (report['id'],))
        self.backend.control('create', '--name', self.backend.name(report['id']),
                             '--label', f'decision-room.execution={report["id"]}',
                             '--network', 'none', self.backend.manifest['image'])
        self.assertEqual(recover_executions(self.config, self.business), [report['id']])
        recovered = get_execution(self.config, self.business, report['id'])
        self.assertEqual(recovered['status'], 'interrupted')
        self.assertIsNone(recovered['result'])
        self.assert_clean(recovered)


if __name__ == '__main__':
    unittest.main()
