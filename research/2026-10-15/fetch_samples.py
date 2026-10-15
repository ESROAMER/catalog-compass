"""Download unchanged public catalog fixtures and record their provenance."""
from pathlib import Path
import csv
import hashlib
import io
import json
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "samples"
DEST.mkdir(parents=True, exist_ok=True)
SOURCES = [
    ("crosspeak-good.csv", "https://raw.githubusercontent.com/crosspeaksoftware/sample-data-woocommerce/refs/heads/main/woo-sample-data-good.csv", "GPL-2.0", "Original good demonstration fixtures, not customer records"),
    ("crosspeak-bad.csv", "https://raw.githubusercontent.com/crosspeaksoftware/sample-data-woocommerce/refs/heads/main/woo-sample-data-bad.csv", "GPL-2.0", "Deliberately corrupted fixtures; names and SKUs leak intended issue labels"),
    ("crosspeak-LICENSE.txt", "https://raw.githubusercontent.com/crosspeaksoftware/sample-data-woocommerce/refs/heads/main/LICENSE", "GPL-2.0", "Upstream license retained unchanged"),
    ("crosspeak-README.md", "https://raw.githubusercontent.com/crosspeaksoftware/sample-data-woocommerce/refs/heads/main/README.md", "GPL-2.0", "Upstream provenance and usage documentation retained unchanged"),
    ("woocommerce-official.csv", "https://raw.githubusercontent.com/woocommerce/woocommerce/refs/heads/trunk/plugins/woocommerce/sample-data/sample_products.csv", "GPL-2.0-or-later", "Official format fixture, not raw supplier data"),
    ("woocommerce-LICENSE.txt", "https://raw.githubusercontent.com/woocommerce/woocommerce/refs/heads/trunk/license.txt", "GPL-2.0-or-later", "Upstream license retained unchanged"),
]

records = []
for name, url, license_name, note in SOURCES:
    req = Request(url, headers={"User-Agent": "CatalogFeasibilityResearch/1.0"})
    with urlopen(req, timeout=45) as response:
        data = response.read()
    text = data.decode("utf-8-sig")
    record = {"file": name, "url": url, "retrieved_on": "2026-10-15", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "license": license_name, "note": note}
    if name.endswith(".csv"):
        parsed = list(csv.reader(io.StringIO(text, newline="")))
        assert parsed and "SKU" in parsed[0], f"Not a product CSV: {name}"
        header, body = parsed[0], parsed[1:]
        record["rows"] = len(body)
        record["columns"] = len(header)
        record["headers"] = header
        record["row_width_mismatches"] = [{"csv_record": i + 2, "fields": len(row)} for i, row in enumerate(body) if len(row) != len(header)]
    (DEST / name).write_bytes(data)
    records.append(record)
    print(json.dumps({k: v for k, v in record.items() if k not in ("headers", "url", "sha256")}, ensure_ascii=False))

(DEST / "provenance.json").write_text(json.dumps({"scope": "Public third-party fixtures for research; unchanged downloads. Not market validation or model accuracy evidence. No image assets downloaded.", "sources": records}, ensure_ascii=False, indent=2), encoding="utf-8")
