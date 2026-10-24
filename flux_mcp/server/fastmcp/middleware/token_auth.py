import hmac
import re
from typing import Callable

from fastapi import HTTPException, Request, status
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware


class TokenAuthMiddleware(Middleware):
    """
    Middleware for basic auth token.
    Check for a basic token match. This is for testing only.
    """

    def __init__(self, static_token: str, header_name: str = "authorization"):
        """
        Set a basic authorization header to validate requests.
        """
        self.static_token = static_token
        self.header_name = header_name

    @staticmethod
    def parse_token(value: str) -> str:
        """
        Return the token from an Authorization header value.
        """
        value = value.strip()
        scheme, _, rest = value.partition(" ")
        if scheme.lower() == "bearer" and rest:
            return rest.strip()
        # Also accept "Bearer:<token>", "Basic:<token>", or the bare token.
        return re.sub(r"^(bearer|basic):", "", value, flags=re.IGNORECASE)

    async def __call__(self, request: Request, call_next: Callable):
        """
        Check the header (auth) on a request.
        """
        # get_http_headers drops credential headers unless asked for them.
        headers = get_http_headers(include={self.header_name})
        auth_header = headers.get(self.header_name)

        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication header missing",
            )

        token = self.parse_token(auth_header)
        if not hmac.compare_digest(token.encode(), self.static_token.encode()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid authentication token",
            )

        response = await call_next(request)
        return response
