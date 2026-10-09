from pathlib import Path
import tempfile
import unittest

from decision_room.reports.posthoc.inventory import build_inventory
from decision_room.reports.posthoc.browser import Browser, chrome_binary
from decision_room.reports.posthoc.presentation import render, check


class PresentationTests(unittest.TestCase):
    def test_real_chrome_preserves_inline_text_and_script_generated_svg(self):
        try:chrome_binary()
        except RuntimeError:self.skipTest('Chrome not installed')
        source='''<!doctype html><html><head><meta charset="utf-8"><title>Test</title></head><body><h1>Informe</h1><p>😀 Total: <b>42</b>,5 %; otra cifra 42.</p><div id="chart"></div><script>document.getElementById('chart').innerHTML='<svg width="140" height="45"><rect width="42" height="15" fill="blue"/><text y="40">42</text></svg>'</script>\n</body></html>\n'''.encode()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);original=root/'original.html';derived=root/'derived.html'
            original.write_bytes(source);inventory=build_inventory(original)
            ledger={o['id']:{'status':'not_checkable' if o['region']=='chart' else 'verified'} for o in inventory['occurrences']}
            derived.write_bytes(render(source,inventory,ledger))
            result=check(original,derived,inventory)
            self.assertTrue(result['invariants_passed']);self.assertEqual(result['charts_compared'],1)
            self.assertEqual(original.read_bytes(),source)
            self.assertTrue(derived.read_bytes().startswith(source))

    def test_changed_source_or_missing_occurrence_is_rejected(self):
        try:chrome_binary()
        except RuntimeError:self.skipTest('Chrome not installed')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.html';path.write_bytes(b'<p>Total 42</p>')
            inventory=build_inventory(path)
            with self.assertRaises(ValueError):render(b'<p>Total 43</p>',inventory,{})
            with self.assertRaises(ValueError):render(path.read_bytes(),inventory,{})

if __name__=='__main__':unittest.main()
