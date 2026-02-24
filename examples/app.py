"""GraphQL MCP Examples - all examples served under one Cloud Run instance."""

import html
from contextlib import asynccontextmanager
from contextlib import AsyncExitStack
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import HTMLResponse

from hello_world import app as hello_world_app
from task_manager import app as task_manager_app
from nested_api import app as nested_api_app
from remote_api import app as remote_api_app

EXAMPLES_DIR = Path(__file__).parent

# Registry of all examples: (path, app, title, description, source_file)
EXAMPLES = [
    ("/hello-world", hello_world_app, "Hello World",
     "Minimal MCP server with a single query — the simplest possible starting point.",
     "hello_world.py"),
    ("/task-manager", task_manager_app, "Task Manager",
     "Full CRUD with enums, mutations, UUID/datetime scalars, and in-memory state.",
     "task_manager.py"),
    ("/nested-api", nested_api_app, "Nested API",
     "Nested tools, @mcpHidden directive, Pydantic models, and async resolvers.",
     "nested_api.py"),
    ("/remote-api", remote_api_app, "Remote API",
     "Wraps a public GraphQL API (Countries) as MCP tools via from_remote_url().",
     "remote_api.py"),
]


async def index(request):
    """Landing page listing all available examples."""
    cards_parts = []
    dialogs_parts = []
    for path, _, title, desc, source_file in EXAMPLES:
        source = html.escape((EXAMPLES_DIR / source_file).read_text())
        dialog_id = path.strip("/")
        cards_parts.append(f'''<div class="card">
            <h2>{title}</h2>
            <p>{desc}</p>
            <div class="card-links">
                <a class="btn btn-primary" href="{path}/">GraphiQL</a>
                <a class="btn btn-secondary" href="{path}/mcp">MCP</a>
                <button class="btn btn-source" onclick="openSource('{dialog_id}')">Source</button>
            </div>
        </div>''')
        dialogs_parts.append(f'''<dialog id="dialog-{dialog_id}" class="source-dialog" onclick="if(event.target===this)this.close()">
            <div class="dialog-inner">
                <div class="dialog-header">
                    <h2>{title}</h2>
                    <button class="dialog-close" onclick="this.closest('dialog').close()">&times;</button>
                </div>
                <p class="dialog-desc">{desc}</p>
                <div class="card-links">
                    <a class="btn btn-primary" href="{path}/">GraphiQL</a>
                    <a class="btn btn-secondary" href="{path}/mcp">MCP</a>
                </div>
                <div class="dialog-source">
                    <div class="dialog-source-label">{source_file}</div>
                    <pre><code class="language-python">{source}</code></pre>
                </div>
            </div>
        </dialog>''')
    cards = "\n".join(cards_parts)
    dialogs = "\n".join(dialogs_parts)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>GraphQL MCP Examples</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/styles/github.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/highlight.min.js"></script>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f8fafc;
            color: #1e293b;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        header {{
            background: #0f172a;
            color: #f1f5f9;
            padding: 0 2rem;
        }}
        .header-inner {{
            max-width: 960px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 64px;
        }}
        .header-inner h1 {{
            font-size: 1.25rem;
            font-weight: 600;
            letter-spacing: -0.01em;
        }}
        .header-inner h1 span {{ color: #60a5fa; }}
        nav a {{
            color: #94a3b8;
            text-decoration: none;
            font-size: 0.875rem;
            margin-left: 1.5rem;
            transition: color 0.15s;
        }}
        nav a:hover {{ color: #f1f5f9; }}
        main {{
            max-width: 960px;
            margin: 0 auto;
            padding: 3rem 2rem;
            width: 100%;
            flex: 1;
        }}
        .subtitle {{
            color: #64748b;
            font-size: 1.05rem;
            margin-bottom: 2rem;
            line-height: 1.6;
        }}
        .card-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 1.25rem;
        }}
        .card {{
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            transition: box-shadow 0.15s, border-color 0.15s;
        }}
        .card:hover {{
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
            border-color: #cbd5e1;
        }}
        .card h2 {{
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }}
        .card p {{
            color: #64748b;
            font-size: 0.9rem;
            line-height: 1.5;
            flex: 1;
            margin-bottom: 1.25rem;
        }}
        .card-links {{
            display: flex;
            gap: 0.5rem;
        }}
        .btn {{
            display: inline-block;
            padding: 0.45rem 1rem;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 500;
            text-decoration: none;
            transition: background 0.15s, color 0.15s;
            cursor: pointer;
            border: none;
        }}
        .btn-primary {{
            background: #3b82f6;
            color: #fff;
        }}
        .btn-primary:hover {{ background: #2563eb; }}
        .btn-secondary {{
            background: #f1f5f9;
            color: #475569;
            border: 1px solid #e2e8f0;
        }}
        .btn-secondary:hover {{ background: #e2e8f0; }}
        .btn-source {{
            background: #f1f5f9;
            color: #475569;
            border: 1px solid #e2e8f0;
            font-family: 'SF Mono', 'Fira Code', Menlo, Consolas, monospace;
        }}
        .btn-source:hover {{ background: #e2e8f0; }}
        footer {{
            text-align: center;
            padding: 2rem;
            color: #94a3b8;
            font-size: 0.8rem;
        }}
        footer a {{ color: #64748b; text-decoration: none; }}
        footer a:hover {{ color: #3b82f6; }}

        /* Dialog */
        .source-dialog {{
            border: none;
            border-radius: 16px;
            padding: 0;
            width: min(92vw, 860px);
            max-height: 88vh;
            margin: auto;
            box-shadow: 0 24px 48px rgba(0,0,0,0.15);
            overflow: hidden;
        }}
        .source-dialog::backdrop {{
            background: rgba(0,0,0,0.4);
        }}
        .dialog-inner {{
            padding: 1.5rem;
            overflow-y: auto;
            max-height: 85vh;
        }}
        .dialog-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.5rem;
        }}
        .dialog-header h2 {{
            font-size: 1.25rem;
            font-weight: 600;
        }}
        .dialog-close {{
            background: none;
            border: none;
            font-size: 1.5rem;
            color: #94a3b8;
            cursor: pointer;
            padding: 0.25rem 0.5rem;
            border-radius: 6px;
            line-height: 1;
        }}
        .dialog-close:hover {{
            background: #f1f5f9;
            color: #1e293b;
        }}
        .dialog-desc {{
            color: #64748b;
            font-size: 0.9rem;
            line-height: 1.5;
            margin-bottom: 1rem;
        }}
        .dialog-source {{
            margin-top: 1.25rem;
            border-top: 1px solid #e2e8f0;
            padding-top: 1rem;
        }}
        .dialog-source-label {{
            font-size: 0.8rem;
            font-weight: 500;
            color: #64748b;
            font-family: 'SF Mono', 'Fira Code', Menlo, Consolas, monospace;
            margin-bottom: 0.5rem;
        }}
        .dialog-source pre {{
            border-radius: 8px;
            font-size: 0.8rem;
            line-height: 1.5;
            overflow: auto;
            max-height: 50vh;
        }}
    </style>
</head>
<body>
    <header>
        <div class="header-inner">
            <h1>GraphQL <span>MCP</span> Examples</h1>
            <nav>
                <a href="https://graphql-mcp.parob.com/">Docs</a>
                <a href="https://github.com/parob/graphql-mcp">GitHub</a>
            </nav>
        </div>
    </header>
    <main>
        <p class="subtitle">
            Each example is a standalone GraphQL MCP server.
            Open GraphiQL to explore the schema interactively, or connect
            to the MCP endpoint from any MCP-compatible client.
        </p>
        <div class="card-grid">
            {cards}
        </div>
        {dialogs}
    </main>
    <footer>
        <a href="https://pypi.org/project/graphql-mcp/">PyPI</a>
        &nbsp;&middot;&nbsp;
        <a href="https://graphql-mcp.parob.com/">Documentation</a>
        &nbsp;&middot;&nbsp;
        <a href="https://github.com/parob/graphql-mcp">Source</a>
    </footer>
    <script>
        hljs.highlightAll();
        function openSource(id) {{
            var d = document.getElementById('dialog-' + id);
            d.showModal();
        }}
    </script>
</body>
</html>"""
    return HTMLResponse(page)


@asynccontextmanager
async def lifespan(app):
    """Enter each example sub-app's lifespan (required for MCP session management)."""
    async with AsyncExitStack() as stack:
        for _, example_app, _, _, _ in EXAMPLES:
            if hasattr(example_app, "lifespan"):
                await stack.enter_async_context(example_app.lifespan(app))
        yield


routes = [Route("/", index, methods=["GET"])]
routes += [Mount(path, app=example_app) for path, example_app, _, _, _ in EXAMPLES]

app = Starlette(routes=routes, lifespan=lifespan)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
