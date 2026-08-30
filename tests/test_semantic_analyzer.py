import tempfile
import unittest
from pathlib import Path

from n8n_production_workflows.analyzer import analyze_workflow
from n8n_production_workflows.validator import validate_package


BASE_MANIFEST = {
    "name": "demo",
    "description": "demo",
    "credentials": [],
    "side_effects": True,
    "retries": "retry external calls",
    "error_handling": "error workflow",
    "idempotency": "request id",
    "observability": "execution logs",
    "tested_with": "n8n 1.x",
}


class SemanticAnalyzerTests(unittest.TestCase):
    def test_destructive_database_operation_is_error(self):
        workflow = {
            "name": "demo",
            "nodes": [{"name": "Delete User", "type": "n8n-nodes-base.postgres", "parameters": {"operation": "delete"}}],
            "connections": {},
        }
        risks, findings = analyze_workflow(workflow, BASE_MANIFEST)
        self.assertEqual(risks[0].risk, "critical")
        self.assertTrue(any(f.code == "node.destructive_operation" and f.severity == "error" for f in findings))

    def test_unauthenticated_webhook_requires_explicit_exception(self):
        workflow = {
            "name": "demo",
            "nodes": [{"name": "Hook", "type": "n8n-nodes-base.webhook", "parameters": {"path": "demo"}}],
            "connections": {},
        }
        _, findings = analyze_workflow(workflow, BASE_MANIFEST)
        self.assertTrue(any(f.code == "webhook.unauthenticated" for f in findings))

    def test_documented_public_webhook_is_warning_not_error(self):
        manifest = {**BASE_MANIFEST, "public_webhook": True, "webhook_security": "rate limited signed ingress in production"}
        workflow = {
            "name": "demo",
            "nodes": [{"name": "Hook", "type": "n8n-nodes-base.webhook", "parameters": {}}],
            "connections": {},
        }
        _, findings = analyze_workflow(workflow, manifest)
        self.assertFalse(any(f.severity == "error" for f in findings))
        self.assertTrue(any(f.code == "webhook.public" for f in findings))


if __name__ == "__main__":
    unittest.main()
