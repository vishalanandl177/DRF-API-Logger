from pathlib import Path

from django.test import SimpleTestCase


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publish.yml"
)


def _step_block(workflow_text, step_name):
    marker = f"      - name: {step_name}\n"
    start = workflow_text.find(marker)
    if start == -1:
        raise AssertionError(f"Workflow step not found: {step_name}")

    next_step = workflow_text.find("\n      - name:", start + len(marker))
    if next_step == -1:
        return workflow_text[start:]
    return workflow_text[start:next_step]


class PublishWorkflowTests(SimpleTestCase):
    def test_existing_pypi_version_skips_publish_without_failing_job(self):
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        check_step = _step_block(
            workflow_text, "Check whether package version exists on PyPI"
        )
        self.assertIn("id: pypi_version", check_step)
        self.assertIn('write_output("exists", "true")', check_step)
        self.assertIn('write_output("exists", "false")', check_step)
        self.assertNotIn("Bump setup.py version before merging to main", check_step)

        skip_step = _step_block(
            workflow_text, "Skip publish because package version already exists"
        )
        self.assertIn("if: steps.pypi_version.outputs.exists == 'true'", skip_step)

        guarded_steps = [
            "Download package artifacts",
            "Ensure downloaded wheel and source distribution exist",
            "Publish package distributions to PyPI",
            "Create GitHub release",
        ]
        for step_name in guarded_steps:
            with self.subTest(step=step_name):
                step = _step_block(workflow_text, step_name)
                self.assertIn("if: steps.pypi_version.outputs.exists != 'true'", step)
