from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from quickdraw.llm.base import LLMClient
from quickdraw.llm.types import LLMResponse

logger = logging.getLogger(__name__)


@dataclass
class ProviderSpec:
    provider: str
    model: str
    max_tokens: int


class LLMRouter(LLMClient):
    """Try providers in order; fall back on error."""

    def __init__(self, providers: list[tuple[ProviderSpec, LLMClient]]) -> None:
        if not providers:
            raise ValueError("LLMRouter requires at least one provider")
        self._providers = providers

    def name(self) -> str:
        return "router"

    def supports_tools(self) -> bool:
        # Router supports tools if the first provider supports tools; the loop will
        # still pass tools, and non-tool providers will ignore them (or we drop).
        return self._providers[0][1].supports_tools()

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str,
        model: str,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
    ) -> LLMResponse:
        last_err: str | None = None
        for idx, (spec, client) in enumerate(self._providers):
            # Allow per-agent overrides to affect the first provider.
            use_model = model if idx == 0 and model else spec.model
            use_max_tokens = max_tokens if idx == 0 and max_tokens else spec.max_tokens
            use_tools = tools if (tools and client.supports_tools()) else None
            logger.info(
                "LLM try: provider=%s model=%s (tools=%s)",
                spec.provider,
                use_model,
                bool(use_tools),
            )
            resp = client.complete(
                messages=messages,
                system=system,
                model=use_model,
                max_tokens=use_max_tokens,
                tools=use_tools,
            )
            if resp.stop_reason != "error":
                logger.info("LLM success: provider=%s", spec.provider)
                return resp
            last_err = resp.error or "Unknown error"
            logger.warning("LLM failed: provider=%s err=%s", spec.provider, last_err)
        return LLMResponse(stop_reason="error", content=[], error=last_err)

