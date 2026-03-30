"""HTTP API channel adapter using aiohttp."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

from aiohttp import web

from quickdraw.channels.base import ChannelAdapter

logger = logging.getLogger(__name__)


def _extract_text(content: Any) -> str:
    """Pull plain text from a message content field (str or block list)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _extract_tool_calls(content: Any) -> list[dict]:
    """Pull tool_use blocks from an assistant message."""
    if not isinstance(content, list):
        return []
    calls = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            calls.append({
                "id": block.get("id", ""),
                "name": block.get("name", ""),
                "input": block.get("input", {}),
            })
    return calls


def _extract_tool_results(content: Any) -> list[dict]:
    """Pull tool_result blocks from a user message (after tool calls)."""
    if not isinstance(content, list):
        return []
    results = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            result_content = block.get("content", "")
            if isinstance(result_content, list):
                result_content = _extract_text(result_content)
            results.append({
                "tool_use_id": block.get("tool_use_id", ""),
                "content": str(result_content)[:2000],
            })
    return results


def _parse_session_messages(lines: list[str]) -> list[dict]:
    """Parse JSONL session lines into structured UI-friendly messages."""
    messages: list[dict] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue

        role = raw.get("role", "")
        content = raw.get("content", "")

        if role == "user":
            tool_results = _extract_tool_results(content)
            if tool_results:
                messages.append({
                    "type": "tool_results",
                    "results": tool_results,
                })
            else:
                text = _extract_text(content)
                if text:
                    messages.append({
                        "type": "user",
                        "content": text,
                    })

        elif role == "assistant":
            text = _extract_text(content)
            tool_calls = _extract_tool_calls(content)
            if text or tool_calls:
                msg: dict = {"type": "assistant"}
                if text:
                    msg["content"] = text
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                messages.append(msg)

    return messages


class HttpApiChannel(ChannelAdapter):
    """HTTP API adapter exposing POST /chat for programmatic access."""

    def __init__(self, channel_id: str, settings: dict[str, Any]) -> None:
        super().__init__(channel_id, settings)
        self._port = settings.get("port", 5000)
        self._host = settings.get("host", "127.0.0.1")
        self._sessions_dir = Path(settings.get("_sessions_dir", ""))
        self._progress_dir = Path(settings.get("_progress_dir", ""))

        self._app = web.Application()
        self._app.router.add_post("/chat", self._handle_chat)
        self._app.router.add_post("/run-turn", self._handle_run_turn)
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/progress", self._handle_progress)
        self._app.router.add_get("/sessions", self._handle_list_sessions)
        self._app.router.add_get("/sessions/{key}", self._handle_get_session)
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        logger.info("HTTP API listening on http://%s:%d", self._host, self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
        logger.info("HTTP API stopped")

    async def _handle_chat(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        user_id = data.get("user_id")
        message = data.get("message")

        if not user_id or not message:
            return web.json_response(
                {"error": "Both 'user_id' and 'message' are required"},
                status=400,
            )

        session_key = f"http:{user_id}"

        response_event = asyncio.Event()
        response_text = ""

        async def reply_fn(text: str) -> None:
            nonlocal response_text
            response_text = text
            response_event.set()

        await self._dispatch(session_key, message, reply_fn)
        await response_event.wait()

        return web.json_response({"response": response_text})

    async def _handle_run_turn(self, request: web.Request) -> web.Response:
        if self._on_run_turn is None:
            return web.json_response({"error": "run-turn not configured"}, status=503)

        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        agent_id = data.get("agent_id", "")
        session_key = data.get("session_key", "")
        user_text = data.get("user_text", "")

        if not agent_id or not session_key or not user_text:
            return web.json_response(
                {"error": "agent_id, session_key, and user_text are required"},
                status=400,
            )

        model = data.get("model", "claude-sonnet-4-5-20250929")
        max_tokens = int(data.get("max_tokens", 4096))

        try:
            result = await self._on_run_turn(agent_id, session_key, user_text, model, max_tokens)
            return web.json_response(result)
        except Exception as e:
            logger.exception("run-turn failed for agent=%s", agent_id)
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    async def _handle_progress(self, request: web.Request) -> web.Response:
        key = request.query.get("key", "")
        since = int(request.query.get("since", "0"))

        if not key or not self._progress_dir:
            return web.json_response({"events": []})

        safe_key = key.replace(":", "_").replace("/", "_")
        path = self._progress_dir / f"{safe_key}.jsonl"

        if not path.exists():
            return web.json_response({"events": []})

        events: list[dict] = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        return web.json_response({"events": events[since:]})

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def _group_sessions(self) -> list[dict]:
        """Group step sessions under their parent chat key.

        Files like:
          chat_abc_lead-qualification_step-0.jsonl
          chat_abc_lead-qualification_step-1.jsonl
        get grouped under parent_key "chat:abc" with workflow info.
        """
        if not self._sessions_dir or not self._sessions_dir.exists():
            return []

        groups: dict[str, dict] = {}

        for fpath in self._sessions_dir.glob("*.jsonl"):
            raw_key = fpath.stem  # e.g. chat_abc_lead-qualification_step-0
            lines = fpath.read_text().strip().splitlines()
            if not lines:
                continue

            parent_key = raw_key
            workflow_name = ""
            step_index = -1

            # Detect step sessions: {parent}_{workflow}_step-{N}
            step_match = re.match(r"^(.+?)_([a-zA-Z][\w-]*)_step-(\d+)(?:_retry-\d+)?$", raw_key)
            if step_match:
                parent_key = step_match.group(1)
                workflow_name = step_match.group(2)
                step_index = int(step_match.group(3))

            display_key = parent_key.replace("_", ":")

            if display_key not in groups:
                groups[display_key] = {
                    "key": display_key,
                    "total_messages": 0,
                    "first_user_message": "",
                    "workflow": workflow_name,
                    "step_count": 0,
                    "step_files": [],
                    "size_bytes": 0,
                }

            g = groups[display_key]
            g["total_messages"] += len(lines)
            g["size_bytes"] += fpath.stat().st_size
            if step_index >= 0:
                g["step_count"] = max(g["step_count"], step_index + 1)
                g["step_files"].append({"step": step_index, "file": fpath.name})
            if workflow_name and not g["workflow"]:
                g["workflow"] = workflow_name

            # Find first user text message for preview
            if not g["first_user_message"]:
                for line in lines:
                    try:
                        msg = json.loads(line)
                        if msg.get("role") == "user":
                            text = _extract_text(msg.get("content", ""))
                            if text and not text.startswith("[{"):
                                g["first_user_message"] = text[:120]
                                break
                    except json.JSONDecodeError:
                        continue

        result = []
        for g in groups.values():
            g.pop("step_files", None)
            result.append(g)

        result.sort(key=lambda x: x["size_bytes"], reverse=True)
        return result

    async def _handle_list_sessions(self, request: web.Request) -> web.Response:
        prefix = request.query.get("prefix", "")
        sessions = self._group_sessions()
        if prefix:
            sessions = [s for s in sessions if s["key"].startswith(prefix)]
        return web.json_response({"sessions": sessions[:50]})

    async def _handle_get_session(self, request: web.Request) -> web.Response:
        key = request.match_info["key"]

        if not self._sessions_dir:
            return web.json_response({"error": "sessions not configured"}, status=503)

        safe_key = key.replace(":", "_").replace("/", "_")

        # Collect all files for this session (main + step files)
        all_files: list[tuple[int, Path]] = []

        main_path = self._sessions_dir / f"{safe_key}.jsonl"
        if main_path.exists():
            all_files.append((-1, main_path))

        for fpath in sorted(self._sessions_dir.glob(f"{safe_key}_*.jsonl")):
            step_match = re.search(r"_step-(\d+)", fpath.stem)
            step_idx = int(step_match.group(1)) if step_match else 99
            all_files.append((step_idx, fpath))

        all_files.sort(key=lambda x: x[0])

        all_messages: list[dict] = []
        for step_idx, fpath in all_files:
            lines = fpath.read_text().splitlines()
            parsed = _parse_session_messages(lines)

            if step_idx >= 0 and parsed:
                agent_match = re.search(r"_([a-zA-Z][\w-]*)_step-", fpath.stem)
                wf_name = agent_match.group(1) if agent_match else ""
                all_messages.append({
                    "type": "step_header",
                    "step": step_idx,
                    "workflow": wf_name,
                })

            all_messages.extend(parsed)

        return web.json_response({"key": key, "messages": all_messages})
