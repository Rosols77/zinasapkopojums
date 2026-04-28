"""Run project tests reliably from any working directory."""

from __future__ import annotations

import os
import time
import unittest
from pathlib import Path


class ReadableTestResult(unittest.TextTestResult):
    _RESET = "\033[0m"
    _GREEN = "\033[32m"
    _RED = "\033[31m"
    _YELLOW = "\033[33m"

    def _name(self, test: unittest.case.TestCase) -> str:
        return self.getDescription(test)

    def addSuccess(self, test: unittest.case.TestCase) -> None:
        super().addSuccess(test)
        self.stream.writeln(f"{self._GREEN}PASS{self._RESET} {self._name(test)}")

    def addError(self, test: unittest.case.TestCase, err) -> None:
        super().addError(test, err)
        self.stream.writeln(f"{self._RED}ERROR{self._RESET} {self._name(test)}")

    def addFailure(self, test: unittest.case.TestCase, err) -> None:
        super().addFailure(test, err)
        self.stream.writeln(f"{self._RED}FAIL{self._RESET} {self._name(test)}")

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        super().addSkip(test, reason)
        self.stream.writeln(f"{self._YELLOW}SKIP{self._RESET} {self._name(test)} ({reason})")


class ReadableTestRunner(unittest.TextTestRunner):
    resultclass = ReadableTestResult

    def run(self, test: unittest.suite.TestSuite):
        start = time.perf_counter()
        self.stream.writeln("\n=== Running test suite ===")
        result = super().run(test)
        duration = time.perf_counter() - start
        status = "OK" if result.wasSuccessful() else "FAILED"
        self.stream.writeln(
            "\n=== Summary ===\n"
            f"Status: {status}\n"
            f"Ran: {result.testsRun}\n"
            f"Failures: {len(result.failures)}\n"
            f"Errors: {len(result.errors)}\n"
            f"Skipped: {len(result.skipped)}\n"
            f"Duration: {duration:.2f}s"
        )
        return result


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent
    os.chdir(repo_root)
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(repo_root / "tests"),
        pattern="test_*.py",
        top_level_dir=str(repo_root),
    )
    runner = ReadableTestRunner(verbosity=0)
    result = runner.run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
