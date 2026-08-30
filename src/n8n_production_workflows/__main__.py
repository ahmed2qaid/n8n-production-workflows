from __future__ import annotations

import argparse
from pathlib import Path

from .validator import validate_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate production-grade n8n workflow packages")
    parser.add_argument("command", choices=["validate"])
    parser.add_argument("path", nargs="?", default="workflows")
    args = parser.parse_args()

    reports = validate_catalog(Path(args.path))
    failed = False
    if not reports:
        print("No workflow packages found.")
        return 0

    for report in reports:
        state = "PASS" if report.ok else "FAIL"
        print(f"{state} {report.package}: {report.score}/100")
        for issue in report.issues:
            print(f"  [{issue.severity.upper()}] {issue.code}: {issue.message}")
        failed = failed or not report.ok

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
