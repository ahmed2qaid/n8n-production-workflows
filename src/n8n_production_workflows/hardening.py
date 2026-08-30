from __future__ import annotations

import copy
from dataclasses import dataclass

from .analyzer import analyze_workflow


@dataclass(frozen=True)
class HardeningAction:
    id: str
    severity: str
    title: str
    reason: str
    pattern: str
    node: str = ""
    auto_fixable: bool = False


@dataclass(frozen=True)
class HardeningPlan:
    score: int
    actions: tuple[HardeningAction, ...]

    @property
    def ready(self) -> bool:
        return not any(action.severity in {"high", "critical"} for action in self.actions)


_FINDING_RECIPES = {
    "http.retry_missing": ("medium", "Enable bounded exponential retries", "rate-limit-backoff", True),
    "webhook.unauthenticated": ("high", "Authenticate or verify the inbound webhook", "verified-webhook", False),
    "webhook.public": ("medium", "Rate-limit and verify public webhook payloads upstream", "verified-webhook", False),
    "http.destructive": ("critical", "Require human approval before destructive HTTP calls", "human-approval", False),
    "http.side_effect": ("high", "Protect external side effects with idempotency and retry policy", "idempotent-side-effect", True),
    "database.destructive_sql": ("critical", "Require approval and backup/compensation before destructive SQL", "human-approval", False),
    "database.write_sql": ("high", "Add an idempotency key and compensation path around database writes", "idempotent-side-effect", False),
    "node.destructive_operation": ("critical", "Gate destructive node operations behind explicit approval", "human-approval", False),
    "node.mutating_operation": ("high", "Make mutating operations idempotent and observable", "idempotent-side-effect", False),
    "code.arbitrary": ("high", "Constrain Code node inputs, secrets and network access", "sandboxed-code", False),
    "reliability.error_handling": ("high", "Attach an error workflow and dead-letter path", "dead-letter-error-workflow", False),
    "reliability.idempotency": ("high", "Define and persist an idempotency key before side effects", "idempotent-side-effect", False),
}


def build_hardening_plan(workflow: dict, manifest: dict) -> HardeningPlan:
    _, findings = analyze_workflow(workflow, manifest)
    actions: list[HardeningAction] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        recipe = _FINDING_RECIPES.get(finding.code)
        if recipe is None:
            continue
        severity, title, pattern, auto_fixable = recipe
        key = (finding.code, finding.node)
        if key in seen:
            continue
        seen.add(key)
        actions.append(
            HardeningAction(
                id=finding.code,
                severity=severity,
                title=title,
                reason=finding.message,
                pattern=pattern,
                node=finding.node,
                auto_fixable=auto_fixable,
            )
        )

    if manifest.get("side_effects") and not manifest.get("dead_letter"):
        actions.append(
            HardeningAction(
                "manifest.dead_letter",
                "high",
                "Document a dead-letter destination",
                "side-effecting workflows need an operator-visible terminal failure path",
                "dead-letter-error-workflow",
            )
        )
    if manifest.get("side_effects") and not manifest.get("human_approval"):
        destructive = any(action.severity == "critical" for action in actions)
        if destructive:
            actions.append(
                HardeningAction(
                    "manifest.human_approval",
                    "critical",
                    "Declare the human-approval boundary",
                    "destructive side effects should not rely on prompt-level intent alone",
                    "human-approval",
                )
            )
    if manifest.get("side_effects") and not manifest.get("observability"):
        actions.append(
            HardeningAction(
                "manifest.observability",
                "medium",
                "Record execution IDs, side effects, latency and terminal errors",
                "side-effecting automation needs a traceable operator trail",
                "observability",
            )
        )

    penalty = sum({"medium": 5, "high": 12, "critical": 25}.get(action.severity, 0) for action in actions)
    return HardeningPlan(score=max(0, 100 - min(100, penalty)), actions=tuple(actions))


def apply_safe_hardening(workflow: dict) -> tuple[dict, tuple[str, ...]]:
    """Apply only semantics-preserving reliability defaults.

    The fixer intentionally does not auto-wire approval or error branches because
    doing that safely requires domain-specific routing decisions. It only adds
    bounded retry defaults to mutating HTTP nodes when no retry policy exists.
    """
    hardened = copy.deepcopy(workflow)
    changes: list[str] = []
    for node in hardened.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type", "")).lower()
        if "httprequest" not in node_type:
            continue
        params = node.setdefault("parameters", {})
        method = str(params.get("method") or params.get("requestMethod") or "GET").upper()
        if method not in {"POST", "PUT", "PATCH", "DELETE"}:
            continue
        if node.get("retryOnFail") or params.get("retryOnFail"):
            continue
        node["retryOnFail"] = True
        node.setdefault("maxTries", 3)
        node.setdefault("waitBetweenTries", 1000)
        changes.append(f"{node.get('name') or node.get('id')}: enabled retryOnFail maxTries=3 waitBetweenTries=1000")
    return hardened, tuple(changes)


def render_hardening_markdown(plan: HardeningPlan) -> str:
    lines = [f"# n8n Production Hardening Plan\n", f"Readiness score: **{plan.score}/100**\n"]
    if not plan.actions:
        lines.append("No hardening actions detected.\n")
        return "\n".join(lines)
    for action in plan.actions:
        target = f" — `{action.node}`" if action.node else ""
        fix = " · safe auto-fix available" if action.auto_fixable else ""
        lines.append(
            f"- **{action.severity.upper()}** `{action.id}`{target}: {action.title}. "
            f"Pattern: `{action.pattern}`{fix}. {action.reason}"
        )
    lines.append("")
    return "\n".join(lines)
