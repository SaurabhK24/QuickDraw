"""Context window compaction.

When a conversation exceeds the token budget, older messages are summarized
by the LLM and replaced with a condensed summary, preserving key facts.
"""

from __future__ import annotations

import asyncio
import json
import logging

from quickdraw.core.session import SessionManager
from quickdraw.llm.base import LLMClient
from quickdraw.llm.types import extract_text

logger = logging.getLogger(__name__)

TOKEN_THRESHOLD = 100_000
SUMMARY_MAX_TOKENS = 2000

COMPACTION_PROMPT = (
    "Summarize this conversation concisely. Preserve:\n"
    "- Key facts about the user (name, preferences, background)\n"
    "- Important decisions made\n"
    "- Open tasks or TODOs\n"
    "- Any tool results or findings worth keeping\n\n"
)


def _estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimate: ~4 chars per token."""
    return sum(len(json.dumps(m)) for m in messages) // 4


class Compactor:
    """Compacts session history when it approaches the context window limit."""

    def __init__(
        self,
        sessions: SessionManager,
        llm: LLMClient,
        model: str = "claude-sonnet-4-5-20250929",
        threshold: int = TOKEN_THRESHOLD,
    ) -> None:
        self._sessions = sessions
        self._llm = llm
        self._model = model
        self._threshold = threshold

    async def compact(
        self, session_key: str, messages: list[dict],
    ) -> list[dict]:
        """Compact messages if they exceed the token threshold.

        Returns the (possibly compacted) message list.
        """
        estimated = _estimate_tokens(messages)
        if estimated < self._threshold:
            return messages

        logger.info(
            "Compacting session %s (~%dk tokens)", session_key, estimated // 1000,
        )

        split = len(messages) // 2
        old_messages = messages[:split]
        recent_messages = messages[split:]

        try:
            summary_response = await asyncio.to_thread(
                lambda: self._llm.complete(
                    model=self._model,
                    max_tokens=SUMMARY_MAX_TOKENS,
                    system="",
                    tools=None,
                    messages=[
                        {
                            "role": "user",
                            "content": COMPACTION_PROMPT + json.dumps(old_messages, indent=2),
                        }
                    ],
                )
            )

            if summary_response.stop_reason == "error":
                raise RuntimeError(summary_response.error or "compaction LLM error")

            summary_text = extract_text(summary_response.content)

            compacted = [
                {"role": "user", "content": f"[Previous conversation summary]\n{summary_text}"},
                {"role": "assistant", "content": "Understood. I have the context from our previous conversation."},
                *recent_messages,
            ]

            self._sessions.save(session_key, compacted)
            logger.info("Compacted %d messages -> %d", len(messages), len(compacted))
            return compacted

        except Exception as e:
            logger.error("Compaction failed: %s", e)
            return messages
