"""Per-client rate limit on the public endpoints that create rows or spend LLM tokens."""

import re
from typing import Any

from litestar import Request
from litestar.middleware.base import DefineMiddleware
from litestar.middleware.rate_limit import RateLimitConfig, get_remote_address

from reic.shared.config import Settings

# POST /leads, POST /chat/sessions, POST /chat/sessions/{id}/messages
_THROTTLED = re.compile(r"^/(leads|chat/sessions(/[^/]+/messages)?)/?$")


async def _is_throttled(request: Request[Any, Any, Any]) -> bool:
    return request.method == "POST" and bool(_THROTTLED.match(request.url.path))


def build_rate_limit(settings: Settings) -> DefineMiddleware | None:
    if settings.rate_limit_per_minute <= 0:
        return None
    header = settings.client_ip_header

    def identifier(request: Request[Any, Any, Any]) -> str:
        # Only trust the header when the deploy says a proxy sets it (Fly-Client-IP on Fly.io).
        if header and (value := request.headers.get(header)):
            return value.strip()
        return get_remote_address(request)

    return RateLimitConfig(
        rate_limit=("minute", settings.rate_limit_per_minute),
        identifier_for_request=identifier,
        check_throttle_handler=_is_throttled,
    ).middleware
