#!/usr/bin/env python3
"""Run a public web search through the Parallel or Perplexity Search API."""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from capability import WEB_SEARCH_PROVIDERS, resolve_brand_dir, resolve_env


def search_request(provider, key, query, objective, domains):
    headers = {"Content-Type": "application/json"}
    if provider == "parallel":
        url = "https://api.parallel.ai/v1/search"
        headers["x-api-key"] = key
        payload = {"search_queries": [query], "mode": "fast"}
        if objective:
            payload["objective"] = objective
        if domains:
            payload["advanced_settings"] = {"source_policy": {"include_domains": domains}}
    else:
        url = "https://api.perplexity.ai/search"
        headers["Authorization"] = "Bearer " + key
        payload = {"query": query}
        if domains:
            payload["search_domain_filter"] = domains
    return Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=("parallel", "perplexity"))
    parser.add_argument("query", help="search keywords")
    parser.add_argument("--objective", help="describe what to find (Parallel only)")
    parser.add_argument("--domain", action="append", help="restrict to a domain (repeatable)")
    parser.add_argument("--root", default=".", help="workspace root (default: current directory)")
    parser.add_argument("--brand", help="use this brand's .env instead of the active brand's")
    args = parser.parse_args(argv)
    if not args.query.strip():
        parser.error("query must not be empty")
    if args.objective and args.provider != "parallel":
        parser.error("--objective is available for Parallel searches")

    root = Path(args.root).expanduser().resolve()
    env, _ = resolve_env(root, resolve_brand_dir(root, args.brand), os.environ)
    key_name = WEB_SEARCH_PROVIDERS[args.provider]
    key = env.get(key_name, "").strip()
    if not key:
        parser.exit(1, f"{key_name} is missing. Use an available search tool or configure the key.\n")

    request = search_request(args.provider, key, args.query, args.objective, args.domain)
    try:
        with urlopen(request, timeout=30) as response:
            data = json.load(response)
    except HTTPError as error:
        parser.exit(1, f"{args.provider} search failed (HTTP {error.code}).\n")
    except (URLError, OSError, ValueError):
        parser.exit(1, f"{args.provider} search could not read the API response.\n")
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        parser.exit(1, f"{args.provider} search returned an unexpected response.\n")

    print(json.dumps({"provider": args.provider, "results": data["results"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
