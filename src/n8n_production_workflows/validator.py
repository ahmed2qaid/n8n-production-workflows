from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .analyzer import NodeRisk, analyze_workflow

_SECRET_RE = re.compile(
    r'''(?ix)
    ["']?(api[_-]?key|secret|token|password)["']?
    \s*[:=]\s*
    ["']?[A-Za-z0-9_\-]{12,}
    '''
)


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str


@dataclass
class ValidationReport:
    package: str
    issues: list[ValidationIssue] = field(default_factory=list)
    node_risks: list[NodeRisk] = field(default_factory=list)
    score: int = 100

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def add(self, severity: str, code: str, message: str, penalty: int) -> None:
        self.issues.append(ValidationIssue(severity, code, message))
        self.score = max(0, self.score - penalty)


_REQUIRED_MANIFEST_KEYS = {
    "name",
    "description",
    "credentials",
    "side_effects",
    "retries",
    "error_handling",
    "idempotency",
    "observability",
}


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing file: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path.name}: {exc.msg}") from exc


def validate_package(package_dir: Path) -> ValidationReport:
    report = ValidationReport(package=package_dir.name)

    try:
        manifest = _load_json(package_dir / "manifest.json")
    except ValueError as exc:
        report.add("error", "manifest.invalid", str(exc), 40)
        return report

    try:
        workflow = _load_json(package_dir / "workflow.json")
    except ValueError as exc:
        report.add("error", "workflow.invalid", str(exc), 40)
        return report

    missing = sorted(_REQUIRED_MANIFEST_KEYS - manifest.keys())
    if missing:
        report.add(
            "error",
            "manifest.missing_keys",
            f"manifest is missing required keys: {', '.join(missing)}",
            min(35, len(missing) * 5),
        )

    nodes = workflow.get("nodes")
    connections = workflow.get("connections")
    if not isinstance(nodes, list) or not nodes:
        report.add("error", "workflow.nodes", "workflow must contain at least one node", 30)
    if not isinstance(connections, dict):
        report.add("error", "workflow.connections", "workflow.connections must be an object", 20)

    workflow_name = workflow.get("name")
    if workflow_name and manifest.get("name") and workflow_name != manifest.get("name"):
        report.add("warning", "identity.name_mismatch", "manifest name does not match workflow name", 5)

    controls = {
        "retries": 8,
        "error_handling": 12,
        "idempotency": 10,
        "observability": 8,
    }
    for key, penalty in controls.items():
        value = manifest.get(key)
        if value in (False, None, "", [], {}):
            report.add("warning", f"control.{key}", f"production control '{key}' is not declared", penalty)

    if manifest.get("side_effects") and manifest.get("idempotency") in (False, None, ""):
        report.add("error", "side_effect.idempotency", "workflow declares side effects but no idempotency strategy", 15)

    raw = (package_dir / "workflow.json").read_text(encoding="utf-8")
    if _SECRET_RE.search(raw):
        report.add("error", "security.inline_secret", "workflow appears to contain an inline secret-like value", 35)

    if isinstance(nodes, list):
        node_risks, semantic_findings = analyze_workflow(workflow, manifest)
        report.node_risks = node_risks
        for finding in semantic_findings:
            prefix = f"{finding.node}: " if finding.node else ""
            report.add(finding.severity, finding.code, prefix + finding.message, finding.penalty)

    return report


def validate_catalog(root: Path) -> list[ValidationReport]:
    if not root.exists():
        raise ValueError(f"catalog path does not exist: {root}")

    packages: Iterable[Path] = sorted(
        path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")
    )
    return [validate_package(package) for package in packages]
