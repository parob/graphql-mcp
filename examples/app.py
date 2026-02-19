"""GraphQL MCP Examples - all examples served under one Cloud Run instance."""

from contextlib import asynccontextmanager
from contextlib import AsyncExitStack

from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import HTMLResponse

from hello_world import app as hello_world_app
from task_manager import app as task_manager_app
from remote_api import app as remote_api_app

# Registry of all examples: (path, app, description)
EXAMPLES = [
    ("/hello-world", hello_world_app, "Minimal hello world MCP server"),
    ("/task-manager", task_manager_app, "CRUD task manager with enums, mutations, and in-memory state"),
    ("/remote-api", remote_api_app, "Wraps a public GraphQL API (Countries) as MCP tools"),
]


async def index(request):
    """Landing page listing all available examples."""
    items = "\n".join(
        f'<li><strong><a href="{path}/">{path}</a></strong> — {desc}'
        f' (<a href="{path}/mcp">MCP</a>)</li>'
        for path, _, desc in EXAMPLES
    )
    html = f"""<!DOCTYPE html>
<html>
<head><title>GraphQL MCP Examples</title></head>
<body>
    <h1>GraphQL MCP Examples</h1>
    <p>Each example is a standalone GraphQL MCP server.
       Click to open GraphiQL or access the MCP endpoint.</p>
    <ul>
        {items}
    </ul>
    <p><a href="https://github.com/parob/graphql-mcp">GitHub</a> |
       <a href="https://graphql-mcp.parob.com/">Docs</a></p>
</body>
</html>"""
    return HTMLResponse(html)


@asynccontextmanager
async def lifespan(app):
    """Enter each example sub-app's lifespan (required for MCP session management)."""
    async with AsyncExitStack() as stack:
        for _, example_app, _ in EXAMPLES:
            if hasattr(example_app, "lifespan"):
                await stack.enter_async_context(example_app.lifespan(app))
        yield


routes = [Route("/", index, methods=["GET"])]
routes += [Mount(path, app=example_app) for path, example_app, _ in EXAMPLES]

app = Starlette(routes=routes, lifespan=lifespan)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
