"""Run project tests reliably from any working directory."""

from __future__ import annotations

import unittest
from pathlib import Path


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(repo_root / "tests"),
        pattern="test_*.py",
        top_level_dir=str(repo_root),
    )
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
