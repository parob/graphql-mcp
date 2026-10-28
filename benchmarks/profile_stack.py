"""Measure framework overhead without database, network, or LLM latency.

Run from graphql-mcp with the sibling libraries on PYTHONPATH, for example:
PYTHONPATH=.:../graphql-api:../graphql-http uv run python benchmarks/profile_stack.py
Use --profile /tmp/graphql-stack to write cProfile data for each workload.
"""

import argparse
import asyncio
import cProfile
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
import platform
import statistics
import sys
import time

import graphql
import graphql_api
import graphql_http
import graphql_mcp
import httpx
from fastmcp import Client
from graphql.execution.middleware import MiddlewareManager
from graphql_api import GraphQLAPI, field
from graphql_http import GraphQLHTTP
from graphql_mcp import server as mcp_module


@dataclass
class Edge:
    id: str
    edge_type: str
    target_node_id: str


@dataclass
class Event:
    id: str
    created_at: str
    event_type: str
    payload: dict
    edges: list[Edge]


EVENTS = [
    Event(str(i), "2026-10-28T10:00:00Z", "message.received",
          {"text": f"Message {i}", "index": i},
          [Edge(f"{i}-{j}", "participant", str(j)) for j in range(3)])
    for i in range(100)
]


class Query:
    @field
    def echo(self, message: str) -> str:
        return message

    @field
    def events(self) -> list[Event]:
        return EVENTS


QUERY = "{ events { id createdAt eventType payload edges { id edgeType targetNodeId } } }"


async def measure(name, variants, iterations, rounds, profile):
    samples = {variant: {"round_ms": [], "round_cpu_ms": []} for variant in variants}
    for call in variants.values():
        for _ in range(10):
            await call()
    for round_index in range(rounds):
        # Alternate the order to reduce bias from changing machine load.
        order = list(variants) if round_index % 2 == 0 else list(reversed(variants))
        for variant in order:
            call = variants[variant]
            start = time.perf_counter()
            cpu_start = time.process_time()
            for _ in range(iterations):
                await call()
            samples[variant]["round_cpu_ms"].append((time.process_time() - cpu_start) * 1000 / iterations)
            samples[variant]["round_ms"].append((time.perf_counter() - start) * 1000 / iterations)
    for variant, call in variants.items():
        samples[variant]["median_ms"] = statistics.median(samples[variant]["round_ms"])
        samples[variant]["median_cpu_ms"] = statistics.median(samples[variant]["round_cpu_ms"])
        if profile:
            profiler = cProfile.Profile()
            profiler.enable()
            for _ in range(iterations):
                await call()
            profiler.disable()
            profiler.dump_stats(f"{profile}-{name}-{variant}.prof")
    return samples


@asynccontextmanager
async def build_workloads(module=mcp_module, middleware=None):
    api = GraphQLAPI(root_type=Query)
    schema = api.schema()
    echo = module._create_tool_function("echo", schema.query_type.fields["echo"], schema)
    nested = module._create_recursive_tool_function(
        [("echo", schema.query_type.fields["echo"])], "query", schema)
    events = module._create_tool_function("events", schema.query_type.fields["events"], schema)
    http = GraphQLHTTP.from_api(api, serve_graphiql=False)
    server = module.GraphQLMCP.from_api(api, graphql_http=False)
    if middleware is not None:
        # The API change only moves context imports and removes temporary
        # kwargs in middleware. Swap that exact baseline implementation while
        # sharing the unchanged schema builder, executor, and dependencies.
        api.execute(QUERY)
        api._cached_executor._middleware_manager = MiddlewareManager(middleware)
        http._middleware_manager = MiddlewareManager(middleware)

    async def api_events():
        result = api.execute(QUERY)
        assert not result.errors, result.errors
        assert len(result.data["events"]) == 100

    async def mcp_echo():
        assert await echo(message="hello") == "hello"

    async def mcp_nested():
        assert await nested(message="hello") == "hello"

    async def mcp_events():
        assert len(await events()) == 100

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=http.app), base_url="http://test") as client, Client(server) as mcp:
        async def http_events():
            response = await client.post("/", json={"query": QUERY})
            result = response.json()
            assert response.status_code == 200 and not result.get("errors"), result
            assert len(result["data"]["events"]) == 100

        async def mcp_client():
            result = await mcp.call_tool("echo", {"message": "hello"})
            assert result.data == "hello", result

        yield {
            "api_events": api_events, "http_events": http_events,
            "mcp_echo": mcp_echo, "mcp_nested": mcp_nested,
            "mcp_events": mcp_events, "mcp_client": mcp_client,
        }


def load_baseline(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def main(args):
    async with AsyncExitStack() as stack:
        variants = {}
        if args.baseline:
            baseline = Path(args.baseline)
            old_mcp = load_baseline("_baseline_mcp", baseline / "graphql_mcp/server.py")
            old_middleware = load_baseline("_baseline_middleware", baseline / "graphql_api/middleware.py")
            variants["before"] = await stack.enter_async_context(
                build_workloads(old_mcp, old_middleware.middleware_combined))
        variants["after"] = await stack.enter_async_context(build_workloads())
        results = {}
        for name in variants["after"]:
            if args.workload and name not in args.workload:
                continue
            results[name] = await measure(
                name, {variant: calls[name] for variant, calls in variants.items()},
                args.iterations, args.rounds, args.profile)
    print(json.dumps({
        "python": platform.python_version(), "graphql_core": graphql.__version__,
        "sources": {module.__name__: str(Path(module.__file__).resolve())
                    for module in (graphql_api, graphql_http, graphql_mcp)},
        "iterations": args.iterations, "rounds": args.rounds, "results": results,
        "baseline": args.baseline,
    }, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--profile")
    parser.add_argument("--workload", action="append")
    parser.add_argument("--baseline", help="Archived graphql_mcp and graphql_api source directories")
    asyncio.run(main(parser.parse_args()))
