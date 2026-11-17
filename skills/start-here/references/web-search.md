# Web search

Use the agent's built-in web search for public source discovery by default. Exa,
Parallel and Perplexity are optional alternatives. Use the provider the user asks for
or has configured for the job. If it is unavailable or errors, fall back to another
available search tool. When none works, use the skill's existing evidence fallback.

| Provider | Connected search tool | API key |
|---|---|---|
| [Exa](https://exa.ai/docs/reference/search) | Exa web search | `EXA_API_KEY` |
| [Parallel](https://docs.parallel.ai/integrations/mcp/quickstart) | Parallel `web_search` or the host's Parallel Search tool | `PARALLEL_API_KEY` |
| [Perplexity](https://docs.perplexity.ai/docs/getting-started/integrations/mcp-server) | `perplexity_search` | `PERPLEXITY_API_KEY` |

Use the connected tool if it is available in this session. The capability manifest
detects keys and some built-in tools. Check the session for connected tools, including
connections that authenticate without an environment variable.
If a restricted research agent lacks the search tool, give it public URLs to verify.

## API key setup

Set one provider's key in the process environment or workspace `.env`. A brand's `.env`
takes precedence. The script uses the active brand or `./brand/` by default. Pass
`--brand <slug>` for an explicitly selected client. Run from the workspace root.
Replace `START_HERE_DIR` with the installed `start-here` skill folder.

```sh
python3 "START_HERE_DIR/scripts/web_search.py" parallel "water heater overcharged" --objective "Find public Reddit discussions about unexpected plumbing bills" --domain reddit.com
python3 "START_HERE_DIR/scripts/web_search.py" perplexity "water heater overcharged" --domain reddit.com
```

These commands use Python's standard library and return JSON with a provider name and
results. For Parallel, use a short keyword query and describe the goal separately with
`--objective`. For Exa, use the connected tool or its Search API. See the
[Parallel Search API](https://docs.parallel.ai/search/search-quickstart) and
[Perplexity Search API](https://docs.perplexity.ai/docs/search/quickstart) for query
filters and usage details.

## Evidence

- Send public search terms only. Keep private client material in the workspace.
- Open result URLs to verify facts and verbatim quotes. Record the provider in working
  notes if results will be compared across runs.
- Use an actual search-results page or a SERP data provider to check observed Google
  positions, People Also Ask, AI Overviews, ads and map packs. If the surface can't be
  observed, label the gap or the proxy the skill calls for.
- Keep `/ai-search` retrieval results labelled `RETRIEVAL PROXY`, including results
  from Perplexity's Search API. Live-answer scoring requires a captured answer from
  the product being measured.
