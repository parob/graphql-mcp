import enum
import pytest

from fastmcp.client import Client

from graphql_mcp.server import GraphQLMCP


@pytest.mark.asyncio
async def test_graphql_generated_tool_schema_matches_direct_tool_schema():
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class PreferenceKey(str, enum.Enum):
        AI_MODEL = "ai_model"
        TOOLS_ENABLED = "tools_enabled"

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def set_preference_test(self, key: PreferenceKey, value: str) -> bool:
            return True

    # Build the MCP server from the GraphQL API
    mcp_server = GraphQLMCP.from_api(api, name="ParityTest")

    # Add a direct MCP tool with the same signature
    @mcp_server.tool
    def set_preference(key: PreferenceKey, value: str) -> bool:
        """Set a preference"""
        return True

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool_map = {t.name: t for t in tools}

        assert "set_preference_test" in tool_map
        assert "set_preference" in tool_map

        t_graphql = tool_map["set_preference_test"].model_dump()
        t_direct = tool_map["set_preference"].model_dump()

        # Both should define an enum schema for the key parameter
        def assert_has_enum_schema(tool_dump: dict):
            input_schema = tool_dump.get("inputSchema") or {}
            defs = input_schema.get("$defs") or {}
            key_prop = (input_schema.get("properties") or {}).get("key") or {}

            # Accept either $ref to enum def OR inline enum with expected values
            if "$ref" in key_prop:
                # $ref approach (direct MCP tools)
                ref = key_prop["$ref"]
                assert ref.startswith("#/$defs/"), f"unexpected ref target: {ref}"
                enum_name = ref.split("/#$defs/")[-1] if "/#$defs/" in ref else ref.split("#/$defs/")[-1]
                assert enum_name in defs, f"enum def {enum_name} not found in $defs: {defs.keys()}"
                enum_def = defs[enum_name]
                assert enum_def.get("type") == "string", f"enum should be string-typed: {enum_def}"
                assert enum_def.get("enum") == ["ai_model", "tools_enabled"], f"enum values mismatch: {enum_def}"
            elif "enum" in key_prop:
                # Inline enum approach (GraphQL tools with Literal types)
                assert key_prop.get("type") == "string", f"enum should be string-typed: {key_prop}"
                enum_values = key_prop.get("enum", [])
                # Should contain the enum values, and may also contain enum names
                assert "ai_model" in enum_values, f"missing 'ai_model' in enum values: {enum_values}"
                assert "tools_enabled" in enum_values, f"missing 'tools_enabled' in enum values: {enum_values}"
            else:
                assert False, f"key property should have either $ref or enum: {key_prop}"

            # Both args should be required
            required = input_schema.get("required") or []
            assert set(required) == {"key", "value"}, f"required mismatch: {required}"

        assert_has_enum_schema(t_direct)
        assert_has_enum_schema(t_graphql)

        # Both should have wrapped boolean result schema (if FastMCP supports output schemas)
        def assert_has_wrapped_bool_output(tool_dump: dict):
            out = tool_dump.get("outputSchema") or {}
            # Skip this check if FastMCP doesn't generate output schemas in this version
            if not out:
                return
            assert out.get("type") == "object"
            assert out.get("x-fastmcp-wrap-result") is True
            props = out.get("properties") or {}
            assert "result" in props and props["result"].get("type") == "boolean"

        assert_has_wrapped_bool_output(t_direct)
        assert_has_wrapped_bool_output(t_graphql)


def test_graphql_api_enum_behavior():
    """Test to validate graphql-api's enum behavior"""
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type
    class Tag(str, enum.Enum):
        PYTHON = "python"
        JAVASCRIPT = "javascript"
        RUST = "rust"

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def check_tag(self, tag: Tag) -> bool:
            return isinstance(tag, Tag)

    executor = api.executor()

    # Using the proper GraphQL Enum variable with the NAME
    query_enum = """
        query CheckTag($tag: TagEnum!) {
            checkTag(tag: $tag)
        }
    """
    result_enum = executor.execute(query_enum, variables={'tag': Tag.PYTHON.name})
    assert result_enum.data == {'checkTag': True}

    # Schema should contain TagEnum
    schema, _ = api.build_schema()
    assert 'TagEnum' in schema.type_map

    # Field argument type should be NonNull(TagEnum)
    assert schema.query_type is not None
    field = schema.query_type.fields['checkTag']
    arg_type = field.args['tag'].type
    from graphql import GraphQLNonNull, GraphQLEnumType
    assert isinstance(arg_type, GraphQLNonNull)
    assert isinstance(arg_type.of_type, GraphQLEnumType)
    assert arg_type.of_type.name == 'TagEnum'

    # Invalid variable using underlying value string should error
    bad = executor.execute(query_enum, variables={'tag': 'python'})
    assert bad.errors and "does not exist in 'TagEnum'" in bad.errors[0].message
