# DataHub Schema Change Blast-Radius Agent

Status: publication-ready offline prototype for the DataHub Agent Hackathon. The
repository deliberately keeps external DataHub access optional and never writes
credentials to disk.

The core accepts two DataHub-style dataset snapshots plus a downstream lineage graph. It detects removed fields, type changes, tightened nullability, and additions, then emits a deterministic Markdown report listing the affected datasets, jobs, and dashboards. The output deliberately stops at a human-review gate before proposing migration SQL or writing governance metadata.

## Run the offline demo

From this directory:

```text
python -m unittest discover -s tests -v
python -m src.schema_agent --before fixtures/before.json --after fixtures/after.json --lineage fixtures/lineage.json --out report.md
```

The official DataHub GraphQL API is documented at `https://docs.datahub.com/docs/api/graphql/overview` and exposes `/api/graphql`. `src/datahub_graphql.py` contains a dependency-free adapter that accepts an endpoint and an optional process-only bearer token, normalizes schema/lineage data into the offline core's shape, and never writes credentials to disk. The fixture tests still run without credentials or an external DataHub deployment.

The fixture uses DataHub URN-shaped identifiers and is synthetic. It contains no customer data, credentials, wallet material, or transaction logic.

## License

Apache-2.0. See `LICENSE`.
