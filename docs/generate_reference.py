"""Generate API reference documentation from graphql-mcp source code."""

import inspect
import sys
import textwrap
from pathlib import Path
from typing import Any, get_type_hints

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import docstring_parser

from graphql_mcp import GraphQLMCP, mcp_hidden
from graphql_mcp.server import (
    add_tools_from_schema,
    add_tools_from_schema_with_remote,
    add_query_tools_from_schema,
    add_mutation_tools_from_schema,
)
from graphql_mcp.remote import (
    RemoteGraphQLClient,
    fetch_remote_schema,
    fetch_remote_schema_sync,
)


def _format_type(annotation: Any) -> str:
    """Format a type annotation as a readable string."""
    if annotation is inspect.Parameter.empty:
        return ""

    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", None)

    # Handle Union types (Optional)
    if origin is type(None):
        return "None"

    # typing.Optional / Union
    import typing
    if origin is typing.Union:
        if args and len(args) == 2 and type(None) in args:
            inner = [a for a in args if a is not type(None)][0]
            return f"Optional[{_format_type(inner)}]"
        return " | ".join(_format_type(a) for a in args)

    # typing.Literal
    if origin is typing.Literal:
        vals = ", ".join(repr(a) for a in args)
        return f'Literal[{vals}]'

    # list, dict, etc.
    if origin is list:
        if args:
            return f"list[{_format_type(args[0])}]"
        return "list"
    if origin is dict:
        if args:
            return f"Dict[{_format_type(args[0])}, {_format_type(args[1])}]"
        return "Dict"

    # Plain class
    if isinstance(annotation, type):
        return annotation.__name__

    return str(annotation).replace("typing.", "")


def _format_default(param: inspect.Parameter) -> str:
    """Format a parameter default value."""
    if param.default is inspect.Parameter.empty:
        return ""
    if param.default is None:
        return "None"
    if isinstance(param.default, str):
        return repr(param.default)
    if isinstance(param.default, bool):
        return str(param.default)
    return str(param.default)


def _render_signature(func: Any, name: str, is_classmethod: bool = False) -> str:
    """Render a function signature as a Python code block."""
    sig = inspect.signature(func)
    params = []

    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue

        type_str = _format_type(param.annotation)
        default_str = _format_default(param)

        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            entry = f"*args"
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            entry = f"**kwargs"
        else:
            entry = pname
            if type_str:
                entry += f": {type_str}"
            if default_str:
                entry += f" = {default_str}"

        params.append(entry)

    # Return type
    ret = sig.return_annotation
    ret_str = ""
    if ret is not inspect.Signature.empty:
        ret_str = f" -> {_format_type(ret)}"

    param_str = ",\n    ".join(params)
    if param_str:
        param_str = f"\n    {param_str},\n"

    return f"```python\n{name}({param_str}){ret_str}\n```"


def _render_param_table(parsed: docstring_parser.Docstring, sig: inspect.Signature) -> str:
    """Render a parameter table from parsed docstring and signature."""
    rows = []

    # Build a map of docstring param descriptions
    doc_params = {p.arg_name: p.description or "" for p in parsed.params}

    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue

        type_str = _format_type(param.annotation)
        default_str = _format_default(param)

        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            desc = doc_params.get("*args", doc_params.get("args", ""))
            rows.append(f"| `*args` | | | {_clean_desc(desc)} |")
            continue
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            desc = doc_params.get("**kwargs", doc_params.get("kwargs", ""))
            rows.append(f"| `**kwargs` | | | {_clean_desc(desc)} |")
            continue

        if not default_str and param.default is inspect.Parameter.empty:
            default_display = "*required*"
        else:
            default_display = f"`{default_str}`" if default_str else "`None`"

        desc = doc_params.get(pname, "")
        type_display = f"`{type_str}`" if type_str else ""

        rows.append(f"| `{pname}` | {type_display} | {default_display} | {_clean_desc(desc)} |")

    if not rows:
        return ""

    header = "| Parameter | Type | Default | Description |\n|-----------|------|---------|-------------|"
    return header + "\n" + "\n".join(rows)


def _clean_desc(desc: str) -> str:
    """Clean a description for table cell use (single line, no pipes)."""
    if not desc:
        return ""
    # Collapse to single line
    result = " ".join(desc.split())
    # Escape pipes for markdown tables
    result = result.replace("|", "\\|")
    return result


def _render_returns(parsed: docstring_parser.Docstring) -> str:
    """Render a Returns section."""
    if parsed.returns and parsed.returns.description:
        type_name = parsed.returns.type_name or ""
        raw_desc = parsed.returns.description
        # Truncate at known section markers that docstring_parser concatenates
        for sep in ["\nNote:", "\nSecurity Note:", "\nSecurity Considerations:"]:
            idx = raw_desc.find(sep)
            if idx != -1:
                raw_desc = raw_desc[:idx]
                break
        desc = _clean_desc(raw_desc)
        if not desc.endswith("."):
            desc += "."
        if type_name:
            return f"**Returns:** `{type_name}` — {desc}"
        return f"**Returns:** {desc}"
    return ""


def _render_method(func: Any, cls_name: str, method_name: str,
                   is_classmethod: bool = False) -> str:
    """Render a complete method documentation section."""
    lines = []

    # Heading
    display_name = f"{cls_name}.{method_name}"
    lines.append(f"### `{display_name}`")
    lines.append("")

    # Signature
    sig_name = display_name
    lines.append(_render_signature(func, sig_name, is_classmethod))
    lines.append("")

    # Parse docstring
    doc = inspect.getdoc(func) or ""
    parsed = docstring_parser.parse(doc)

    # Description (short + long)
    desc_parts = []
    if parsed.short_description:
        desc_parts.append(parsed.short_description)
    if parsed.long_description:
        desc_parts.append(parsed.long_description)
    if desc_parts:
        lines.append(" ".join(desc_parts))
        lines.append("")

    # Parameter table
    sig = inspect.signature(func)
    table = _render_param_table(parsed, sig)
    if table:
        lines.append(table)
        lines.append("")

    # Returns
    returns = _render_returns(parsed)
    if returns:
        lines.append(returns)
        lines.append("")

    # Extra sections (Security Considerations, Notes, etc.)
    for meta in parsed.meta:
        if hasattr(meta, "args") and meta.args and meta.args[0] not in ("param", "returns", "raises"):
            section_name = " ".join(meta.args).title()
            lines.append(f"> **{section_name}:** {_clean_desc(meta.description)}")
            lines.append("")

    return "\n".join(lines)


def _render_function(func: Any, func_name: str) -> str:
    """Render a standalone function documentation section."""
    lines = []

    lines.append(f"### `{func_name}`")
    lines.append("")

    lines.append(_render_signature(func, func_name))
    lines.append("")

    doc = inspect.getdoc(func) or ""
    parsed = docstring_parser.parse(doc)

    desc_parts = []
    if parsed.short_description:
        desc_parts.append(parsed.short_description)
    if parsed.long_description:
        desc_parts.append(parsed.long_description)
    if desc_parts:
        lines.append(" ".join(desc_parts))
        lines.append("")

    sig = inspect.signature(func)
    table = _render_param_table(parsed, sig)
    if table:
        lines.append(table)
        lines.append("")

    returns = _render_returns(parsed)
    if returns:
        lines.append(returns)
        lines.append("")

    return "\n".join(lines)


def _render_class(cls: type, cls_name: str, methods: list[tuple[str, Any, bool]]) -> str:
    """Render a class with its methods."""
    lines = []

    # Class docstring
    doc = inspect.getdoc(cls) or ""
    if doc:
        lines.append(doc)
        lines.append("")

    for method_name, method_func, is_cm in methods:
        lines.append(_render_method(method_func, cls_name, method_name, is_cm))

    return "\n".join(lines)


def generate() -> str:
    """Generate the complete API reference markdown."""
    sections = []

    # Header
    sections.append(textwrap.dedent("""\
        ---
        title: "API Reference"
        ---

        # API Reference

        Auto-generated from source. See the [guides](/getting-started) for usage examples.

        ## `GraphQLMCP`

        ```python
        from graphql_mcp import GraphQLMCP
        ```

        The main class for creating MCP servers from GraphQL schemas. Extends [FastMCP](https://gofastmcp.com/).
    """).rstrip())

    # GraphQLMCP methods
    sections.append(_render_method(
        GraphQLMCP.__init__, "GraphQLMCP", "__init__"))

    # from_api (conditional)
    if hasattr(GraphQLMCP, "from_api"):
        sections.append(_render_method(
            GraphQLMCP.from_api, "GraphQLMCP", "from_api", is_classmethod=True))
    else:
        sections.append(textwrap.dedent("""\
            ### `GraphQLMCP.from_api`

            > Requires `graphql-api` to be installed. Not available in current environment.
        """).rstrip())

    sections.append(_render_method(
        GraphQLMCP.from_remote_url, "GraphQLMCP", "from_remote_url", is_classmethod=True))

    sections.append(_render_method(
        GraphQLMCP.http_app, "GraphQLMCP", "http_app"))

    # mcp_hidden
    sections.append(textwrap.dedent("""\
        ## `mcp_hidden`

        ```python
        from graphql_mcp import mcp_hidden
        ```

        A `SchemaDirective` that marks GraphQL arguments as hidden from MCP tools. The argument remains visible in the GraphQL schema but is not exposed as an MCP tool parameter.

        Requires `graphql-api` to be installed. When `graphql-api` is not available, `mcp_hidden` is `None`.

        See [Customization](/customization#mcp-hidden) for usage examples.
    """).rstrip())

    # Low-Level API
    sections.append(textwrap.dedent("""\
        ## Low-Level API

        These functions are importable from `graphql_mcp.server` and `graphql_mcp.remote` but are not part of the primary public interface. Use them when you need fine-grained control over tool registration.
    """).rstrip())

    sections.append(_render_function(add_tools_from_schema, "add_tools_from_schema"))
    sections.append(_render_function(add_tools_from_schema_with_remote, "add_tools_from_schema_with_remote"))
    sections.append(_render_function(add_query_tools_from_schema, "add_query_tools_from_schema"))
    sections.append(_render_function(add_mutation_tools_from_schema, "add_mutation_tools_from_schema"))

    # RemoteGraphQLClient
    sections.append(textwrap.dedent("""\
        ### `RemoteGraphQLClient`

        ```python
        from graphql_mcp.remote import RemoteGraphQLClient
        ```
    """).rstrip())

    sections.append(_render_method(
        RemoteGraphQLClient.__init__, "RemoteGraphQLClient", "__init__"))

    sections.append(_render_method(
        RemoteGraphQLClient.execute, "RemoteGraphQLClient", "execute"))

    sections.append(_render_method(
        RemoteGraphQLClient.execute_with_token, "RemoteGraphQLClient", "execute_with_token"))

    # fetch functions
    sections.append(_render_function(fetch_remote_schema, "fetch_remote_schema"))
    sections.append(_render_function(fetch_remote_schema_sync, "fetch_remote_schema_sync"))

    return "\n\n".join(sections) + "\n"


if __name__ == "__main__":
    output_path = Path(__file__).parent / "public" / "api-reference.md"
    content = generate()
    output_path.write_text(content)
    print(f"Generated: {output_path} ({len(content)} bytes)")
