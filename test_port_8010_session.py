#!/usr/bin/env python3
"""
Test the exact session flow that the browser should use for port 8010
"""

import httpx
import json
import asyncio

async def test_port_8010_session():
    """Test session management on port 8010 exactly like the browser does."""

    url = "http://localhost:8010/mcp"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    print(f"🧪 Testing MCP server at {url}")

    async with httpx.AsyncClient() as client:

        # Step 1: Try tools/list directly (should fail with session error)
        print("\n1️⃣ Testing direct tools/list (should fail)...")
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }

            response = await client.post(url, headers=headers, json=payload)
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            print(f"Response: {response.text}")

            # Check for session ID in response
            session_id = response.headers.get('mcp-session-id')
            if session_id:
                print(f"🔑 Got session ID: {session_id}")

                # Step 2: Initialize session
                print("\n2️⃣ Initializing session...")
                init_payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "roots": {
                                "listChanged": False
                            }
                        },
                        "clientInfo": {
                            "name": "MCP Web Inspector Test",
                            "version": "1.0.0"
                        }
                    }
                }

                # Include session ID in headers
                session_headers = headers.copy()
                session_headers['mcp-session-id'] = session_id

                init_response = await client.post(url, headers=session_headers, json=init_payload)
                print(f"Init Status: {init_response.status_code}")
                print(f"Init Response: {init_response.text[:300]}...")

                if init_response.status_code == 200:
                    # Step 3: Now try tools/list with session
                    print("\n3️⃣ Trying tools/list with session...")
                    tools_payload = {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/list",
                        "params": {}
                    }

                    tools_response = await client.post(url, headers=session_headers, json=tools_payload)
                    print(f"Tools Status: {tools_response.status_code}")
                    if tools_response.status_code == 200:
                        print("✅ SUCCESS: Tools/list works with session!")

                        # Parse response
                        text = tools_response.text
                        if text.startswith('event: message'):
                            lines = text.split('\n')
                            for line in lines:
                                if line.startswith('data: '):
                                    try:
                                        data = json.loads(line[6:])
                                        if data.get('result', {}).get('tools'):
                                            tools = data['result']['tools']
                                            print(f"Found {len(tools)} tools:")
                                            for tool in tools:
                                                print(f"  • {tool['name']}: {tool['description']}")
                                        break
                                    except:
                                        pass
                    else:
                        print(f"❌ Tools/list failed: {tools_response.text}")
                else:
                    print(f"❌ Session initialization failed: {init_response.text}")
            else:
                print("❌ No session ID in response headers")

        except Exception as e:
            print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_port_8010_session())