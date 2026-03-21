from pathlib import Path
import unittest


class ProjectStructureTests(unittest.TestCase):
    def test_required_files_exist(self) -> None:
        required = [
            Path("README.md"),
            Path("Makefile"),
            Path("run_tests.py"),
            Path("run_observability_demo.py"),
            Path("observability_test_env.py"),
            Path("docs/TESTING.md"),
            Path("docker-compose.test.yml"),
            Path(".github/workflows/tests.yml"),
        ]
        for file_path in required:
            with self.subTest(file=str(file_path)):
                self.assertTrue(file_path.exists())


if __name__ == "__main__":
    unittest.main()
