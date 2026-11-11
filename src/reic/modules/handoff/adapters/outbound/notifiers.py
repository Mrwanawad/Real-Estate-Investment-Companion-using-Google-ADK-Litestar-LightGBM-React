import hashlib
import hmac
import json
import logging
import time

import httpx

from reic.modules.handoff.domain.models import Lead

logger = logging.getLogger(__name__)


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """X-REIC-Signature value: sha256=<hex hmac of "<X-REIC-Timestamp>." + raw body>.

    Binding the timestamp lets receivers reject stale deliveries (replay protection).
    """
    message = timestamp.encode() + b"." + body
    return "sha256=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


class NullNotifier:
    async def notify(self, lead: Lead) -> None:
        return None


class HmacWebhookNotifier:
    """POSTs the lead as JSON, signed so the receiver can verify origin. Never raises."""

    def __init__(
        self,
        url: str,
        secret: str,
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._url = url
        self._secret = secret
        self._client = client
        self._timeout = timeout

    async def notify(self, lead: Lead) -> None:
        body = json.dumps(lead.to_dict(), separators=(",", ":"), sort_keys=True).encode()
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-REIC-Signature": sign(self._secret, timestamp, body),
            "X-REIC-Timestamp": timestamp,
        }
        try:
            if self._client is not None:
                response = await self._client.post(
                    self._url, content=body, headers=headers, timeout=self._timeout
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(self._url, content=body, headers=headers)
            response.raise_for_status()
        except Exception:
            logger.warning("lead webhook failed for lead %s", lead.id, exc_info=True)
