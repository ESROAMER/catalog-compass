import os
import unittest
from unittest.mock import patch
from catalog_check import model


class ModelAdapterTests(unittest.TestCase):
    def profile(self):
        return {"headers": ["Code", "Label", "Price"], "column_samples": {"Code": ["001"], "Label": ["Tote"], "Price": ["10"]}}

    def test_actual_response_is_validated_and_labelled(self):
        reply = {"model": "test-open-model", "choices": [{"message": {"content": '{"sku":"Code","name":"Label","regular_price":"Price","sale_price":"Price","barcode":"invented"}'}}]}
        with patch.object(model, "request_json", return_value=reply):
            result = model.suggest_mapping(self.profile())
        self.assertEqual(result["mapping"]["sku"], "Code")
        self.assertIsNone(result["mapping"]["sale_price"])
        self.assertIsNone(result["mapping"]["regular_price"])
        self.assertIsNone(result["mapping"]["barcode"])
        self.assertEqual(result["engine"]["kind"], "open_model")
        self.assertEqual(len(result["warnings"]), 2)
        missing = next(w for w in result["warnings"] if w["code"] == "unknown_column")
        self.assertEqual(missing["column"], "invented")
        self.assertIn("Barcode / GTIN", missing["message"])
        self.assertIn("Not provided", missing["action"])

    def test_identifier_candidates_use_headers_not_digit_length(self):
        headers = ["Item ref", "GTIN", "EAN-13", "UPC", "barcode", "BarCode", "SKU", "SKU / EAN", "External ID"]
        schema = model.mapping_schema(headers)
        sku = schema["properties"]["sku"]["anyOf"][0]["enum"]
        barcode = schema["properties"]["barcode"]["anyOf"][0]["enum"]
        for header in ["GTIN", "EAN-13", "UPC", "barcode", "BarCode"]:
            self.assertNotIn(header, sku)
            self.assertIn(header, barcode)
            self.assertNotIn(header, schema["properties"]["description"]["anyOf"][0]["enum"])
        for header in ["Item ref", "SKU"]:
            self.assertIn(header, sku)
            self.assertNotIn(header, barcode)
        for header in ["SKU / EAN", "External ID"]:
            self.assertIn(header, sku)
            self.assertIn(header, barcode)
        self.assertEqual(model.mapping_schema(["GTIN"])["properties"]["sku"], {"type": "null"})

    def test_ambiguous_duplicate_clears_all_fields_without_first_winner(self):
        mapping, warnings = model.validate_suggestions(
            {"sku": "Identifier", "barcode": "Identifier", "description": "Identifier", "name": "Label"},
            ["Identifier", "Label"])
        self.assertEqual(mapping["name"], "Label")
        for field in ("sku", "barcode", "description"):
            self.assertIsNone(mapping[field])
        warning, = warnings
        self.assertEqual(warning["column"], "Identifier")
        self.assertEqual(warning["fields"], ["sku", "barcode", "description"])
        for label in ("SKU", "Barcode / GTIN", "Description", "Identifier"):
            self.assertIn(label, warning["message"])
        self.assertIn("Not provided", warning["action"])

    def test_swapped_identifiers_are_rejected_without_inventing_replacements(self):
        mapping, warnings = model.validate_suggestions(
            {"sku": "GTIN", "barcode": "Item ref"}, ["GTIN", "Item ref"])
        self.assertIsNone(mapping["sku"])
        self.assertIsNone(mapping["barcode"])
        self.assertEqual([w["code"] for w in warnings], ["identifier_mismatch"] * 2)
        self.assertIn('"GTIN"', warnings[0]["message"])
        self.assertIn("internal item reference", warnings[0]["action"])

    def test_missing_optional_fields_do_not_warn(self):
        mapping, warnings = model.validate_suggestions(
            {"sku": "Item ref", "name": "Label", "regular_price": "Price", "barcode": None, "description": None},
            ["Item ref", "Label", "Price"])
        self.assertEqual(mapping["sku"], "Item ref")
        self.assertEqual(warnings, [])

    def test_non_string_model_column_is_reported_without_crashing(self):
        mapping, warnings = model.validate_suggestions({"barcode": ["GTIN"]}, ["GTIN"])
        self.assertIsNone(mapping["barcode"])
        self.assertEqual(warnings[0]["code"], "unknown_column")
        self.assertEqual(warnings[0]["fields"], ["barcode"])

    def test_model_failure_is_not_silently_replaced(self):
        with patch.object(model, "request_json", side_effect=OSError("offline")):
            with self.assertRaises(RuntimeError):
                model.suggest_mapping(self.profile())

    def test_invalid_json_is_not_accepted(self):
        reply = {"choices": [{"message": {"content": "Trust me, everything is correct."}}]}
        with patch.object(model, "request_json", return_value=reply):
            with self.assertRaises(RuntimeError):
                model.suggest_mapping(self.profile())

    def test_remote_endpoint_disallowed(self):
        with patch.dict(os.environ, {"CATALOG_MODEL_URL": "https://example.com/v1"}):
            with self.assertRaises(ValueError):
                model.endpoint()

    def test_values_are_bounded_and_passed_as_data(self):
        profile = self.profile()
        profile["column_samples"]["Label"] = ["X" * 10000]
        reply = {"choices": [{"message": {"content": "{}"}}]}
        with patch.object(model, "request_json", return_value=reply) as call:
            model.suggest_mapping(profile)
        payload = call.call_args.args[1]
        self.assertLess(len(payload["messages"][-1]["content"]), 3000)
        self.assertIn("untrusted data", payload["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()
