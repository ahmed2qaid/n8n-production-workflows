from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from n8n_production_workflows.validator import validate_catalog, validate_package


class ValidatorTests(unittest.TestCase):
    def test_reference_catalog_passes(self) -> None:
        reports = validate_catalog(Path("workflows"))
        self.assertTrue(reports)
        self.assertTrue(all(report.ok for report in reports))
        self.assertGreaterEqual(reports[0].score, 90)

    def test_inline_secret_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "name": "Unsafe",
                "description": "test",
                "credentials": [],
                "side_effects": False,
                "retries": "declared",
                "error_handling": "declared",
                "idempotency": "declared",
                "observability": "declared"
            }
            workflow = {
                "name": "Unsafe",
                "nodes": [{"name": "HTTP", "parameters": {"api_key": "abcdefghijklmnop"}}],
                "connections": {}
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "workflow.json").write_text(json.dumps(workflow), encoding="utf-8")

            report = validate_package(root)
            self.assertFalse(report.ok)
            self.assertTrue(any(issue.code == "security.inline_secret" for issue in report.issues))


if __name__ == "__main__":
    unittest.main()
