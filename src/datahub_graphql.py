"""Small, dependency-free DataHub GraphQL adapter for the offline core."""

from __future__ import annotations

import json
from urllib import request
from typing import Any


DATASET_QUERY = """
query DatasetSchemaAndLineage($urn: String!) {
  dataset(urn: $urn) {
    urn
    schemaMetadata {
      fields { fieldPath nullable nativeDataType }
    }
    relationships(input: {types: [\"DownstreamOf\"], direction: OUTGOING, start: 0, count: 100}) {
      relationships { entity { urn type } }
    }
  }
}
""".strip()


def build_request_body(dataset_urn: str) -> bytes:
    return json.dumps(
        {"query": DATASET_QUERY, "variables": {"urn": dataset_urn}},
        separators=(",", ":"),
    ).encode("utf-8")


class DataHubGraphQLClient:
    def __init__(self, endpoint: str, token: str | None = None, timeout: int = 30) -> None:
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout

    def fetch_dataset(self, dataset_urn: str) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = request.Request(
            self.endpoint,
            data=build_request_body(dataset_urn),
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("errors"):
            raise RuntimeError("DataHub GraphQL returned errors")
        dataset = payload.get("data", {}).get("dataset")
        if not isinstance(dataset, dict):
            raise ValueError("DataHub response did not contain data.dataset")
        return dataset


def normalize_dataset(dataset: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert a DataHub response into the core snapshot and lineage shapes."""

    schema = dataset.get("schemaMetadata") or {}
    raw_fields = schema.get("fields") or []
    fields = []
    for field in raw_fields:
        if not isinstance(field, dict) or not isinstance(field.get("fieldPath"), str):
            continue
        fields.append(
            {
                "fieldPath": field["fieldPath"],
                "nativeDataType": field.get("nativeDataType") or "UNKNOWN",
                "nullable": field.get("nullable", True),
            }
        )
    downstream: list[str] = []
    relationships = dataset.get("relationships") or {}
    for relationship in relationships.get("relationships", []):
        entity = relationship.get("entity") if isinstance(relationship, dict) else None
        if isinstance(entity, dict) and isinstance(entity.get("urn"), str):
            downstream.append(entity["urn"])
    urn = dataset.get("urn", "unknown")
    return {"urn": urn, "schema": fields}, {"downstream": {urn: sorted(set(downstream))}}
