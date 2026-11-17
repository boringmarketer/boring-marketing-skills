import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "_system" / "scripts"
SKILLS = Path(__file__).resolve().parents[1] / "skills"
sys.path.insert(0, str(SCRIPTS))
import route


def run(args, env=None, cwd=None):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "route.py"),
            "--skills-dir",
            str(SKILLS),
            *args,
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd or tempfile.mkdtemp(),
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class Route(unittest.TestCase):
    def test_leads_from_empty_dir_prepends_foundation(self):
        plan = run(["--goal", "leads"], env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(plan["workflow"], "I Need Leads")
        stage_zero = {step["skill"] for step in plan["sequence"] if step["stage"] == 0}
        self.assertTrue({"brand-voice", "positioning-angles"} & stage_zero)

    def test_exactly_one_advisor_line_without_keys(self):
        plan = run(["--goal", "traffic"], env={"PATH": "/usr/bin:/bin"})
        self.assertIsNotNone(plan["advisor"])
        self.assertIn("toolset", plan["advisor"])
        self.assertTrue(plan["advisor"]["line"])

    def test_firecrawl_grounding_and_no_internal_names(self):
        plan = run(
            ["--goal", "leads"],
            env={
                "PATH": "/usr/bin:/bin",
                "CLAUDECODE": "1",
                "FIRECRAWL_API_KEY": "k",
            },
        )
        providers = {
            provider
            for step in plan["sequence"]
            for provider in step["grounding"]["via"]
        }
        self.assertIn("firecrawl", providers)
        self.assertNotIn("br" + "ain", json.dumps(plan).lower())

    def test_task_mode(self):
        plan = run(["--task", "seo-content"], env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(plan["mode"], "task")
        self.assertEqual(plan["sequence"][0]["skill"], "seo-content")

    def test_search_provider_from_brand_env_with_built_in_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brand = root / "brands" / "acme"
            brand.mkdir(parents=True)
            (brand / ".env").write_text("PARALLEL_API_KEY=local-test-key\n")
            manifest = root / "capabilities.json"
            manifest.write_text(json.dumps({
                "capabilities": {"web-search": {
                    "available": True, "via": "websearch", "providers": ["websearch"],
                }},
            }))
            plan = run(
                ["--task", "brand-voice", "--brand", "acme", "--capabilities", str(manifest)],
                env={"CLAUDECODE": "1"},
                cwd=root,
            )
        self.assertEqual(plan["sequence"][0]["grounding"]["via"], ["webfetch", "websearch", "parallel"])

    def test_all_brands(self):
        root = Path(tempfile.mkdtemp())
        for slug in ("acme", "northwind"):
            (root / "brands" / slug).mkdir(parents=True)
            (root / "brands" / slug / "brand.yaml").write_text(
                "brand:\n  slug: {0}\n".format(slug)
            )
        plan = run(
            ["--goal", "convert", "--all-brands", "--root", str(root)],
            env={"PATH": "/usr/bin:/bin"},
        )
        self.assertEqual(plan["mode"], "all-brands")
        self.assertEqual(
            [entry["brand"] for entry in plan["plans"]], ["acme", "northwind"]
        )

    def test_all_brands_overlay_client_env_over_capabilities_file(self):
        root = Path(tempfile.mkdtemp())
        providers = {"acme": "KIT_API_KEY=acme\n", "northwind": "BEEHIIV_API_KEY=northwind\n"}
        for slug, env_file in providers.items():
            client = root / "brands" / slug
            client.mkdir(parents=True)
            (client / "brand.yaml").write_text("brand:\n  slug: {0}\n".format(slug))
            (client / ".env").write_text(env_file)
        manifest = root / "capabilities.json"
        manifest.write_text(json.dumps({"environment": "unknown", "capabilities": {}}))

        plan = run(
            [
                "--goal",
                "leads",
                "--all-brands",
                "--root",
                str(root),
                "--capabilities",
                str(manifest),
            ],
            env={"PATH": "/usr/bin:/bin"},
        )
        by_brand = {entry["brand"]: entry for entry in plan["plans"]}

        def esp_provider(entry):
            return next(
                provider
                for step in entry["sequence"]
                if step["skill"] == "email-sequences"
                for provider in step["grounding"]["via"]
            )

        self.assertEqual(esp_provider(by_brand["acme"]), "kit")
        self.assertEqual(esp_provider(by_brand["northwind"]), "beehiiv")

    def test_local_goals_route_to_the_local_pack(self):
        expected = {
            "found": "google-business-profile",
            "chosen": "reviews",
            "calls": "google-ads-tracking",
            "clients": "find-local-clients",
        }
        for goal, first in expected.items():
            with self.subTest(goal=goal):
                plan = run(["--goal", goal], env={"PATH": "/usr/bin:/bin"})
                skills = [step["skill"] for step in plan["sequence"]]
                self.assertIn(first, skills)
                self.assertIsNotNone(plan["advisor"])

    def test_request_mode_ranks_skills(self):
        plan = run(["--request", "write a welcome email sequence"], env={"PATH": "/usr/bin:/bin"})
        self.assertEqual(plan["mode"], "request")
        self.assertEqual(plan["matches"][0]["skill"], "email-sequences")

    def test_cap_enhances_only_public_keys(self):
        import capability

        self.assertTrue(set(route.CAP_ENHANCES) <= set(capability.CAPABILITY_ORDER))

    def test_advisor_names_top_missing_toolset_never_composio(self):
        plan = run(
            ["--goal", "launch"],
            env={"PATH": "/usr/bin:/bin", "CLAUDECODE": "1"},
        )
        self.assertEqual(plan["advisor"]["toolset"], "creative")
        plan_with_keys = run(
            ["--goal", "launch"],
            env={
                "PATH": "/usr/bin:/bin",
                "CLAUDECODE": "1",
                "COMPOSIO_API_KEY": "c",
                "REPLICATE_API_TOKEN": "r",
            },
        )
        self.assertIsNone(plan_with_keys["advisor"])


if __name__ == "__main__":
    unittest.main()
