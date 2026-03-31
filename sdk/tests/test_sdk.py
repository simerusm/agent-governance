from __future__ import annotations

import unittest

from sdk import (
    ArtifactRef,
    DefaultRuntimeClient,
    governed_agent,
    record_artifact,
    record_tool_invocation,
)
from sdk.context import current_run_context


class TestGovernedAgent(unittest.TestCase):
    def test_metadata_attached(self) -> None:
        @governed_agent(policy="test-policy", tags={"team": "a"})
        def agent(x: int) -> int:
            return x + 1

        meta = getattr(agent, "__governance_metadata__")
        self.assertEqual(meta.policy, "test-policy")
        self.assertEqual(meta.name, "agent")
        self.assertEqual(meta.tags["team"], "a")

    def test_runs_with_default_client(self) -> None:
        @governed_agent(policy="p")
        def agent(x: int) -> int:
            self.assertIsNotNone(current_run_context())
            return x * 2

        self.assertEqual(agent(3), 6)

    def test_explicit_client(self) -> None:
        @governed_agent(policy="p", client=DefaultRuntimeClient())
        def agent() -> str:
            return "ok"

        self.assertEqual(agent(), "ok")


class TestToolingArtifacts(unittest.TestCase):
    def test_record_under_run(self) -> None:
        captured: tuple[int, int] | None = None

        @governed_agent(policy="p")
        def agent() -> None:
            nonlocal captured
            record_tool_invocation("search", {"q": "x"})
            record_artifact(ArtifactRef(kind="file", uri="file:///tmp/a.txt", name="a"))
            ctx = current_run_context()
            assert ctx is not None
            captured = (len(ctx.tool_events), len(ctx.artifact_refs))

        agent()
        self.assertEqual(captured, (1, 1))
        self.assertIsNone(current_run_context())


if __name__ == "__main__":
    unittest.main()
