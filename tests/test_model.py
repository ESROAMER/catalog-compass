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
        self.assertIsNone(result["mapping"]["barcode"])
        self.assertEqual(result["engine"]["kind"], "open_model")
        self.assertEqual(len(result["warnings"]), 2)

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
