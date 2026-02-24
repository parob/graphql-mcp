"""Generate API reference documentation from graphql-mcp source code."""

import inspect
import json
import os
import re
import sys
import textwrap
import urllib.request
from datetime import datetime
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


GITHUB_REPO = "parob/graphql-mcp"
PYPI_PACKAGE = "graphql-mcp"


def _parse_version(tag: str) -> tuple[int, ...]:
    """Parse a version tag like '1.7.7' into a sortable tuple."""
    return tuple(int(x) for x in tag.split("."))


def _fetch_releases() -> list[dict] | None:
    """Fetch releases from GitHub API. Returns None on failure."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=100"
    headers = {"Accept": "application/vnd.github+json"}

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Warning: Could not fetch releases from GitHub: {e}")
        return None


def _clean_release_body(body: str) -> str:
    """Strip auto-generated 'Full Changelog' boilerplate from release body."""
    if not body:
        return ""
    # Remove "**Full Changelog**: https://..." lines
    cleaned = re.sub(
        r"\*\*Full Changelog\*\*:\s*https://[^\s]+", "", body
    ).strip()
    return cleaned


def _render_release_history(releases: list[dict]) -> str:
    """Render the release history section from GitHub releases."""
    # Filter out drafts/prereleases and sort by version descending
    valid = [
        r for r in releases
        if not r.get("draft") and not r.get("prerelease")
    ]
    valid.sort(key=lambda r: _parse_version(r["tag_name"]), reverse=True)

    lines = ["---", "", "## Release History"]

    # Group by (major, minor)
    from itertools import groupby

    def minor_key(r):
        parts = _parse_version(r["tag_name"])
        return (parts[0], parts[1])

    for (major, minor), group_iter in groupby(valid, key=minor_key):
        group = list(group_iter)
        lines.append("")
        lines.append(f"### {major}.{minor}")

        for release in group:
            tag = release["tag_name"]
            published = release.get("published_at", "")
            if published:
                dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                date_str = dt.strftime("%B %-d, %Y")
            else:
                date_str = ""

            pypi_url = f"https://pypi.org/project/{PYPI_PACKAGE}/{tag}/"
            gh_url = release.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}")

            date_part = f" — {date_str}" if date_str else ""
            lines.append("")
            lines.append(
                f"**{tag}**{date_part} &nbsp; "
                f"[PyPI]({pypi_url}) · [GitHub]({gh_url})"
            )

            body = _clean_release_body(release.get("body", ""))
            if body:
                lines.append("")
                lines.append(body)

    return "\n".join(lines)


def _get_latest_version(releases: list[dict]) -> str | None:
    """Return the latest non-draft, non-prerelease version string."""
    valid = [
        r["tag_name"] for r in releases
        if not r.get("draft") and not r.get("prerelease")
    ]
    if not valid:
        return None
    valid.sort(key=_parse_version, reverse=True)
    return valid[0]


def _update_index_version(version: str) -> None:
    """Update the homepage version badge with the latest release."""
    index_path = Path(__file__).parent / "public" / "index.md"
    content = index_path.read_text()

    # Replace version in text: "vX.Y.Z"
    content = re.sub(
        r'text: "v[\d.]+"',
        f'text: "v{version}"',
        content,
    )
    # Replace version in PyPI link
    content = re.sub(
        r'link: "https://pypi\.org/project/graphql-mcp/[\d.]+/"',
        f'link: "https://pypi.org/project/graphql-mcp/{version}/"',
        content,
    )
    index_path.write_text(content)
    print(f"Updated index.md version badge to v{version}")


def generate() -> str:
    """Generate the complete API reference markdown."""
    sections = []

    # Header + Concepts
    sections.append(textwrap.dedent("""\
        ---
        title: "API Reference"
        ---

        # API Reference

        ## Concepts

        ### Tool Generation

        Each top-level field in your GraphQL schema becomes an MCP tool:

        - **Query fields** become read tools
        - **Mutation fields** become write tools (when `allow_mutations=True`)

        GraphQL field names (camelCase) are converted to snake_case for tool names: `getUser` becomes `get_user`, `addBook` becomes `add_book`.

        Tool descriptions come from your GraphQL field descriptions (docstrings in graphql-api). Fields without descriptions produce tools with no description.

        If a query and mutation share the same name, the **query takes precedence**.

        #### Nested Tools

        Beyond top-level fields, tools are also generated for nested field paths that have arguments at depth >= 2. For example, `user(id) { posts(limit) }` produces a `user_posts` tool. Parent field arguments are prefixed: `user_posts(user_id, limit)`.

        ### Type Mapping

        | GraphQL | Python | Notes |
        |---------|--------|-------|
        | `String` | `str` | |
        | `Int` | `int` | |
        | `Float` | `float` | |
        | `Boolean` | `bool` | |
        | `ID` | `str` | |
        | `UUID` | `uuid.UUID` | graphql-api only |
        | `DateTime` | `datetime` | graphql-api only |
        | `Date` | `date` | graphql-api only |
        | `JSON` | `dict` | graphql-api only |
        | `Bytes` | `bytes` | graphql-api only |
        | `Type!` (non-null) | `T` | Required parameter |
        | `Type` (nullable) | `Optional[T]` | Optional parameter |
        | `[Type!]!` | `list[T]` | |
        | Enum | `Literal[values]` | Case-insensitive — accepts both names and values |
        | Input Object | Pydantic model | Dynamic model with proper field types |

        ### Selection Sets

        When a tool returns an object type, graphql-mcp builds a selection set automatically:

        - Only scalar fields are selected
        - Nested objects are traversed up to **5 levels deep** (local) or **2 levels deep** (remote)
        - Circular type references are detected and stopped
        - If an object has no scalar fields, `__typename` is returned

        ### Local vs Remote Execution

        **Local** (`GraphQLMCP(schema=...)` or `from_api()`): Tools execute GraphQL directly via graphql-core. Bearer tokens are available through FastMCP's Context.

        **Remote** (`from_remote_url()`): Tools forward queries to the remote server via HTTP. The schema is introspected once at startup. `null` values for array fields are converted to `[]` for MCP validation. Unused variables are removed from queries. Bearer tokens are **not** forwarded unless `forward_bearer_token=True`.

        ---

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

        See [Configuration](/configuration#mcp-hidden) for usage examples.
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

    # Fetch releases and append release history
    releases = _fetch_releases()
    if releases:
        content += "\n" + _render_release_history(releases) + "\n"
        latest = _get_latest_version(releases)
        if latest:
            _update_index_version(latest)
    else:
        print("Skipping release history (GitHub API unavailable)")

    output_path.write_text(content)
    print(f"Generated: {output_path} ({len(content)} bytes)")
