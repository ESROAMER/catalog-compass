"""Deterministic checks for one supplier CSV; no guessing or value repairs.

All source values remain strings. Row numbers identify CSV records (header = 1),
not physical text lines, so quoted multiline values count as one record.
Export functions escape spreadsheet formulas; they never mutate stored values.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any


CANONICAL_FIELDS = (
    "sku", "name", "regular_price", "sale_price", "currency", "product_type",
    "parent_sku", "barcode", "stock", "description",
)
_NUMBER = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$")
_INTEGER = re.compile(r"^[+]?[0-9]+$")
_BASE_TYPES = {"simple", "variation", "variable", "grouped", "external"}


def decode_csv(data: bytes, encoding: str = "auto") -> str:
    """Decode strictly. Legacy CP1252 requires an explicit caller choice.

    'auto' accepts UTF-8 with or without a BOM, without a lossy fallback.
    UTF-16 and binary files are intentionally outside this prototype's scope.
    """
    aliases = {"auto": "utf-8-sig", "utf8": "utf-8-sig", "utf-8": "utf-8-sig",
               "utf-8-sig": "utf-8-sig", "cp1252": "cp1252", "windows-1252": "cp1252"}
    codec = aliases.get(encoding.lower())
    if codec is None:
        raise ValueError("Supported encodings: UTF-8 or explicitly selected CP1252.")
    try:
        text = data.decode(codec, errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"The file is not valid {codec}. Save it as UTF-8 CSV.") from exc
    if "\x00" in text:
        raise ValueError("NUL bytes are not supported. Save the file as UTF-8 CSV.")
    return text


def _delimiter(text: str) -> str:
    try:
        return csv.Sniffer().sniff(text[:65536], delimiters=",;\t").delimiter
    except csv.Error:
        # A truncated quoted value or malformed data row can defeat Sniffer.
        # Read just the header for each allowed delimiter, then validate widths.
        candidates = []
        for delimiter in (",", ";", "\t"):
            try:
                header = next(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True))
            except (csv.Error, StopIteration):
                continue
            candidates.append((len(header), delimiter))
        if not candidates:
            return ","
        return max(candidates, key=lambda item: item[0])[1]


def parse_csv(text: str) -> dict[str, Any]:
    """Parse comma, semicolon, or tab CSV, preserving exact header/value strings.

    Blank physical records are skipped by the CSV convention; records with empty
    cells remain data. Ragged records and duplicate/empty headers are rejected.
    """
    if not isinstance(text, str):
        raise ValueError("CSV input must be decoded text.")
    text = text.removeprefix("\ufeff")
    if not text.strip():
        raise ValueError("The CSV is empty.")
    if "\x00" in text:
        raise ValueError("The CSV contains NUL characters; UTF-16/binary files are unsupported.")
    delimiter = _delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        headers = next(reader)
        if not headers or any(not header.strip() for header in headers):
            raise ValueError("Every column must have a non-empty header.")
        comparable = [header.strip() for header in headers]
        duplicates = [name for name, count in Counter(comparable).items() if count > 1]
        if duplicates:
            raise ValueError("Duplicate CSV headers: " + ", ".join(duplicates))
        rows = []
        for record in reader:
            if not record:
                continue
            row_number = len(rows) + 2
            if len(record) != len(headers):
                raise ValueError(
                    f"CSV record {row_number} has {len(record)} cells; expected {len(headers)}. "
                    "Check the delimiter and quoting."
                )
            rows.append(dict(zip(headers, record)))
    except csv.Error as exc:
        raise ValueError(f"Invalid CSV quoting or field size: {exc}") from exc
    return {"headers": headers, "rows": rows, "delimiter": delimiter}


def profile_csv(text: str) -> dict[str, Any]:
    parsed = parse_csv(text)
    samples: dict[str, list[str]] = {}
    for header in parsed["headers"]:
        values: list[str] = []
        for row in parsed["rows"]:
            value = row[header]
            if value.strip() and value not in values:
                values.append(value)
            if len(values) == 3:
                break
        samples[header] = values
    return {"headers": parsed["headers"], "row_count": len(parsed["rows"]),
            "delimiter": parsed["delimiter"], "preview": parsed["rows"][:5],
            "column_samples": samples}


def _number(value: str) -> Decimal | None:
    value = value.strip()
    if not _NUMBER.fullmatch(value):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def validate_catalog(text: str, mapping: dict[str, str | None],
                     options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Check a confirmed canonical-field -> source-header mapping.

    Missing/null/empty-string mappings produce empty canonical values (and the
    usual issues). Empty strings support unselected HTML form controls.
    Unknown source columns are retained in the original input, not normalized
    exports. No SKU is merged. Currency option supplies comparison context only.
    """
    parsed = parse_csv(text)
    if not isinstance(mapping, dict):
        raise ValueError("Mapping must be an object of canonical fields to CSV headers.")
    unknown = set(mapping) - set(CANONICAL_FIELDS)
    if unknown:
        raise ValueError("Unknown mapping fields: " + ", ".join(sorted(unknown)))
    selected: dict[str, str | None] = {}
    for field in CANONICAL_FIELDS:
        header = mapping.get(field)
        if header == "":
            header = None
        if header is not None and (not isinstance(header, str) or header not in parsed["headers"]):
            raise ValueError(f"Mapping for {field} references an unknown CSV header.")
        selected[field] = header
    options = options or {}
    default_currency = str(options.get("default_currency") or options.get("currency") or "").strip().upper()
    records = [{field: source[header] if header is not None else ""
                for field, header in selected.items()} for source in parsed["rows"]]
    issues: list[dict[str, Any]] = []
    notes = [
        "Row numbers count CSV records, with the header as record 1; quoted multiline cells count once.",
        "SKU comparisons use exact, case-sensitive source strings within this file; no rows are merged.",
        "Original values are retained. CSV exports prefix risky text with an apostrophe to prevent spreadsheet formulas.",
        "Prices accept a decimal point without currency symbols or thousands separators; ambiguous formats require review.",
    ]
    assumed_simple = 0
    numeric_prices: list[dict[str, Decimal | None]] = []
    currencies = []

    def add(index: int, code: str, severity: str, field: str, message: str,
            value: str | None = None) -> None:
        record = records[index]
        issues.append({"id": f"issue-{len(issues) + 1:04d}", "code": code,
                       "severity": severity, "row": index + 2, "field": field,
                       "sku": record["sku"], "message": message,
                       "value": record.get(field, "") if value is None else value})

    seen_rows: dict[tuple[str, ...], int] = {}
    sku_groups: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        if not record["name"].strip():
            add(index, "missing_name", "error", "name", "Product name is missing.")
        if not record["sku"].strip():
            add(index, "missing_sku", "warning", "sku", "SKU is missing; this record cannot be matched for SKU conflicts.")
        else:
            sku_groups[record["sku"]].append(index)

        raw_type = record["product_type"].strip().lower()
        if not raw_type:
            product_type = "simple"
            assumed_simple += 1
        else:
            # WooCommerce may append virtual/downloadable flags to a base type.
            parts = [part.strip() for part in raw_type.split(",")]
            base_types = [part for part in parts if part in _BASE_TYPES]
            if len(base_types) == 1 and all(part in _BASE_TYPES | {"virtual", "downloadable"} for part in parts):
                product_type = base_types[0]
            else:
                product_type = "unknown"
                add(index, "unknown_product_type", "warning", "product_type",
                    "Unrecognized product type; confirm its price requirements.")

        if not record["regular_price"].strip():
            if product_type in {"simple", "variation"}:
                add(index, "missing_regular_price", "error", "regular_price",
                    f"Regular price is required for {product_type} products.")
            elif product_type in {"external", "unknown"}:
                add(index, "missing_regular_price", "warning", "regular_price",
                    f"Regular price is missing for an {product_type} product; confirm whether this is intentional.")

        prices: dict[str, Decimal | None] = {}
        for field in ("regular_price", "sale_price"):
            value = record[field]
            price = _number(value) if value.strip() else None
            prices[field] = price
            if not value.strip():
                continue
            if price is None:
                add(index, "invalid_price", "warning", field,
                    "Price is not an unambiguous decimal number. Review the original value.")
            elif price < 0:
                add(index, "negative_price", "warning", field, "Price is negative; confirm the intended value.")
            elif price == 0:
                add(index, "zero_price", "warning", field, "Price is zero; confirm that this product is free.")
        regular, sale = prices["regular_price"], prices["sale_price"]
        if regular is not None and sale is not None and sale > regular:
            add(index, "sale_above_regular", "warning", "sale_price", "Sale price exceeds regular price.")
        numeric_prices.append(prices)
        currencies.append(record["currency"].strip().upper() or default_currency)

        stock = record["stock"].strip()
        if stock and stock.lower() != "parent" and not _INTEGER.fullmatch(stock):
            add(index, "invalid_stock", "warning", "stock",
                "Stock must be a non-negative whole number, blank, or 'parent' for inherited stock.")

        signature = tuple(parsed["rows"][index][header] for header in parsed["headers"])
        if signature in seen_rows:
            add(index, "duplicate_record", "warning", "sku",
                f"This entire source record is identical to record {seen_rows[signature] + 2}; neither record was removed.")
        else:
            seen_rows[signature] = index

    skipped_currency_groups = 0
    for sku, indices in sku_groups.items():
        if len(indices) < 2:
            continue
        conflicted: set[int] = set()
        currency_groups: dict[str, list[int]] = defaultdict(list)
        for index in indices:
            currency_groups[currencies[index]].append(index)
        if len(currency_groups) > 1:
            skipped_currency_groups += 1
        for currency, same_currency in currency_groups.items():
            for field in ("regular_price", "sale_price"):
                values = {numeric_prices[index][field] for index in same_currency if numeric_prices[index][field] is not None}
                if len(values) > 1:
                    relevant = [index for index in same_currency if numeric_prices[index][field] is not None]
                    rows = ", ".join(str(index + 2) for index in relevant[:10])
                    if len(relevant) > 10:
                        rows += ", …"
                    for index in relevant:
                        conflicted.add(index)
                        add(index, "sku_price_conflict", "error", field,
                            f"The same SKU has different {field.replace('_', ' ')} values in records {rows} "
                            f"({currency or 'currency unspecified'}). Confirm which value is correct.")
        barcode_values = {records[index]["barcode"] for index in indices if records[index]["barcode"].strip()}
        if len(barcode_values) > 1:
            relevant = [index for index in indices if records[index]["barcode"].strip()]
            rows = ", ".join(str(index + 2) for index in relevant[:10])
            if len(relevant) > 10:
                rows += ", …"
            for index in relevant:
                conflicted.add(index)
                add(index, "sku_barcode_conflict", "error", "barcode",
                    f"The same SKU has different barcodes in records {rows}. Confirm the product identity.")
        for index in indices:
            if index not in conflicted:
                add(index, "duplicate_sku", "warning", "sku",
                    "This SKU occurs more than once. No conflicting numeric prices within a currency or non-empty barcodes "
                    "were detected for this record; review before importing.")

    if assumed_simple:
        notes.append(f"{assumed_simple} record(s) with blank or unmapped product type were checked as simple products; source values remain unchanged.")
    if default_currency:
        notes.append(f"{default_currency} was used only as comparison context where currency was blank or unmapped; it was not written into records.")
    else:
        notes.append("Blank currencies are compared only with other blank currencies. Confirm the file's currency before relying on price conflicts.")
    if skipped_currency_groups:
        notes.append(f"Price comparisons across different currencies were skipped for {skipped_currency_groups} repeated SKU group(s).")
    unmapped = [field for field in CANONICAL_FIELDS if selected[field] is None]
    if unmapped:
        notes.append("Unmapped fields are empty in normalized output: " + ", ".join(unmapped) + ".")
    issues.sort(key=lambda issue: (issue["row"], issue["severity"] != "error", issue["code"], issue["field"]))
    for index, issue in enumerate(issues, start=1):
        issue["id"] = f"issue-{index:04d}"
    return {"summary": {"total_rows": len(records),
                        "error_count": sum(issue["severity"] == "error" for issue in issues),
                        "warning_count": sum(issue["severity"] == "warning" for issue in issues),
                        "affected_rows": len({issue["row"] for issue in issues}),
                        "assumed_simple_rows": assumed_simple},
            "issues": issues, "records": records, "notes": notes, "mapping": selected}


def _safe_cell(value: Any, *, numeric: bool = False) -> str:
    text = str(value) if value is not None else ""
    # Legitimate signed prices/stock stay numeric; SKU/barcode/text never get this
    # exemption. Strip only for detection, preserving the original cell content.
    if numeric and _number(text) is not None:
        return text
    candidate = text.lstrip(" \t\r\n\v\f\ufeff")
    if candidate.startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def issues_csv(result: dict[str, Any]) -> str:
    """Return a spreadsheet-safe UTF-8-ready issue CSV (no mutation)."""
    columns = ("id", "code", "severity", "row", "field", "sku", "message", "value")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(columns)
    for issue in result["issues"]:
        writer.writerow([_safe_cell(issue.get(column, ""),
                                   numeric=column == "row" or (column == "value" and issue.get("field") in {"regular_price", "sale_price", "stock"}))
                         for column in columns])
    return output.getvalue()


def normalized_csv(result: dict[str, Any]) -> str:
    """Export mapped strings, escaping formulas; this does not repair data.

    Spreadsheet applications may still infer numeric SKUs and drop leading zeros
    on opening CSV. Import SKU/barcode columns as text to retain their display.
    The bytes written here preserve the original digit strings.
    """
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(CANONICAL_FIELDS)
    for record in result["records"]:
        writer.writerow([_safe_cell(record.get(field, ""), numeric=field in {"regular_price", "sale_price", "stock"})
                         for field in CANONICAL_FIELDS])
    return output.getvalue()
