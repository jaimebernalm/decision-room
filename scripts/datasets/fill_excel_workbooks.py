"""Stream the full data into Artifact Tool-authored workbook layouts.

Artifact Tool authors the worksheets, formatting, sources and previews. Its
public export API has no streaming row interface. This standard-library pass
fills sheetData without holding 4.7 million rows in memory, retaining layouts.
"""
import csv
from datetime import date
from decimal import Decimal
import hashlib
import json
import re
import shutil
from pathlib import Path
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
import zipfile

from convert_bacpac import BASE, OUT
from prepare_excel_plan import typed_rows

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ROW_LIMIT = 1_000_000

def column_name(i):
    s = ""
    while i:
        i, rem = divmod(i-1, 26)
        s = chr(65+rem)+s
    return s

def safe_text(v):
    # Preserve literal OOXML escape sequences before encoding control characters.
    v = re.sub(r"_x[0-9A-Fa-f]{4}_", lambda m: "_x005F_"+m[0][1:], v)
    v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", lambda m: f"_x{ord(m[0]):04X}_", v)
    return escape(v).replace("\r", "&#13;")

def value_for_excel(v, col, table, rownum, colnum, large_values):
    if v is None:
        return None, None
    if len(v) > 32767:
        suffix = ".hex" if v.startswith("0x") else ".txt"
        relative = f"large-values/{table}/{rownum}_{colnum}{suffix}"
        target = OUT/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(v, encoding="utf-8")
        large_values.append({"table": table, "row": rownum, "column": col["name"], "path": relative, "characters": len(v), "sha256": hashlib.sha256(v.encode()).hexdigest()})
        return "inlineStr", "../"+relative
    typ = col["type"]
    if typ == "date":
        d = date.fromisoformat(v)
        days = (d-date(1899,12,30)).days
        assert days >= 61, "Earlier Excel dates require explicit handling"
        return "n", str(days)
    if typ == "bit":
        assert v in ("0", "1")
        return "b", v
    if typ in ("int", "bigint", "decimal") and not col["name"].endswith("ID"):
        digits = len(Decimal(v).as_tuple().digits)
        if digits <= 15:
            return "n", v
    return "inlineStr", v

def hash_row(digest, row):
    digest.update(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    digest.update(b"\n")

def sheet_paths(z):
    workbook = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    paths = {r.get("Id"): r.get("Target") for r in rels}
    return {s.get("name"): "xl/"+paths[s.get("{"+REL+"}id")].lstrip("/").removeprefix("xl/") for s in workbook.find("m:sheets", NS)}

def main():
    manifest = json.loads((OUT/"manifest.json").read_text())
    plan = json.loads((OUT/"metadata/excel-plan.json").read_text())
    tables = {t["table"]:t for t in manifest["tables"]}
    (OUT/"excel").mkdir(exist_ok=True)
    checks = {"workbooks": [], "large_values": []}
    for group, sheets in plan["groups"].items():
        template = BASE/".tools/spreadsheets/templates"/f"{group}.xlsx"
        target = OUT/"excel"/f"WideWorldImporters-{group}.xlsx"
        record = {"file": str(target.relative_to(OUT)), "sheets": []}
        with zipfile.ZipFile(template) as src, zipfile.ZipFile(str(target)+".part", "w", compression=zipfile.ZIP_DEFLATED, compresslevel=5, allowZip64=True) as dest:
            paths = sheet_paths(src)
            by_path = {paths[p["sheet"]]: p for p in sheets}
            iterators = {}
            for item in src.infolist():
                if item.filename not in by_path:
                    dest.writestr(item,src.read(item))
                    continue
                p = by_path[item.filename]
                table = tables[p["table"]]
                cols = table["columns"]
                data = src.read(item).decode("utf-8")
                data = re.sub(r"<(/?)x:", r"<\1", data).replace('xmlns:x=', 'xmlns=')
                root = ET.fromstring(data)
                row2 = root.find("m:sheetData/m:row[@r='2']",NS)
                styles = {}
                if row2 is not None:
                    styles = {re.sub(r"\d+", "", c.get("r")): c.get("s") for c in row2}
                sd = root.find("m:sheetData", NS)
                # Keep Artifact Tool's original styled header XML unmodified.
                match = re.search(r"<sheetData[^>]*>(.*?)</sheetData>",data,re.S)
                if not match:
                    raise ValueError("Template sheetData missing")
                head = re.search(r"<row\b[^>]*\br=\"1\"[^>]*>.*?</row>",match[1],re.S)[0]
                before,after=data[:match.start()],data[match.end():]
                area=f"A1:{column_name(len(cols))}{p['rows']+1}"
                before=re.sub(r'<dimension\b[^>]*/>',f'<dimension ref="{area}"/>',before)
                if '<dimension ' not in before:
                    before=re.sub(r'(<worksheet\b[^>]*>)',rf'\1<dimension ref="{area}"/>',before,count=1)
                after=re.sub(r'<autoFilter\b[^>]*/>', '', after)
                after=f'<autoFilter ref="{area}"/>'+after
                iterator=iterators.setdefault(p["table"],iter(typed_rows(table)))
                digest=hashlib.sha256()
                sheet_record={"sheet":p["sheet"],"table":p["table"],"rows":p["rows"],"columns":len(cols),"start":p["start"]}
                with dest.open(item.filename,"w",force_zip64=True) as out:
                    out.write((before+"<sheetData>"+head).encode())
                    buffer=[]
                    for i in range(p["rows"]):
                        row=next(iterator)
                        cells=[]
                        canonical=[]
                        for j,(v,c) in enumerate(zip(row,cols),1):
                            typ,val=value_for_excel(v,c,p["table"],p["start"]+i+1,j,checks["large_values"])
                            canonical.append(None if typ is None else [typ,val])
                            if typ is None:
                                continue
                            letter=column_name(j)
                            style=f' s="{styles[letter]}"' if styles.get(letter) is not None else ""
                            address=f'{letter}{i+2}'
                            if typ=="inlineStr":
                                cells.append(f'<c r="{address}"{style} t="inlineStr"><is><t xml:space="preserve">{safe_text(val)}</t></is></c>')
                            else:
                                cells.append(f'<c r="{address}"{style} t="{typ}"><v>{val}</v></c>')
                        hash_row(digest,canonical)
                        buffer.append(f'<row r="{i+2}" ht="44" customHeight="1">'+"".join(cells)+"</row>")
                        if len(buffer)==1000:
                            out.write("".join(buffer).encode())
                            buffer=[]
                    if buffer:
                        out.write("".join(buffer).encode())
                    out.write(("</sheetData>"+after).encode())
                sheet_record["expected_data_digest"]=digest.hexdigest()
                record["sheets"].append(sheet_record)
                print(f"{group}/{p['sheet']}: {p['rows']:,} rows",flush=True)
                if p["start"]+p["rows"]==table["rows"]:
                    assert next(iterator,None) is None
            record["rows"]=sum(s["rows"] for s in record["sheets"])
        Path(str(target)+".part").replace(target)
        record.update(bytes=target.stat().st_size,sha256=hashlib.file_digest(target.open("rb"),"sha256").hexdigest())
        checks["workbooks"].append(record)
        (OUT/"metadata/excel-checks.json").write_text(json.dumps(checks,indent=2)+"\n")
        print(f"Saved {target.name}",flush=True)

if __name__=="__main__":
    main()
