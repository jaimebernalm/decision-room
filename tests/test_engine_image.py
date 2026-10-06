"""Opt-in smoke of the real pinned image; no model prompts or provider credentials.

Set DECISION_ROOM_ENGINE_IMAGE_ID to the immutable locally built image ID.
The test owns and removes only its uniquely named container and internal network.
"""
import json
import os
import re
import secrets
import subprocess
import time
import textwrap
import unittest
from pathlib import Path
from uuid import uuid4

from decision_room.docker_backend import DockerBackend


def smoke(image_id):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
        raise ValueError('Use an immutable local engine image ID.')
    b=DockerBackend();ident=uuid4().hex;name='dr-engine-smoke-'+ident;network=name+'-net'
    image=image_id
    password=secrets.token_urlsafe(32)
    config={'autoupdate':False,'share':'disabled','snapshot':False,'model':'openai/gpt-6-luna','permission':{'*':'deny'}}
    env={**b.cli_env,'OPENCODE_SERVER_PASSWORD':password,'OPENCODE_CONFIG_CONTENT':json.dumps(config)}
    def docker(*args,check=True,**kwargs):
     return subprocess.run([*b.prefix,*args],env=env,capture_output=True,text=True,timeout=60,check=check,**kwargs)
    try:
     docker('network','create','--internal','--label','decision-room.engine-smoke='+ident,network)
     docker('run','-d','--name',name,'--label','decision-room.engine-smoke='+ident,
            '--network',network,'--dns','127.0.0.1','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--pids-limit','512','--memory','2g','--cpus','2','--user','10001:10001',
            '--tmpfs','/tmp:rw,nosuid,nodev,size=268435456','--tmpfs','/home/agent:rw,nosuid,nodev,uid=10001,gid=10001',
            '--tmpfs','/work:rw,nosuid,nodev,uid=10001,gid=10001','--tmpfs','/state:rw,nosuid,nodev,uid=10001,gid=10001',
            '-e','OPENCODE_SERVER_PASSWORD','-e','OPENCODE_CONFIG_CONTENT',image,'serve','--hostname','0.0.0.0','--port','4096')
     probe=r'''    import base64,json,os,time,urllib.request,urllib.error
    base='http://127.0.0.1:4096'
    key=base64.b64encode(('opencode:'+os.environ['OPENCODE_SERVER_PASSWORD']).encode()).decode()
    def request(path,body=None,method=None,authenticated=True):
     headers={'Authorization':'Basic '+key} if authenticated else {}
     if body is not None: headers['Content-Type']='application/json'
     req=urllib.request.Request(base+path,headers=headers,data=None if body is None else json.dumps(body).encode(),method=method)
     with urllib.request.urlopen(req,timeout=3) as response:
      raw=response.read();return json.loads(raw) if raw else None
    for _ in range(25):
     try: health=request('/global/health');break
     except (OSError,urllib.error.URLError):time.sleep(1)
    else:raise RuntimeError('Server unavailable')
    assert health=={'healthy':True,'version':'1.18.34'}
    try:request('/global/health',authenticated=False)
    except urllib.error.HTTPError as error:assert error.code==401
    else:raise AssertionError('Unauthenticated server access')
    session=request('/session?directory=/work',{'title':'Engine smoke without model calls','model':{'id':'gpt-6-luna','providerID':'openai','variant':'low'}})
    path='/session/'+session['id']
    assert request(path)['title']=='Engine smoke without model calls'
    assert request(path+'/message')==[]
    assert request(path+'/children')==[]
    assert request(path+'/abort',method='POST') is True
    print('Real OpenCode 1.18.34: auth, session, title, messages, children, abort OK; no prompt sent')
    '''
     result=docker('exec','-i',name,'python','-',input=textwrap.dedent(probe))
     assert 'Real OpenCode 1.18.34' in result.stdout
     result=docker('exec',name,'python','-c',"import os,socket; assert 'OPENAI_API_KEY' not in os.environ; assert not os.path.exists('/Users'); socket.setdefaulttimeout(2);\ntry: socket.getaddrinfo('example.com',443)\nexcept OSError: print('No provider key, host paths or external DNS')\nelse: raise RuntimeError('External DNS unexpectedly available')")
     assert 'No provider key, host paths or external DNS' in result.stdout
    finally:
     docker('rm','-f',name,check=False)
     docker('network','rm',network,check=False)


class ImageTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DECISION_ROOM_ENGINE_IMAGE_ID'), 'Build the pinned engine image to run this smoke test.')
    def test_real_serve_auth_session_and_isolation_without_model(self):
        smoke(os.environ['DECISION_ROOM_ENGINE_IMAGE_ID'])


if __name__ == '__main__':
    unittest.main()
