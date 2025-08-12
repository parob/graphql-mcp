#!/usr/bin/env python3
"""
Example demonstrating nested GraphQL queries via MCP tools.

This example shows how nested GraphQL structures like:

query MeasurementManager {
    measurementManager {
        getSensors {
            totalCount
        }
    }
}

Are converted to MCP tools that can be called individually.
"""

import asyncio
from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString, GraphQLInt, GraphQLArgument
from graphql_mcp.server import GraphQLMCPServer
from fastmcp.client import Client


async def create_measurement_manager_example():
    """Creates a measurement manager-style nested schema example."""
    
    # Define the nested types
    sensor_data_type = GraphQLObjectType(
        "SensorData",
        fields={
            "totalCount": GraphQLField(GraphQLInt, description="Total number of sensors"),
            "sensors": GraphQLField(
                GraphQLString,  # Simplified for demo
                args={
                    "sensorId": GraphQLArgument(GraphQLString, description="Specific sensor ID")
                },
                description="Get specific sensor data"
            )
        }
    )
    
    measurement_manager_type = GraphQLObjectType(
        "MeasurementManager", 
        fields={
            "getSensors": GraphQLField(
                sensor_data_type,
                args={
                    "limit": GraphQLArgument(GraphQLInt, description="Maximum sensors to return"),
                    "type": GraphQLArgument(GraphQLString, description="Type filter")
                },
                description="Get sensor information with filtering"
            ),
            "getStatus": GraphQLField(
                GraphQLString,
                description="Get manager status"
            )
        }
    )
    
    # Create the root schema
    schema = GraphQLSchema(
        query=GraphQLObjectType(
            "Query",
            fields={
                "measurementManager": GraphQLField(
                    measurement_manager_type,
                    args={
                        "managerId": GraphQLArgument(GraphQLString, description="Manager ID")
                    },
                    description="Access to measurement manager instance"
                )
            }
        )
    )
    
    # Create MCP server from schema
    server = GraphQLMCPServer.from_schema(schema, name="Nested Query Demo")
    
    return server, schema


async def demonstrate_nested_tools():
    """Demonstrates the nested tools created from the schema."""
    
    print("🔧 Creating measurement manager schema...")
    server, schema = await create_measurement_manager_example()
    
    print("📡 Starting MCP client...")
    async with Client(server) as client:
        # List all available tools
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]
        
        print("🛠️  Available MCP tools:")
        for name in sorted(tool_names):
            print(f"   • {name}")
        
        print("\n📊 The original nested GraphQL query:")
        print("""   query MeasurementManager {
       measurementManager(managerId: "mgr-001") {
           getSensors(limit: 10, type: "temperature") {
               totalCount
               sensors(sensorId: "temp-01") 
           }
       }
   }""")
        
        print("\n🔄 Can now be called as individual MCP tools:")
        print("   1. measurement_manager(managerId='mgr-001')")
        print("   2. measurement_manager_get_sensors(measurementManager_managerId='mgr-001', limit=10, type='temperature')")
        print("   3. measurement_manager_get_sensors_sensors(measurementManager_managerId='mgr-001', getSensors_limit=10, getSensors_type='temperature', sensorId='temp-01')")
        
        print("\n🎯 Nested tools automatically created:")
        nested_tools = [name for name in tool_names if '_' in name and name.count('_') > 1]
        for tool in nested_tools:
            print(f"   • {tool}")
            
        print("\n✨ These tools represent the nested GraphQL field chains!")
        print("   Each tool executes the full nested query path and returns the specific data.")


async def demonstrate_user_profile_nested_pattern():
    """Demonstrates a common user profile nested pattern."""
    
    print("\n" + "="*60)
    print("🧑 User Profile Nested Query Example")
    print("="*60)
    
    # Create nested user profile schema
    notification_settings_type = GraphQLObjectType(
        "NotificationSettings",
        fields={
            "enabled": GraphQLField(GraphQLString),
            "frequency": GraphQLField(GraphQLString),
            "types": GraphQLField(
                GraphQLString,
                args={
                    "category": GraphQLArgument(GraphQLString, description="Notification category")
                }
            )
        }
    )
    
    user_settings_type = GraphQLObjectType(
        "UserSettings", 
        fields={
            "notifications": GraphQLField(
                notification_settings_type,
                args={
                    "scope": GraphQLArgument(GraphQLString, description="Settings scope")
                }
            ),
            "theme": GraphQLField(GraphQLString)
        }
    )
    
    user_profile_type = GraphQLObjectType(
        "UserProfile",
        fields={
            "settings": GraphQLField(user_settings_type),
            "displayName": GraphQLField(GraphQLString),
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
                        "userId": GraphQLArgument(GraphQLString, description="User ID")
                    }
                )
            }
        )
    )
    
    server = GraphQLMCPServer.from_schema(schema, name="User Profile Demo")
    
    async with Client(server) as client:
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]
        
        print("🛠️  Available MCP tools for user profile:")
        for name in sorted(tool_names):
            print(f"   • {name}")
        
        print("\n📊 Original nested GraphQL query:")
        print("""   query UserProfile {
       user(userId: "user-123") {
           profile {
               settings {
                   notifications(scope: "global") {
                       types(category: "email")
                   }
               }
           }
       }
   }""")
        
        print("\n🔄 Equivalent deeply nested MCP tool call:")
        deepest_tool = "user_profile_settings_notifications_types"
        if deepest_tool in tool_names:
            print(f"   {deepest_tool}(")
            print(f"       user_userId='user-123',")
            print(f"       notifications_scope='global',") 
            print(f"       category='email'")
            print(f"   )")


async def main():
    """Main demonstration function."""
    
    print("🚀 GraphQL-MCP Nested Query Demonstration")
    print("=" * 50)
    
    await demonstrate_nested_tools()
    await demonstrate_user_profile_nested_pattern()
    
    print("\n" + "="*60)
    print("✅ Demonstration Complete!")
    print("=" * 60)
    print("🎉 The graphql-mcp library automatically converts nested GraphQL")
    print("   queries into individual MCP tools that can be called directly!")
    print("📚 Each nested field chain with arguments becomes its own tool.")
    print("🔧 This enables fine-grained access to deeply nested GraphQL APIs.")


if __name__ == "__main__":
    asyncio.run(main())