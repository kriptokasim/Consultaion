from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_content_size: int):
        self.app = app
        self.max_content_size = max_content_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # 1. Fast check using Content-Length
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_content_size:
                    response = Response("Content too large", status_code=413)
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass

        # 2. Track streamed bytes to catch chunked encoding bypasses
        total_size = 0
        response_started = False

        async def wrapped_send(message: dict) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        async def wrapped_receive() -> dict:
            nonlocal total_size
            message = await receive()
            if message["type"] == "http.request":
                total_size += len(message.get("body", b""))
                if total_size > self.max_content_size:
                    raise ValueError("Content too large")
            return message

        try:
            await self.app(scope, wrapped_receive, wrapped_send)
        except ValueError as exc:
            if str(exc) == "Content too large":
                if not response_started:
                    response = Response("Content too large", status_code=413)
                    await response(scope, receive, send)
            else:
                raise
