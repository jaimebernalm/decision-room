"""Build the contained browser into a trusted, pinned local image (no report input)."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',required=True)
    args=parser.parse_args()
    files={name:ROOT/'engine/report_browser'/name for name in ('Dockerfile','chrome.py','worker.py','.dockerignore')}
    files['inventory.py']=ROOT/'decision_room/reports/inventory.py'
    hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()}
    with tempfile.TemporaryDirectory(prefix='dr-browser-build-') as temp:
        for name,path in files.items(): shutil.copyfile(path,Path(temp)/name)
        subprocess.run(['docker','--context',args.context,'build','-t','decision-room-report-browser:local',temp],check=True)
    info=json.loads(subprocess.run(['docker','--context',args.context,'image','inspect','decision-room-report-browser:local'],check=True,capture_output=True).stdout)[0]
    runtime={'context':args.context,'image':info['Id'],'build_files':hashes,'architecture':info['Architecture']}
    target=ROOT/'.local/report-browser-runtime.json';target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(runtime,indent=2)+'\n');target.chmod(0o600)
    print(json.dumps(runtime,indent=2))


if __name__=='__main__': main()
