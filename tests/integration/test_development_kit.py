"""Small offline checks for the public kit's operator entrypoints."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DevelopmentEntrypoints(unittest.TestCase):
    def test_default_make_target_is_help_not_deployment(self):
        result = subprocess.run(["make"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validate", result.stdout)
        self.assertIn("No deployment", result.stdout)

    def test_validator_rejects_deployment_arguments(self):
        script = ROOT / "scripts" / "validate.sh"
        self.assertTrue(script.is_file(), "The offline validator is missing")
        result = subprocess.run(["bash", str(script), "--deploy"], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Unknown argument", result.stderr)

    def test_ci_validates_without_deployment_credentials(self):
        workflow = ROOT / ".github" / "workflows" / "validate.yml"
        self.assertTrue(workflow.is_file(), "Native CI validation is missing")
        text = workflow.read_text()
        self.assertIn("contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("make validate", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("terraform apply", text)
        self.assertNotIn("compose up", text)

    def test_ci_builds_the_minio_source_image(self):
        text = (ROOT / ".github" / "workflows" / "validate.yml").read_text()
        self.assertIn("minio-build:", text)
        self.assertIn("docker build", text)
        self.assertIn("services/minio", text)
        self.assertIn("--version", text)

    def test_native_validation_includes_locked_helm_renders(self):
        text = (ROOT / "scripts" / "validate.sh").read_text()
        self.assertIn("kubernetes/charts.lock.json", text)
        self.assertIn("kubernetes/tests/render.sh", text)


if __name__ == "__main__":
    unittest.main()
