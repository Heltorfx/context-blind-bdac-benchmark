from types import SimpleNamespace
import unittest
from unittest.mock import patch

from BDAC.proofs.aurora_backend import AuroraBackend
from BDAC.proofs.show_runner import show_output_dir


class AuroraVersionTests(unittest.TestCase):
    def test_default_and_validation(self):
        self.assertEqual(AuroraBackend().version, "normal")
        with self.assertRaises(ValueError):
            AuroraBackend(version="typo")
        with self.assertRaises(ValueError):
            AuroraBackend(make_zk=False, version="v2")

    def test_workspace_separation(self):
        instance = SimpleNamespace(disclosure=SimpleNamespace(indexes=(0, 1, 2, 3)))
        normal = show_output_dir(instance, make_zk=True)
        v2 = show_output_dir(instance, make_zk=True, version="v2")
        self.assertEqual(normal.name, "show_zk_d4")
        self.assertEqual(v2.name, "show_zk_v2_d4")

    def test_backend_forwards_version(self):
        with patch("BDAC.proofs.aurora_backend.run_aurora_show_zk", return_value={}) as run:
            AuroraBackend(version="v2").prove_show("instance")
            run.assert_called_once_with("instance", version="v2")


if __name__ == "__main__":
    unittest.main()
