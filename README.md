# n8n Production Workflows

A curated n8n automation catalog that competes on **production readiness, not workflow count**.

Every workflow package is checked for operational metadata and semantically analyzed at node level before it is accepted by CI.

## v0.2 — semantic workflow risk analysis

The CLI now understands common n8n risk patterns instead of checking JSON shape only:

- unauthenticated Webhook nodes
- explicitly documented public webhook exceptions
- mutating and destructive HTTP methods
- destructive database operations and SQL
- Code/Function nodes
- credential reference integrity
- manifest credential declarations
- external HTTP retry flags
- high-risk workflow error/idempotency requirements
- n8n `tested_with` compatibility metadata
- per-node `low / medium / high / critical` risk with a node score

```bash
pip install -e .
n8n-workflow-check validate workflows
```

Example output:

```text
PASS webhook-incident-intake: 96/100
  [NODE MEDIUM  ] Incident Webhook (...) score=15: public unauthenticated webhook
  [WARNING] webhook.public: Incident Webhook: public webhook is explicitly documented...
```

A destructive workflow can fail CI:

```text
FAIL customer-delete: 55/100
  [NODE CRITICAL] Delete Customer (...) score=45: destructive node operation
  [ERROR] node.destructive_operation: Delete Customer: destructive operation detected: delete
```

## Workflow package contract

```text
workflows/<workflow-name>/
├── workflow.json
├── manifest.json
└── README.md
```

The manifest documents credentials, side effects, retries, error handling, idempotency, observability, n8n compatibility, and any deliberate public webhook exposure.

## Why this is different

Large template repositories optimize for the number of importable JSON files. This repository's direction is closer to a production automation review system: a workflow earns its place only when its operational risks are visible and testable.

Next, v0.3 will add fixture-driven execution tests, mocks, expected outputs, and regression snapshots.

See [ROADMAP.md](ROADMAP.md).

## License

MIT.
