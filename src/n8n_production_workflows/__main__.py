from __future__ import annotations

import argparse
import json
from pathlib import Path

from .hardening import apply_safe_hardening, build_hardening_plan, render_hardening_markdown
from .harness import render_markdown, run_catalog
from .validator import validate_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate, regression-test, and harden production-grade n8n workflow packages")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="static production-readiness analysis")
    validate_parser.add_argument("path", nargs="?", default="workflows")

    test_parser = sub.add_parser("test", help="fixture-driven deterministic regression tests")
    test_parser.add_argument("path", nargs="?", default="workflows")
    test_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    test_parser.add_argument("--update-snapshots", action="store_true")

    harden_parser = sub.add_parser("harden", help="build a production hardening plan and optionally write safe fixes")
    harden_parser.add_argument("path", help="workflow package directory or workflow.json")
    harden_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    harden_parser.add_argument("--write", help="write a safely-hardened workflow JSON to this path")

    args = parser.parse_args()
    if args.command == "validate":
        return _validate(Path(args.path))
    if args.command == "test":
        return _test(Path(args.path), args.format, args.update_snapshots)
    return _harden(Path(args.path), args.format, args.write)


def _validate(path: Path) -> int:
    reports = validate_catalog(path)
    failed = False
    if not reports:
        print("No workflow packages found.")
        return 0
    for report in reports:
        state = "PASS" if report.ok else "FAIL"
        print(f"{state} {report.package}: {report.score}/100")
        for risk in report.node_risks:
            if risk.risk != "low":
                details = "; ".join(risk.findings) or "risk heuristic"
                print(f"  [NODE {risk.risk.upper():8}] {risk.node} ({risk.node_type}) score={risk.score}: {details}")
        for issue in report.issues:
            print(f"  [{issue.severity.upper()}] {issue.code}: {issue.message}")
        failed = failed or not report.ok
    return 1 if failed else 0


def _test(path: Path, output_format: str, update_snapshots: bool) -> int:
    results = run_catalog(path, update_snapshots=update_snapshots)
    if not results:
        print("No workflow test fixtures found.")
        return 0

    if output_format == "json":
        print(
            json.dumps(
                [
                    {
                        "package": r.package,
                        "case": r.case,
                        "passed": r.passed,
                        "errors": list(r.errors),
                        "snapshot": r.snapshot.to_dict(),
                    }
                    for r in results
                ],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    elif output_format == "markdown":
        print(render_markdown(results), end="")
    else:
        for result in results:
            state = "PASS" if result.passed else "FAIL"
            print(f"{state} {result.package}/{result.case}: {' -> '.join(result.snapshot.path)}")
            for error in result.errors:
                print(f"  [ERROR] {error}")

    return 1 if any(not result.passed for result in results) else 0


def _load_package(path: Path) -> tuple[dict, dict]:
    if path.is_dir():
        workflow_path = path / "workflow.json"
        manifest_path = path / "manifest.json"
    else:
        workflow_path = path
        manifest_path = path.with_name("manifest.json")
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    if not isinstance(workflow, dict) or not isinstance(manifest, dict):
        raise ValueError("workflow and manifest must contain JSON objects")
    return workflow, manifest


def _harden(path: Path, output_format: str, write_path: str | None) -> int:
    workflow, manifest = _load_package(path)
    plan = build_hardening_plan(workflow, manifest)
    hardened, changes = apply_safe_hardening(workflow)

    if write_path:
        target = Path(write_path)
        target.write_text(json.dumps(hardened, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if output_format == "json":
        print(
            json.dumps(
                {
                    "score": plan.score,
                    "ready": plan.ready,
                    "actions": [action.__dict__ for action in plan.actions],
                    "safe_changes": list(changes),
                    "written": write_path,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
    elif output_format == "markdown":
        print(render_hardening_markdown(plan), end="")
    else:
        print(f"Production hardening score: {plan.score}/100")
        for action in plan.actions:
            target = f" ({action.node})" if action.node else ""
            auto = " [safe-auto-fix]" if action.auto_fixable else ""
            print(f"  [{action.severity.upper()}] {action.id}{target}{auto}: {action.title}")
        for change in changes:
            print(f"  [FIX] {change}")
        if write_path:
            print(f"Wrote safely-hardened workflow: {write_path}")

    return 0 if plan.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
