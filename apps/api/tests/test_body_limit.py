from middleware.body_limit import BodySizeLimitMiddleware
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient


def _make_app() -> Starlette:
    def homepage(request):
        return PlainTextResponse("OK")

    return Starlette(
        routes=[Route("/", endpoint=homepage, methods=["POST"])],
        middleware=[Middleware(BodySizeLimitMiddleware, max_content_size=100)],
    )


def test_body_limit_middleware_allow_small_content():
    client = TestClient(_make_app())
    response = client.post("/", content="x" * 50)
    assert response.status_code == 200
    assert response.text == "OK"


def test_body_limit_middleware_block_large_content():
    client = TestClient(_make_app())
    response = client.post("/", content="x" * 150)
    assert response.status_code == 413
    assert response.text == "Content too large"


def test_body_limit_middleware_without_content_length_header():
    """Requests without Content-Length remain accepted by the current middleware contract."""
    client = TestClient(_make_app())

    # A streaming iterator makes httpx use transfer-encoding: chunked instead of
    # synthesizing a Content-Length header, exercising the middleware's fallback.
    response = client.post("/", content=iter([b"x" * 50]))

    assert response.status_code == 200
    assert response.text == "OK"
