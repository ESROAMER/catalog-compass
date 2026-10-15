"""Behavior tests, including public sample files and adversarial CSV cells."""

import copy
import csv
import io
from pathlib import Path
import unittest

from catalog_check.catalog import (
    CANONICAL_FIELDS, decode_csv, issues_csv, normalized_csv, parse_csv,
    profile_csv, validate_catalog,
)


SAMPLES = Path(__file__).resolve().parents[1] / "research" / "2026-10-15" / "samples"
SIMPLE_MAPPING = {"sku": "SKU", "name": "Name", "regular_price": "Price"}
WOO_MAPPING = {
    "sku": "SKU", "name": "Name", "regular_price": "Regular price",
    "sale_price": "Sale price", "product_type": "Type", "parent_sku": "Parent",
    "stock": "Stock", "description": "Description",
}


def make_csv(headers, rows, delimiter=","):
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=delimiter)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


class CSVParsingTests(unittest.TestCase):
    def test_multiline_quoted_csv_preserves_values_and_record_numbers(self):
        source = 'SKU,Name,Price,Description\r\n00017,"Tea, green",12.50,"Line one\nLine two"\r\n00018,Other,,plain\r\n'
        mapping = {**SIMPLE_MAPPING, "description": "Description"}
        parsed = parse_csv(source)
        self.assertEqual(parsed["rows"][0]["SKU"], "00017")
        self.assertEqual(parsed["rows"][0]["Description"], "Line one\nLine two")
        self.assertEqual(parsed["rows"][0]["Name"], "Tea, green")
        result = validate_catalog(source, mapping)
        self.assertEqual([issue["row"] for issue in result["issues"] if issue["code"] == "missing_regular_price"], [3])
        exported = list(csv.DictReader(io.StringIO(normalized_csv(result))))
        self.assertEqual(exported[0]["sku"], "00017")
        self.assertEqual(exported[0]["description"], "Line one\nLine two")
        self.assertEqual(source, 'SKU,Name,Price,Description\r\n00017,"Tea, green",12.50,"Line one\nLine two"\r\n00018,Other,,plain\r\n')

    def test_supported_delimiters(self):
        for delimiter in (",", ";", "\t"):
            with self.subTest(delimiter=delimiter):
                parsed = parse_csv(make_csv(["SKU", "Name", "Price"], [["001", "Widget", "12"]], delimiter))
                self.assertEqual(parsed["delimiter"], delimiter)
                self.assertEqual(parsed["rows"][0]["SKU"], "001")

    def test_duplicate_empty_headers_and_ragged_rows_rejected(self):
        for source in ("SKU,SKU\na,b\n", "SKU, SKU \na,b\n", "SKU,,Price\na,b,1\n",
                       "SKU,Name\na,b,c\n", "SKU,Name\na\n", "", " \n"):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    parse_csv(source)

    def test_bad_quotes_rejected(self):
        with self.assertRaises(ValueError):
            parse_csv('SKU,Name\n1,"unterminated\n')

    def test_header_only_is_allowed(self):
        result = validate_catalog("SKU,Name,Price\n", SIMPLE_MAPPING)
        self.assertEqual(result["summary"]["total_rows"], 0)
        self.assertEqual(result["issues"], [])

    def test_encoding_strict_utf8_and_opt_in_cp1252(self):
        self.assertEqual(decode_csv(b"\xef\xbb\xbfSKU,Name\n1,Tea\n"), "SKU,Name\n1,Tea\n")
        self.assertEqual(parse_csv("\ufeffSKU,Name\n1,Tea\n")["headers"], ["SKU", "Name"])
        cp1252 = "SKU,Name\n1,Café\n".encode("cp1252")
        with self.assertRaises(ValueError):
            decode_csv(cp1252)
        self.assertIn("Café", decode_csv(cp1252, "cp1252"))
        with self.assertRaises(ValueError):
            decode_csv(b"a\x00b")
        with self.assertRaises(ValueError):
            decode_csv(b"a", "utf-16")

    def test_profile_samples_are_bounded_and_not_coerced(self):
        source = make_csv(["Item", "Label"], [["001", ""], ["002", "A"], ["003", "A"], ["004", "B"], ["005", "C"], ["006", "D"]])
        profile = profile_csv(source)
        self.assertEqual(profile["row_count"], 6)
        self.assertEqual(len(profile["preview"]), 5)
        self.assertEqual(profile["column_samples"]["Item"], ["001", "002", "003"])
        self.assertEqual(profile["column_samples"]["Label"], ["A", "B", "C"])


class CatalogCheckTests(unittest.TestCase):
    def test_public_samples_parent_rows_can_have_blank_prices(self):
        counts = {"woocommerce-official.csv": 25, "crosspeak-good.csv": 31, "crosspeak-bad.csv": 30}
        for filename, count in counts.items():
            with self.subTest(filename=filename):
                source = (SAMPLES / filename).read_text(encoding="utf-8-sig")
                result = validate_catalog(source, WOO_MAPPING)
                self.assertEqual(result["summary"]["total_rows"], count)
                parent_rows = {index + 2 for index, row in enumerate(result["records"])
                               if row["product_type"] in {"variable", "grouped"}}
                self.assertTrue(parent_rows)
                self.assertFalse(any(issue["row"] in parent_rows and issue["code"] == "missing_regular_price" for issue in result["issues"]))
                if filename == "crosspeak-bad.csv":
                    self.assertTrue(any(issue["code"] == "missing_regular_price" for issue in result["issues"]))
                if filename in {"woocommerce-official.csv", "crosspeak-good.csv"}:
                    self.assertEqual(result["summary"]["error_count"], 0)

    def test_mapping_uses_selected_headers_and_preserves_input_objects(self):
        source = make_csv(["货号", "标题", "售价", "Other"], [["0001", "杯子", "12.00", "Retain me in original"]])
        mapping = {"sku": "货号", "name": "标题", "regular_price": "售价"}
        before_mapping = copy.deepcopy(mapping)
        options = {"currency": "USD"}
        result = validate_catalog(source, mapping, options)
        self.assertEqual(result["records"][0]["sku"], "0001")
        self.assertEqual(result["records"][0]["regular_price"], "12.00")
        self.assertEqual(result["records"][0]["currency"], "")
        self.assertEqual(result["records"][0]["product_type"], "")
        self.assertEqual(result["summary"]["assumed_simple_rows"], 1)
        self.assertTrue(any("checked as simple" in note for note in result["notes"]))
        self.assertEqual(mapping, before_mapping)
        self.assertEqual(options, {"currency": "USD"})
        self.assertEqual(parse_csv(source)["rows"][0]["Other"], "Retain me in original")
        with self.assertRaises(ValueError):
            validate_catalog(source, {"sku": "not a header"})
        with self.assertRaises(ValueError):
            validate_catalog(source, {"not a field": "货号"})

    def test_missing_prices_names_and_sku_have_distinct_severities(self):
        source = make_csv(["SKU", "Name", "Price", "Type"], [
            ["001", "Simple", "", "simple"], ["002", "Variation", "", "variation"],
            ["003", "Parent", "", "variable"], ["004", "Group", "", "grouped"],
            ["005", "External", "", "external"], ["", "", "", ""],
        ])
        result = validate_catalog(source, {**SIMPLE_MAPPING, "product_type": "Type"})
        missing = {issue["row"]: issue["severity"] for issue in result["issues"] if issue["code"] == "missing_regular_price"}
        self.assertEqual(missing, {2: "error", 3: "error", 6: "warning", 7: "error"})
        self.assertIn(("missing_name", "error"), [(issue["code"], issue["severity"]) for issue in result["issues"]])
        self.assertIn(("missing_sku", "warning"), [(issue["code"], issue["severity"]) for issue in result["issues"]])

    def test_unselected_optional_field_accepts_empty_string(self):
        source = "SKU,Name,Price\n001,Widget,12.00\n"
        mapping = {**SIMPLE_MAPPING, "sale_price": "", "product_type": None}
        result = validate_catalog(source, mapping)
        self.assertIsNone(result["mapping"]["sale_price"])
        self.assertEqual(result["records"][0]["sale_price"], "")
        self.assertEqual(result["summary"]["error_count"], 0)
        self.assertEqual(mapping["sale_price"], "")

    def test_woocommerce_type_flags(self):
        source = 'SKU,Name,Price,Type\n1,Download,2,"simple, downloadable, virtual"\n'
        result = validate_catalog(source, {**SIMPLE_MAPPING, "product_type": "Type"})
        self.assertEqual(result["issues"], [])

    def test_prices_and_stock_are_checked_without_guessing(self):
        source = make_csv(["SKU", "Name", "Price", "Sale", "Stock"], [
            ["1", "A", "not available", "", "1.5"], ["2", "B", "-2", "", "-1"],
            ["3", "C", "0", "", "parent"], ["4", "D", "9.99", "10", "005"],
            ["5", "E", "1,200", "", ""], ["6", "F", "NaN", "", ""],
        ])
        result = validate_catalog(source, {**SIMPLE_MAPPING, "sale_price": "Sale", "stock": "Stock"})
        codes = [issue["code"] for issue in result["issues"]]
        self.assertEqual(codes.count("invalid_price"), 3)
        self.assertEqual(codes.count("invalid_stock"), 2)
        self.assertEqual(codes.count("negative_price"), 1)
        self.assertEqual(codes.count("zero_price"), 1)
        self.assertEqual(codes.count("sale_above_regular"), 1)
        self.assertTrue(all(issue["severity"] == "warning" for issue in result["issues"]))

    def test_duplicate_sku_price_and_barcode_conflicts(self):
        source = make_csv(["SKU", "Name", "Price", "EAN"], [
            ["001", "A", "12.0", "000101"], ["001", "A", "13", "000102"],
            ["same", "B", "3.00", ""], ["same", "B", "3.00", ""],
        ])
        result = validate_catalog(source, {**SIMPLE_MAPPING, "barcode": "EAN"})
        price_issues = [issue for issue in result["issues"] if issue["code"] == "sku_price_conflict"]
        self.assertEqual([issue["row"] for issue in price_issues], [2, 3])
        self.assertTrue(all(issue["severity"] == "error" for issue in price_issues))
        self.assertEqual(sum(issue["code"] == "sku_barcode_conflict" for issue in result["issues"]), 2)
        self.assertEqual(sum(issue["code"] == "duplicate_record" for issue in result["issues"]), 1)
        self.assertEqual(sum(issue["code"] == "duplicate_sku" for issue in result["issues"]), 2)
        self.assertEqual(result["summary"]["affected_rows"], 4)
        self.assertEqual(len(result["records"]), 4)

    def test_sku_identity_and_decimal_equality(self):
        source = make_csv(["SKU", "Name", "Price"], [
            ["abc", "A", "12.00"], ["ABC", "A", "99"], [" abc", "A", "42"],
            ["abc", "A", "12"],
        ])
        result = validate_catalog(source, SIMPLE_MAPPING)
        self.assertFalse(any(issue["code"] == "sku_price_conflict" for issue in result["issues"]))
        self.assertEqual({issue["row"] for issue in result["issues"] if issue["code"] == "duplicate_sku"}, {2, 5})

    def test_cross_currency_prices_are_not_compared(self):
        source = make_csv(["SKU", "Name", "Price", "Currency"], [
            ["001", "A", "12", "USD"], ["001", "A", "100", "CNY"],
            ["001", "A", "30", ""],
        ])
        mapping = {**SIMPLE_MAPPING, "currency": "Currency"}
        result = validate_catalog(source, mapping)
        self.assertFalse(any(issue["code"] == "sku_price_conflict" for issue in result["issues"]))
        self.assertTrue(any("across different currencies were skipped" in note for note in result["notes"]))
        result_with_default = validate_catalog(source, mapping, {"currency": "USD"})
        self.assertEqual({issue["row"] for issue in result_with_default["issues"] if issue["code"] == "sku_price_conflict"}, {2, 4})
        self.assertEqual(result_with_default["records"][2]["currency"], "")

    def test_exports_escape_formulas_without_mutation_or_destroying_negative_numbers(self):
        source = make_csv(["SKU", "Name", "Price", "Description"], [
            ["=1+1", " +SUM(A1)", "-12.50", "@danger"],
            ["-123", "\t=CMD()", "=2+3", "\r=CMD()"],
            ["0003", "Normal", "12", "Multiline\nvalue"],
        ])
        result = validate_catalog(source, {**SIMPLE_MAPPING, "description": "Description"})
        before = copy.deepcopy(result)
        normalized = list(csv.DictReader(io.StringIO(normalized_csv(result))))
        self.assertEqual(normalized[0]["sku"], "'=1+1")
        self.assertEqual(normalized[0]["name"], "' +SUM(A1)")
        self.assertEqual(normalized[0]["regular_price"], "-12.50")
        self.assertEqual(normalized[0]["description"], "'@danger")
        self.assertEqual(normalized[1]["sku"], "'-123")
        self.assertEqual(normalized[1]["name"], "'\t=CMD()")
        self.assertEqual(normalized[1]["regular_price"], "'=2+3")
        self.assertEqual(normalized[1]["description"], "'\r=CMD()")
        self.assertEqual(normalized[2]["sku"], "0003")
        exported_issues = list(csv.DictReader(io.StringIO(issues_csv(result))))
        negative = next(issue for issue in exported_issues if issue["code"] == "negative_price")
        self.assertEqual(negative["value"], "-12.50")
        self.assertEqual(negative["sku"], "'=1+1")
        self.assertEqual(result, before)
        self.assertEqual(list(normalized[0]), list(CANONICAL_FIELDS))


if __name__ == "__main__":
    unittest.main()
