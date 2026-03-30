"""Signal channel adapter via signal-cli REST API.

Requires a running signal-cli-rest-api instance (Docker):
  docker run -d --name signal-api -p 8080:8080 \
    -v ./signal-data:/home/.local/share/signal-cli \
    bbernhard/signal-cli-rest-api

Register your number first:
  curl -X POST 'http://localhost:8080/v1/register/+1234567890'
  curl -X POST 'http://localhost:8080/v1/register/+1234567890/verify/CODE'
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from quickdraw.channels.base import ChannelAdapter

logger = logging.getLogger(__name__)

POLL_INTERVAL = 1.0
SIGNAL_MAX_LENGTH = 4096
HTTP_RECEIVE_TIMEOUT_SECONDS = 30


def _chunk_message(text: str, limit: int = SIGNAL_MAX_LENGTH) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


class SignalChannel(ChannelAdapter):
    """Signal adapter — listens to signal-cli REST API for incoming messages."""

    def __init__(self, channel_id: str, settings: dict[str, Any]) -> None:
        super().__init__(channel_id, settings)
        self._api_url = settings.get("api_url", "http://localhost:8080").rstrip("/")
        self._number = settings.get("number", "")
        self._session_scope = settings.get("session_scope", "per-user")
        self._poll_interval = settings.get("poll_interval", POLL_INTERVAL)
        self._running = False
        self._task: asyncio.Task | None = None
        self._http: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        if not self._number:
            raise ValueError(
                "Signal number not configured. Set 'number' in signal channel config "
                "(e.g. '+1234567890')."
            )
        self._http = aiohttp.ClientSession()

        try:
            async with self._http.get(f"{self._api_url}/v1/about") as resp:
                if resp.status != 200:
                    raise ConnectionError(f"signal-cli REST API not reachable at {self._api_url}")
                about = await resp.json()
                logger.info("Signal API connected: %s", about)
        except aiohttp.ClientError as e:
            raise ConnectionError(
                f"Cannot connect to signal-cli REST API at {self._api_url}. "
                f"Is the Docker container running? Error: {e}"
            ) from e

        self._running = True
        self._task = asyncio.create_task(self._ws_loop())
        logger.info("Signal channel started (number: %s)", self._number)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        if self._http:
            await self._http.close()
        logger.info("Signal channel stopped")

    def _ws_url(self) -> str:
        """Convert REST base URL to websocket base URL."""
        if self._api_url.startswith("https://"):
            return "wss://" + self._api_url[len("https://") :]
        if self._api_url.startswith("http://"):
            return "ws://" + self._api_url[len("http://") :]
        # Fallback: assume ws://
        return "ws://" + self._api_url

    async def _ws_loop(self) -> None:
        """Keep a websocket subscription open for incoming messages.

        The REST API documents `/v1/receive/{number}` as a websocket. In some setups it may not
        accept websocket upgrades; if we see that, fall back to HTTP polling.
        """
        if not self._http:
            return

        while self._running:
            try:
                ws_endpoint = f"{self._ws_url()}/v1/receive/{self._number}"
                async with self._http.ws_connect(ws_endpoint) as ws:
                    logger.info("Signal websocket connected")
                    while self._running:
                        msg = await ws.receive()
                        if msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.CLOSE,
                        ):
                            break
                        if msg.type == aiohttp.WSMsgType.ERROR:
                            break
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue

                        if not msg.data:
                            continue

                        # Expect JSON payloads.
                        try:
                            payload = json.loads(msg.data)
                        except json.JSONDecodeError:
                            logger.debug("Signal ws non-JSON payload: %r", msg.data[:200])
                            continue

                        if isinstance(payload, list):
                            for item in payload:
                                if isinstance(item, dict):
                                    await self._process_message(item)
                        elif isinstance(payload, dict):
                            await self._process_message(payload)

            except asyncio.CancelledError:
                return
            except aiohttp.WSServerHandshakeError as e:
                # If the server doesn't support websocket upgrades (e.g. returns 400),
                # fall back to HTTP receive polling.
                logger.warning("Signal websocket handshake failed (%s). Falling back to HTTP receive.", e)
                await self._http_poll_loop()
                # After polling loop returns, attempt websocket reconnect again.
            except Exception as e:
                logger.error("Signal websocket error: %s", e)

            # Backoff before reconnecting.
            await asyncio.sleep(self._poll_interval)

    async def _http_poll_loop(self) -> None:
        """Fallback HTTP polling receive loop."""
        if not self._http:
            return

        while self._running:
            try:
                url = f"{self._api_url}/v1/receive/{self._number}"
                async with self._http.get(url, timeout=HTTP_RECEIVE_TIMEOUT_SECONDS) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.warning("Signal receive returned %d: %s", resp.status, body[:160])
                    else:
                        # When there are no messages, some deployments return text/plain.
                        payload = await resp.json(content_type=None)
                        if isinstance(payload, list):
                            for item in payload:
                                if isinstance(item, dict):
                                    await self._process_message(item)
                        elif isinstance(payload, dict):
                            await self._process_message(payload)

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error("Signal HTTP receive error: %s", e)

            await asyncio.sleep(self._poll_interval)

    async def _process_message(self, msg: dict) -> None:
        """Process a single incoming Signal message."""
        # signal-cli payloads are usually shaped like:
        # { "envelope": { "dataMessage": { ... }, "sourceNumber": "...", ... } }
        # but in practice we should be defensive because the REST API wrapper
        # may vary payload structure and mime-types.
        envelope = msg.get("envelope") or msg
        data_message = envelope.get("dataMessage") or {}

        text = data_message.get("message") or ""
        if not text:
            return

        source_number = (
            envelope.get("sourceNumber")
            or msg.get("sourceNumber")
            or data_message.get("sourceNumber")
            or data_message.get("sender")
            or ""
        )
        source_name = envelope.get("sourceName") or msg.get("sourceName") or source_number

        group_info = data_message.get("groupInfo") or None

        session_key = self._make_session_key(source_number, group_info)

        if group_info:
            attributed_text = f"[{source_name}] {text}"
        else:
            attributed_text = text

        async def reply_fn(response: str) -> None:
            # If we can't determine the sender number, skip replying instead
            # of sending to an empty phone string (which the API rejects).
            if not source_number and not group_info:
                logger.warning("Skipping Signal reply: missing sender phone number")
                return
            await self._send_message(response, source_number, group_info)

        logger.info("Signal message from %s: %s", source_name, text[:80])

        try:
            await self._dispatch(session_key, attributed_text, reply_fn)
        except Exception as e:
            logger.error("Error handling Signal message: %s", e)
            await self._send_message(f"Error: {e}", source_number, group_info)

    async def _send_message(
        self,
        text: str,
        recipient: str,
        group_info: dict | None,
    ) -> None:
        """Send a message back via Signal."""
        if not self._http:
            return

        for chunk in _chunk_message(text):
            payload: dict[str, Any] = {
                "message": chunk,
                "number": self._number,
                "text_mode": "normal",
            }

            if group_info:
                group_id = group_info.get("groupId", "")
                payload["recipients"] = [group_id] if group_id else []
            else:
                payload["recipients"] = [recipient] if recipient else []

            # Prevent API calls like recipients=[""].
            if not payload["recipients"]:
                logger.warning("Signal send skipped: no valid recipients (recipient=%r)", recipient)
                return

            async with self._http.post(
                f"{self._api_url}/v2/send", json=payload,
            ) as resp:
                if resp.status not in (200, 201):
                    body = await resp.text()
                    logger.error("Signal send failed (%d): %s", resp.status, body[:200])

    def _make_session_key(self, source_number: str, group_info: dict | None) -> str:
        if group_info:
            group_id = group_info.get("groupId", "unknown")
            if self._session_scope == "per-channel-peer":
                return f"signal:{group_id}:{source_number}"
            return f"signal:{group_id}"
        return f"signal:{source_number}"

    async def _send_typing(self, recipient: str) -> None:
        """Show typing indicator."""
        if not self._http:
            return
        payload = {"recipient": recipient}
        try:
            async with self._http.put(
                f"{self._api_url}/v1/typing-indicator/{self._number}", json=payload,
            ):
                pass
        except Exception:
            pass

    async def _send_receipt(self, source_number: str, timestamp: int) -> None:
        """Send a read receipt."""
        if not self._http:
            return
        payload = {
            "receipt_type": "read",
            "recipient": source_number,
            "timestamps": [timestamp],
        }
        try:
            async with self._http.post(
                f"{self._api_url}/v1/receipts/{self._number}", json=payload,
            ):
                pass
        except Exception:
            pass
