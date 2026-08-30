from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class HarnessError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkflowTestCase:
    name: str
    input: dict[str, Any]
    expected: Any
    mocks: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "WorkflowTestCase":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            name=str(data.get("name") or path.stem),
            input=dict(data.get("input") or {}),
            expected=data.get("expected"),
            mocks=dict(data.get("mocks") or {}),
        )


@dataclass(frozen=True)
class ExecutionSnapshot:
    case: str
    path: tuple[str, ...]
    node_outputs: dict[str, Any]
    final: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case,
            "path": list(self.path),
            "node_outputs": self.node_outputs,
            "final": self.final,
        }


@dataclass(frozen=True)
class TestResult:
    package: str
    case: str
    passed: bool
    errors: tuple[str, ...]
    snapshot: ExecutionSnapshot


class WorkflowHarness:
    """Deterministic test runner for a safe n8n subset, with mocks for external nodes."""

    def __init__(self, workflow: dict) -> None:
        self.workflow = workflow
        self.nodes = {str(node.get("name")): node for node in workflow.get("nodes", []) if node.get("name")}
        self.connections = workflow.get("connections") or {}
        self._validate_graph()

    def run(self, case: WorkflowTestCase) -> ExecutionSnapshot:
        starts = self._start_nodes()
        if not starts:
            raise HarnessError("workflow has no start node")
        queue: list[tuple[str, Any]] = [(name, _deepcopy(case.input)) for name in starts]
        path: list[str] = []
        outputs: dict[str, Any] = {}
        final: Any = None
        visits = 0
        max_visits = max(10, len(self.nodes) * 5)

        while queue:
            name, payload = queue.pop(0)
            visits += 1
            if visits > max_visits:
                raise HarnessError("workflow graph exceeded deterministic visit limit")
            node = self.nodes[name]
            output = self._execute_node(node, payload, case.mocks)
            path.append(name)
            outputs[name] = _deepcopy(output)
            next_nodes = self._next_nodes(name)
            if not next_nodes:
                final = output
            for next_name in next_nodes:
                queue.append((next_name, _deepcopy(output)))

        return ExecutionSnapshot(case.name, tuple(path), outputs, final)

    def _execute_node(self, node: dict, payload: Any, mocks: dict[str, Any]) -> Any:
        name = str(node.get("name"))
        if name in mocks:
            return _deepcopy(mocks[name])

        node_type = str(node.get("type", ""))
        parameters = node.get("parameters") or {}
        if node_type.endswith(".webhook") or node_type.endswith(".manualTrigger"):
            return payload
        if node_type.endswith(".set"):
            return self._execute_set(parameters, payload)
        if node_type.endswith(".respondToWebhook"):
            return self._execute_response(parameters, payload)
        if node_type.endswith(".noOp"):
            return payload

        raise HarnessError(
            f"node '{name}' ({node_type}) requires a fixture mock; "
            "the harness intentionally does not execute arbitrary external/code nodes"
        )

    @staticmethod
    def _execute_set(parameters: dict, payload: Any) -> dict[str, Any]:
        source = payload if isinstance(payload, dict) else {"value": payload}
        assignments = ((parameters.get("assignments") or {}).get("assignments") or [])
        result: dict[str, Any] = {}
        for item in assignments:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            result[str(item["name"])] = _eval_value(item.get("value"), source)
        return result

    @staticmethod
    def _execute_response(parameters: dict, payload: Any) -> Any:
        body = parameters.get("responseBody", payload)
        if not isinstance(body, str):
            return _deepcopy(body)
        rendered = body[1:] if body.startswith("=") else body
        rendered = _TEMPLATE.sub(lambda m: str(_resolve_path(payload, m.group(1))), rendered)
        try:
            return json.loads(rendered)
        except json.JSONDecodeError:
            return rendered

    def _start_nodes(self) -> list[str]:
        targeted = set()
        for source in self.connections:
            targeted.update(self._next_nodes(source))
        starts = [name for name in self.nodes if name not in targeted]
        return starts

    def _next_nodes(self, name: str) -> list[str]:
        connection = self.connections.get(name) or {}
        main = connection.get("main") or []
        result: list[str] = []
        for branch in main:
            if not isinstance(branch, list):
                continue
            for edge in branch:
                target = edge.get("node") if isinstance(edge, dict) else None
                if target:
                    result.append(str(target))
        return result

    def _validate_graph(self) -> None:
        for source in self.connections:
            if source not in self.nodes:
                raise HarnessError(f"connection source does not exist: {source}")
            for target in self._next_nodes(source):
                if target not in self.nodes:
                    raise HarnessError(f"connection target does not exist: {target}")


def run_package(package: Path, *, update_snapshots: bool = False) -> list[TestResult]:
    workflow_path = package / "workflow.json"
    tests_dir = package / "tests"
    if not workflow_path.exists() or not tests_dir.exists():
        return []
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    harness = WorkflowHarness(workflow)
    snapshot_dir = package / "snapshots"
    results: list[TestResult] = []

    for fixture in sorted(tests_dir.glob("*.json")):
        case = WorkflowTestCase.load(fixture)
        errors: list[str] = []
        try:
            snapshot = harness.run(case)
        except Exception as exc:
            snapshot = ExecutionSnapshot(case.name, (), {}, None)
            errors.append(str(exc))
            results.append(TestResult(package.name, case.name, False, tuple(errors), snapshot))
            continue

        if snapshot.final != case.expected:
            errors.append(f"final output mismatch: expected={case.expected!r} actual={snapshot.final!r}")

        snapshot_path = snapshot_dir / f"{fixture.stem}.json"
        if update_snapshots:
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(
                json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        elif snapshot_path.exists():
            expected_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            if snapshot.to_dict() != expected_snapshot:
                errors.append("execution snapshot changed")
        else:
            errors.append("regression snapshot is missing")

        results.append(TestResult(package.name, case.name, not errors, tuple(errors), snapshot))
    return results


def run_catalog(root: Path, *, update_snapshots: bool = False) -> list[TestResult]:
    if not root.exists():
        return []
    results: list[TestResult] = []
    for package in sorted(path for path in root.iterdir() if path.is_dir()):
        results.extend(run_package(package, update_snapshots=update_snapshots))
    return results


def render_markdown(results: list[TestResult]) -> str:
    lines = ["# n8n Workflow Test Report", "", "| Package | Case | Status | Path |", "| --- | --- | --- | --- |"]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        path = " → ".join(result.snapshot.path) or "-"
        lines.append(f"| {result.package} | {result.case} | {status} | {path} |")
        for error in result.errors:
            lines.append(f"\n- **{result.package}/{result.case}**: {error}")
    return "\n".join(lines) + "\n"


def _eval_value(value: Any, payload: dict) -> Any:
    if not isinstance(value, str) or not value.startswith("={{"):
        return _deepcopy(value)
    expression = value[3:-2].strip()
    parts = [part.strip() for part in expression.split("||", 1)]
    resolved = _eval_atom(parts[0], payload)
    if (resolved is None or resolved == "") and len(parts) == 2:
        return _eval_atom(parts[1], payload)
    return resolved


def _eval_atom(atom: str, payload: dict) -> Any:
    atom = atom.strip()
    if atom.startswith("$json."):
        return _resolve_path(payload, atom[6:])
    if (atom.startswith("'") and atom.endswith("'")) or (atom.startswith('"') and atom.endswith('"')):
        return atom[1:-1]
    if atom in {"true", "false"}:
        return atom == "true"
    if atom == "null":
        return None
    try:
        return int(atom)
    except ValueError:
        try:
            return float(atom)
        except ValueError:
            return atom


def _resolve_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _deepcopy(value: Any) -> Any:
    return json.loads(json.dumps(value))


_TEMPLATE = re.compile(r"{{\s*\$json\.([A-Za-z0-9_.-]+)\s*}}")
