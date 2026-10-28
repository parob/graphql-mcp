# GraphQL stack performance

The 2026-10-28 investigation found avoidable work in local MCP calls and
`graphql-api` field middleware. The changes cache generated MCP documents and
selection sets, avoid redundant output type inspection, and remove repeated
context imports and temporary keyword dictionaries from API middleware.

`graphql-http` already caches parsing and validation and reuses its middleware
manager. No independent HTTP change was needed; HTTP execution benefits from
the API middleware improvement.

## Measurements

The benchmark uses 100 in-memory events, each with three edges: 1,401 field
resolutions per event-list operation. It measures warmed calls without a
database, external services, socket transport, authentication, or LLM work.
The MCP client case includes the actual FastMCP protocol over its in-process
transport. The `mcp_nested` case exercises the recursive tool builder with a
single-field scalar path; multi-level paths are covered by regression tests.

Results are recorded in [results.json](results.json). The final comparison
alternates old and new implementations within one process, reversing the order
each round. Each of nine rounds executes 200 calls per implementation, after
10 warm-up calls. Tables report the median per-call mean across those rounds.
Both elapsed time and process CPU time are saved. Profiling runs are separate
from timed measurements.

| Workload | Before (ms) | After (ms) | Elapsed reduction | CPU reduction |
| --- | ---: | ---: | ---: | ---: |
| API: 100 events | 4.570 | 4.449 | 2.6% | 2.3% |
| HTTP/ASGI: 100 events | 5.800 | 5.565 | 4.1% | 3.3% |
| MCP generated scalar tool | 0.604 | 0.017 | 97.1% | 97.1% |
| MCP recursive builder, scalar path | 0.582 | 0.017 | 97.0% | 97.0% |
| MCP generated tool: 100 events | 4.864 | 4.047 | 16.8% | 16.8% |
| FastMCP client: scalar tool | 1.998 | 0.969 | 51.5% | 57.4% |

Environment: macOS arm64, CPython 3.12.10, graphql-core 3.3.1, FastMCP 4.0.5,
Pydantic 2.14.1, Starlette 1.6.0, httpx 0.28.1. Baseline commits:

- graphql-mcp: `957ef3cad0674c53ca162e0790c0cefef76aa00b`
- graphql-api: `757f71e64f8a0dc0410b46a6be786829f0bfdcdd`
- graphql-http (unchanged): `8b09b508cf8bbbcf158f5bf540b9267d07810665`

This development machine was under changing load. An earlier separate-process
run measured 6.60 ms for the updated MCP client, with substantial event-loop
waiting in its profile; an isolated rerun measured 0.81 ms. Those observations
are retained alongside the final paired samples, rather than discarded.
These figures describe framework overhead, not production response times.

## Reproduce

Run from the graphql-mcp checkout with sibling graphql-api and graphql-http
checkouts. `PYTHONPATH` is important: otherwise dependency imports may silently
use published versions instead of the local changes. The script reports the
paths it imported.

```sh
uv sync --frozen
PYTHONPATH=.:../graphql-api:../graphql-http uv run --frozen python benchmarks/profile_stack.py
```

For an alternating comparison, archive the old implementations into a temporary
directory. The benchmark loads the old MCP module separately and supplies the
old combined middleware to dedicated API and HTTP executors. Both variants use
the same dependencies and unchanged schema-building/execution code; the API
change is limited to context imports and middleware construction of field context.

```sh
baseline_dir=$(mktemp -d)
git archive 957ef3cad0674c53ca162e0790c0cefef76aa00b graphql_mcp | tar -x -C "$baseline_dir"
git -C ../graphql-api archive 757f71e64f8a0dc0410b46a6be786829f0bfdcdd graphql_api | tar -x -C "$baseline_dir"
PYTHONPATH=.:../graphql-api:../graphql-http uv run --frozen python benchmarks/profile_stack.py --baseline "$baseline_dir" --iterations 200 --rounds 9
```

Add `--profile /tmp/graphql-stack` to save cProfile files for each workload and
variant. Add `--workload mcp_echo` (repeatable) to narrow a run. Inspect profiles
with `python -m pstats /tmp/graphql-stack-mcp_echo-after.prof`.

## Correctness and integration checks

Local tools retain at most 128 validated documents each. They never cache
variables or results. Every call still coerces inputs and executes resolvers,
including mutations. Optional-argument shapes are distinct, keyword ordering
is canonical, and invalid documents are not cached. Tools and their schemas can
be collected together; there is no new global schema cache. Registered schemas
are treated as fixed, consistent with their generated MCP signatures.

Seven new tests cover fresh mutation execution, variable coercion on cache hits,
omitted/null/default arguments, asynchronous request-context isolation through
a multi-level path, schema isolation, bounded eviction, and validation errors.
Existing enum, JSON, nullable-output, and concurrency suites also pass.

| Suite | Result |
| --- | --- |
| graphql-mcp, with local API and HTTP | 428 passed, 1 skipped |
| graphql-api | 342 passed |
| graphql-http, with local API | 191 passed, 2 skipped |
| Outeract selected GraphQL, session, and performance tests | 25 passed |
| Natter admin schema and remote MCP integration tests | 24 passed |
| Homecast Cloud API, MCP protocol, and alignment tests | 82 passed |

The library lint checks pass; MCP's suite also runs pyright. Product checks ran
under Python 3.13 with local library sources and graphql-core 3.3.1 supplied
through a temporary import overlay, without changing product dependencies.
Natter's remote-tool tests used `LITELLM_LOCAL_MODEL_COST_MAP=True` to prevent
an unrelated import-time pricing download from violating their HTTP mocks.

The separate graphql-db suite has **31 passes and 13 failures with both the
baseline and changed API** under the same graphql-core 3.3.1 overlay. Its tests
use the obsolete `GraphQLAPI.build_schema` method and register conflicting
SQLAlchemy `Post` models, causing cascading mapper failures. This prevents
using that full suite as evidence about database performance. No graphql-db
code was changed.

## Application impact and follow-up

All three products use the affected local MCP path. Outeract's event lists,
Natter's typed API responses, and Homecast's nested home data also exercise
API middleware once per returned field. Actual gains depend on how much time
each request spends in database, relay, network, or LLM work.

The remaining large-list profile is mainly graphql-core field completion and
awaitable checks, plus MCP output conversion. The change does not eliminate
those costs or measure SQL query counts in production. Further work should use
representative application traces and repair the graphql-db performance tests
before drawing conclusions about ORM batching.

These are local changes, not releases or deployments. Outeract and Natter's
checked lockfiles still selected older library majors during this investigation.
Outeract's `api/graphql_http.py` also refers to `execution_context_class`, whereas
the current shared libraries use `executor_class`; resolve that compatibility
issue before upgrading its HTTP transport. Homecast Cloud already had an
in-progress dependency upgrade, which was left intact. Release the shared
libraries and then update/verify consumers through the normal release process.
