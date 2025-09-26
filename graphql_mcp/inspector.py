import os
import logging
import json
import httpx
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.requests import Request
from starlette.routing import Route
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


class MCPInspector:
    """Frontend-only web inspection tool for MCP servers using direct MCP protocol."""

    def __init__(self, mcp_server: FastMCP, title: str = "MCP Inspector"):
        self.mcp_server = mcp_server
        self.title = title
        self.app = self._create_app()

    def _create_app(self) -> Starlette:
        """Create the Starlette application for the inspector."""
        routes = [
            Route("/", self.index, methods=["GET"]),
            Route("/debug", self.debug_mcp, methods=["GET"]),
        ]

        return Starlette(routes=routes)

    async def index(self, request: Request) -> HTMLResponse:
        """Serve the frontend-only inspector interface."""

        # Get the current URL to determine the MCP endpoint
        base_url = str(request.url).rstrip('/')
        if base_url.endswith('/inspector'):
            base_url = base_url[:-10]  # Remove /inspector
        mcp_url = f"{base_url}/mcp"

        # Load HTML template from file
        template_path = os.path.join(os.path.dirname(__file__), 'inspector.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            html_template = f.read()

        # Replace template variables (avoiding format conflicts with CSS)
        html = html_template.replace('{title}', self.title)
        html = html.replace('{mcp_url}', mcp_url)

        return HTMLResponse(html)

    async def debug_mcp(self, request: Request) -> JSONResponse:
        """Debug endpoint to test MCP communication programmatically."""

        # Get the MCP URL
        base_url = str(request.url).rstrip('/')
        if base_url.endswith('/debug'):
            base_url = base_url[:-6]  # Remove /debug
        if base_url.endswith('/inspector'):
            base_url = base_url[:-10]  # Remove /inspector
        mcp_url = f"{base_url}/mcp"

        results = []

        # Test 1: Direct tools/list request (same as browser)
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }

            # Try port 8010 specifically for testing
            test_url_8010 = mcp_url.replace(':8003', ':8010')

            async with httpx.AsyncClient() as client:
                # Test both ports
                response = await client.post(mcp_url, headers=headers, json=payload, timeout=5.0)

                # Also test port 8010 if different
                response_8010 = None
                if test_url_8010 != mcp_url:
                    try:
                        response_8010 = await client.post(test_url_8010, headers=headers, json=payload, timeout=5.0)
                    except:
                        pass

                result = {
                    "test": "tools/list direct",
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "url": mcp_url,
                    "request_payload": payload,
                    "request_headers": headers
                }

                if response.status_code == 200:
                    result["response_text"] = response.text[:500]  # Truncate for readability
                    result["success"] = True
                else:
                    result["response_text"] = response.text
                    result["success"] = False

                results.append(result)

        except Exception as e:
            results.append({
                "test": "tools/list direct",
                "error": str(e),
                "success": False,
                "url": mcp_url
            })

        # Test 2: Initialize then tools/list (proper MCP flow)
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }

            # First initialize
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "Debug Client",
                        "version": "1.0.0"
                    }
                }
            }

            async with httpx.AsyncClient() as client:
                init_response = await client.post(mcp_url, headers=headers, json=init_payload, timeout=5.0)

                init_result = {
                    "test": "initialize",
                    "status_code": init_response.status_code,
                    "response_text": init_response.text[:300],
                    "success": init_response.status_code == 200
                }
                results.append(init_result)

                # If initialize succeeded, try tools/list
                if init_response.status_code == 200:
                    tools_payload = {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/list",
                        "params": {}
                    }

                    tools_response = await client.post(mcp_url, headers=headers, json=tools_payload, timeout=5.0)

                    tools_result = {
                        "test": "tools/list after initialize",
                        "status_code": tools_response.status_code,
                        "response_text": tools_response.text[:500],
                        "success": tools_response.status_code == 200
                    }
                    results.append(tools_result)

        except Exception as e:
            results.append({
                "test": "initialize + tools/list",
                "error": str(e),
                "success": False
            })

        # Return detailed debug information
        return JSONResponse({
            "debug_results": results,
            "server_info": {
                "mcp_url": mcp_url,
                "base_url": base_url,
                "request_url": str(request.url)
            }
        })