"""Inspect the source schema without requiring a database server."""
import collections
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

BASE = Path(__file__).resolve().parents[2]
SOURCE = BASE / "data/wide-world-importers/WideWorldImporters-Full.bacpac"

def get_schema(z):
    root = ET.fromstring(z.read("model.xml"))
    ns = {"m": root.tag.split("}")[0][1:]}
    result = {}
    for t in root.findall(".//m:Element[@Type='SqlTable']", ns):
        name = t.get("Name").replace("[", "").replace("]", "")
        cols = []
        for c in t.findall("m:Relationship[@Name='Columns']/m:Entry/m:Element", ns):
            props = {p.get("Name"): p.get("Value", p.findtext("m:Value", namespaces=ns)) for p in c.findall("m:Property", ns)}
            spec = c.find("m:Relationship[@Name='TypeSpecifier']/m:Entry/m:Element", ns)
            column = {"name": c.get("Name").split(".[")[-1].rstrip("]"), "computed": c.get("Type") == "SqlComputedColumn", "nullable": props.get("IsNullable") != "False"}
            if spec is not None:
                typ = spec.find(".//m:References", ns)
                column.update(type=typ.get("Name").strip("[]"), **{p.get("Name"): p.get("Value") for p in spec.findall("m:Property", ns)})
            else:
                column["expression"] = props.get("ExpressionScript")
            cols.append(column)
        result[name] = {"columns": cols, "members": sorted(n for n in z.namelist() if n.startswith(f"Data/{name}/"))}
    return result

if __name__ == "__main__":
    with zipfile.ZipFile(SOURCE) as z:
        schema = get_schema(z)
        target = BASE / "data/wide-world-importers/schema.json"
        target.write_text(json.dumps(schema, indent=2) + "\n")
        print("Types:", collections.Counter(c.get("type", "computed") for t in schema.values() for c in t["columns"]))
        print("Origin:", z.read("Origin.xml").decode()[:1800])
        for name in ("Application.PaymentMethods", "Sales.InvoiceLines", "Sales.Customers", "Warehouse.StockItems", "Warehouse.ColdRoomTemperatures"):
            t = schema[name]
            print(name, json.dumps(t["columns"]))
            if t["members"]:
                print(z.read(t["members"][0])[:180].hex())
