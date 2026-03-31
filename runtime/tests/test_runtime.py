from __future__ import annotations

import unittest

from runtime import GovernedRunner, MockLLM, RuntimePolicy
from sdk.context import AgentMetadata


class TestRuntimeGovernance(unittest.TestCase):
    def test_warn_default(self) -> None:
        r = GovernedRunner(policy=RuntimePolicy(block_on_alert=False), llm=MockLLM())

        def agent(*, execution_context=None) -> str:
            return execution_context.governed_complete("sk-ant-api01-aaaaaaaaaaaaaaaaaaaa")

        meta = AgentMetadata(policy="default", name="agent")
        out = r.run_agent(agent, meta, (), {})
        self.assertIn("Mock response", out)
        decisions = [e for e in r.last_trace if e["name"] == "governance.decision"]
        self.assertEqual(decisions[0]["payload"]["phase"], "pre_prompt")

    def test_block_feature_flag(self) -> None:
        r = GovernedRunner(
            policy=RuntimePolicy(block_on_alert=True, alert_threshold=10.0),
            llm=MockLLM(),
        )

        def agent(*, execution_context=None) -> str:
            return execution_context.governed_complete("sk-ant-api01-aaaaaaaaaaaaaaaaaaaa")

        meta = AgentMetadata(policy="default", name="agent")
        with self.assertRaises(RuntimeError):
            r.run_agent(agent, meta, (), {})


if __name__ == "__main__":
    unittest.main()

