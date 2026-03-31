from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v


@dataclass(frozen=True)
class GovernanceConfig:
    """
    SDK / runtime wiring. Override via environment or pass explicitly to clients.

    Environment (optional):
      GOVERNANCE_CONTROL_PLANE_URL — base URL for run reporting (no trailing slash required)
      GOVERNANCE_API_KEY — sent as Bearer if set
      GOVERNANCE_DEFAULT_POLICY — default policy name for decorators
      GOVERNANCE_CLIENT — ``local`` | ``http`` (hint for which client factory to use)
    """

    control_plane_url: str | None = None
    api_key: str | None = None
    default_policy: str = "default"
    client_kind: str = "local"  # local | http
    extra: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> GovernanceConfig:
        return cls(
            control_plane_url=_env("GOVERNANCE_CONTROL_PLANE_URL"),
            api_key=_env("GOVERNANCE_API_KEY"),
            default_policy=_env("GOVERNANCE_DEFAULT_POLICY", "default") or "default",
            client_kind=_env("GOVERNANCE_CLIENT", "local") or "local",
        )


def load_config(
    *,
    env: bool = True,
    overrides: Mapping[str, Any] | None = None,
) -> GovernanceConfig:
    """
    Build config: start from env (if ``env``), then apply ``overrides`` keys that exist
    on :class:`GovernanceConfig` (``control_plane_url``, ``api_key``, ``default_policy``, ``client_kind``, ``extra``).
    """
    base = GovernanceConfig.from_env() if env else GovernanceConfig()
    if not overrides:
        return base
    data = {
        "control_plane_url": base.control_plane_url,
        "api_key": base.api_key,
        "default_policy": base.default_policy,
        "client_kind": base.client_kind,
        "extra": dict(base.extra),
    }
    for k, v in overrides.items():
        if k == "extra" and isinstance(v, Mapping):
            data["extra"] = {**data["extra"], **dict(v)}
        elif k in data and k != "extra":
            data[k] = v  # type: ignore[assignment]
    return GovernanceConfig(
        control_plane_url=data["control_plane_url"],
        api_key=data["api_key"],
        default_policy=data["default_policy"],
        client_kind=data["client_kind"],
        extra=data["extra"],
    )
