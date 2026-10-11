"""Host controller: only a dedicated, pinned container executes report HTML."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import struct
import subprocess
import time
from uuid import UUID

from ..config import ROOT
from . import derive_policy as policy, inventory

MAX_OUTPUT = 36 * 1024 * 1024
SNAPSHOT_PREFIX = '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="referrer" content="no-referrer"><body style="margin:0;background:white">'
SNAPSHOT_SUFFIX = '</body></html>'
IMAGE = re.compile(r'<img alt="Página del informe" width="1280" height="([0-9]{1,4})" style="display:block;max-width:100%;height:auto" src="data:image/png;base64,([A-Za-z0-9+/=]+)">')


def validate_snapshot(value):
    """Only our static raster template can leave the browser container."""
    if not isinstance(value,str) or len(value.encode())>policy.MAX_SNAPSHOT_BYTES or not value.startswith(SNAPSHOT_PREFIX) or not value.endswith(SNAPSHOT_SUFFIX):
        raise ValueError('Invalid static report snapshot.')
    body=value[len(SNAPSHOT_PREFIX):-len(SNAPSHOT_SUFFIX)]
    position=total=count=0
    for match in IMAGE.finditer(body):
        if match.start()!=position: raise ValueError('Snapshot includes untrusted markup.')
        height=int(match[1]);png=base64.b64decode(match[2],validate=True)
        if not 1<=height<=2000 or png[:8]!=b'\x89PNG\r\n\x1a\n' or len(png)<24 or struct.unpack('>II',png[16:24])!=(1280,height):
            raise ValueError('Snapshot image identity differs.')
        total+=height;count+=1;position=match.end()
    if not count or position!=len(body) or total>24000:
        raise ValueError('Snapshot includes partial or oversized content.')
    return value


class Renderer:
    def __init__(self):
        try:
            self.manifest=json.loads((ROOT/'.local/report-browser-runtime.json').read_text())
        except (OSError,ValueError):
            raise RuntimeError('Build the contained report browser first.') from None
        image=self.manifest.get('image')
        if not isinstance(image,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',image):
            raise ValueError('Report browser image must be pinned.')
        files={name:ROOT/'engine/report_browser'/name for name in ('Dockerfile','chrome.py','worker.py','.dockerignore')}
        files['inventory.py']=ROOT/'decision_room/reports/inventory.py'
        hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()}
        if hashes!=self.manifest.get('build_files'):
            raise RuntimeError('Report browser source differs from its pinned image. Rebuild it.')
        if policy.renderer_version()!=policy.RENDERER_VERSION+':'+image:
            raise RuntimeError('Report renderer changed since the worker started. Restart it.')
        self.env={key:os.environ[key] for key in ('PATH','HOME','TMPDIR') if key in os.environ}
        endpoint=subprocess.run(['docker','context','inspect',self.manifest['context'],'--format','{{.Endpoints.docker.Host}}'],
                                env=self.env,check=True,capture_output=True,text=True,timeout=15).stdout.strip()
        if not endpoint.startswith('unix://'): raise ValueError('The browser requires a local Docker daemon.')
        folder=ROOT/'.local/report-browser-cli';folder.mkdir(mode=0o700,exist_ok=True)
        (folder/'config.json').write_text('{}\n')
        self.prefix=['docker','--config',str(folder),'--host',endpoint]
        info=json.loads(self.control('image','inspect',image).stdout)[0]
        if info['Id']!=image: raise ValueError('Report browser image differs.')

    def control(self,*args,check=True):
        return subprocess.run([*self.prefix,*args],env=self.env,check=check,capture_output=True,timeout=20)

    def cleanup(self,name,identity):
        found=self.control('container','inspect',name,check=False)
        if found.returncode:
            self.control('info','--format','{{.ID}}')  # daemon failure is not container absence
            return
        row=json.loads(found.stdout)[0]
        if (row['Config'].get('Labels') or {}).get('decision-room.report-render')!=identity:
            raise ValueError('Render container is not owned by this job.')
        self.control('rm','-f',name)

    def render(self,source,job_id):
        if not isinstance(source,bytes) or not 1<=len(source)<=262144:
            raise ValueError('HTML receipt is outside its bound.')
        source.decode('utf-8',errors='strict')
        identity=str(UUID(str(job_id)));name='dr-render-'+identity
        self.cleanup(name,identity)  # exact orphan recovery; never adopt another container
        process=None
        try:
            self.control('create','--pull=never','--name',name,'--label','decision-room.report-render='+identity,
                '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                '--pids-limit','256','--memory','1g','--memory-swap','1g','--cpus','1',
                '--user','10001:10001','--log-driver','none','--init','-i',
                '--tmpfs','/tmp:rw,nosuid,nodev,size=536870912,uid=10001,gid=10001',self.manifest['image'])
            process=subprocess.Popen([*self.prefix,'start','-ai',name],env=self.env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            buffers={'out':bytearray(),'err':bytearray()};pending=memoryview(source)
            with selectors.DefaultSelector() as selector:
                for pipe,events,key in [(process.stdin,selectors.EVENT_WRITE,'in'),(process.stdout,selectors.EVENT_READ,'out'),(process.stderr,selectors.EVENT_READ,'err')]:
                    os.set_blocking(pipe.fileno(),False);selector.register(pipe,events,key)
                deadline=time.monotonic()+45
                while selector.get_map():
                    if time.monotonic()>deadline: raise TimeoutError('Contained browser exceeded its deadline.')
                    for selected,_ in selector.select(.1):
                        if selected.data=='in':
                            written=os.write(selected.fd,pending[:65536]);pending=pending[written:]
                            if not pending: selector.unregister(selected.fileobj);selected.fileobj.close()
                        else:
                            chunk=os.read(selected.fd,65536)
                            if not chunk: selector.unregister(selected.fileobj);continue
                            target=buffers[selected.data];target.extend(chunk)
                            if len(target)>(MAX_OUTPUT if selected.data=='out' else 65536):
                                raise ValueError('Contained browser exceeded its output bound.')
            process.wait(timeout=5)
            state=json.loads(self.control('inspect',name).stdout)[0]['State']
            if process.returncode or state['ExitCode'] or state['OOMKilled']:
                raise RuntimeError('Contained report rendering failed.')
            data=json.loads(buffers['out'])
            if not isinstance(data,dict) or set(data)!={'inventory','snapshot_html'}:
                raise ValueError('Contained report receipt differs.')
            rendered=inventory.validate(data['inventory'])
            if rendered['source_sha256']!=hashlib.sha256(source).hexdigest() or len(rendered['text'])>policy.MAX_TEXT or len(inventory.canonical(rendered))>policy.MAX_INVENTORY_BYTES:
                raise ValueError('Contained inventory identity differs.')
            data['snapshot_html']=validate_snapshot(data['snapshot_html'])
            return data
        finally:
            try:
                self.cleanup(name,identity)
            finally:
                if process is not None:
                    if process.poll() is None: process.kill()
                    process.wait(timeout=5)
                    for stream in (process.stdin,process.stdout,process.stderr):
                        if stream and not stream.closed: stream.close()
