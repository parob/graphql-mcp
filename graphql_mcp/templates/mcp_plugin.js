        // MCP Tools Plugin for GraphiQL
        const mcpPlugin = {
            title: 'MCP Inspector',
            description: 'Inspect and execute MCP (Model Context Protocol) tools directly from GraphiQL',
            icon: function() {
                return React.createElement('span', {
                    style: {
                        fontSize: '12px',
                        fontWeight: 'bold',
                        fontFamily: 'monospace'
                    }
                }, 'MCP');
            },
            content: function() {
                // Inject CSS to force system-ui font on all buttons
                React.useEffect(() => {
                    const styleId = 'mcp-font-override';
                    if (!document.getElementById(styleId)) {
                        const style = document.createElement('style');
                        style.id = styleId;
                        style.textContent = `
                            .graphiql-container button,
                            .graphiql-container input,
                            .graphiql-container select,
                            .graphiql-container textarea,
                            button,
                            input,
                            select,
                            textarea,
                            .graphiql-plugin button,
                            .graphiql-plugin input,
                            .graphiql-plugin select,
                            .graphiql-plugin textarea,
                            .graphiql-plugin-content button,
                            .graphiql-plugin-content input,
                            .graphiql-plugin-content select,
                            .graphiql-plugin-content textarea {
                                font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
                            }

                            /* Universal override for any remaining form elements */
                            * {
                                --font-family-override: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                            }

                            input[type="text"],
                            input[type="password"],
                            input[type="email"],
                            input[type="url"],
                            textarea,
                            select,
                            button {
                                font-family: var(--font-family-override) !important;
                            }
                        `;
                        document.head.appendChild(style);
                    }
                    return () => {
                        const existingStyle = document.getElementById(styleId);
                        if (existingStyle) {
                            existingStyle.remove();
                        }
                    };
                }, []);

                const [status, setStatus] = React.useState('🔄 Connecting...');
                const [tools, setTools] = React.useState([]);
                const [connected, setConnected] = React.useState(false);
                const [expandedTool, setExpandedTool] = React.useState(null);
                const [toolResults, setToolResults] = React.useState({});
                const [toolInputs, setToolInputs] = React.useState({});
                const [validationErrors, setValidationErrors] = React.useState({});
                const [callHistory, setCallHistory] = React.useState(() => {
                    try {
                        return JSON.parse(localStorage.getItem('mcp-call-history') || '[]');
                    } catch {
                        return [];
                    }
                });
                // Smart MCP URL detection - works with GraphiQL at any path
                const getDefaultMcpUrl = () => {
                    const currentUrl = new URL(window.location.href);
                    // Remove any existing query parameters and fragments
                    currentUrl.search = '';
                    currentUrl.hash = '';

                    // If we're at root (/), MCP is at /mcp
                    if (currentUrl.pathname === '/' || currentUrl.pathname === '') {
                        return currentUrl.origin + '/mcp';
                    }

                    // Otherwise, MCP is relative to current path: /tools/ -> /tools/mcp
                    let basePath = currentUrl.pathname;
                    if (!basePath.endsWith('/')) {
                        basePath += '/';
                    }
                    return currentUrl.origin + basePath + 'mcp';
                };

                const [mcpUrl, setMcpUrl] = React.useState(() => getDefaultMcpUrl());
                const [clearingHistory, setClearingHistory] = React.useState(false);
                const [authType, setAuthType] = React.useState(() => localStorage.getItem('mcp-auth-type') || 'none');
                const [bearerToken, setBearerToken] = React.useState(() => localStorage.getItem('mcp-bearer-token') || '');
                const [apiKey, setApiKey] = React.useState(() => localStorage.getItem('mcp-api-key') || '');
                const [apiKeyHeader, setApiKeyHeader] = React.useState(() => localStorage.getItem('mcp-api-key-header') || 'X-API-Key');
                const [customHeaders, setCustomHeaders] = React.useState(() => localStorage.getItem('mcp-custom-headers') || '{}');
                const [showAuth, setShowAuth] = React.useState(() => localStorage.getItem('mcp-show-auth') === 'true');
                const [applyingAuth, setApplyingAuth] = React.useState(false);
                const [refreshing, setRefreshing] = React.useState(false);
                const [activeTab, setActiveTab] = React.useState('tools');

                // MCP Client setup - now uses configurable URL

                // Helper function to build auth headers
                const buildAuthHeaders = React.useCallback(() => {
                    const headers = {};

                    if (authType === 'bearer' && bearerToken) {
                        headers['Authorization'] = `Bearer ${bearerToken}`;
                    } else if (authType === 'apikey' && apiKey && apiKeyHeader) {
                        headers[apiKeyHeader] = apiKey;
                    } else if (authType === 'custom' && customHeaders) {
                        try {
                            const parsed = JSON.parse(customHeaders);
                            Object.assign(headers, parsed);
                        } catch (e) {
                            console.warn('Invalid custom headers JSON:', e);
                        }
                    }

                    return headers;
                }, [authType, bearerToken, apiKey, apiKeyHeader, customHeaders]);

                // Helper function to get auth display name
                const getAuthDisplayName = React.useCallback(() => {
                    switch (authType) {
                        case 'bearer': return 'Bearer Token';
                        case 'apikey': return 'API Key';
                        case 'custom': return 'Custom Headers';
                        default: return 'None';
                    }
                }, [authType]);


                // Persist auth state to localStorage
                React.useEffect(() => {
                    localStorage.setItem('mcp-auth-type', authType);
                }, [authType]);


                React.useEffect(() => {
                    localStorage.setItem('mcp-bearer-token', bearerToken);
                }, [bearerToken]);

                React.useEffect(() => {
                    localStorage.setItem('mcp-api-key', apiKey);
                }, [apiKey]);

                React.useEffect(() => {
                    localStorage.setItem('mcp-api-key-header', apiKeyHeader);
                }, [apiKeyHeader]);

                React.useEffect(() => {
                    localStorage.setItem('mcp-custom-headers', customHeaders);
                }, [customHeaders]);

                React.useEffect(() => {
                    localStorage.setItem('mcp-show-auth', showAuth.toString());
                }, [showAuth]);

                React.useEffect(() => {
                    localStorage.setItem('mcp-server-url', mcpUrl);
                }, [mcpUrl]);

                React.useEffect(() => {
                    try {
                        localStorage.setItem('mcp-call-history', JSON.stringify(callHistory));
                    } catch {
                        // Storage quota exceeded — trim oldest entries and retry
                        try {
                            const trimmed = callHistory.slice(-20);
                            localStorage.setItem('mcp-call-history', JSON.stringify(trimmed));
                        } catch {
                            localStorage.removeItem('mcp-call-history');
                        }
                    }
                }, [callHistory]);

                // Clear tools when URL changes
                React.useEffect(() => {
                    setTools([]);
                    setConnected(false);
                    setStatus('URL changed - ready to connect');
                }, [mcpUrl]);

                const client = React.useMemo(() => {
                    // MCP Transport and Client classes (simplified for direct injection)
                    class MCPHttpTransport {
                        constructor(url, customHeaders = {}) {
                            this.url = url;
                            this.sessionId = null;
                            this.customHeaders = customHeaders;
                        }

                        updateHeaders(newHeaders) {
                            // Replace auth headers completely instead of merging
                            this.customHeaders = { ...newHeaders };
                        }

                        async send(request) {
                            const headers = {
                                'Content-Type': 'application/json',
                                'Accept': 'application/json, text/event-stream',
                                ...this.customHeaders
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

                            // Handle SSE format
                            if (response.headers.get('content-type')?.includes('text/event-stream')) {
                                const lines = responseText.split('\n');
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
                            this.requestId = 1;
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

                    return new MCPClient(new MCPHttpTransport(mcpUrl, {}));
                }, [mcpUrl]);

                // Basic connection function without auth headers (for initial connection)
                const connectWithoutAuth = React.useCallback(async (statusMessage = '🔄 Connecting...') => {
                    try {
                        setStatus(statusMessage);
                        setConnected(false);
                        setTools([]);

                        // Initialize connection
                        await client.initialize();

                        // Load tools
                        const toolsResponse = await client.listTools();
                        const toolsList = toolsResponse.tools || [];
                        setTools(toolsList);
                        setConnected(true);

                        // Set success status
                        setStatus(`✓ Connected (${toolsList.length} tools)`);

                        return { success: true, toolCount: toolsList.length };
                    } catch (error) {
                        setStatus(`✗ Connection failed: ${error.message || error}`);
                        setConnected(false);
                        setTools([]);
                        return { success: false, error: error.message || error };
                    }
                }, [client]);

                // Authentication application function (called explicitly)
                const applyAuthentication = React.useCallback(async (statusMessage = '🔒 Applying authentication...') => {
                    try {
                        setStatus(statusMessage);
                        setConnected(false);
                        setTools([]);

                        // Update auth headers and reconnect
                        const newHeaders = buildAuthHeaders();
                        client.transport.updateHeaders(newHeaders);

                        // Initialize connection
                        await client.initialize();

                        // Load tools
                        const toolsResponse = await client.listTools();
                        const toolsList = toolsResponse.tools || [];
                        setTools(toolsList);
                        setConnected(true);

                        // Set success status
                        const authIndicator = authType !== 'none' ? ' with authentication' : '';
                        setStatus(`✓ Connected${authIndicator} (${toolsList.length} tools)`);

                        return { success: true, toolCount: toolsList.length };
                    } catch (error) {
                        setStatus(`✗ Connection failed: ${error.message || error}`);
                        setConnected(false);
                        setTools([]);
                        return { success: false, error: error.message || error };
                    }
                }, [client, buildAuthHeaders]);

                // Auto-apply authentication when authType changes to 'none' (but not on initial load)
                const isInitialMount = React.useRef(true);
                React.useEffect(() => {
                    if (isInitialMount.current) {
                        isInitialMount.current = false;
                        return;
                    }
                    if (authType === 'none') {
                        applyAuthentication();
                    }
                }, [authType, applyAuthentication]);

                // Initialize MCP connection
                React.useEffect(() => {
                    connectWithoutAuth('🔄 Initializing...');
                }, [connectWithoutAuth]);

                // Clean up MCP response format
                const formatMCPResponse = (result) => {
                    // If result has structuredContent, prefer that
                    if (result.structuredContent) {
                        return result.structuredContent;
                    }

                    // If result has content array, extract and format
                    if (result.content && Array.isArray(result.content)) {
                        if (result.content.length === 1 && result.content[0].type === 'text') {
                            const text = result.content[0].text;
                            try {
                                // Try to parse as JSON for better formatting
                                const parsed = JSON.parse(text);
                                return parsed;
                            } catch {
                                // Return as-is if not JSON
                                return text;
                            }
                        }
                        // Multiple content items - return the array
                        return result.content;
                    }

                    // Return as-is for other formats
                    return result;
                };

                // Tool interaction handlers
                const toggleTool = (toolName) => {
                    setExpandedTool(expandedTool === toolName ? null : toolName);
                };

                const updateToolInput = (toolName, paramName, value) => {
                    setToolInputs(prev => ({
                        ...prev,
                        [toolName]: {
                            ...prev[toolName],
                            [paramName]: value
                        }
                    }));
                    // Clear validation error for this field when user types
                    setValidationErrors(prev => {
                        const toolErrors = prev[toolName];
                        if (!toolErrors || !toolErrors[paramName]) return prev;
                        const updated = { ...toolErrors };
                        delete updated[paramName];
                        if (Object.keys(updated).length === 0) {
                            const newState = { ...prev };
                            delete newState[toolName];
                            return newState;
                        }
                        return { ...prev, [toolName]: updated };
                    });
                };

                // Parse Pydantic validation errors into per-field messages
                const parsePydanticError = (errorText) => {
                    const fieldErrors = {};
                    if (!errorText || typeof errorText !== 'string') return { parsed: false, fieldErrors };

                    const pydanticMatch = errorText.match(/(\d+) validation errors? for/);
                    if (pydanticMatch) {
                        const lines = errorText.split('\n');
                        let currentField = null;
                        for (let i = 1; i < lines.length; i++) {
                            const line = lines[i];
                            if (line && !line.startsWith(' ') && !line.startsWith('\t')) {
                                currentField = line.trim();
                            } else if (currentField && line.trim()) {
                                const detail = line.trim();
                                if (detail.startsWith('For further information')) continue;
                                const cleanMsg = detail
                                    .replace(/\s*\[type=\w+,.*?\]/, '')
                                    .trim();
                                if (cleanMsg) {
                                    fieldErrors[currentField] = cleanMsg;
                                    currentField = null;
                                }
                            }
                        }
                        return { parsed: true, fieldErrors };
                    }
                    return { parsed: false, fieldErrors };
                };

                const callTool = async (toolName) => {
                    const tool = tools.find(t => t.name === toolName);
                    const args = toolInputs[toolName] || {};

                    // Client-side pre-validation: check required fields
                    if (tool && tool.inputSchema && tool.inputSchema.required) {
                        const errors = {};
                        for (const requiredParam of tool.inputSchema.required) {
                            const value = args[requiredParam];
                            if (value === undefined || value === null || value === '') {
                                errors[requiredParam] = 'Required';
                            }
                        }
                        if (Object.keys(errors).length > 0) {
                            setValidationErrors(prev => ({ ...prev, [toolName]: errors }));
                            return;
                        }
                    }

                    // Clear validation errors on valid submission
                    setValidationErrors(prev => {
                        const newState = { ...prev };
                        delete newState[toolName];
                        return newState;
                    });

                    const timestamp = new Date();

                    // Add to history immediately (pending)
                    const historyEntry = {
                        id: Date.now() + Math.random(),
                        toolName,
                        inputs: { ...args },
                        timestamp: timestamp.toLocaleTimeString(),
                        fullTimestamp: timestamp,
                        status: 'pending'
                    };

                    setCallHistory(prev => [historyEntry, ...prev]);

                    try {
                        console.log(`Calling MCP tool: ${toolName}`);

                        const result = await client.callTool(toolName, args);
                        console.log('MCP tool result:', result);

                        // Handle MCP tool errors (isError flag)
                        if (result && result.isError) {
                            const errorText = (result.content && result.content[0] && result.content[0].text) || 'Tool returned an error';
                            const parsed = parsePydanticError(errorText);
                            if (parsed.parsed && Object.keys(parsed.fieldErrors).length > 0) {
                                setValidationErrors(prev => ({ ...prev, [toolName]: parsed.fieldErrors }));
                            }
                            throw new Error(parsed.parsed && Object.keys(parsed.fieldErrors).length > 0
                                ? Object.entries(parsed.fieldErrors).map(([f, m]) => `${f}: ${m}`).join(', ')
                                : errorText);
                        }

                        // Store formatted result in state
                        const formattedResult = formatMCPResponse(result);
                        const successResult = {
                            success: true,
                            result: formattedResult,
                            timestamp: timestamp.toLocaleTimeString()
                        };

                        setToolResults(prev => ({
                            ...prev,
                            [toolName]: successResult
                        }));

                        // Update history with success
                        setCallHistory(prev => prev.map(entry =>
                            entry.id === historyEntry.id
                                ? { ...entry, status: 'success', result: formattedResult }
                                : entry
                        ));
                    } catch (error) {
                        console.error('MCP tool call failed:', error);

                        // Try to parse Pydantic validation errors from server
                        const parsed = parsePydanticError(error.message);
                        if (parsed.parsed && Object.keys(parsed.fieldErrors).length > 0) {
                            setValidationErrors(prev => ({ ...prev, [toolName]: parsed.fieldErrors }));
                        }

                        const displayError = (parsed.parsed && Object.keys(parsed.fieldErrors).length > 0)
                            ? Object.entries(parsed.fieldErrors).map(([f, m]) => `${f}: ${m}`).join(', ')
                            : error.message;

                        const errorResult = {
                            success: false,
                            error: displayError,
                            timestamp: timestamp.toLocaleTimeString()
                        };

                        // Store error in state
                        setToolResults(prev => ({
                            ...prev,
                            [toolName]: errorResult
                        }));

                        // Update history with error
                        setCallHistory(prev => prev.map(entry =>
                            entry.id === historyEntry.id
                                ? { ...entry, status: 'error', error: displayError }
                                : entry
                        ));
                    }
                };

                return React.createElement('div', {
                    style: {
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        fontFamily: 'system-ui, -apple-system, sans-serif',
                        fontSize: '14px'
                    }
                }, [
                    // Header section (fixed)
                    React.createElement('div', {
                        key: 'header',
                        style: {
                            padding: '0',
                            flexShrink: 0
                        }
                    }, [
                    React.createElement('h3', {
                        key: 'title',
                        style: {
                            margin: '0px 0px 4px',
                            fontSize: '29px',
                            fontWeight: 'bold'
                        }
                    }, 'MCP Inspector'),
                    React.createElement('p', {
                        key: 'description',
                        className: 'graphiql-markdown-description',
                        style: {
                            margin: '0px 0px 20px',
                            color: 'rgba(59, 75, 104, 0.76)'
                        }
                    }, 'Inspect and execute MCP (Model Context Protocol) tools'),

                    // MCP Server Details section title
                    React.createElement('h3', {
                        key: 'server-details-title',
                        style: {
                            margin: '20px 0px 12px',
                            fontSize: '16px',
                            fontWeight: '600',
                            color: '#333',
                            fontFamily: 'system-ui, -apple-system, sans-serif'
                        }
                    }, 'Server Details'),

                    // Modern header layout: URL | Status | Refresh | Auth
                    React.createElement('div', {
                        key: 'header-section',
                        style: {
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: '8px',
                            marginBottom: '12px',
                            alignItems: 'center'
                        }
                    }, [
                        // URL input (fills available space, shrinks first)
                        React.createElement('input', {
                            key: 'url-input',
                            type: 'text',
                            value: mcpUrl,
                            onChange: (e) => setMcpUrl(e.target.value),
                            placeholder: '/mcp',
                            style: {
                                flex: '1 1 200px',
                                minWidth: '120px',
                                padding: '6px 8px',
                                fontSize: '13px',
                                border: '1px solid #ddd',
                                borderRadius: '6px',
                                fontFamily: 'system-ui, monospace',
                                outline: 'none',
                                transition: 'border-color 0.2s'
                            }
                        }),

                        // Button group (stays together when wrapping)
                        React.createElement('div', {
                            key: 'button-group',
                            style: {
                                display: 'flex',
                                gap: '8px',
                                alignItems: 'center',
                                flexShrink: 0
                            }
                        }, [

                        // Status display (compact)
                        React.createElement('div', {
                            key: 'status',
                            style: {
                                padding: '6px 10px',
                                borderRadius: '6px',
                                fontSize: '12px',
                                fontWeight: '500',
                                background: connected ? '#e8f5e8' : '#fff3e0',
                                color: connected ? '#2e7d32' : '#f57c00',
                                whiteSpace: 'nowrap',
                                minWidth: '120px',
                                textAlign: 'center'
                            }
                        }, status),

                        // Refresh button (icon-first, minimal)
                        React.createElement('button', {
                            key: 'refresh-btn',
                            disabled: refreshing,
                            onClick: async () => {
                                try {
                                    setRefreshing(true);
                                    const startTime = Date.now();

                                    // Call the refresh function
                                    await applyAuthentication('🔄 Refreshing...');

                                    // Ensure minimum 0.4s press time for visual feedback
                                    const elapsedTime = Date.now() - startTime;
                                    const remainingTime = Math.max(0, 400 - elapsedTime);
                                    setTimeout(() => {
                                        setRefreshing(false);
                                    }, remainingTime);
                                } catch (error) {
                                    console.error('Failed to refresh:', error);

                                    // Ensure minimum 0.4s press time for error case too
                                    const elapsedTime = Date.now() - startTime;
                                    const remainingTime = Math.max(0, 400 - elapsedTime);
                                    setTimeout(() => {
                                        setRefreshing(false);
                                    }, remainingTime);
                                }
                            },
                            style: {
                                padding: '6px 10px',
                                fontSize: '12px',
                                backgroundColor: refreshing ? '#e9ecef' : '#f8f9fa',
                                border: 'none',
                                borderRadius: '6px',
                                cursor: refreshing ? 'not-allowed' : 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                fontWeight: '500',
                                fontFamily: 'system-ui, -apple-system, sans-serif !important',
                                color: '#495057',
                                transition: 'all 0.2s',
                                boxShadow: '0 1px 2px rgba(0,0,0,0.1)'
                            },
                            onMouseEnter: (e) => {
                                e.target.style.backgroundColor = '#e9ecef';
                                e.target.style.transform = 'translateY(-1px)';
                            },
                            onMouseLeave: (e) => {
                                e.target.style.backgroundColor = '#f8f9fa';
                                e.target.style.transform = 'translateY(0)';
                            }
                        }, [
                            React.createElement('span', { key: 'refresh-icon', style: { fontSize: '14px' } }, '⟲'),
                            refreshing ? 'Refreshing...' : 'Refresh'
                        ]),

                        // Auth button (minimal, modern)
                        React.createElement('button', {
                            key: 'auth-btn',
                            onClick: () => {
                                // If closing auth tab, auto-apply authentication
                                if (showAuth) {
                                    applyAuthentication();
                                }
                                setShowAuth(!showAuth);
                            },
                            style: {
                                padding: '6px 10px',
                                fontSize: '12px',
                                backgroundColor: showAuth ? '#1976d2' : '#f8f9fa',
                                color: showAuth ? 'white' : '#495057',
                                border: 'none',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                fontWeight: '500',
                                fontFamily: 'system-ui, -apple-system, sans-serif !important',
                                transition: 'all 0.2s',
                                boxShadow: '0 1px 2px rgba(0,0,0,0.1)'
                            },
                            onMouseEnter: (e) => {
                                if (!showAuth) {
                                    e.target.style.backgroundColor = '#e9ecef';
                                    e.target.style.transform = 'translateY(-1px)';
                                }
                            },
                            onMouseLeave: (e) => {
                                if (!showAuth) {
                                    e.target.style.backgroundColor = '#f8f9fa';
                                    e.target.style.transform = 'translateY(0)';
                                }
                            }
                        }, [
                            React.createElement('span', {
                                key: 'auth-icon',
                                style: {
                                    display: 'inline-block',
                                    width: '12px',
                                    height: '12px',
                                    marginRight: '4px'
                                },
                                dangerouslySetInnerHTML: {
                                    __html: `<svg width="12" height="12" viewBox="0 0 12 12" fill="none" style="background: transparent;">
                                        <path d="M6 1C4.3 1 3 2.3 3 4v1H2.5c-.6 0-1 .4-1 1v5c0 .6.4 1 1 1h7c.6 0 1-.4 1-1V6c0-.6-.4-1-1-1H9V4c0-1.7-1.3-3-3-3zM6 2c1.1 0 2 .9 2 2v1H4V4c0-1.1.9-2 2-2z" fill="currentColor"/>
                                    </svg>`
                                }
                            }),
                            'Authentication',
                            authType !== 'none' ? React.createElement('span', {
                                key: 'auth-tag',
                                style: {
                                    fontSize: '10px',
                                    padding: '1px 4px',
                                    marginLeft: '4px',
                                    backgroundColor: showAuth ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.1)',
                                    borderRadius: '3px',
                                    fontWeight: '600'
                                }
                            }, authType === 'bearer' ? 'Bearer Token' : authType === 'apikey' ? 'API Key' : authType === 'custom' ? 'Custom Headers' : authType.toUpperCase()) : null
                        ])
                    ]) ]),

                    // Authentication modal overlay
                    showAuth ? React.createElement('div', {
                        key: 'auth-overlay',
                        onMouseDown: (e) => {
                            if (e.target === e.currentTarget) {
                                applyAuthentication();
                                setShowAuth(false);
                            }
                        },
                        style: {
                            position: 'fixed',
                            top: 0,
                            left: 0,
                            right: 0,
                            bottom: 0,
                            background: 'rgba(59, 75, 104, 0.15)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            zIndex: 100
                        }
                    }, React.createElement('div', {
                        key: 'auth-modal',
                        className: 'graphiql-dialog',
                        onMouseDown: (e) => e.stopPropagation(),
                        style: { pointerEvents: 'auto', width: '380px', maxWidth: '90vw' }
                    }, [
                        // Dialog header
                        React.createElement('div', {
                            key: 'modal-header',
                            className: 'graphiql-dialog-header'
                        }, [
                            React.createElement('h2', {
                                key: 'auth-title',
                                className: 'graphiql-dialog-title'
                            }, 'Authentication'),
                            React.createElement('button', {
                                key: 'close-btn',
                                type: 'button',
                                'aria-label': 'Close dialog',
                                onClick: () => {
                                    applyAuthentication();
                                    setShowAuth(false);
                                },
                                style: {
                                    position: 'absolute', top: '21px', right: '21px',
                                    background: '#ffffff', border: '2px solid #e0e0e0', cursor: 'pointer',
                                    width: '38px', height: '38px', borderRadius: '6px',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    color: '#5c6370', fontSize: '24px', lineHeight: 0, fontWeight: '300', paddingBottom: '2px'
                                },
                                onMouseEnter: (e) => e.currentTarget.style.background = '#f5f5f5',
                                onMouseLeave: (e) => e.currentTarget.style.background = '#ffffff'
                            }, '\u00d7')
                        ]),
                        // Auth type section
                        React.createElement('div', { key: 'auth-type-section', className: 'graphiql-dialog-section' }, [
                            React.createElement('div', { key: 'info' }, [
                                React.createElement('div', { key: 'title', className: 'graphiql-dialog-section-title' }, 'Type'),
                                React.createElement('div', { key: 'caption', className: 'graphiql-dialog-section-caption' }, 'Select authentication method for the MCP endpoint.')
                            ]),
                            React.createElement('div', { key: 'buttons', className: 'graphiql-button-group' },
                                [['none', 'None'], ['bearer', 'Bearer'], ['apikey', 'API Key'], ['custom', 'Custom']].map(([val, label]) =>
                                    React.createElement('button', {
                                        key: val, type: 'button',
                                        className: authType === val ? 'graphiql-button active' : 'graphiql-button',
                                        onClick: () => setAuthType(val)
                                    }, label)
                                )
                            )
                        ]),
                        // Bearer token input
                        authType === 'bearer' ? React.createElement('div', { key: 'bearer-section', className: 'graphiql-dialog-section' }, [
                            React.createElement('div', { key: 'info' }, [
                                React.createElement('div', { key: 'title', className: 'graphiql-dialog-section-title' }, 'Token'),
                                React.createElement('div', { key: 'caption', className: 'graphiql-dialog-section-caption' }, 'Bearer token sent in the Authorization header.')
                            ]),
                            React.createElement('input', {
                                key: 'bearer-field', type: 'text', value: bearerToken,
                                onChange: (e) => setBearerToken(e.target.value),
                                placeholder: 'Enter bearer token',
                                className: 'graphiql-dialog-section-input',
                                style: { width: '100%', padding: '8px 10px', fontSize: '13px', border: '1px solid var(--color-border, #ddd)', borderRadius: '6px', background: 'var(--color-base, #fff)', outline: 'none' }
                            })
                        ]) : null,
                        // API key inputs
                        authType === 'apikey' ? React.createElement('div', { key: 'apikey-section', className: 'graphiql-dialog-section' }, [
                            React.createElement('div', { key: 'info' }, [
                                React.createElement('div', { key: 'title', className: 'graphiql-dialog-section-title' }, 'API Key'),
                                React.createElement('div', { key: 'caption', className: 'graphiql-dialog-section-caption' }, 'Sent as a custom header with each request.')
                            ]),
                            React.createElement('input', {
                                key: 'apikey-header-field', type: 'text', value: apiKeyHeader,
                                onChange: (e) => setApiKeyHeader(e.target.value),
                                placeholder: 'Header name (e.g. X-API-Key)',
                                style: { width: '100%', padding: '8px 10px', fontSize: '13px', border: '1px solid var(--color-border, #ddd)', borderRadius: '6px', background: 'var(--color-base, #fff)', outline: 'none', marginBottom: '8px' }
                            }),
                            React.createElement('input', {
                                key: 'apikey-value-field', type: 'text', value: apiKey,
                                onChange: (e) => setApiKey(e.target.value),
                                placeholder: 'API key value',
                                style: { width: '100%', padding: '8px 10px', fontSize: '13px', border: '1px solid var(--color-border, #ddd)', borderRadius: '6px', background: 'var(--color-base, #fff)', outline: 'none' }
                            })
                        ]) : null,
                        // Custom headers input
                        authType === 'custom' ? React.createElement('div', { key: 'custom-section', className: 'graphiql-dialog-section' }, [
                            React.createElement('div', { key: 'info' }, [
                                React.createElement('div', { key: 'title', className: 'graphiql-dialog-section-title' }, 'Custom Headers'),
                                React.createElement('div', { key: 'caption', className: 'graphiql-dialog-section-caption' }, 'JSON object of headers to send with each request.')
                            ]),
                            React.createElement('textarea', {
                                key: 'custom-field', value: customHeaders,
                                onChange: (e) => setCustomHeaders(e.target.value),
                                placeholder: '{"X-Custom-Header": "value"}',
                                rows: 3,
                                style: { width: '100%', padding: '8px 10px', fontSize: '13px', border: '1px solid var(--color-border, #ddd)', borderRadius: '6px', background: 'var(--color-base, #fff)', outline: 'none', fontFamily: 'monospace', resize: 'vertical' }
                            })
                        ]) : null,
                        // Apply button section
                        authType !== 'none' ? React.createElement('div', { key: 'apply-section', className: 'graphiql-dialog-section' },
                            React.createElement('button', {
                                key: 'apply-auth',
                                disabled: applyingAuth,
                                className: 'graphiql-button active',
                                onClick: async () => {
                                    try {
                                        setApplyingAuth(true);
                                        const startTime = Date.now();
                                        const result = await applyAuthentication();
                                        if (result.success) {
                                            setStatus('\u2713 Authentication applied successfully!');
                                            setTimeout(() => {
                                                const authIndicator = authType !== 'none' ? ' with authentication' : '';
                                                setStatus(`\u2713 Connected${authIndicator} (${result.toolCount} tools)`);
                                            }, 2000);
                                            setShowAuth(false);
                                        }
                                        const elapsedTime = Date.now() - startTime;
                                        setTimeout(() => { setApplyingAuth(false); }, Math.max(0, 400 - elapsedTime));
                                    } catch (error) {
                                        console.error('Failed to apply authentication:', error);
                                        setTimeout(() => { setApplyingAuth(false); }, 400);
                                    }
                                },
                                style: { width: '100%', cursor: applyingAuth ? 'not-allowed' : 'pointer' }
                            }, applyingAuth ? 'Authenticating...' : 'Authenticate')
                        ) : null
                    ])) : null,

                    // Tab bar (relative container so Clear can float over it)
                    React.createElement('div', {
                        key: 'tab-bar',
                        style: { flexShrink: 0, marginBottom: '12px', position: 'relative' }
                    }, [
                        React.createElement('div', {
                            key: 'tabs',
                            className: 'graphiql-button-group'
                        }, [
                            React.createElement('button', {
                                key: 'tab-tools',
                                className: activeTab === 'tools' ? 'graphiql-button active' : 'graphiql-button',
                                onClick: () => setActiveTab('tools')
                            }, `Tools (${tools.length})`),
                            React.createElement('button', {
                                key: 'tab-history',
                                className: activeTab === 'history' ? 'graphiql-button active' : 'graphiql-button',
                                onClick: () => setActiveTab('history')
                            }, callHistory.length > 0 ? `History (${callHistory.length})` : 'History')
                        ]),
                        // Clear history button (floating over tab bar, right side)
                        activeTab === 'history' && callHistory.length > 0 ? React.createElement('button', {
                            key: 'clear-history-btn',
                            className: 'graphiql-button',
                            disabled: clearingHistory,
                            onClick: async () => {
                                setClearingHistory(true);
                                setCallHistory([]);
                                setTimeout(() => { setClearingHistory(false); }, 1000);
                            },
                            style: {
                                position: 'absolute',
                                right: 0,
                                top: '50%',
                                transform: 'translateY(-50%)',
                                cursor: clearingHistory ? 'not-allowed' : 'pointer',
                                opacity: clearingHistory ? 0.6 : 1
                            }
                        }, clearingHistory ? 'Cleared!' : 'Clear') : null
                    ]),

                    // Scrollable content section
                    React.createElement('div', {
                        key: 'content',
                        style: {
                            flex: 1,
                            overflow: 'auto',
                            padding: '0'
                        }
                    }, [
                        // Tools section (visible on tools tab)
                        activeTab === 'tools' ? React.createElement('div', {
                            key: 'tools-section',
                            style: { marginBottom: '24px' }
                        }, [
                            React.createElement('div', {
                        key: 'tools',
                        style: { display: 'flex', flexDirection: 'column', gap: '8px' }
                    }, tools.map((tool, index) => {
                        const isExpanded = expandedTool === tool.name;
                        const toolResult = toolResults[tool.name];

                        return React.createElement('div', {
                            key: tool.name || index,
                            style: {
                                background: isExpanded ? '#f1f3f4' : '#ffffff',
                                border: isExpanded ? '2px solid #1976d2' : '1px solid #e0e0e0',
                                borderRadius: '6px',
                                overflow: 'hidden',
                                transition: 'all 0.2s ease'
                            }
                        }, [
                            // Tool header (clickable to expand)
                            React.createElement('div', {
                                key: 'header',
                                style: {
                                    padding: '12px',
                                    cursor: 'pointer',
                                    background: isExpanded ? '#e3f2fd' : 'transparent',
                                    borderBottom: isExpanded ? '1px solid #e0e0e0' : 'none'
                                },
                                onClick: () => toggleTool(tool.name)
                            }, [
                                React.createElement('div', {
                                    key: 'name-row',
                                    style: {
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between'
                                    }
                                }, [
                                    React.createElement('div', {
                                        key: 'name',
                                        style: {
                                            fontWeight: '600',
                                            color: '#1976d2',
                                            fontFamily: 'monospace',
                                            fontSize: '14px'
                                        }
                                    }, tool.name),
                                    React.createElement('div', {
                                        key: 'expand-icon',
                                        style: {
                                            fontSize: '12px',
                                            color: '#666',
                                            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                                            transition: 'transform 0.2s'
                                        }
                                    }, '▼')
                                ]),
                                React.createElement('div', {
                                    key: 'description',
                                    style: {
                                        fontSize: '12px',
                                        color: '#666',
                                        marginTop: '4px'
                                    }
                                }, tool.description || 'No description')
                            ]),

                            // Expanded content (parameters + results)
                            isExpanded ? React.createElement('div', {
                                key: 'expanded',
                                style: {
                                    padding: '16px',
                                    background: '#fafafa'
                                }
                            }, [
                                // Parameters section (only if there are parameters)
                                tool.inputSchema && tool.inputSchema.properties && Object.keys(tool.inputSchema.properties).length > 0 ? React.createElement('div', {
                                    key: 'params-section',
                                    style: { marginBottom: '16px' }
                                }, [
                                    React.createElement('div', {
                                        key: 'params-title',
                                        style: {
                                            fontSize: '13px',
                                            fontWeight: '600',
                                            color: '#333',
                                            marginBottom: '8px'
                                        }
                                    }, 'Parameters:'),
                                    React.createElement('div', {
                                        key: 'params-list',
                                        style: { display: 'flex', flexDirection: 'column', gap: '8px' }
                                    }, Object.entries(tool.inputSchema.properties).map(([paramName, paramSchema]) => {
                                        const fieldError = validationErrors[tool.name] && validationErrors[tool.name][paramName];
                                        return React.createElement('div', {
                                            key: paramName,
                                            style: { display: 'flex', flexDirection: 'column' }
                                        }, [
                                            React.createElement('label', {
                                                key: 'label',
                                                style: {
                                                    fontSize: '12px',
                                                    color: fieldError ? '#d32f2f' : '#555',
                                                    marginBottom: '4px',
                                                    fontFamily: 'monospace'
                                                }
                                            }, `${paramName}${tool.inputSchema.required && tool.inputSchema.required.includes(paramName) ? ' *' : ''} (${paramSchema.type || 'any'})`),
                                            React.createElement('input', {
                                                key: 'input',
                                                type: 'text',
                                                placeholder: paramSchema.description || `Enter ${paramName}`,
                                                style: {
                                                    padding: '6px 8px',
                                                    border: fieldError ? '2px solid #f44336' : '1px solid #ccc',
                                                    borderRadius: '4px',
                                                    fontSize: '12px',
                                                    fontFamily: 'monospace',
                                                    transition: 'border-color 0.2s'
                                                },
                                                value: (toolInputs[tool.name] && toolInputs[tool.name][paramName]) || '',
                                                onChange: (e) => updateToolInput(tool.name, paramName, e.target.value)
                                            }),
                                            fieldError ? React.createElement('div', {
                                                key: 'field-error',
                                                style: {
                                                    fontSize: '11px',
                                                    color: '#d32f2f',
                                                    marginTop: '2px'
                                                }
                                            }, fieldError) : null
                                        ]);
                                    }))
                                ]) : null,

                                // Output schema section
                                tool.outputSchema ? React.createElement('div', {
                                    key: 'output-schema-section',
                                    style: { marginBottom: '16px' }
                                }, [
                                    React.createElement('div', {
                                        key: 'output-schema-title',
                                        style: {
                                            fontSize: '13px',
                                            fontWeight: '600',
                                            color: '#333',
                                            marginBottom: '8px'
                                        }
                                    }, 'Output Schema:'),
                                    React.createElement('div', {
                                        key: 'output-schema-content',
                                        style: {
                                            background: '#f8f9fa',
                                            border: '1px solid #e0e0e0',
                                            borderRadius: '4px',
                                            padding: '12px',
                                            fontSize: '11px',
                                            fontFamily: 'monospace',
                                            whiteSpace: 'pre-wrap',
                                            maxHeight: '150px',
                                            overflow: 'auto',
                                            color: '#333'
                                        }
                                    }, JSON.stringify(tool.outputSchema, null, 2))
                                ]) : null,

                                // Run button
                                React.createElement('button', {
                                    key: 'run-button',
                                    style: {
                                        background: '#1976d2',
                                        color: 'white',
                                        border: 'none',
                                        padding: '8px 16px',
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        fontSize: '12px',
                                        fontWeight: '600',
                                        fontFamily: 'system-ui, -apple-system, sans-serif !important',
                                        marginBottom: toolResult ? '16px' : '0'
                                    },
                                    onClick: () => callTool(tool.name)
                                }, 'Run Tool'),

                                // Results section
                                toolResult ? React.createElement('div', {
                                    key: 'results-section'
                                }, [
                                    React.createElement('div', {
                                        key: 'results-header',
                                        style: {
                                            fontSize: '13px',
                                            fontWeight: '600',
                                            color: '#333',
                                            marginBottom: '8px'
                                        }
                                    }, `Result (${toolResult.timestamp}):`),
                                    React.createElement('div', {
                                        key: 'results-content',
                                        style: {
                                            background: toolResult.success ? '#e8f5e8' : '#ffebee',
                                            border: `1px solid ${toolResult.success ? '#4caf50' : '#f44336'}`,
                                            borderRadius: '4px',
                                            padding: '12px',
                                            fontSize: '12px',
                                            fontFamily: 'monospace',
                                            whiteSpace: 'pre-wrap',
                                            maxHeight: '200px',
                                            overflow: 'auto'
                                        }
                                    }, toolResult.success ? (() => {
                                        // Smart formatting based on result type
                                        const result = toolResult.result;
                                        if (typeof result === 'string') {
                                            return result;
                                        } else if (typeof result === 'boolean' || typeof result === 'number') {
                                            return String(result);
                                        } else {
                                            return JSON.stringify(result, null, 2);
                                        }
                                    })() : toolResult.error)
                                ]) : null
                            ]) : null
                        ]);
                    }))
                        ]) : null,

                        // History section (visible on history tab)
                        activeTab === 'history' ? React.createElement('div', {
                        key: 'history-section',
                        style: {}
                    }, callHistory.length > 0 ? [
                        React.createElement('div', {
                            key: 'history-list',
                            style: {
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '8px'
                            }
                        }, callHistory.slice(0, 10).map((historyItem, index) =>
                            React.createElement('div', {
                                key: historyItem.id,
                                style: {
                                    background: historyItem.status === 'success' ? '#e8f5e8' :
                                               historyItem.status === 'error' ? '#ffebee' : '#fff3e0',
                                    border: `1px solid ${historyItem.status === 'success' ? '#4caf50' :
                                                         historyItem.status === 'error' ? '#f44336' : '#ff9800'}`,
                                    borderRadius: '4px',
                                    padding: '8px 12px',
                                    fontSize: '12px'
                                }
                            }, [
                                React.createElement('div', {
                                    key: 'header',
                                    style: {
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center',
                                        marginBottom: '4px'
                                    }
                                }, [
                                    React.createElement('span', {
                                        key: 'tool-name',
                                        style: {
                                            fontWeight: '600',
                                            fontFamily: 'monospace',
                                            color: '#1976d2'
                                        }
                                    }, historyItem.toolName),
                                    React.createElement('span', {
                                        key: 'timestamp',
                                        style: {
                                            fontSize: '11px',
                                            color: '#666'
                                        }
                                    }, historyItem.timestamp)
                                ]),
                                Object.keys(historyItem.inputs).length > 0 ? React.createElement('div', {
                                    key: 'inputs',
                                    style: { marginBottom: '4px' }
                                }, [
                                    React.createElement('div', {
                                        key: 'inputs-label',
                                        style: {
                                            fontSize: '11px',
                                            fontWeight: '600',
                                            color: '#555',
                                            marginBottom: '2px'
                                        }
                                    }, 'Inputs:'),
                                    React.createElement('div', {
                                        key: 'inputs-content',
                                        style: {
                                            fontFamily: 'monospace',
                                            fontSize: '11px',
                                            color: '#666',
                                            backgroundColor: 'rgba(255,255,255,0.5)',
                                            padding: '4px 6px',
                                            borderRadius: '2px'
                                        }
                                    }, JSON.stringify(historyItem.inputs, null, 1))
                                ]) : null,
                                historyItem.result ? React.createElement('div', {
                                    key: 'result',
                                    style: {}
                                }, [
                                    React.createElement('div', {
                                        key: 'result-label',
                                        style: {
                                            fontSize: '11px',
                                            fontWeight: '600',
                                            color: '#555',
                                            marginBottom: '2px'
                                        }
                                    }, 'Output:'),
                                    React.createElement('div', {
                                        key: 'result-content',
                                        style: {
                                            fontFamily: 'monospace',
                                            fontSize: '11px',
                                            color: '#666',
                                            backgroundColor: 'rgba(255,255,255,0.5)',
                                            padding: '4px 6px',
                                            borderRadius: '2px',
                                            maxHeight: '100px',
                                            overflow: 'auto'
                                        }
                                    }, typeof historyItem.result === 'string' ? historyItem.result : JSON.stringify(historyItem.result, null, 1))
                                ]) : historyItem.error ? React.createElement('div', {
                                    key: 'error',
                                    style: {}
                                }, [
                                    React.createElement('div', {
                                        key: 'error-label',
                                        style: {
                                            fontSize: '11px',
                                            fontWeight: '600',
                                            color: '#d32f2f',
                                            marginBottom: '2px'
                                        }
                                    }, 'Error:'),
                                    React.createElement('div', {
                                        key: 'error-content',
                                        style: {
                                            fontFamily: 'monospace',
                                            fontSize: '11px',
                                            color: '#d32f2f',
                                            backgroundColor: 'rgba(255,255,255,0.5)',
                                            padding: '4px 6px',
                                            borderRadius: '2px'
                                        }
                                    }, historyItem.error)
                                ]) : React.createElement('div', {
                                    key: 'pending',
                                    style: {
                                        fontSize: '11px',
                                        color: '#ff9800',
                                        fontStyle: 'italic'
                                    }
                                }, 'Running...')
                            ])
                        ))
                    ] : [
                        React.createElement('div', {
                            key: 'history-empty',
                            style: {
                                padding: '40px 24px',
                                textAlign: 'center',
                                color: '#999',
                                fontSize: '13px'
                            }
                        }, 'No calls yet. Execute a tool to see history here.')
                    ]) : null
                ])
                ])
                ])
            },

            // Add CSS to hide graphiql-sessions tab on plugin load
            onMount: function() {
                // Hide the graphiql-sessions tab to make MCP plugin full screen
                const style = document.createElement('style');
                style.textContent = `
                    /* Hide graphiql-sessions tab to make MCP plugin full screen */
                    .graphiql-tabs button[title*="session"],
                    .graphiql-tabs button[data-tab="sessions"],
                    .graphiql-tabs div[title*="session"],
                    .graphiql-tabs div[data-tab="sessions"] {
                        display: none !important;
                    }
                `;
                if (!document.getElementById('mcp-plugin-styles')) {
                    style.id = 'mcp-plugin-styles';
                    document.head.appendChild(style);
                }
            }
        };