import unittest

from BDAC.proofs.longfellow_backend import parse_longfellow_output


class LongfellowOutputTest(unittest.TestCase):
    def test_valid_proof_and_public_input_check(self):
        circuit, proof = parse_longfellow_output(
            "constraints=63473 variables=65000 compile_s=1.2\n"
            "run=1 prove_s=2.3 verify_s=0.4 proof_bytes=12345 valid=1\n"
            "modified_public_input_accepted=0\n"
        )
        self.assertEqual(circuit["constraints"], "63473")
        self.assertEqual(proof["proof_bytes"], "12345")

    def test_invalid_or_missing_public_input_check(self):
        for suffix in ("", "modified_public_input_accepted=1\n"):
            with self.subTest(suffix=suffix), self.assertRaises(RuntimeError):
                parse_longfellow_output(
                    "constraints=63473\nrun=1 valid=1\n" + suffix
                )


if __name__ == "__main__":
    unittest.main()
