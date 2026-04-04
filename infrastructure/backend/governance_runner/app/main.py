"""
HTTP API for in-pod governance + LLM round-trip.

Run with: uvicorn app.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from typing import Any, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from runtime.decision_engine import DecisionEngine
from runtime.policies import RuntimePolicy

from .governed_flow import run_governed_chat

app = FastAPI(
    title="Governance Runner",
    description="Evaluate prompts/responses with governance_engine; optional OpenAI-compatible LLM.",
    version="0.1.0",
)


class PolicyModel(BaseModel):
    name: str = "default"
    alert_threshold: float = 75.0
    block_on_alert: bool = False


class LLMModel(BaseModel):
    """If base_url is omitted, a mock echo LLM is used."""

    base_url: Optional[str] = Field(
        default=None,
        description="OpenAI-compatible API root, e.g. https://api.openai.com/v1",
    )
    api_key: Optional[str] = Field(default=None, description="Bearer token (optional for mock)")
    model: str = "gpt-4o-mini"


class GovernedCompleteRequest(BaseModel):
    prompt: str
    policy: PolicyModel = Field(default_factory=PolicyModel)
    llm: LLMModel = Field(default_factory=LLMModel)


class GovernanceSummaryModel(BaseModel):
    phase: str
    action: str
    score: float
    alert: bool
    threshold: float
    finding_count: int
    rule_hits: List[str]


class GovernedCompleteResponse(BaseModel):
    blocked: bool
    blocked_phase: Optional[str] = None
    response_text: Optional[str] = None
    prompt_governance: GovernanceSummaryModel
    response_governance: Optional[GovernanceSummaryModel] = None


class EvaluateRequest(BaseModel):
    text: str
    phase: str = "evaluate"
    policy: PolicyModel = Field(default_factory=PolicyModel)


class EvaluateResponse(BaseModel):
    phase: str
    action: str
    score: float
    alert: bool
    threshold: float
    finding_count: int
    rule_hits: List[str]


def _to_policy(m: PolicyModel) -> RuntimePolicy:
    return RuntimePolicy(
        name=m.name,
        alert_threshold=m.alert_threshold,
        block_on_alert=m.block_on_alert,
    )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/evaluate", response_model=EvaluateResponse)
def evaluate(req: EvaluateRequest) -> EvaluateResponse:
    """Run analyze + score_report on arbitrary text (no LLM)."""
    pol = _to_policy(req.policy)
    engine = DecisionEngine(pol)
    d = engine.evaluate_text(phase=req.phase, text=req.text or "")
    s = d.to_summary()
    return EvaluateResponse(
        phase=s["phase"],
        action=s["action"],
        score=s["score"],
        alert=s["alert"],
        threshold=s["threshold"],
        finding_count=s["finding_count"],
        rule_hits=s["rule_hits"],
    )


@app.post("/v1/governed-complete", response_model=GovernedCompleteResponse)
def governed_complete(req: GovernedCompleteRequest) -> GovernedCompleteResponse:
    """
    Full path: pre-governance on prompt → LLM → post-governance on model output.

    - If ``policy.block_on_alert`` and score ≥ threshold → may block before or after LLM.
    - If ``llm.base_url`` is null, uses mock echo LLM (no network).
    """
    pol = _to_policy(req.policy)
    try:
        out = run_governed_chat(
            req.prompt,
            policy=pol,
            llm_base_url=req.llm.base_url,
            llm_api_key=req.llm.api_key,
            llm_model=req.llm.model,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"LLM HTTP error: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    def _sum(d: dict[str, Any]) -> GovernanceSummaryModel:
        return GovernanceSummaryModel(
            phase=d["phase"],
            action=d["action"],
            score=d["score"],
            alert=d["alert"],
            threshold=d["threshold"],
            finding_count=d["finding_count"],
            rule_hits=d["rule_hits"],
        )

    resp_gov = _sum(out.response_summary) if out.response_summary else None
    return GovernedCompleteResponse(
        blocked=out.blocked,
        blocked_phase=out.blocked_phase,
        response_text=out.response_text,
        prompt_governance=_sum(out.prompt_summary),
        response_governance=resp_gov,
    )

