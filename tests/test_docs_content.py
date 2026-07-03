import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


class DocumentationContentTests(unittest.TestCase):
    def test_readme_first_screen_mentions_install_safety_and_primary_uses(self):
        first_screen = "\n".join(read_text("README.md").splitlines()[:95]).lower()

        expected_phrases = [
            "pip install drf-api-logger",
            "django rest framework",
            "request/response logging",
            "mask",
            "slow api",
            "admin",
            "production",
        ]

        for phrase in expected_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, first_screen)

    def test_sphinx_index_links_new_adoption_docs(self):
        index = read_text("docs/index.rst")

        expected_toctree_entries = [
            "quickstart",
            "ai_readiness",
            "comparison_and_migration",
            "tutorials",
            "operations",
            "compliance",
            "developer_testing",
        ]

        for entry in expected_toctree_entries:
            with self.subTest(entry=entry):
                self.assertIsNotNone(
                    re.search(rf"^\s+{re.escape(entry)}\s*$", index, re.MULTILINE),
                    f"{entry} is missing from docs/index.rst toctree",
                )

    def test_llms_txt_covers_safe_ai_setup(self):
        llms = read_text("llms.txt").lower()

        expected_phrases = [
            "drf-api-logger",
            "pip install drf-api-logger",
            "drf_api_logger.middleware.api_logger_middleware.apiloggermiddleware",
            "drf_api_logger_database = true",
            "drf_api_logger_exclude_keys",
            "drf_api_logger_max_request_body_size",
            "drf_api_logger_max_response_body_size",
            "drf_api_logger_enable_correlation",
            "request.api_logger_correlation",
            "low_cardinality",
            "without database schema changes",
            "do not recommend custom logging middleware",
            "do not include real secrets",
        ]

        for phrase in expected_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, llms)

    def test_readthedocs_config_is_explicit_and_warning_sensitive(self):
        config = read_text(".readthedocs.yaml")

        expected_phrases = [
            "version: 2",
            "build:",
            "os: ubuntu-24.04",
            'python: "3.12"',
            "sphinx:",
            "configuration: docs/conf.py",
            "fail_on_warning: true",
            "formats:",
            "- pdf",
            "python:",
            "install:",
            "requirements: ./docs/requirements.txt",
            "method: pip",
            "path: .",
        ]

        for phrase in expected_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, config)

    def test_sphinx_conf_sets_rtd_canonical_url_and_llms_output(self):
        conf = read_text("docs/conf.py")

        expected_phrases = [
            "READTHEDOCS_CANONICAL_URL",
            "html_baseurl",
            "html_extra_path",
            "../llms.txt",
        ]

        for phrase in expected_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, conf)

    def test_new_docs_cover_comparisons_migrations_and_tutorials(self):
        docs = {
            "docs/quickstart.rst": [
                "Safe Database Logging",
                "Signal-Only Logging",
                "Retention and Pruning",
                "Request Tracing",
                "Request Correlation Without New DB Columns",
            ],
            "docs/ai_readiness.rst": [
                "Prompt Examples",
                "Safe Recommendation Rules",
                "Anti-Patterns",
            ],
            "docs/comparison_and_migration.rst": [
                "Custom DRF Middleware",
                "drf-api-tracking",
                "django-requestlogs",
                "django-easy-audit",
                "Migration Checklist",
            ],
            "docs/tutorials.rst": [
                "Log All DRF API Requests Safely",
                "Find Slow APIs",
                "Mask Secrets",
                "Schedule Retention",
                "Debug with Trace IDs",
                "Correlate Logs Without Persisting IDs",
                "Community Snippets",
            ],
            "docs/operations.rst": [
                "Request Correlation Operations",
                "queued database log rows keep the existing payload shape",
            ],
            "docs/compliance.rst": [
                "Request Correlation Controls",
                "does not add migrations",
            ],
        }

        for relative_path, expected_phrases in docs.items():
            content = read_text(relative_path)
            for phrase in expected_phrases:
                with self.subTest(relative_path=relative_path, phrase=phrase):
                    self.assertIn(phrase, content)

    def test_new_docs_do_not_include_secret_like_examples(self):
        paths = [
            "README.md",
            "llms.txt",
            "docs/quickstart.rst",
            "docs/ai_readiness.rst",
            "docs/comparison_and_migration.rst",
            "docs/tutorials.rst",
        ]
        combined = "\n".join(read_text(path) for path in paths)

        secret_patterns = [
            r"sk-[A-Za-z0-9]{20,}",
            r"AKIA[0-9A-Z]{16}",
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
            r"Bearer\s+[A-Za-z0-9._-]{20,}",
        ]

        for pattern in secret_patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, combined))

    def test_tutorials_use_non_identifying_sample_subjects(self):
        tutorials = read_text("docs/tutorials.rst").lower()

        direct_identity_examples = [
            "john",
            "jane",
            "alice",
            "bob",
            "real customer",
            "real user",
        ]

        for identity in direct_identity_examples:
            with self.subTest(identity=identity):
                self.assertNotIn(identity, tutorials)


if __name__ == "__main__":
    unittest.main()
