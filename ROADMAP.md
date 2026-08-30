# Execution Roadmap

## v0.1 — Quality contract and validator

- [x] Repository structure and project positioning
- [x] Production-readiness manifest design
- [x] Static workflow validator
- [x] Secret-pattern checks
- [x] Reference workflow package
- [x] Unit tests and CI

## v0.2 — Semantic n8n analysis

- [x] node-type risk classification
- [x] credential-reference validation
- [x] webhook authentication checks
- [x] documented public-webhook exception
- [x] destructive action detection
- [x] destructive/write SQL detection
- [x] HTTP side-effect and retry inspection
- [x] high-risk error/idempotency review
- [x] n8n version compatibility metadata
- [x] richer per-node risk score and severity levels
- [x] semantic analyzer tests

Exit criteria: CI can fail a workflow for security/production semantics even when its JSON structure is valid.

## v0.3 — Test harness

- fixture-driven workflow tests
- mock HTTP/API responses
- deterministic test mode
- expected node outputs
- regression snapshots
- CLI report in JSON and Markdown

## v0.4 — Production hardening

- idempotency recipes
- dead-letter patterns
- rate-limit backoff templates
- human-approval patterns
- reusable error-handling subworkflows
- observability integration examples

## v1.0 — Curated production catalog

- 20+ reviewed workflows across support, operations, engineering, data, and AI automation
- automated compatibility matrix
- signed manifest metadata
- searchable documentation site
- contribution policy and review checklist

## Non-goals

This project will not compete on raw workflow count. A workflow should not enter the catalog unless it has test fixtures, operational metadata, and a clear production-readiness story.
