"""Static output validation and native hostile HTML inside Docker, never host Chrome."""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import struct
import time
import unittest
from uuid import uuid4

from decision_room.config import ROOT
from decision_room.reports import inventory, render_browser as rb


class OutputTests(unittest.TestCase):
    def test_static_snapshot_cannot_smuggle_markup_urls_or_dimensions(self):
        for value in [None,'<script>alert(1)</script>',rb.SNAPSHOT_PREFIX+'<img src="https://example.org">'+rb.SNAPSHOT_SUFFIX,
                      rb.SNAPSHOT_PREFIX+'<img onerror="x" src="data:image/png;base64,AA">'+rb.SNAPSHOT_SUFFIX,
                      rb.SNAPSHOT_PREFIX+rb.SNAPSHOT_SUFFIX]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError): rb.validate_snapshot(value)

    def test_inventory_spans_preserve_unicode_inline_nodes_and_sign(self):
        source=b'<p>fixture</p>'
        snapshot={'nodes':[{'path':[0,0],'text':'Units \U0001f600 -','region':'text'}, {'path':[0,1],'text':'5','region':'text'},
                           {'separator':'\n'}, {'path':[1,0],'text':'Total 12'}]}
        result=inventory.validate(inventory.from_snapshot(source,snapshot))
        self.assertEqual([r['text'] for r in result['occurrences']],['-5','12'])
        self.assertEqual(result['occurrences'][0]['parts'][0]['span'],[9,10])
        self.assertEqual(result['text'],'Units \U0001f600 -5\nTotal 12')


@unittest.skipUnless((ROOT/'.local/report-browser-runtime.json').is_file(),'Build the contained report browser for native tests.')
class NativeBrowserTests(unittest.TestCase):
    def test_executed_script_svg_negative_and_pixel_snapshot_agree(self):
        raw=b'''<html><body><h1>Units 5</h1><div id="chart"></div>
            <script>document.getElementById('chart').innerHTML='<svg width="300" height="80"><text x="10" y="30">Delta -5</text><rect x="0" y="40" width="50" height="20"/></svg>'</script></body></html>'''
        output=rb.Renderer().render(raw,uuid4())
        self.assertIn('Delta -5',output['inventory']['text'])
        self.assertIn('-5',[r['text'] for r in output['inventory']['occurrences']])
        self.assertEqual(output['inventory']['charts'][0]['tag'],'svg')
        rb.validate_snapshot(output['snapshot_html'])
        self.assertNotIn('<script',output['snapshot_html']); self.assertNotIn('<svg',output['snapshot_html'])

    def test_network_and_file_urls_do_not_enter_canonical_text(self):
        raw=b'''<h1>Public 5</h1><script>
          for(const url of ['http://127.0.0.1:1/secret','https://example.invalid/secret','file:///opt/report/worker.py'])
            fetch(url).then(r=>r.text()).then(t=>document.body.append(t)).catch(()=>{});
          document.body.append('safe');
        </script>'''
        output=rb.Renderer().render(raw,uuid4())
        self.assertIn('safe',output['inventory']['text'])
        self.assertNotIn('import',output['inventory']['text'])
        self.assertNotIn('secret',output['inventory']['text'])

    def test_js_cannot_replace_inspection_globals(self):
        raw=b'''<h1>Real 25</h1><script>
          window.getComputedStyle=()=>({display:'none'});
          Document.prototype.createRange=()=>({getClientRects:()=>[]});
        </script>'''
        self.assertIn('Real 25',rb.Renderer().render(raw,uuid4())['inventory']['text'])

    def test_long_report_tiled_without_silent_crop(self):
        raw=b'<html><body><div style="height:4200px">Start 1</div><p>End 2</p></body></html>'
        output=rb.Renderer().render(raw,uuid4())
        matches=list(rb.IMAGE.finditer(output['snapshot_html']))
        self.assertGreater(len(matches),2)
        self.assertGreater(sum(int(m[1]) for m in matches),4200)
        self.assertIn('End 2',output['inventory']['text'])

    def test_invalid_encoding_overflow_navigation_and_unstable_dom_fail_closed(self):
        cases=[b'\xff',b'<div style="height:24001px">cut</div>',b'<div style="width:1600px">wide</div>',
               b'<script>location.href="data:text/html,changed"</script>',
               b'<p id="x">0</p><script>setInterval(()=>document.getElementById("x").textContent=Math.random(),50)</script>']
        for raw in cases:
            with self.subTest(raw=raw[:60]), self.assertRaises((ValueError,RuntimeError,TimeoutError)):
                rb.Renderer().render(raw,uuid4())

    def test_busy_script_is_contained_and_removed_after_failure(self):
        renderer=rb.Renderer();identity=uuid4();name='dr-render-'+str(identity)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(renderer.render,b'<script>while(true){}</script>',identity)
            row=None;deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                inspected=renderer.control('container','inspect',name,check=False)
                if inspected.returncode==0:
                    row=json.loads(inspected.stdout)[0]
                    if row['State']['Running']: break
                time.sleep(.05)
            self.assertIsNotNone(row)
            self.assertEqual(row['HostConfig']['NetworkMode'],'none')
            self.assertTrue(row['HostConfig']['ReadonlyRootfs'])
            self.assertEqual(row['HostConfig']['CapDrop'],['ALL'])
            self.assertFalse(row['Mounts'])
            self.assertEqual(row['HostConfig']['PidsLimit'],256)
            self.assertEqual(row['HostConfig']['Memory'],1024**3)
            self.assertEqual(row['HostConfig']['MemorySwap'],1024**3)
            self.assertEqual(row['HostConfig']['NanoCpus'],10**9)
            self.assertEqual(row['Config']['User'],'10001:10001')
            self.assertFalse(any('OPENAI' in v or 'DATABASE' in v for v in row['Config']['Env']))
            with self.assertRaises((ValueError,RuntimeError,TimeoutError)): future.result(timeout=55)
        self.assertNotEqual(renderer.control('container','inspect',name,check=False).returncode,0)

    def test_orphan_recovery_uses_exact_job_identity_and_refuses_foreign_labels(self):
        renderer=rb.Renderer();identity=uuid4();name='dr-render-'+str(identity)
        args=['create','--name',name,'--label','decision-room.report-render='+str(identity),
              '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
              '--user','10001:10001','--memory','64m','--pids-limit','16','--cpus','1','--entrypoint','python',
              renderer.manifest['image'],'-I','-c','import time;time.sleep(60)']
        renderer.control(*args);self.addCleanup(lambda:renderer.control('rm','-f',name,check=False))
        renderer.control('start',name)
        result=renderer.render(b'<h1>Recovered 5</h1>',identity)
        self.assertIn('Recovered 5',result['inventory']['text'])
        self.assertNotEqual(renderer.control('container','inspect',name,check=False).returncode,0)
        args[4]='decision-room.report-render='+str(uuid4())
        renderer.control(*args)
        with self.assertRaises(ValueError): renderer.render(b'<h1>Foreign</h1>',identity)
        self.assertEqual(renderer.control('container','inspect',name).returncode,0)
