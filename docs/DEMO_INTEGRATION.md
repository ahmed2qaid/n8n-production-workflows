# Demo Integration Contract

This repository remains the production-readiness and hardening layer for n8n workflows. The end-to-end demo uses a reviewed workflow package from this repository and validates it in CI before the integration stack is considered releasable.

## Role in `ai-automation-infra-demo`

```text
Inbound webhook / event
        ↓
Production-reviewed n8n workflow
        ↓
Agent orchestration / approval / notification
```

## Demo responsibilities

- provide the inbound automation workflow that starts the reference scenario
- validate the workflow package with `n8n-workflow-check validate`
- run deterministic fixtures and snapshots with `n8n-workflow-check test`
- apply/document production hardening requirements
- model idempotency, bounded retry and dead-letter behavior
- keep high-risk approval decisions outside the raw n8n prompt path

## Stable integration surface

The integration repository may vendor or pin one released workflow package for repeatable demos, but the canonical workflow and its tests remain in `n8n-production-workflows`.

The demo CI should fail if the selected workflow no longer passes validation or its deterministic snapshot changes unexpectedly.

## Reference scenario

An authenticated webhook receives a refund/support request, normalizes the payload, generates a correlation ID, calls the orchestration service, waits for the final durable result and emits the final notification/audit status.

## Boundary rule

Workflow hardening rules, static analysis, deterministic fixtures and production templates belong in `n8n-production-workflows`. The demo consumes a released workflow; it does not become another workflow catalog.
