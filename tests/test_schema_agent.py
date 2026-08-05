import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request

from src.datahub_graphql import DataHubGraphQLClient, build_request_body, normalize_dataset
from src.schema_agent import build_report, diff_schema, impacted_entities


class SchemaAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).parents[1]
        self.before = json.loads((root / "fixtures/before.json").read_text(encoding="utf-8"))
        self.after = json.loads((root / "fixtures/after.json").read_text(encoding="utf-8"))
        self.lineage = json.loads((root / "fixtures/lineage.json").read_text(encoding="utf-8"))

    def test_finds_breaking_and_informational_changes(self) -> None:
        findings = diff_schema(self.before, self.after)
        self.assertEqual([finding["kind"] for finding in findings], [
            "added_field",
            "type_changed",
            "nullability_tightened",
        ])
        self.assertEqual(sum(f["severity"] == "breaking" for f in findings), 2)

    def test_traverses_downstream_lineage_without_cycles(self) -> None:
        urn = self.after["urn"]
        impacted = impacted_entities(urn, self.lineage)
        self.assertEqual(len(impacted), 3)
        self.assertEqual(impacted[0], "urn:li:dataJob:(urn:li:dataFlow:airflow,orders_daily,PROD)")

    def test_report_is_deterministic_and_review_oriented(self) -> None:
        report = build_report(self.before, self.after, self.lineage)
        self.assertIn("Breaking findings: **2**", report)
        self.assertIn("warehouse.orders", report)
        self.assertIn("human reviews", report)

    def test_cli_writes_report(self) -> None:
        from src.schema_agent import main
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "report.md"
            import sys
            old = sys.argv
            try:
                sys.argv = ["schema_agent", "--before", "fixtures/before.json", "--after", "fixtures/after.json", "--lineage", "fixtures/lineage.json", "--out", str(out)]
                self.assertEqual(main(), 0)
            finally:
                sys.argv = old
            self.assertTrue(out.exists())

    def test_graphql_request_body_contains_only_query_and_urn(self) -> None:
        body = json.loads(build_request_body("urn:li:dataset:test").decode("utf-8"))
        self.assertEqual(body["variables"], {"urn": "urn:li:dataset:test"})
        self.assertNotIn("token", body)

    @patch("src.datahub_graphql.request.urlopen")
    def test_graphql_client_normalizes_schema_and_lineage(self, urlopen: object) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({
                    "data": {"dataset": {
                        "urn": "urn:li:dataset:test",
                        "schemaMetadata": {"fields": [{"fieldPath": "id", "nullable": False, "nativeDataType": "BIGINT"}]},
                        "relationships": {"relationships": [{"entity": {"urn": "urn:li:dataset:downstream", "type": "DATASET"}}]},
                    }}
                }).encode("utf-8")

        urlopen.return_value = Response()
        dataset = DataHubGraphQLClient("https://datahub.example/api/graphql", token="process-only").fetch_dataset("urn:li:dataset:test")
        snapshot, lineage = normalize_dataset(dataset)
        self.assertEqual(snapshot["schema"][0]["nativeDataType"], "BIGINT")
        self.assertEqual(lineage["downstream"]["urn:li:dataset:test"], ["urn:li:dataset:downstream"])
        req = urlopen.call_args.args[0]
        self.assertIsInstance(req, request.Request)
        self.assertEqual(req.headers["Authorization"], "Bearer process-only")


if __name__ == "__main__":
    unittest.main()
