from subprocess import CompletedProcess
import unittest

from BDAC.proofs.show_runner import aurora_run_is_valid


class AuroraVerdictTest(unittest.TestCase):
    def test_explicit_success(self):
        self.assertTrue(aurora_run_is_valid(
            CompletedProcess([], 0), CompletedProcess([], 0, "profile\n[OK] VALID\n")))

    def test_invalid_is_not_valid(self):
        for code in (0, 1):
            self.assertFalse(aurora_run_is_valid(
                CompletedProcess([], 0), CompletedProcess([], code, "[FAIL] INVALID\n")))

    def test_failed_process_or_missing_verdict(self):
        for prover_code, verifier_code, output in (
            (1, 0, "[OK] VALID\n"), (0, 1, "[OK] VALID\n"),
            (0, 0, ""), (0, 0, "VALID"), (0, 0, "[OK] VALID\n[FAIL] INVALID\n"),
        ):
            self.assertFalse(aurora_run_is_valid(
                CompletedProcess([], prover_code),
                CompletedProcess([], verifier_code, output)))


if __name__ == "__main__":
    unittest.main()
