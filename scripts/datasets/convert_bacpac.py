"""Lossless CSV extraction for the native BCP types used by this WWI package.

This is dataset preparation, not a general SQL Server backup importer.
Native layouts follow Microsoft's bcp prefix-length rules; every field is
encoded back to its original bytes during extraction to check the decoder.
"""
import argparse
import csv
from datetime import date
from decimal import Decimal
import hashlib
import gzip
import io
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile

from inspect_bacpac import BASE, SOURCE, get_schema

OUT = BASE / "data/wide-world-importers/exports"

def export_columns(spec):
    result = []
    for c in spec["columns"]:
        c = dict(c)
        if c["computed"]:
            c["reconstructed_from_expression"] = True
            if c["name"] == "IsFinalized":
                c.update(type="bit", nullable=False)
            elif c["name"] == "ConfirmedDeliveryTime":
                c.update(type="datetime2", Scale="7")
            else:
                c.update(type="nvarchar", IsMax="True")
        result.append(c)
    return result

def computed_value(c, values):
    n = c["name"]
    if n == "SearchName":
        return (values["PreferredName"] or "") + " " + (values["FullName"] or "")
    if n == "SearchDetails":
        return (values["StockItemName"] or "") + " " + (values["MarketingComments"] or "")
    if n == "IsFinalized":
        return int(values["FinalizationDate"] is not None)
    src = values["ReturnedDeliveryData"] if n.startswith("Confirmed") else values["CustomFields"]
    obj = json.loads(src) if src else {}
    key = {"OtherLanguages": "OtherLanguages", "Tags": "Tags", "ConfirmedDeliveryTime": "DeliveredWhen", "ConfirmedReceivedBy": "ReceivedBy"}[n]
    v = obj.get(key)
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    if n == "ConfirmedDeliveryTime" and v:
        v = v.replace("T", " ")
        if "." not in v:
            v += ".0000000"
        return v
    return v

class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, n):
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError(f"Truncated field at byte {self.pos}: {n}")
        b = self.data[self.pos:self.pos+n]
        self.pos += n
        return b

def field(r, c):
    typ = c["type"]
    prefix = 0
    if typ in ("nvarchar", "varbinary"):
        prefix = 8 if c.get("IsMax") == "True" else 2
    elif "geography" in typ:
        prefix = 8
    elif typ in ("decimal", "bit") or c["nullable"]:
        prefix = 1
    fixed = {"int": 4, "bigint": 8, "bit": 1, "date": 3,
             "datetime2": (3 if int(c.get("Scale", 7)) < 3 else 4 if int(c.get("Scale", 7)) < 5 else 5) + 3}
    n = int.from_bytes(r.take(prefix), "little", signed=True) if prefix else fixed.get(typ)
    if n == -1:
        if not c["nullable"]:
            raise ValueError(f"Unexpected NULL in {c['name']}")
        return None
    b = r.take(n)
    if typ in fixed and n != fixed[typ]:
        raise ValueError(f"Unexpected length {n} for {typ}")
    if typ in ("int", "bigint", "bit"):
        v = int.from_bytes(b, "little", signed=typ != "bit")
        if typ == "bit" and v not in (0, 1):
            raise ValueError("Invalid bit")
        encoded = v.to_bytes(n, "little", signed=typ != "bit")
    elif typ == "nvarchar":
        v = b.decode("utf-16-le")
        encoded = v.encode("utf-16-le")
    elif typ == "decimal":
        if n != 19 or b[0] != int(c["Precision"]) or b[1] != int(c["Scale"]) or b[2] not in (0, 1):
            raise ValueError(f"Invalid decimal layout {b.hex()}")
        mag = int.from_bytes(b[3:], "little")
        v = Decimal(mag).scaleb(-b[1]) * (1 if b[2] else -1)
        encoded = bytes((b[0], b[1], b[2])) + int(abs(v).scaleb(b[1])).to_bytes(16, "little")
        v = format(v, f".{b[1]}f")
    elif typ == "date":
        ordinal = int.from_bytes(b, "little") + 1
        v = date.fromordinal(ordinal).isoformat()
        encoded = (date.fromisoformat(v).toordinal()-1).to_bytes(3, "little")
    elif typ == "datetime2":
        scale = int(c.get("Scale", 7))
        ticks = int.from_bytes(b[:-3], "little")
        factor = 10**scale
        seconds, fraction = divmod(ticks, factor)
        if seconds >= 86400:
            raise ValueError("Invalid time")
        h, rem = divmod(seconds, 3600)
        m, sec = divmod(rem, 60)
        day = date.fromordinal(int.from_bytes(b[-3:], "little")+1)
        v = f"{day.isoformat()} {h:02}:{m:02}:{sec:02}" + (f".{fraction:0{scale}}" if scale else "")
        encoded = ((h*3600+m*60+sec)*factor+fraction).to_bytes(n-3,"little") + (day.toordinal()-1).to_bytes(3,"little")
    elif typ == "varbinary" or "geography" in typ:
        v = "0x" + b.hex()
        encoded = bytes.fromhex(v[2:])
    else:
        raise ValueError(f"Unsupported type: {typ}")
    if encoded != b:
        raise ValueError(f"Roundtrip mismatch for {c['name']}")
    return v

def extract_table(z, table, spec, limit=None):
    cols = [c for c in spec["columns"] if not c["computed"]]
    count = 0
    for name in spec["members"]:
        r = Reader(z.read(name))
        while r.pos < len(r.data):
            start = r.pos
            try:
                raw = [field(r, c) for c in cols]
                values = dict(zip((c["name"] for c in cols), raw))
                row = [computed_value(c, values) if c["computed"] else values[c["name"]] for c in spec["columns"]]
            except Exception as e:
                raise ValueError(f"{table}, file {name}, row {count+1}, byte {start}: {e}") from e
            yield row
            count += 1
            if limit and count >= limit:
                return

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()
    with zipfile.ZipFile(SOURCE) as z:
        schema = get_schema(z)
        if args.probe:
            for table, spec in schema.items():
                rows = list(extract_table(z, table, spec, limit=2))
                print(table, json.dumps(rows, ensure_ascii=False)[:500], flush=True)
            return
        (OUT/"csv").mkdir(parents=True, exist_ok=True)
        (OUT/"metadata/null-masks").mkdir(parents=True, exist_ok=True)
        manifest = {"source": SOURCE.name, "source_sha256": hashlib.file_digest(SOURCE.open("rb"), "sha256").hexdigest(), "tables": []}
        total = 0
        for table, spec in schema.items():
            cols = export_columns(spec)
            dest = OUT/"csv"/f"{table}.csv"
            count, nulls, blanks, max_chars = 0, [0]*len(cols), [0]*len(cols), [0]*len(cols)
            samples = []
            nullfile = OUT/"metadata/null-masks"/f"{table}.bin.gz"
            with dest.open("w", encoding="utf-8-sig", newline="") as f, gzip.open(nullfile, "wb") as masks:
                # QUOTE_NOTNULL preserves NULL (unquoted empty) vs empty string (quoted).
                writer = csv.writer(f, quoting=csv.QUOTE_NOTNULL)
                writer.writerow([c["name"] for c in cols])
                for row in extract_table(z, table, spec):
                    writer.writerow(row)
                    mask = sum(1 << j for j, v in enumerate(row) if v is None)
                    masks.write(mask.to_bytes((len(cols)+7)//8,"little"))
                    count += 1
                    if len(samples) < 8:
                        samples.append(row)
                    for j, v in enumerate(row):
                        nulls[j] += v is None
                        blanks[j] += v == ""
                        max_chars[j] = max(max_chars[j], len(str(v)) if v is not None else 0)
            item = {"table": table, "rows": count, "columns": cols, "null_counts": nulls, "empty_string_counts": blanks, "max_characters": max_chars, "sample": samples, "csv": f"csv/{table}.csv", "null_mask": str(nullfile.relative_to(OUT)), "sha256": hashlib.file_digest(dest.open("rb"),"sha256").hexdigest()}
            manifest["tables"].append(item)
            total += count
            print(f"{table}: {count:,} rows", flush=True)
        origin = ET.fromstring(z.read("Origin.xml"))
        expected = int(next(e.text for e in origin.iter() if e.tag.endswith("TableRowCountTotalTag")))
        if total != expected:
            raise ValueError(f"Row count mismatch: {total} vs source {expected}")
        manifest.update(total_rows=total, expected_source_rows=expected, all_fields_binary_roundtrip_verified=True)
        (OUT/"manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+"\n")
        print(f"Verified {total:,} rows against source metadata", flush=True)

if __name__ == "__main__":
    main()
