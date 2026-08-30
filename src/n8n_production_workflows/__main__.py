from __future__ import annotations

import argparse
import json
from pathlib import Path

from .harness import render_markdown, run_catalog
from .validator import validate_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and regression-test production-grade n8n workflow packages")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="static production-readiness analysis")
    validate_parser.add_argument("path", nargs="?", default="workflows")

    test_parser = sub.add_parser("test", help="fixture-driven deterministic regression tests")
    test_parser.add_argument("path", nargs="?", default="workflows")
    test_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    test_parser.add_argument("--update-snapshots", action="store_true")

    args = parser.parse_args()
    if args.command == "validate":
        return _validate(Path(args.path))
    return _test(Path(args.path), args.format, args.update_snapshots)


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


if __name__ == "__main__":
    raise SystemExit(main())
