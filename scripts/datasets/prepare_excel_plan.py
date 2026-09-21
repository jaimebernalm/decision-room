"""Plan four Excel workbooks and bounded worksheet previews from the CSVs."""
import csv
import gzip
import json
from pathlib import Path

from convert_bacpac import BASE, OUT

MAX_ROWS = 1_000_000

def typed_rows(table):
    csv.field_size_limit(10_000_000)
    width = (len(table["columns"])+7)//8
    with (OUT/table["csv"]).open(encoding="utf-8-sig", newline="") as f, gzip.open(OUT/table["null_mask"], "rb") as masks:
        reader = csv.reader(f)
        assert next(reader) == [c["name"] for c in table["columns"]]
        for row in reader:
            raw = masks.read(width)
            assert len(raw) == width
            mask = int.from_bytes(raw, "little")
            yield [None if mask & (1 << j) else value for j, value in enumerate(row)]
        assert not masks.read(1)

def main():
    manifest = json.loads((OUT/"manifest.json").read_text())
    groups = {g: [] for g in ("Sales", "Purchasing", "Warehouse", "Application")}
    for table in manifest["tables"]:
        samples = {}
        count = 0
        for count, row in enumerate(typed_rows(table), 1):
            if (count-1) % MAX_ROWS < 8:
                samples.setdefault((count-1)//MAX_ROWS, []).append(row)
        assert count == table["rows"], table["table"]
        group, name = table["table"].split(".")
        pieces = max(1, (count+MAX_ROWS-1)//MAX_ROWS)
        for part in range(pieces):
            sheet = name if len(name) <= 31 and pieces == 1 else name.replace("Temperatures", "Temps").replace("_Archive", "_History")[:26] + (f"_{part+1}" if pieces > 1 else "")
            groups[group].append({"table": table["table"], "sheet": sheet, "part": part, "start": part*MAX_ROWS, "rows": min(MAX_ROWS, max(0, count-part*MAX_ROWS)), "columns": table["columns"], "sample": samples.get(part, []), "max_characters": table["max_characters"]})
    plan = {"max_data_rows_per_sheet": MAX_ROWS, "groups": groups}
    (OUT/"metadata/excel-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2)+"\n")
    print("Workbook worksheets:", {k:len(v) for k,v in groups.items()})

if __name__ == "__main__":
    main()
