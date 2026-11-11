import hmac
from collections.abc import Callable

from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException, ServiceUnavailableException
from litestar.handlers.base import BaseRouteHandler


def broker_guard(api_key: str | None) -> Callable[[ASGIConnection, BaseRouteHandler], None]:
    """Guard for broker routes: 503 when no key is configured, 401 on a missing/wrong X-API-Key."""

    def guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
        if not api_key:
            raise ServiceUnavailableException("broker API disabled")
        supplied = connection.headers.get("x-api-key", "")
        if not hmac.compare_digest(supplied.encode(), api_key.encode()):
            raise NotAuthorizedException("invalid API key")

    return guard
