# Bridge — hosted MCP for any GraphQL API

Bridge is the hosted companion to graphql-mcp. Paste any GraphQL endpoint into your MCP client, attach your own auth headers, and Bridge exposes every query and mutation as an MCP tool that your agent can call. No code, no servers, no keys to sign up for.

It is the fastest way to get a GraphQL API into Claude, Cursor, or any MCP-speaking client — and a zero-effort demo of what graphql-mcp does under the hood.

## Generate your MCP URL

<div class="bridge-url-generator">
  <label for="bridge-upstream"><strong>GraphQL endpoint</strong></label>
  <input id="bridge-upstream" type="url" placeholder="https://api.example.com/graphql" autocomplete="off" spellcheck="false" />
  <label for="bridge-output"><strong>MCP URL</strong> (paste this into your MCP client)</label>
  <div class="bridge-output-row">
    <input id="bridge-output" type="text" readonly placeholder="Enter a GraphQL endpoint above…" />
    <button id="bridge-copy" type="button">Copy</button>
  </div>
  <p id="bridge-status" class="bridge-hint">The upstream URL is base64url-encoded — no tricky <code>%3A%2F</code> characters to escape in your JSON config.</p>
</div>

<style>
.bridge-url-generator {
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin: 1rem 0 1.5rem;
  background: var(--vp-c-bg-soft);
}
.bridge-url-generator label {
  display: block;
  font-size: 0.85rem;
  margin: 0.5rem 0 0.25rem;
  color: var(--vp-c-text-2);
}
.bridge-url-generator input[type="url"],
.bridge-url-generator input[type="text"] {
  width: 100%;
  padding: 0.5rem 0.65rem;
  border: 1px solid var(--vp-c-divider);
  border-radius: 6px;
  background: var(--vp-c-bg);
  color: var(--vp-c-text-1);
  font-family: var(--vp-font-family-mono);
  font-size: 0.85rem;
  box-sizing: border-box;
}
.bridge-url-generator input[readonly] {
  background: var(--vp-c-bg-alt);
}
.bridge-output-row {
  display: flex;
  gap: 0.5rem;
  align-items: stretch;
}
.bridge-output-row input {
  flex: 1 1 auto;
  min-width: 0;
}
.bridge-url-generator button {
  padding: 0 1rem;
  border: 1px solid var(--vp-c-brand-1);
  border-radius: 6px;
  background: var(--vp-c-brand-1);
  color: var(--vp-c-white);
  cursor: pointer;
  font-size: 0.85rem;
  white-space: nowrap;
}
.bridge-url-generator button:hover {
  background: var(--vp-c-brand-2);
  border-color: var(--vp-c-brand-2);
}
.bridge-url-generator button.copied {
  background: var(--vp-c-green-1);
  border-color: var(--vp-c-green-1);
}
.bridge-hint {
  font-size: 0.8rem;
  color: var(--vp-c-text-2);
  margin: 0.5rem 0 0;
}
.bridge-hint code {
  font-size: 0.8rem;
}
.bridge-hint.error {
  color: var(--vp-c-danger-1, #e85a5a);
}
</style>

<script setup>
import { onMounted } from 'vue';

const BRIDGE_BASE = 'https://bridge.graphql-mcp.com/mcp/';
const EXAMPLE = 'https://countries.trevorblades.com/graphql';

const toBase64Url = (value) => {
  const bytes = new TextEncoder().encode(value);
  let binary = '';
  bytes.forEach((b) => { binary += String.fromCharCode(b); });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};

const DEFAULT_HINT = 'The upstream URL is base64url-encoded — no tricky <code>%3A%2F</code> characters to escape in your JSON config.';

onMounted(() => {
  const input = document.getElementById('bridge-upstream');
  const output = document.getElementById('bridge-output');
  const copyBtn = document.getElementById('bridge-copy');
  const status = document.getElementById('bridge-status');
  if (!input || !output || !copyBtn || !status) return;

  const setStatus = (html, isError) => {
    status.innerHTML = html;
    status.classList.toggle('error', !!isError);
  };

  const render = () => {
    const typed = (input.value || '').trim();
    // Empty: show the default-example URL so the box is never blank.
    const raw = typed || EXAMPLE;
    if (!/^https?:\/\//i.test(raw)) {
      output.value = '';
      setStatus('URL must start with <code>http://</code> or <code>https://</code>.', true);
      return;
    }
    try {
      const u = new URL(raw);
      if (!(u.protocol === 'http:' || u.protocol === 'https:') || !u.hostname) {
        throw new Error('bad url');
      }
      output.value = BRIDGE_BASE + toBase64Url(raw);
      if (!typed) {
        setStatus(DEFAULT_HINT + ' <em>Showing example — paste your endpoint above.</em>', false);
      } else {
        setStatus(DEFAULT_HINT, false);
      }
    } catch {
      output.value = '';
      setStatus('That doesn\'t look like a URL. Try <code>https://api.example.com/graphql</code>.', true);
    }
  };

  input.addEventListener('input', render);
  input.addEventListener('change', render);
  input.addEventListener('keyup', render);

  copyBtn.addEventListener('click', async () => {
    if (!output.value) return;
    try {
      await navigator.clipboard.writeText(output.value);
      copyBtn.classList.add('copied');
      copyBtn.textContent = 'Copied';
      setTimeout(() => {
        copyBtn.classList.remove('copied');
        copyBtn.textContent = 'Copy';
      }, 1200);
    } catch {
      output.select();
    }
  });

  input.placeholder = EXAMPLE;
  render();
});
</script>

## One-line setup

Bridge accepts **either** a base64url-encoded upstream (the form the generator above produces) or a standard URL-encoded upstream:

```text
https://bridge.graphql-mcp.com/mcp/<base64url upstream>        ← cleaner
https://bridge.graphql-mcp.com/mcp/<url-encoded upstream>      ← also works
```

For example, to expose the public [Countries API](https://countries.trevorblades.com):

```json
{
  "mcpServers": {
    "countries": {
      "url": "https://bridge.graphql-mcp.com/mcp/aHR0cHM6Ly9jb3VudHJpZXMudHJldm9yYmxhZGVzLmNvbS9ncmFwaHFs"
    }
  }
}
```

Restart your MCP client and every query the Countries API exposes is now a tool.

## Authenticated APIs

Pass your upstream credentials via your MCP client's headers. Bridge forwards `Authorization`, `X-API-Key`, and `Cookie` to the upstream by default — everything else is stripped.

```json
{
  "mcpServers": {
    "github": {
      "url": "https://bridge.graphql-mcp.com/mcp/aHR0cHM6Ly9hcGkuZ2l0aHViLmNvbS9ncmFwaHFs",
      "headers": {
        "Authorization": "Bearer ghp_yourtoken"
      }
    }
  }
}
```

Bridge never stores or logs header values. See [Security](/bridge-security) for details.

## When to use Bridge vs. the library

Bridge is the best place to start — try your API in an MCP client in under a minute. Graduate to the [graphql-mcp library](/existing-apis) when you need any of:

- **Private GraphQL endpoints** not reachable from the public internet.
- **Custom tool shaping** with the `@mcp` directive (rename, hide, annotate).
- **Higher request volume** than Bridge's public rate limit.
- **Co-location** with your API for lower latency.
- **Auth schemes** beyond simple header forwarding.

Bridge and the library share the same engine: anything that works on one works on the other. Moving from Bridge to self-hosted graphql-mcp is a few lines of Python.

## Limits

Bridge is free and anonymous. To keep it that way:

- **60 requests per minute per IP**, token bucket.
- **30 second** upstream timeout.
- **5 MB** maximum upstream response.
- Upstreams must be reachable on the public internet (no RFC1918, loopback, or link-local addresses).
- Upstream schema introspection must be enabled.

If you need more, [self-host Bridge](/bridge-self-hosting) — it's open source.

## How it works

1. Your MCP client sends a `tools/list` or `tools/call` to `bridge.graphql-mcp.com/mcp/<encoded-upstream>`.
2. Bridge validates the upstream URL and rate-limits by IP.
3. On the first hit for a given upstream, Bridge introspects the schema once, builds an MCP tool surface, and caches the whole thing in memory (1 hour TTL).
4. Every subsequent request is a cache hit — Bridge just forwards the query to the upstream, passing your auth headers verbatim.

Bridge is built directly on [`GraphQLMCP.from_remote_url()`](/existing-apis). It adds caching, SSRF protection, header allowlisting, and rate limiting on top — nothing more.
