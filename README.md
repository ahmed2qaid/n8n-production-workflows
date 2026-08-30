# n8n Production Workflows

Production-grade n8n automation blueprints with tests, safety metadata, failure handling expectations, and a machine-readable quality gate.

> Not more workflows. Better workflows.

## Why this exists

Most workflow collections optimize for quantity. This repository optimizes for deployability: every published workflow should document inputs, credentials, side effects, retries, idempotency, observability, and test fixtures.

## v0.1 scope

- A manifest contract for production-readiness metadata.
- A zero-dependency Python validator and CLI.
- A reference workflow package with test fixtures.
- CI that rejects malformed workflow packages.
- A scoring model that makes missing production controls visible.

## Target package layout

```text
workflows/<workflow-name>/
├── workflow.json
├── manifest.json
├── fixtures/
│   ├── input.json
│   └── expected.json
└── README.md
```

## Quick start

```bash
PYTHONPATH=src python -m n8n_production_workflows validate workflows
python -m unittest discover -s tests
```

## Production-readiness checks

The initial validator checks for:

- valid n8n workflow structure (`nodes` and `connections`)
- manifest/workflow identity consistency
- declared credentials and side effects
- retry and error-path declarations
- idempotency expectations
- observability/alerting expectations
- suspicious inline secret-like values

The score is advisory in v0.1. Future releases will add node-level semantic rules, n8n version compatibility checks, synthetic execution, and regression fixtures.

## Roadmap

See [ROADMAP.md](ROADMAP.md).

## Status

Early development — v0.1 foundation.

## License

MIT. Imported third-party workflows, when added, must preserve their original attribution and compatible license notices.