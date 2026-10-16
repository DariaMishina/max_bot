from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AndroidWorkflowTests(unittest.TestCase):
    def test_dependency_resolution_has_bounded_retry_before_build(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text()

        self.assertIn("name: Resolve Android dependencies", workflow)
        self.assertIn("for attempt in 1 2 3", workflow)
        self.assertIn(":app:checkDebugAarMetadata", workflow)
        self.assertEqual(workflow.count(":app:assembleDebug"), 1)
        self.assertLess(
            workflow.index("name: Resolve Android dependencies"),
            workflow.index("name: Assemble debug"),
        )


if __name__ == "__main__":
    unittest.main()
