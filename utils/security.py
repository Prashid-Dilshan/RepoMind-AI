import hmac

from fastapi import HTTPException, Request
from starlette.datastructures import MutableHeaders

from utils import config
from utils.ratelimit import RateLimiter

index_limiter = RateLimiter(config.RATE_LIMIT_INDEX_PER_HOUR, 3600)
query_limiter = RateLimiter(config.RATE_LIMIT_QUERY_PER_MINUTE, 60)


def require_access(request: Request):
    """If ACCESS_KEY is set, every protected route needs a matching X-Access-Key header."""
    if not config.ACCESS_KEY:
        return
    supplied = request.headers.get("x-access-key", "")
    if not hmac.compare_digest(supplied.encode(), config.ACCESS_KEY.encode()):
        raise HTTPException(status_code=401, detail="Enter the access key to use this app.")


def _limit(limiter, what):
    def dependency(request: Request):
        ip = request.client.host if request.client else "unknown"
        allowed, retry_after = limiter.hit(ip)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many {what}. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency


limit_indexing = _limit(index_limiter, "indexing requests")
limit_questions = _limit(query_limiter, "questions")


_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
_CSP = (
    "default-src 'self'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)
_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware:
    """Plain ASGI middleware, so streaming (SSE) responses are never buffered."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        add_csp = not scope.get("path", "").startswith(_DOC_PATHS)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
                if add_csp:
                    headers.setdefault("Content-Security-Policy", _CSP)
            await send(message)

        await self.app(scope, receive, send_with_headers)
