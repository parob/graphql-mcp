"""Tests for nested GraphQL queries via remote MCP tools."""

import pytest
from unittest.mock import AsyncMock, patch
from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString, GraphQLInt, GraphQLArgument

from graphql_mcp.server import GraphQLMCP, add_tools_from_schema_with_remote
from graphql_mcp.remote import RemoteGraphQLClient
from fastmcp import FastMCP
from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast


def get_result_text(result):
    """Helper function to get text from result"""
    if hasattr(result, 'content'):
        return cast(TextContent, result.content[0]).text
    else:
        return cast(TextContent, result[0]).text


@pytest.mark.asyncio
async def test_nested_measurement_manager_query():
    """Test nested GraphQL query like measurementManager { getSensors { totalCount } }"""

    # Create a schema that matches the nested structure
    # NOTE: Nested tools are only created when nested fields have arguments
    sensor_data_type = GraphQLObjectType(
        "SensorData",
        fields={
            "totalCount": GraphQLField(GraphQLInt, description="Total number of sensors")
        }
    )

    measurement_manager_type = GraphQLObjectType(
        "MeasurementManager",
        fields={
            "getSensors": GraphQLField(
                sensor_data_type,
                args={
                    "limit": GraphQLArgument(GraphQLInt, description="Maximum sensors to return")
                },
                description="Get sensor information"
            )
        }
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            "Query",
            fields={
                "measurementManager": GraphQLField(
                    measurement_manager_type,
                    description="Access to measurement manager"
                )
            }
        )
    )

    # Mock the remote client
    mock_client = AsyncMock(spec=RemoteGraphQLClient)
    mock_client.execute_with_token = AsyncMock()

    # Create MCP server with the schema and remote client
    mcp_server = FastMCP(name="TestNestedServer")
    add_tools_from_schema_with_remote(schema, mcp_server, mock_client)

    # Mock the expected nested response
    mock_client.execute_with_token.return_value = {
        "measurementManager": {
            "getSensors": {
                "totalCount": 42
            }
        }
    }

    async with Client(mcp_server) as client:
        # List available tools - should include nested tool
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]

        # Should have both the root tool and the nested tool (because getSensors has args)
        assert "measurement_manager" in tool_names
        assert "measurement_manager_get_sensors" in tool_names

        # Test the root measurementManager tool
        result = await client.call_tool("measurement_manager", {})
        response_data = get_result_text(result)
        # Should return the nested data
        assert "getSensors" in str(response_data)

        # Test the nested measurementManager_getSensors tool
        result = await client.call_tool("measurement_manager_get_sensors", {"limit": 10})
        response_data = get_result_text(result)
        assert "totalCount" in str(response_data) or "42" in str(response_data)

        # Verify the remote client was called correctly
        assert mock_client.execute_with_token.call_count >= 1

        # Check that the generated query includes the nested structure
        call_args = mock_client.execute_with_token.call_args_list[0]
        query = call_args[0][0]
        assert "measurementManager" in query
        assert "getSensors" in query


@pytest.mark.asyncio
async def test_nested_query_with_arguments():
    """Test nested GraphQL query with arguments at multiple levels"""

    # Create a more complex nested schema with arguments
    sensor_type = GraphQLObjectType(
        "Sensor",
        fields={
            "id": GraphQLField(GraphQLString),
            "name": GraphQLField(GraphQLString),
            "value": GraphQLField(GraphQLInt)
        }
    )

    sensor_data_type = GraphQLObjectType(
        "SensorData",
        fields={
            "totalCount": GraphQLField(GraphQLInt),
            "sensors": GraphQLField(
                sensor_type,
                args={
                    "sensorId": GraphQLArgument(GraphQLString, description="ID of specific sensor")
                },
                description="Get specific sensor by ID"
            )
        }
    )

    measurement_manager_type = GraphQLObjectType(
        "MeasurementManager",
        fields={
            "getSensors": GraphQLField(
                sensor_data_type,
                args={
                    "limit": GraphQLArgument(GraphQLInt, description="Maximum number of sensors"),
                    "type": GraphQLArgument(GraphQLString, description="Type of sensors to retrieve")
                },
                description="Get sensor information with filtering"
            )
        }
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            "Query",
            fields={
                "measurementManager": GraphQLField(
                    measurement_manager_type,
                    args={
                        "managerId": GraphQLArgument(GraphQLString, description="Manager instance ID")
                    },
                    description="Access to measurement manager"
                )
            }
        )
    )

    # Mock the remote client
    mock_client = AsyncMock(spec=RemoteGraphQLClient)
    mock_client.execute_with_token = AsyncMock()

    # Create MCP server
    mcp_server = FastMCP(name="TestComplexNestedServer")
    add_tools_from_schema_with_remote(schema, mcp_server, mock_client)

    # Mock nested response with arguments
    mock_client.execute_with_token.return_value = {
        "measurementManager": {
            "getSensors": {
                "sensors": {
                    "id": "sensor-123",
                    "name": "Temperature Sensor",
                    "value": 23
                }
            }
        }
    }

    async with Client(mcp_server) as client:
        # List available tools
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]

        # Should have the deeply nested tool with all arguments
        assert "measurement_manager_get_sensors_sensors" in tool_names

        # Test the deeply nested tool with arguments
        result = await client.call_tool("measurement_manager_get_sensors_sensors", {
            "measurementManager_managerId": "mgr-001",
            "getSensors_limit": 10,
            "getSensors_type": "temperature",
            "sensorId": "sensor-123"
        })

        response_data = get_result_text(result)
        # Should return the sensor data
        assert "sensor-123" in str(response_data) or "Temperature Sensor" in str(response_data) or "23" in str(response_data)

        # Verify the query was constructed correctly with all arguments
        call_args = mock_client.execute_with_token.call_args[0]
        query = call_args[0]
        variables = call_args[1]

        # Check the query structure
        assert "measurementManager" in query
        assert "getSensors" in query
        assert "sensors" in query
        assert "managerId" in query
        assert "limit" in query
        assert "type" in query
        assert "sensorId" in query

        # Check the variables were passed correctly
        assert variables["measurementManager_managerId"] == "mgr-001"
        assert variables["getSensors_limit"] == 10
        assert variables["getSensors_type"] == "temperature"
        assert variables["sensorId"] == "sensor-123"


@pytest.mark.asyncio
async def test_measurement_manager_from_remote_url():
    """Test creating a server from remote URL that would support the measurement manager pattern"""

    # Mock the schema fetch to return our measurement manager schema
    with patch('graphql_mcp.remote.fetch_remote_schema_sync') as mock_fetch:
        # Create the expected schema
        sensor_data_type = GraphQLObjectType(
            "SensorData",
            fields={
                "totalCount": GraphQLField(GraphQLInt)
            }
        )

        measurement_manager_type = GraphQLObjectType(
            "MeasurementManager",
            fields={
                "getSensors": GraphQLField(
                    sensor_data_type,
                    args={
                        "limit": GraphQLArgument(GraphQLInt, description="Maximum sensors")
                    }
                )
            }
        )

        mock_schema = GraphQLSchema(
            query=GraphQLObjectType(
                "Query",
                fields={
                    "measurementManager": GraphQLField(measurement_manager_type)
                }
            )
        )
        mock_fetch.return_value = mock_schema

        # Create server from remote URL
        server = GraphQLMCP.from_remote_url(
            url="http://measurement.example.com/graphql",
            name="Measurement Manager API"
        )

        # Verify the schema fetch was called
        mock_fetch.assert_called_once()

        # The server should be a FastMCP instance with tools
        assert isinstance(server, FastMCP)

        # Test the created server has the expected tools
        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]

            # Should have both root and nested tools
            assert "measurement_manager" in tool_names
            assert "measurement_manager_get_sensors" in tool_names


@pytest.mark.asyncio
async def test_real_world_nested_query_pattern():
    """Test a realistic nested query pattern that developers commonly use"""

    # This simulates a common pattern like:
    # query {
    #   user {
    #     profile {
    #       settings {
    #         notifications { enabled }
    #       }
    #     }
    #   }
    # }

    notification_settings_type = GraphQLObjectType(
        "NotificationSettings",
        fields={
            "enabled": GraphQLField(GraphQLString),
            "frequency": GraphQLField(GraphQLString)
        }
    )

    user_settings_type = GraphQLObjectType(
        "UserSettings",
        fields={
            "notifications": GraphQLField(
                notification_settings_type,
                args={
                    "type": GraphQLArgument(GraphQLString, description="Notification type filter")
                }
            ),
            "theme": GraphQLField(GraphQLString)
        }
    )

    user_profile_type = GraphQLObjectType(
        "UserProfile",
        fields={
            "settings": GraphQLField(user_settings_type),
            "name": GraphQLField(GraphQLString),
            "email": GraphQLField(GraphQLString)
        }
    )

    user_type = GraphQLObjectType(
        "User",
        fields={
            "profile": GraphQLField(user_profile_type),
            "id": GraphQLField(GraphQLString)
        }
    )

    schema = GraphQLSchema(
        query=GraphQLObjectType(
            "Query",
            fields={
                "user": GraphQLField(
                    user_type,
                    args={
                        "id": GraphQLArgument(GraphQLString, description="User ID")
                    }
                )
            }
        )
    )

    # Mock remote client
    mock_client = AsyncMock(spec=RemoteGraphQLClient)
    mock_client.execute_with_token = AsyncMock()

    # Create MCP server
    mcp_server = FastMCP(name="TestUserNestedServer")
    add_tools_from_schema_with_remote(schema, mcp_server, mock_client)

    # Mock deeply nested response
    mock_client.execute_with_token.return_value = {
        "user": {
            "profile": {
                "settings": {
                    "notifications": {
                        "enabled": "true",
                        "frequency": "daily"
                    }
                }
            }
        }
    }

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]

        # Should have the deeply nested tool
        assert "user_profile_settings_notifications" in tool_names

        # Test the deeply nested tool
        result = await client.call_tool("user_profile_settings_notifications", {
            "user_id": "user-123",
            "type": "email"
        })

        response_data = get_result_text(result)
        assert "enabled" in str(response_data) or "true" in str(response_data)

        # Verify correct query generation
        call_args = mock_client.execute_with_token.call_args[0]
        query = call_args[0]
        variables = call_args[1]

        # Should include the full nested path
        assert "user" in query
        assert "profile" in query
        assert "settings" in query
        assert "notifications" in query

        # Should include arguments at the right levels
        assert variables["user_id"] == "user-123"
        assert variables["type"] == "email"
