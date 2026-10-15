"""Read-only profiling of downloaded fixtures; not an AI validation benchmark."""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import json

ROOT = Path(__file__).resolve().parent
results = []
for path in sorted((ROOT / "samples").glob("*.csv")):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = reader.fieldnames
    by_sku = defaultdict(list)
    blank_price_by_type = Counter()
    examples = []
    for index, row in enumerate(rows, 2):
        sku = row.get("SKU", "")
        if sku:
            by_sku[sku].append(index)
        if not row.get("Regular price", "").strip():
            blank_price_by_type[row.get("Type", "")] += 1
        if path.name == "crosspeak-bad.csv":
            examples.append({"csv_record": index, **{k: row.get(k, "") for k in ("Type", "SKU", "Name", "Regular price", "Sale price", "Parent")}})
    result = {"file": path.name, "data_records": len(rows), "columns": len(columns), "product_types": dict(Counter(row.get("Type", "") for row in rows)), "blank_regular_price_by_type": dict(blank_price_by_type), "duplicate_nonempty_exact_skus": {k: v for k, v in by_sku.items() if len(v) > 1}, "warning": "Blank prices and repeated values are observations, not automatically errors. SKU comparison here is exact and scoped to one file.", "bad_fixture_examples": examples}
    results.append(result)
    print(json.dumps(result, ensure_ascii=True))
(ROOT / "sample_profile.json").write_text(json.dumps({"method": "Python csv.DictReader; counts exclude header; CSV record numbers may differ from physical lines for multiline fields. No model was run.", "files": results}, ensure_ascii=False, indent=2), encoding="utf-8")
