from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SemanticFinding:
    severity: str
    risk: str
    code: str
    message: str
    node: str = ""
    penalty: int = 0


@dataclass
class NodeRisk:
    node: str
    node_type: str
    risk: str = "low"
    score: int = 0
    findings: list[str] = field(default_factory=list)


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_DESTRUCTIVE = re.compile(r"\b(delete|drop|truncate|destroy|remove|revoke|terminate)\b", re.I)
_MUTATING = re.compile(r"\b(create|insert|update|upsert|send|publish|execute|write|modify)\b", re.I)
_SQL_DESTRUCTIVE = re.compile(r"\b(delete\s+from|drop\s+(table|database|schema)|truncate\s+table)\b", re.I)
_SQL_WRITE = re.compile(r"\b(insert\s+into|update\s+\w+|create\s+(table|schema)|alter\s+table)\b", re.I)


def _raise_risk(node: NodeRisk, risk: str, points: int, reason: str) -> None:
    if _RISK_ORDER[risk] > _RISK_ORDER[node.risk]:
        node.risk = risk
    node.score = min(100, node.score + points)
    node.findings.append(reason)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def analyze_workflow(workflow: dict, manifest: dict) -> tuple[list[NodeRisk], list[SemanticFinding]]:
    nodes = workflow.get("nodes") or []
    findings: list[SemanticFinding] = []
    risks: list[NodeRisk] = []
    declared_credentials = {str(x) for x in (manifest.get("credentials") or [])}

    if not manifest.get("tested_with"):
        findings.append(SemanticFinding("warning", "medium", "compatibility.n8n_version", "manifest should declare tested_with n8n version", penalty=5))

    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            continue
        name = str(raw_node.get("name") or raw_node.get("id") or "unnamed")
        node_type = str(raw_node.get("type") or "unknown")
        lower_type = node_type.lower()
        params = raw_node.get("parameters") or {}
        risk = NodeRisk(node=name, node_type=node_type)

        credentials = raw_node.get("credentials") or {}
        if credentials:
            if not isinstance(credentials, dict):
                findings.append(SemanticFinding("error", "high", "credentials.invalid", "credentials must be an object", name, 15))
                _raise_risk(risk, "high", 20, "invalid credential reference")
            else:
                for credential_type, reference in credentials.items():
                    if not isinstance(reference, dict) or not (reference.get("id") or reference.get("name")):
                        findings.append(SemanticFinding("error", "high", "credentials.unresolved", f"credential '{credential_type}' has no id/name reference", name, 15))
                        _raise_risk(risk, "high", 20, "unresolved credential reference")
                    if declared_credentials and str(credential_type) not in declared_credentials:
                        findings.append(SemanticFinding("warning", "medium", "credentials.undeclared", f"credential type '{credential_type}' is not declared in manifest", name, 5))

        if lower_type.endswith(".webhook") or lower_type == "n8n-nodes-base.webhook":
            auth = str(params.get("authentication") or "none").lower()
            if auth in {"none", "", "false"}:
                if manifest.get("public_webhook") is True and manifest.get("webhook_security"):
                    findings.append(SemanticFinding("warning", "medium", "webhook.public", "public webhook is explicitly documented; ensure upstream verification/rate limiting", name, 4))
                    _raise_risk(risk, "medium", 15, "public unauthenticated webhook")
                else:
                    findings.append(SemanticFinding("error", "high", "webhook.unauthenticated", "webhook has no authentication and no documented public-webhook exception", name, 20))
                    _raise_risk(risk, "high", 35, "unauthenticated webhook")

        if "httprequest" in lower_type:
            method = str(params.get("method") or params.get("requestMethod") or "GET").upper()
            if method == "DELETE":
                findings.append(SemanticFinding("error", "critical", "http.destructive", "HTTP DELETE creates a destructive external side effect", name, 20))
                _raise_risk(risk, "critical", 45, "destructive HTTP DELETE")
            elif method in {"POST", "PUT", "PATCH"}:
                findings.append(SemanticFinding("warning", "high", "http.side_effect", f"HTTP {method} may create an external side effect", name, 8))
                _raise_risk(risk, "high", 25, f"mutating HTTP {method}")
            retry_on_fail = bool(raw_node.get("retryOnFail") or params.get("retryOnFail"))
            if not retry_on_fail:
                findings.append(SemanticFinding("warning", "medium", "http.retry_missing", "external HTTP node has no explicit retryOnFail flag", name, 5))

        if lower_type.endswith(".code") or "function" in lower_type:
            findings.append(SemanticFinding("warning", "high", "code.arbitrary", "Code/Function node executes arbitrary user code; review inputs, secrets, and network access", name, 8))
            _raise_risk(risk, "high", 30, "arbitrary code execution")

        text = " ".join(_strings(params))
        if _SQL_DESTRUCTIVE.search(text):
            findings.append(SemanticFinding("error", "critical", "database.destructive_sql", "destructive SQL detected in node parameters", name, 25))
            _raise_risk(risk, "critical", 50, "destructive SQL")
        elif _SQL_WRITE.search(text):
            findings.append(SemanticFinding("warning", "high", "database.write_sql", "database write SQL detected", name, 8))
            _raise_risk(risk, "high", 25, "database write SQL")

        operation_text = " ".join(
            str(params.get(key, "")) for key in ("operation", "action", "resource", "mode")
        )
        if _DESTRUCTIVE.search(operation_text):
            findings.append(SemanticFinding("error", "critical", "node.destructive_operation", f"destructive operation detected: {operation_text.strip()}", name, 20))
            _raise_risk(risk, "critical", 45, "destructive node operation")
        elif _MUTATING.search(operation_text):
            findings.append(SemanticFinding("warning", "high", "node.mutating_operation", f"mutating operation detected: {operation_text.strip()}", name, 6))
            _raise_risk(risk, "high", 20, "mutating node operation")

        if risk.risk == "low" and credentials:
            _raise_risk(risk, "medium", 10, "uses external credentials")
        risks.append(risk)

    high_risk = any(item.risk in {"high", "critical"} for item in risks)
    if high_risk and not manifest.get("error_handling"):
        findings.append(SemanticFinding("error", "high", "reliability.error_handling", "high-risk workflow must document error_handling", penalty=15))
    if high_risk and not manifest.get("idempotency"):
        findings.append(SemanticFinding("error", "high", "reliability.idempotency", "high-risk workflow must document idempotency strategy", penalty=15))

    return risks, findings


def risk_summary(risks: list[NodeRisk]) -> dict:
    return {
        "nodes": len(risks),
        "critical": sum(1 for item in risks if item.risk == "critical"),
        "high": sum(1 for item in risks if item.risk == "high"),
        "medium": sum(1 for item in risks if item.risk == "medium"),
        "low": sum(1 for item in risks if item.risk == "low"),
        "max_score": max((item.score for item in risks), default=0),
    }
