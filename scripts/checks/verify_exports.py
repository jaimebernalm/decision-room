"""Check saved workbook values, source row counts, relationships and amounts."""
import argparse
import collections
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from xml.parsers import expat
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/datasets'))

from convert_bacpac import BASE, OUT, SOURCE
from fill_excel_workbooks import hash_row, sheet_paths
from prepare_excel_plan import typed_rows

def unescape_ooxml(s):
    return re.sub(r"_x([0-9A-Fa-f]{4})_",lambda m:chr(int(m[1],16)),s)

def verify_excel():
    checks=json.loads((OUT/"metadata/excel-checks.json").read_text())
    total=0
    for book in checks["workbooks"]:
        with zipfile.ZipFile(OUT/book["file"]) as z:
            paths=sheet_paths(z)
            for spec in book["sheets"]:
                digest=hashlib.sha256()
                state={"count":0,"rownum":0,"row":None,"celltype":None,"col":0,"capture":False,"text":[]}
                def start(name,attrs):
                    name=name.split("|")[-1]
                    if name=="row":
                        state["rownum"]=int(attrs["r"])
                        state["row"]=[None]*spec["columns"]
                    elif name=="c":
                        col=0
                        for ch in re.match(r"[A-Z]+",attrs["r"])[0]:col=col*26+ord(ch)-64
                        state["col"]=col-1
                        state["celltype"]=attrs.get("t","n")
                        state["text"]=[]
                    elif name in ("v","t"):
                        state["capture"]=True
                    elif name=="f":
                        raise AssertionError("Unexpected formula in raw export")
                def end(name):
                    name=name.split("|")[-1]
                    if name in ("v","t"):
                        state["capture"]=False
                    elif name=="c" and state["rownum"]>1:
                        typ=state["celltype"]
                        assert typ in ("inlineStr","n","b"),typ
                        text="".join(state["text"])
                        if typ=="inlineStr":text=unescape_ooxml(text)
                        assert len(text)<=32767
                        state["row"][state["col"]]=[typ,text]
                    elif name=="row" and state["rownum"]>1:
                        state["count"]+=1
                        assert state["rownum"]==state["count"]+1
                        hash_row(digest,state["row"])
                def char(s):
                    if state["capture"]:state["text"].append(s)
                parser=expat.ParserCreate(namespace_separator="|")
                parser.StartElementHandler=start
                parser.EndElementHandler=end
                parser.CharacterDataHandler=char
                with z.open(paths[spec["sheet"]]) as f:
                    parser.ParseFile(f)
                assert state["count"]==spec["rows"],spec
                assert digest.hexdigest()==spec["expected_data_digest"],spec
                total+=state["count"]
                print(f"Verified saved values: {spec['sheet']} ({state['count']:,})",flush=True)
        book["saved_values_verified"]=True
        assert hashlib.file_digest((OUT/book["file"]).open("rb"),"sha256").hexdigest()==book["sha256"]
    manifest=json.loads((OUT/"manifest.json").read_text())
    assert total==manifest["total_rows"]
    for entry in checks["large_values"]:
        v=(OUT/entry["path"]).read_bytes()
        assert hashlib.sha256(v).hexdigest()==entry["sha256"]
    checks["verified_total_rows"]=total
    (OUT/"metadata/excel-checks.json").write_text(json.dumps(checks,indent=2)+"\n")

def verify_relations():
    manifest=json.loads((OUT/"manifest.json").read_text())
    tables={t["table"]:t for t in manifest["tables"]}
    with zipfile.ZipFile(SOURCE) as z:root=ET.fromstring(z.read("model.xml"))
    ns={"m":root.tag.split("}")[0][1:]}
    def refs(e,name):
        return [r.get("Name").replace("[","").replace("]","") for r in e.findall(f"m:Relationship[@Name='{name}']/m:Entry/m:References",ns)]
    fks=[]
    needed=collections.defaultdict(set)
    for e in root.findall(".//m:Element[@Type='SqlForeignKeyConstraint']",ns):
        table=refs(e,"DefiningTable")[0];parent=refs(e,"ForeignTable")[0]
        cols=tuple(n.rsplit(".",1)[1] for n in refs(e,"Columns"))
        pcols=tuple(n.rsplit(".",1)[1] for n in refs(e,"ForeignColumns"))
        fks.append((e.get("Name"),table,cols,parent,pcols))
        needed[table].add(cols);needed[parent].add(pcols)
    keys={}
    nulls={}
    for table,fields in needed.items():
        spec=tables[table];names=[c["name"] for c in spec["columns"]]
        indexes={cols:tuple(names.index(c)for c in cols)for cols in fields}
        for cols in fields:keys[(table,cols)]=set()
        for row in typed_rows(spec):
            for cols,positions in indexes.items():
                value=tuple(row[j] for j in positions)
                if None not in value:keys[(table,cols)].add(value)
    invalid=[]
    for name,table,cols,parent,pcols in fks:
        missing=keys[(table,cols)]-keys[(parent,pcols)]
        if missing:invalid.append({"constraint":name,"missing":len(missing),"examples":list(missing)[:5]})
    spec=tables["Sales.InvoiceLines"];names=[c["name"]for c in spec["columns"]]
    sums=collections.defaultdict(Decimal);mismatches=0;tax_mismatches=0
    for row in typed_rows(spec):
        d=dict(zip(names,row));qty=Decimal(d["Quantity"]);price=Decimal(d["UnitPrice"])
        tax=Decimal(d["TaxAmount"]);extended=Decimal(d["ExtendedPrice"])
        mismatches+=qty*price+tax!=extended
        tax_mismatches+=(qty*price*Decimal(d["TaxRate"])/100).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)!=tax
        for col in ("Quantity","TaxAmount","ExtendedPrice","LineProfit"):sums[col]+=Decimal(d[col])
    report={"foreign_keys_checked":len(fks),"foreign_key_violations":invalid,"invoice_lines_checked":spec["rows"],"invoice_arithmetic_mismatches":mismatches,"invoice_tax_mismatches":tax_mismatches,"invoice_line_totals":{k:str(v)for k,v in sums.items()},"source_total_rows":manifest["expected_source_rows"],"csv_total_rows":manifest["total_rows"]}
    (OUT/"metadata/data-validation.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2),flush=True)
    assert not invalid and mismatches==0 and tax_mismatches==0

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--relations",action="store_true");a=p.parse_args()
    if a.relations:verify_relations()
    else:verify_excel()
