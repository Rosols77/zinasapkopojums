from pathlib import Path
import unittest


class SmokeTests(unittest.TestCase):
    def test_readme_exists(self) -> None:
        """Basic smoke test to ensure repository root has README."""
        self.assertTrue(Path("README.md").exists())


if __name__ == "__main__":
    unittest.main()
