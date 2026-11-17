import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "start-here" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import web_search


class WebSearch(unittest.TestCase):
    def test_search_requests_and_brand_key_resolution(self):
        for provider, variable, url, auth, payload in (
            (
                "parallel", "PARALLEL_API_KEY", "https://api.parallel.ai/v1/search",
                ("X-api-key", "brand-key"),
                {
                    "search_queries": ["water heater overcharged"],
                    "objective": "Find public threads about unexpected bills",
                    "mode": "fast",
                    "advanced_settings": {"source_policy": {"include_domains": ["reddit.com"]}},
                },
            ),
            (
                "perplexity", "PERPLEXITY_API_KEY", "https://api.perplexity.ai/search",
                ("Authorization", "Bearer brand-key"),
                {"query": "water heater overcharged", "search_domain_filter": ["reddit.com"]},
            ),
        ):
            with self.subTest(provider=provider), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / ".env").write_text(f"{variable}=workspace-key\n")
                brand = root / "brands" / "acme"
                brand.mkdir(parents=True)
                (brand / ".env").write_text(f"{variable}=brand-key\n")
                (root / "brands" / "active").write_text("acme\n")
                result = {"title": "A public discussion", "url": "https://www.reddit.com/r/plumbing/"}
                args = [provider, "water heater overcharged", "--domain", "reddit.com", "--root", tmp]
                if provider == "parallel":
                    args += ["--objective", payload["objective"]]
                with patch.dict(web_search.os.environ, {variable: "process-key"}, clear=True):
                    with patch.object(web_search, "urlopen") as open_url, redirect_stdout(io.StringIO()) as out:
                        open_url.return_value = io.BytesIO(json.dumps({"results": [result]}).encode())
                        self.assertEqual(web_search.main(args), 0)
                request, = open_url.call_args.args
                self.assertEqual(request.get_method(), "POST")
                self.assertEqual(request.full_url, url)
                self.assertEqual(request.get_header(auth[0]), auth[1])
                self.assertEqual(json.loads(request.data), payload)
                self.assertEqual(json.loads(out.getvalue()), {"provider": provider, "results": [result]})

    def test_missing_key_skips_network(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(web_search.os.environ, clear=True), patch.object(web_search, "urlopen") as open_url:
                with redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as stopped:
                    web_search.main(["parallel", "a query", "--root", root])
        self.assertEqual(stopped.exception.code, 1)
        self.assertIn("PARALLEL_API_KEY is missing", err.getvalue())
        open_url.assert_not_called()

    def test_http_error_exits_without_printing_response_body(self):
        failure = HTTPError("https://api.perplexity.ai/search", 401, "Unauthorized", {}, io.BytesIO(b"private error body"))
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(web_search.os.environ, {"PERPLEXITY_API_KEY": "key"}, clear=True):
                with patch.object(web_search, "urlopen", side_effect=failure):
                    with redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as stopped:
                        web_search.main(["perplexity", "a query", "--root", root])
        self.assertEqual(stopped.exception.code, 1)
        self.assertEqual(err.getvalue(), "perplexity search failed (HTTP 401).\n")
