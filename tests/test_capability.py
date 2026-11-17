import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_system" / "scripts"))
import capability as cap


class Manifest(unittest.TestCase):
    def test_baseline_unknown_env(self):
        m = cap.build_manifest(env={}, root=tempfile.mkdtemp())
        expected_order = [
            "web-scrape",
            "web-search",
            "social-data",
            "creative",
            "esp",
            "analytics",
            "search-console",
            "ads",
            "social-api",
            "scheduling",
        ]
        self.assertEqual(m["environment"], "unknown")
        self.assertFalse(m["capabilities"]["web-scrape"]["available"])
        self.assertEqual(cap.CAPABILITY_ORDER, expected_order)
        self.assertEqual(list(m["capabilities"]), expected_order)

    def test_claude_code_baseline_web(self):
        m = cap.build_manifest(env={"CLAUDECODE": "1"}, root=tempfile.mkdtemp())
        self.assertEqual(m["environment"], "claude-code")
        self.assertEqual(m["capabilities"]["web-scrape"]["via"], "webfetch")
        self.assertEqual(m["capabilities"]["web-search"]["via"], "websearch")

    def test_each_optional_search_provider_works_without_builtin_search(self):
        with tempfile.TemporaryDirectory() as root:
            for key, provider in (
                ("EXA_API_KEY", "exa"),
                ("PARALLEL_API_KEY", "parallel"),
                ("PERPLEXITY_API_KEY", "perplexity"),
            ):
                with self.subTest(provider=provider):
                    m = cap.build_manifest(env={key: "search-test-value"}, root=root)
                    self.assertEqual(m["capabilities"]["web-search"], {
                        "available": True, "via": provider, "providers": [provider],
                    })
                    self.assertFalse(m["capabilities"]["web-scrape"]["available"])
                    self.assertNotIn("search-test-value", json.dumps(m))

    def test_builtin_search_stays_primary_with_optional_providers(self):
        with tempfile.TemporaryDirectory() as root:
            m = cap.build_manifest(
                env={
                    "CLAUDECODE": "1",
                    "EXA_API_KEY": "x",
                    "PARALLEL_API_KEY": "y",
                    "PERPLEXITY_API_KEY": "z",
                },
                root=root,
            )
        search = m["capabilities"]["web-search"]
        self.assertEqual(search["via"], "websearch")
        self.assertEqual(search["providers"], ["websearch", "exa", "parallel", "perplexity"])

    def test_firecrawl_and_social_data(self):
        m = cap.build_manifest(
            env={
                "CLAUDECODE": "1",
                "FIRECRAWL_API_KEY": "x",
                "SCRAPECREATORS_API_KEY": "y",
            },
            root=tempfile.mkdtemp(),
        )
        self.assertEqual(m["capabilities"]["web-scrape"]["via"], "firecrawl")
        self.assertEqual(m["capabilities"]["web-search"]["via"], "websearch")
        self.assertEqual(m["capabilities"]["social-data"]["via"], "scrapecreators")

    def test_no_internal_toolsets(self):
        internal_key = "B" + "RAIN_API_KEY"
        internal_home = "H" + "ERMES_HOME"
        m = cap.build_manifest(
            env={internal_key: "z", internal_home: "/tmp"}, root=tempfile.mkdtemp()
        )
        manifest = json.dumps(m).lower()
        self.assertNotIn("br" + "ain", manifest)
        self.assertNotIn("h" + "ermes", manifest)

    def test_brand_env_overrides_root_env(self):
        root = Path(tempfile.mkdtemp())
        (root / ".env").write_text("KIT_API_KEY=rootkey\n")
        (root / "brands" / "acme").mkdir(parents=True)
        (root / "brands" / "acme" / ".env").write_text("BEEHIIV_API_KEY=brandkey\n")
        (root / "brands" / "active").write_text("acme\n")
        m = cap.build_manifest(env={}, root=str(root), brand_dir="auto")
        self.assertEqual(m["capabilities"]["esp"]["providers"], ["kit", "beehiiv"])
        self.assertIn("brands/acme/.env", m["env_sources"])
        out = json.dumps(m)
        self.assertNotIn("rootkey", out)
        self.assertNotIn("brandkey", out)

    def test_brand_files_include_preferences(self):
        self.assertIn("preferences.md", cap.BRAND_FILES)

    def test_composio_fills_missing_toolsets(self):
        m = cap.build_manifest(
            env={"CLAUDECODE": "1", "COMPOSIO_API_KEY": "c"},
            root=tempfile.mkdtemp(),
        )
        for key in (
            "esp",
            "analytics",
            "search-console",
            "ads",
            "scheduling",
            "social-api",
        ):
            self.assertEqual(m["capabilities"][key]["via"], "composio", key)
        self.assertEqual(m["capabilities"]["web-scrape"]["via"], "webfetch")

    def test_native_key_wins_over_composio(self):
        m = cap.build_manifest(
            env={
                "CLAUDECODE": "1",
                "COMPOSIO_API_KEY": "c",
                "KIT_API_KEY": "k",
            },
            root=tempfile.mkdtemp(),
        )
        self.assertEqual(m["capabilities"]["esp"]["via"], "kit")
        self.assertIn("composio", m["capabilities"]["esp"]["providers"])

    def test_cli_runs(self):
        r = subprocess.run(
            [sys.executable, str(Path(cap.__file__)), "--json"],
            capture_output=True,
            text=True,
            cwd=tempfile.mkdtemp(),
        )
        self.assertEqual(r.returncode, 0)
        json.loads(r.stdout)


if __name__ == "__main__":
    unittest.main()
