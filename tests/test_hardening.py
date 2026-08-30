from __future__ import annotations

import unittest

from n8n_production_workflows.hardening import apply_safe_hardening, build_hardening_plan


class HardeningTests(unittest.TestCase):
    def test_destructive_workflow_requires_approval_and_dead_letter(self):
        workflow = {
            "nodes": [
                {
                    "name": "Delete Customer",
                    "type": "n8n-nodes-base.httpRequest",
                    "parameters": {"method": "DELETE", "url": "https://api.example.com/customer/1"},
                }
            ]
        }
        manifest = {
            "side_effects": True,
            "tested_with": "n8n 1.x",
            "error_handling": "error workflow",
            "idempotency": "request key",
        }
        plan = build_hardening_plan(workflow, manifest)
        ids = {action.id for action in plan.actions}
        self.assertIn("http.destructive", ids)
        self.assertIn("manifest.dead_letter", ids)
        self.assertIn("manifest.human_approval", ids)
        self.assertFalse(plan.ready)

    def test_safe_fixer_only_adds_bounded_http_retries(self):
        workflow = {
            "name": "mutating",
            "nodes": [
                {
                    "name": "Create Ticket",
                    "type": "n8n-nodes-base.httpRequest",
                    "parameters": {"method": "POST", "url": "https://api.example.com/tickets"},
                },
                {
                    "name": "Read Ticket",
                    "type": "n8n-nodes-base.httpRequest",
                    "parameters": {"method": "GET", "url": "https://api.example.com/tickets/1"},
                },
            ],
        }
        hardened, changes = apply_safe_hardening(workflow)
        create = hardened["nodes"][0]
        read = hardened["nodes"][1]
        self.assertTrue(create["retryOnFail"])
        self.assertEqual(create["maxTries"], 3)
        self.assertEqual(create["waitBetweenTries"], 1000)
        self.assertNotIn("retryOnFail", read)
        self.assertEqual(len(changes), 1)
        self.assertNotIn("retryOnFail", workflow["nodes"][0])


if __name__ == "__main__":
    unittest.main()
