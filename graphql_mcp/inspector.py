import os
import logging
import json
import httpx
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, Response
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
            Route("/mcp-plugin.js", self.mcp_plugin_js, methods=["GET"]),
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

    async def mcp_plugin_js(self, request: Request) -> Response:
        """Serve JavaScript code to inject MCP functionality into GraphiQL."""

        # JavaScript code to inject MCP panel into GraphiQL
        js_code = '''
// MCP GraphiQL Plugin - Injects MCP tools panel into GraphiQL
(function() {
    console.log('🔧 Loading MCP GraphiQL Plugin...');

    // MCP Client Classes (same as standalone)
    class MCPHttpTransport {
        constructor(url) {
            this.url = url;
            this.sessionId = null;
        }

        async send(request) {
            const headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream',
            };

            if (this.sessionId) {
                headers['mcp-session-id'] = this.sessionId;
            }

            const response = await fetch(this.url, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(request)
            });

            const mcpSessionId = response.headers.get('mcp-session-id');
            if (mcpSessionId) {
                this.sessionId = mcpSessionId;
            }

            if (!response.ok) {
                if (response.status === 400) {
                    const errorText = await response.text();
                    if (errorText.includes('Missing session ID')) {
                        return { error: { code: -32600, message: 'Session required' } };
                    }
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const responseText = await response.text();

            if (responseText.startsWith('event: message')) {
                const lines = responseText.split('\\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        return JSON.parse(line.substring(6));
                    }
                }
                throw new Error('No data found in SSE response');
            } else {
                return JSON.parse(responseText);
            }
        }
    }

    class MCPClient {
        constructor(transport) {
            this.transport = transport;
            this.requestId = 0;
            this.initialized = false;
        }

        async request(method, params = {}) {
            const request = {
                jsonrpc: '2.0',
                id: ++this.requestId,
                method: method,
                params: params
            };

            const response = await this.transport.send(request);

            if (response.error && response.error.message === 'Session required') {
                console.log('🔄 Initializing MCP session...');
                await this.initialize();
                return await this.request(method, params);
            }

            if (response.error) {
                throw new Error(response.error.message || 'MCP request failed');
            }

            return response.result;
        }

        async initialize() {
            if (this.initialized) return;

            const initRequest = {
                jsonrpc: '2.0',
                id: ++this.requestId,
                method: 'initialize',
                params: {
                    protocolVersion: '2024-11-05',
                    capabilities: {
                        roots: {
                            listChanged: false
                        }
                    },
                    clientInfo: {
                        name: 'GraphiQL MCP Plugin',
                        version: '1.0.0'
                    }
                }
            };

            const response = await this.transport.send(initRequest);

            if (response.error) {
                throw new Error(`Initialization failed: ${response.error.message}`);
            }

            const initNotification = {
                jsonrpc: '2.0',
                method: 'notifications/initialized',
                params: {}
            };

            try {
                await this.transport.send(initNotification);
                console.log('✅ MCP session initialized');
            } catch (notificationError) {
                console.warn('⚠️ Initialized notification failed:', notificationError.message);
            }

            this.initialized = true;
            return response.result;
        }

        async listTools() {
            return await this.request('tools/list');
        }

        async callTool(name, args) {
            return await this.request('tools/call', { name, arguments: args });
        }
    }

    // GraphiQL Plugin Registration
    function createMCPPlugin() {
        // Dynamically determine MCP URL from current page location
        const mcpUrl = window.location.origin + '/mcp';
        console.log('🔗 MCP URL:', mcpUrl);

        const transport = new MCPHttpTransport(mcpUrl);
        const client = new MCPClient(transport);

        // Create the plugin component
        function MCPToolsPlugin() {
            const [status, setStatus] = React.useState('🔄 Connecting...');
            const [tools, setTools] = React.useState([]);
            const [connected, setConnected] = React.useState(false);

            // Initialize MCP connection
            React.useEffect(() => {
                async function initMCP() {
                    try {
                        setStatus('🔄 Initializing session...');
                        await client.initialize();

                        setStatus('🔄 Loading tools...');
                        const result = await client.listTools();
                        const toolsList = result.tools || [];

                        setTools(toolsList);
                        setStatus(`✅ Connected (${toolsList.length} tools)`);
                        setConnected(true);
                    } catch (error) {
                        setStatus(`❌ Failed: ${error.message}`);
                        console.error('MCP initialization failed:', error);
                    }
                }
                initMCP();
            }, []);

            // Tool call handler
            const callTool = async (toolName) => {
                try {
                    console.log(`Calling MCP tool: ${toolName}`);
                    const result = await client.callTool(toolName, {});
                    console.log('MCP tool result:', result);

                    // Show result in a modal or alert
                    alert(`${toolName} result:\\n${JSON.stringify(result, null, 2)}`);
                } catch (error) {
                    console.error('MCP tool call failed:', error);
                    alert(`Error calling ${toolName}:\\n${error.message}`);
                }
            };

            return React.createElement('div', {
                style: {
                    padding: '0px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    fontSize: '14px'
                }
            }, [
                React.createElement('div', {
                    key: 'status',
                    style: {
                        padding: '8px 12px',
                        marginBottom: '12px',
                        borderRadius: '4px',
                        fontSize: '13px',
                        background: connected ? '#e8f5e8' : '#e3f2fd',
                        color: connected ? '#2e7d32' : '#1565c0'
                    }
                }, status),

                React.createElement('div', {
                    key: 'tools',
                    style: { display: 'flex', flexDirection: 'column', gap: '8px' }
                }, tools.map(tool =>
                    React.createElement('div', {
                        key: tool.name,
                        style: {
                            background: '#f8f9fa',
                            border: '1px solid #e9ecef',
                            borderRadius: '4px',
                            padding: '12px',
                            cursor: 'pointer',
                            transition: 'background-color 0.2s'
                        },
                        onClick: () => callTool(tool.name),
                        onMouseEnter: (e) => e.target.style.background = '#e9ecef',
                        onMouseLeave: (e) => e.target.style.background = '#f8f9fa'
                    }, [
                        React.createElement('div', {
                            key: 'name',
                            style: {
                                fontWeight: '600',
                                color: '#007bff',
                                fontFamily: 'monospace',
                                marginBottom: '4px'
                            }
                        }, tool.name),
                        React.createElement('div', {
                            key: 'description',
                            style: {
                                fontSize: '12px',
                                color: '#6c757d'
                            }
                        }, tool.description || 'No description')
                    ])
                ))
            ]);
        }

        return {
            title: 'MCP Tools',
            icon: () => React.createElement('span', {}, '🔧'),
            content: MCPToolsPlugin
        };
    }

    // Inject MCP plugin directly into GraphiQL plugins array
    function registerMCPPlugin() {
        console.log('📊 Looking for GraphiQL plugins array...');

        // Try to find and modify the plugins array in the global scope
        if (typeof window !== 'undefined') {
            // Look for the plugins array variable
            const scripts = document.querySelectorAll('script');
            let foundPluginsArray = false;

            for (const script of scripts) {
                if (script.innerHTML && script.innerHTML.includes('const plugins = [')) {
                    console.log('📊 Found GraphiQL plugins array, injecting MCP plugin...');

                    // Create the MCP plugin
                    const mcpPlugin = createMCPPlugin();

                    // Try to inject by modifying the script content
                    const originalContent = script.innerHTML;
                    const newContent = originalContent.replace(
                        /const plugins = \[(.*?)\];/s,
                        (match, pluginsList) => {
                            return `const plugins = [${pluginsList}, (() => ${JSON.stringify(mcpPlugin).replace(/"function MCPToolsPlugin\(\)[\s\S]*?return React\.createElement[^}]+}[^}]+}[^}]+}/, '"FUNCTION_PLACEHOLDER"')})()];`.replace('"FUNCTION_PLACEHOLDER"', mcpPlugin.content.toString());
                        }
                    );

                    if (newContent !== originalContent) {
                        // Replace the script
                        const newScript = document.createElement('script');
                        newScript.innerHTML = newContent;
                        script.parentNode.insertBefore(newScript, script);
                        script.remove();
                        foundPluginsArray = true;
                        console.log('✅ MCP plugin injected into GraphiQL plugins array');
                        break;
                    }
                }
            }

            if (!foundPluginsArray) {
                console.log('⚠️ Could not find GraphiQL plugins array, trying alternative approach...');

                // Alternative: Try to inject into window after GraphiQL loads
                if (window.GraphiQL) {
                    console.log('📊 Found GraphiQL global, attempting to add plugin...');
                    // This approach might work if GraphiQL exposes plugins
                    injectIntoLoadedGraphiQL();
                } else {
                    console.log('⚠️ GraphiQL not found, falling back to manual panel');
                    injectMCPPanelFallback();
                }
            }
        } else {
            console.log('⚠️ Window not available, falling back to manual panel');
            injectMCPPanelFallback();
        }
    }

    // Try to inject into already loaded GraphiQL
    function injectIntoLoadedGraphiQL() {
        // This is a more complex approach - for now, use fallback
        console.log('⚠️ Alternative GraphiQL injection not implemented, using fallback');
        injectMCPPanelFallback();
    }

    // Fallback: Manual panel injection (original approach)
    function injectMCPPanelFallback() {
        const mcpUrl = window.location.origin + '/mcp';
        const transport = new MCPHttpTransport(mcpUrl);
        const client = new MCPClient(transport);

        // Create MCP panel HTML (simplified version of original)
        const mcpPanel = document.createElement('div');
        mcpPanel.id = 'mcp-panel';
        mcpPanel.style.cssText = `
            position: fixed;
            top: 60px;
            right: 20px;
            width: 350px;
            height: 400px;
            background: white;
            border: 1px solid #ccc;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 1000;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        `;

        mcpPanel.innerHTML = `
            <div style="padding: 12px; background: #f8f9fa; border-bottom: 1px solid #dee2e6; font-weight: 600; color: #495057;">
                🔧 MCP Tools (Fallback)
                <span id="mcp-toggle" style="float: right; cursor: pointer; font-size: 12px;">−</span>
            </div>
            <div id="mcp-content" style="flex: 1; overflow: auto; padding: 12px;">
                <div id="mcp-status" style="padding: 8px; margin-bottom: 12px; border-radius: 4px; font-size: 13px; background: #e3f2fd; color: #1565c0;">
                    🔄 Connecting...
                </div>
                <div id="mcp-tools"></div>
            </div>
        `;

        document.body.appendChild(mcpPanel);

        // Toggle functionality
        let collapsed = false;
        document.getElementById('mcp-toggle').addEventListener('click', () => {
            const content = document.getElementById('mcp-content');
            collapsed = !collapsed;
            content.style.display = collapsed ? 'none' : 'flex';
            document.getElementById('mcp-toggle').textContent = collapsed ? '+' : '−';
            mcpPanel.style.height = collapsed ? '48px' : '400px';
        });

        // Initialize MCP connection
        initializeMCPFallback(client);
    }

    async function initializeMCPFallback(client) {
        const status = document.getElementById('mcp-status');
        const toolsContainer = document.getElementById('mcp-tools');

        try {
            status.textContent = '🔄 Initializing session...';
            await client.initialize();

            status.textContent = '🔄 Loading tools...';
            const result = await client.listTools();
            const tools = result.tools || [];

            status.style.cssText = 'padding: 8px; margin-bottom: 12px; border-radius: 4px; font-size: 13px; background: #e8f5e8; color: #2e7d32;';
            status.textContent = `✅ Connected (${tools.length} tools)`;

            // Render tools
            toolsContainer.innerHTML = tools.map(tool => `
                <div style="background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 4px; padding: 8px; margin-bottom: 8px; cursor: pointer;"
                     onclick="window.callMCPTool('${tool.name}', ${JSON.stringify(tool).replace(/"/g, '&quot;')})">
                    <div style="font-weight: 600; color: #007bff; font-family: monospace;">${tool.name}</div>
                    <div style="font-size: 12px; color: #6c757d; margin-top: 2px;">${tool.description || 'No description'}</div>
                </div>
            `).join('');

            // Add global tool call function
            window.callMCPTool = async function(toolName, toolData) {
                try {
                    console.log(`Calling MCP tool: ${toolName}`);
                    const result = await client.callTool(toolName, {});
                    console.log('MCP tool result:', result);

                    // Show result in a simple alert for demo - could be enhanced
                    alert(`${toolName} result:\\n${JSON.stringify(result, null, 2)}`);
                } catch (error) {
                    console.error('MCP tool call failed:', error);
                    alert(`Error calling ${toolName}:\\n${error.message}`);
                }
            };

        } catch (error) {
            status.style.cssText = 'padding: 8px; margin-bottom: 12px; border-radius: 4px; font-size: 13px; background: #ffebee; color: #c62828;';
            status.textContent = `❌ Failed: ${error.message}`;
            console.error('MCP initialization failed:', error);
        }
    }

    // Register MCP plugin when GraphiQL loads
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            // Wait a bit for GraphiQL to fully initialize
            setTimeout(registerMCPPlugin, 1000);
        });
    } else {
        // Wait a bit for GraphiQL to fully initialize
        setTimeout(registerMCPPlugin, 1000);
    }

    console.log('✅ MCP GraphiQL Plugin loaded');
})();
'''

        return Response(
            content=js_code,
            media_type="application/javascript"
        )