from __future__ import annotations

from typing import Any


def messages_to_plain_text(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert QuickDraw/Anthropic-like messages into plain role/content pairs.

    This is used for providers where we haven't implemented tool-call parity yet.
    Tool blocks are dropped; tool results are summarized into text.
    """

    out: list[dict[str, str]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            # Content blocks
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif isinstance(block, dict) and block.get("type") == "tool_result":
                    parts.append(f"[tool_result]\n{block.get('content','')}")
            text = "\n".join(p for p in parts if p)
        else:
            text = str(content) if content is not None else ""

        if not text:
            continue

        if role not in ("user", "assistant"):
            continue

        out.append({"role": role, "content": text})

    return out

