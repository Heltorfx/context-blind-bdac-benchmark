"""Verify a generated artifact using public data only and reject changes."""
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[2]
    source = root / "aurora_workspace/show_zk_v2_d4"
    verifier = root / "capss-aggregation/build-openmp/capss/aurora_verify_r1cs_256_zk_bin"
    with tempfile.TemporaryDirectory(prefix="bdac-aurora-test-") as tmp:
        work = Path(tmp)
        for path in source.glob("r1cs-*.txt"):
            if path.name == "r1cs-auxiliary-inputs.txt":
                continue
            shutil.copyfile(path, work / path.name)
        shutil.copyfile(source / "proof-bdac-zk.bin", work / "proof.bin")

        def verify():
            result = subprocess.run(
                [str(verifier), "proof.bin", "v2"], cwd=work,
                capture_output=True, text=True, timeout=180,
            )
            return result.returncode == 0 and result.stdout.strip().endswith("[OK] VALID")

        assert verify(), "original artifact rejected"
        primary = work / "r1cs-primary-inputs.txt"
        original = primary.read_text()
        fields = original.split()
        fields[2] = str(int(fields[2]) + 1)
        primary.write_text(" ".join(fields) + "\n")
        assert not verify(), "modified public challenge accepted"
        primary.write_text(original)
        proof = work / "proof.bin"
        data = bytearray(proof.read_bytes())
        data[-1] ^= 1
        proof.write_bytes(data)
        assert not verify(), "modified proof accepted"
    print(
        "PASS: verifier used no auxiliary witness; original valid; "
        "changed challenge and changed proof rejected"
    )


if __name__ == "__main__":
    main()
