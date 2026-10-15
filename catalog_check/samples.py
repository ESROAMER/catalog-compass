"""Public fixtures and an explicitly synthetic, independently authored demo."""
import csv
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "research" / "2026-10-15" / "samples"
SAMPLES = [
    {"id": "supplier-demo", "name": "Supplier desk essentials", "description": "10 synthetic rows with unfamiliar headers, a missing price, a duplicate and conflicts. No customer data."},
    {"id": "woocommerce-official", "name": "WooCommerce official", "description": "25 public example records. Includes parent rows with legitimate blank prices. GPL-2.0-or-later."},
    {"id": "crosspeak-good", "name": "CrossPeak normal examples", "description": "31 public test records. Normal product and variant structures. GPL-2.0."},
    {"id": "crosspeak-bad", "name": "CrossPeak problem examples", "description": "30 intentionally flawed records. Names contain issue hints; use for rule checks, not an AI accuracy benchmark. GPL-2.0."},
]


def supplier_demo():
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Item ref", "Display label", "List amount", "Deal amount", "Money", "Units available", "GTIN", "Kind"])
    writer.writerows([
        ["00081", "Canvas tote", "24.00", "", "USD", "12", "0012345000011", "simple"],
        ["00082", "Desk tray", "", "", "USD", "7", "0012345000028", "simple"],
        ["00083", "Steel bottle", "32.00", "", "USD", "20", "0012345000035", "simple"],
        ["00083", "Steel bottle", "39.00", "", "USD", "20", "0012345000035", "simple"],
        ["00084", "Notebook", "8.00", "", "USD", "14", "0012345000042", "simple"],
        ["00084", "Notebook", "8.00", "", "USD", "14", "0012345000042", "simple"],
        ["00085", "Cable pouch", "18.00", "22.00", "USD", "8", "0012345000059", "simple"],
        ["00086", "Travel mug", "26.00", "", "USD", "four", "0012345000066", "simple"],
        ["00087", "Pen set", "0.00", "", "USD", "2", "0012345000073", "simple"],
        ["00088", "", "14.00", "", "USD", "10", "0012345000080", "simple"],
    ])
    return output.getvalue()


def get_sample(sample_id):
    if sample_id == "supplier-demo":
        return {"filename": "synthetic-supplier-demo.csv", "csv": supplier_demo()}
    allowed = {sample["id"] for sample in SAMPLES} - {"supplier-demo"}
    if sample_id not in allowed:
        raise ValueError("Unknown sample.")
    path = DATA / f"{sample_id}.csv"
    return {"filename": path.name, "csv": path.read_text(encoding="utf-8-sig")}

