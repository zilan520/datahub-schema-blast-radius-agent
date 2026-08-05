"""Offline core for a DataHub-style schema change blast-radius report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


def _fields(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields = snapshot.get("schema", [])
    if not isinstance(fields, list):
        raise ValueError("schema must be a list")
    result: dict[str, dict[str, Any]] = {}
    for field in fields:
        if not isinstance(field, dict) or not isinstance(field.get("fieldPath"), str):
            raise ValueError("each schema field needs a fieldPath")
        result[field["fieldPath"]] = field
    return result


def diff_schema(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Return deterministic findings; severity is breaking or informational."""

    old = _fields(before)
    new = _fields(after)
    findings: list[dict[str, Any]] = []

    for name in sorted(old.keys() - new.keys()):
        findings.append({"kind": "removed_field", "fieldPath": name, "severity": "breaking"})

    for name in sorted(new.keys() - old.keys()):
        findings.append({"kind": "added_field", "fieldPath": name, "severity": "informational"})

    for name in sorted(old.keys() & new.keys()):
        previous = old[name]
        current = new[name]
        old_type = previous.get("type") or previous.get("nativeDataType")
        new_type = current.get("type") or current.get("nativeDataType")
        if old_type != new_type:
            findings.append(
                {
                    "kind": "type_changed",
                    "fieldPath": name,
                    "from": old_type,
                    "to": new_type,
                    "severity": "breaking",
                }
            )
        if previous.get("nullable", True) and current.get("nullable", True) is False:
            findings.append(
                {"kind": "nullability_tightened", "fieldPath": name, "severity": "breaking"}
            )

    return findings


def impacted_entities(dataset_urn: str, lineage: dict[str, Any]) -> list[str]:
    """Traverse downstream lineage once, returning stable breadth-first order."""

    downstream = lineage.get("downstream", {})
    if not isinstance(downstream, dict):
        raise ValueError("downstream lineage must be an object")
    queue = [dataset_urn]
    seen = {dataset_urn}
    result: list[str] = []
    while queue:
        current = queue.pop(0)
        for child in sorted(downstream.get(current, [])):
            if not isinstance(child, str) or child in seen:
                continue
            seen.add(child)
            result.append(child)
            queue.append(child)
    return result


def build_report(
    before: dict[str, Any], after: dict[str, Any], lineage: dict[str, Any]
) -> str:
    dataset_urn = str(after.get("urn") or before.get("urn") or "unknown")
    findings = diff_schema(before, after)
    impacted = impacted_entities(dataset_urn, lineage)
    breaking = [finding for finding in findings if finding["severity"] == "breaking"]

    lines = [
        "# Schema Change Blast Radius",
        "",
        f"Dataset: `{dataset_urn}`",
        f"Breaking findings: **{len(breaking)}**",
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append("No schema differences detected.")
    else:
        for finding in findings:
            detail = ""
            if finding["kind"] == "type_changed":
                detail = f" ({finding['from']} -> {finding['to']})"
            lines.append(
                f"- `{finding['severity']}` `{finding['kind']}` `{finding['fieldPath']}`{detail}"
            )
    lines.extend(["", "## Downstream Impact", ""])
    if impacted:
        lines.extend(f"- `{urn}`" for urn in impacted)
    else:
        lines.append("No downstream entities found.")
    lines.extend(
        [
            "",
            "## Suggested Actions",
            "",
            "- Review breaking findings with the owning team.",
            "- Generate migration SQL or a PR only after a human reviews the proposed change.",
            "- Write a governance tag or incident note back to DataHub after approval.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, help="previous DataHub-style dataset snapshot")
    parser.add_argument("--after", required=True, help="new DataHub-style dataset snapshot")
    parser.add_argument("--lineage", required=True, help="downstream lineage fixture")
    parser.add_argument("--out", required=True, help="Markdown report path")
    args = parser.parse_args()
    report = build_report(load_json(args.before), load_json(args.after), load_json(args.lineage))
    Path(args.out).write_text(report, encoding="utf-8")
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
