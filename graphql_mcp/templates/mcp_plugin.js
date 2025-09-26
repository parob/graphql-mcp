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
                const [status, setStatus] = React.useState('🔄 Connecting...');
                const [tools, setTools] = React.useState([]);
                const [connected, setConnected] = React.useState(false);
                const [expandedTool, setExpandedTool] = React.useState(null);
                const [toolResults, setToolResults] = React.useState({});
                const [toolInputs, setToolInputs] = React.useState({});
                const [callHistory, setCallHistory] = React.useState([]);

                // MCP Client setup
                const mcpUrl = window.location.origin + '/mcp';
                const client = React.useMemo(() => {
                    // MCP Transport and Client classes (simplified for direct injection)
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

                    return new MCPClient(new MCPHttpTransport(mcpUrl));
                }, [mcpUrl]);

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
                            setStatus(`● Connected (${toolsList.length} tools)`);
                            setConnected(true);
                        } catch (error) {
                            setStatus(`❌ Failed: ${error.message}`);
                            console.error('MCP initialization failed:', error);
                        }
                    }
                    initMCP();
                }, [client]);

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
                };

                const callTool = async (toolName) => {
                    const timestamp = new Date();
                    const args = toolInputs[toolName] || {};

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

                        const errorResult = {
                            success: false,
                            error: error.message,
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
                                ? { ...entry, status: 'error', error: error.message }
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
                    React.createElement('div', {
                        key: 'status',
                        style: {
                            padding: '8px 12px',
                            marginBottom: '12px',
                            borderRadius: '4px',
                            fontSize: '13px',
                            background: connected ? '#e8f4f8' : '#e3f2fd',
                            color: connected ? '#1976d2' : '#1565c0'
                        }
                    }, status)
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
                        // Tools section
                        React.createElement('div', {
                            key: 'tools-section',
                            style: { marginBottom: '24px' }
                        }, [
                            React.createElement('h4', {
                                key: 'tools-title',
                                style: {
                                    margin: '0 0 12px 0',
                                    fontSize: '16px',
                                    fontWeight: '600',
                                    color: '#333'
                                }
                            }, 'Tools'),
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
                                    }, Object.entries(tool.inputSchema.properties).map(([paramName, paramSchema]) =>
                                        React.createElement('div', {
                                            key: paramName,
                                            style: { display: 'flex', flexDirection: 'column' }
                                        }, [
                                            React.createElement('label', {
                                                key: 'label',
                                                style: {
                                                    fontSize: '12px',
                                                    color: '#555',
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
                                                    border: '1px solid #ccc',
                                                    borderRadius: '4px',
                                                    fontSize: '12px',
                                                    fontFamily: 'monospace'
                                                },
                                                value: (toolInputs[tool.name] && toolInputs[tool.name][paramName]) || '',
                                                onChange: (e) => updateToolInput(tool.name, paramName, e.target.value)
                                            })
                                        ])
                                    ))
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
                                    })() : `Error: ${toolResult.error}`)
                                ]) : null
                            ]) : null
                        ]);
                    }))
                        ]),

                        // History section (at the end)
                        callHistory.length > 0 ? React.createElement('div', {
                        key: 'history-section',
                        style: {
                            marginTop: '24px',
                            borderTop: '2px solid #e0e0e0',
                            paddingTop: '16px'
                        }
                    }, [
                        React.createElement('h4', {
                            key: 'history-title',
                            style: {
                                margin: '0 0 12px 0',
                                fontSize: '16px',
                                fontWeight: '600',
                                color: '#333'
                            }
                        }, 'Call History'),
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
                    ]) : null
                    ])
                ]);
            }
        };