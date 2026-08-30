# Execution Roadmap

## v0.1 — Quality contract and validator

Goal: establish a strict package format so every workflow is testable and reviewable.

- [x] Repository structure and project positioning
- [x] Production-readiness manifest design
- [x] Static workflow validator
- [x] Secret-pattern checks
- [x] Reference workflow package
- [x] Unit tests and CI

Exit criteria: CI can scan the repository and fail on malformed workflow packages.

## v0.2 — Semantic n8n analysis

- node-type risk classification
- credential-reference validation
- webhook authentication checks
- destructive action detection
- retry/error workflow inspection
- n8n version compatibility metadata
- richer quality score with severity levels

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