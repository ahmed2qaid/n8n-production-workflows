# Execution Roadmap

## v0.1 — Quality contract and validator

- [x] Repository structure and production-readiness manifest
- [x] static workflow validator and secret-pattern checks
- [x] reference workflow package, tests and CI

## v0.2 — Semantic n8n analysis

- [x] node-type risk classification
- [x] credential and webhook security checks
- [x] destructive SQL/HTTP/action detection
- [x] retry, idempotency and error-path inspection
- [x] per-node production/security score

## v0.3 — Deterministic test harness

- [x] fixture-driven workflow tests
- [x] mock outputs for HTTP/API/code/unsupported nodes
- [x] deterministic graph runner for a safe built-in node subset
- [x] Set/Edit Fields expression evaluation for common `$json` paths and fallbacks
- [x] Respond to Webhook output rendering
- [x] exact expected final-output assertions
- [x] per-node execution snapshots
- [x] regression snapshot comparison
- [x] `--update-snapshots` workflow
- [x] CLI report in text, JSON and Markdown
- [x] CI gate on deterministic workflow snapshots
- [x] first executable reference fixture and snapshot

Exit criteria: a workflow package can fail CI because its deterministic behavior or execution path changed even when its exported n8n JSON remains syntactically valid.

## v0.4 — Production hardening

- [x] machine-readable idempotency recipe
- [x] dead-letter/error-workflow pattern
- [x] bounded retry/backoff defaults for mutating HTTP nodes
- [x] human-approval boundary pattern for destructive actions
- [x] webhook verification and Code-node containment recipes
- [x] observability/correlation pattern
- [x] hardening planner with production readiness score
- [x] safe auto-fixer that never auto-wires destructive/approval branches
- [x] `n8n-workflow-check harden` text/JSON/Markdown CLI with optional hardened export

Exit criteria: maintainers receive a concrete production hardening plan for risky workflows, can apply semantics-preserving retry defaults automatically, and have reusable machine-readable patterns for the controls that require domain-specific wiring.

## v1.0 — Curated production catalog

- 20+ reviewed workflows across support, operations, engineering, data, and AI automation
- automated compatibility matrix
- signed manifest metadata
- searchable documentation site
- contribution policy and review checklist

## Non-goals

This project will not compete on raw workflow count. The deterministic harness also does not attempt to reimplement the full n8n runtime: arbitrary/external nodes must be mocked unless explicitly supported.
