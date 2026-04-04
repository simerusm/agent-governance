from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from runtime.decision_engine import DecisionEngine
from runtime.policies import RuntimePolicy

from .llm_client import complete_openai_compatible, mock_complete


@dataclass
class GovernedChatResult:
    blocked: bool
    blocked_phase: Optional[str]
    response_text: Optional[str]
    prompt_summary: Dict[str, Any]
    response_summary: Optional[Dict[str, Any]]


def run_governed_chat(
    prompt: str,
    *,
    policy: RuntimePolicy,
    llm_base_url: Optional[str],
    llm_api_key: Optional[str],
    llm_model: str,
) -> GovernedChatResult:
    """
    Pre-governance on prompt → LLM → post-governance on response.
    """
    engine = DecisionEngine(policy)
    pre = engine.evaluate_text(phase="pre_prompt", text=prompt or "")
    pre_sum = pre.to_summary()

    if pre.action.value == "block":
        return GovernedChatResult(
            blocked=True,
            blocked_phase="pre_prompt",
            response_text=None,
            prompt_summary=pre_sum,
            response_summary=None,
        )

    if llm_base_url:
        llm_call: Callable[[str], str] = lambda p: complete_openai_compatible(
            p,
            base_url=llm_base_url,
            api_key=llm_api_key,
            model=llm_model,
        )
    else:
        llm_call = lambda p: mock_complete(p, model=llm_model)

    response_text = llm_call(prompt or "")
    post = engine.evaluate_text(phase="post_response", text=response_text or "")
    post_sum = post.to_summary()

    if post.action.value == "block":
        return GovernedChatResult(
            blocked=True,
            blocked_phase="post_response",
            response_text=None,
            prompt_summary=pre_sum,
            response_summary=post_sum,
        )

    return GovernedChatResult(
        blocked=False,
        blocked_phase=None,
        response_text=response_text,
        prompt_summary=pre_sum,
        response_summary=post_sum,
    )
