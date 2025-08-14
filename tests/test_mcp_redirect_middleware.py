from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient



def create_app():
    """Creates a minimal Starlette application instrumented with the middleware."""
    app = Starlette()

    @app.route("/mcp/")
    async def mcp_endpoint(request):  # type: ignore
        # Return the path seen by the endpoint so we can assert the rewrite happened.
        return PlainTextResponse(request.url.path)

    # Additional route to test nested path behaviour.
    @app.route("/prefix/mcp/")
    async def prefixed_mcp_endpoint(request):  # type: ignore
        return PlainTextResponse(request.url.path)
    return app


def test_mcp_redirect_rewrites_to_trailing_slash():
    """Requests to /mcp should be transparently rewritten to /mcp/."""
    app = create_app()
    client = TestClient(app)

    # 1. Path with trailing slash should be rewritten.
    response = client.get("/mcp")
    assert response.status_code == 200
    assert response.text == "/mcp/"  # Endpoint received the rewritten path.

    # 2. Path with trailing slash should still work.
    response = client.get("/mcp/")
    assert response.status_code == 200
    assert response.text == "/mcp/"

    # 3. Different paths should not be affected by the middleware.
    response = client.get("/mcp-other")
    assert response.status_code == 404

    # 4. Nested path ending with /mcp should also be rewritten.
    response = client.get("/prefix/mcp")
    assert response.status_code == 200
    assert response.text == "/prefix/mcp/"
