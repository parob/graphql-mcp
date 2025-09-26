#!/usr/bin/env python3
"""
MCP Inspector Plugin for GraphiQL

This module contains the MCP Inspector functionality that gets injected
as a plugin into GraphiQL interfaces. It provides a web-based interface
for inspecting and testing MCP tools.
"""

from pathlib import Path
from starlette.types import Scope


class MCPInspector:
    """MCP Inspector plugin for GraphiQL integration"""

    def __init__(self):
        self.base_dir = Path(__file__).parent

    def _load_template(self, filename: str) -> str:
        """Load a template file from the templates directory"""
        template_path = self.base_dir / "templates" / filename
        if template_path.exists():
            return template_path.read_text(encoding='utf-8')
        else:
            raise FileNotFoundError(f"Template file not found: {filename}")

    def get_plugin_javascript(self) -> str:
        """Get the JavaScript code for the MCP plugin"""
        return self._load_template("mcp_plugin.js")

    def inject_plugin_into_html(self, html_body: bytes) -> bytes:
        """Inject MCP plugin directly into GraphiQL plugins array."""
        html_str = html_body.decode('utf-8', errors='ignore')

        # Check if this looks like GraphiQL HTML
        if not ("graphiql" in html_str.lower() and "<html" in html_str.lower()):
            return html_body

        # Try to inject directly into plugins array for proper GraphiQL integration
        if "const plugins = [" in html_str:
            # Get the plugin JavaScript code
            mcp_plugin_code = self.get_plugin_javascript()

            # Find the plugins array and inject the plugin definition before it
            plugins_start = html_str.find("const plugins = [")
            if plugins_start != -1:
                # Find the end of the plugins array
                plugins_end = html_str.find("];", plugins_start)
                if plugins_end != -1:
                    # Insert our plugin definition before the plugins array
                    before_plugins = html_str[:plugins_start]
                    plugins_array = html_str[plugins_start:plugins_end]
                    after_plugins = html_str[plugins_end:]

                    # Add mcpPlugin at the end of the array (before the closing bracket)
                    html_str = before_plugins + mcp_plugin_code + "\n        " + plugins_array + ", mcpPlugin" + after_plugins

            injection_script = '''
    <!-- MCP Plugin Successfully Injected -->
    <script>
        console.log('✅ MCP Plugin injected directly into GraphiQL plugins array');
    </script>
</head>'''
        else:
            # Fallback to external script loading if plugins array not found
            injection_script = '''
    <!-- MCP Plugin Auto-Injection (Fallback) -->
    <script>
        console.log('🔧 Auto-loading MCP GraphiQL Plugin (Fallback)...');
        console.warn('⚠️ GraphiQL plugins array not found - using fallback method');
    </script>
</head>'''

        # Add the injection script before </head>
        html_str = html_str.replace('</head>', injection_script)

        return html_str.encode('utf-8')

    def is_graphiql_request(self, scope: Scope) -> bool:
        """Check if this request is likely from GraphiQL"""
        headers = dict(scope.get("headers", []))

        # Check Accept header for HTML (GraphiQL requests)
        accept = headers.get(b"accept", b"").decode().lower()
        if "text/html" in accept:
            return True

        # Check User-Agent for browser (GraphiQL is served to browsers)
        user_agent = headers.get(b"user-agent", b"").decode().lower()
        if any(browser in user_agent for browser in ["mozilla", "chrome", "safari", "edge"]):
            return True

        return False


def get_inspector() -> MCPInspector:
    """Get a singleton MCP Inspector instance"""
    return MCPInspector()
