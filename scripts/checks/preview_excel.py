"""Create bounded QA copies from saved workbook XML; originals are unchanged."""
import json
import re
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/datasets'))

from convert_bacpac import BASE, OUT
from fill_excel_workbooks import sheet_paths

dest_dir=BASE/".tools/spreadsheets/saved-previews"
dest_dir.mkdir(parents=True,exist_ok=True)
plan=json.loads((OUT/"metadata/excel-plan.json").read_text())
for group,specs in plan["groups"].items():
    original=OUT/"excel"/f"WideWorldImporters-{group}.xlsx"
    with zipfile.ZipFile(original) as src,zipfile.ZipFile(BASE/".tools/spreadsheets/templates"/f"{group}.xlsx") as template,zipfile.ZipFile(dest_dir/f"{group}.xlsx","w",compression=zipfile.ZIP_DEFLATED) as out:
        paths=sheet_paths(src);by_path={paths[s["sheet"]]:s for s in specs}
        for info in src.infolist():
            if info.filename not in by_path:
                out.writestr(info,src.read(info));continue
            spec=by_path[info.filename]
            target_rows=min(7,spec["rows"]+1)
            data=b""
            with src.open(info) as f:
                while data.count(b"</row>")<target_rows:
                    block=f.read(32768)
                    if not block:break
                    data+=block
            text=data.decode("utf-8",errors="ignore")
            ends=list(re.finditer(r"</row>",text))
            text=text[:ends[target_rows-1].end()]+"</sheetData>"
            tail=template.read(info.filename).decode()
            tail=re.sub(r"<(/?)x:",r"<\1",tail).replace('xmlns:x=','xmlns=')
            tail=tail.split("</sheetData>",1)[1]
            text=re.sub(r'(<dimension ref="[A-Z]+\d+:[A-Z]+)\d+',rf'\g<1>{target_rows}',text)
            out.writestr(info.filename,text+tail)
    print("QA copy:",group)
