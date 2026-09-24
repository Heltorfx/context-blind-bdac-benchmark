from __future__ import annotations

from BDAC.crypto.wots import (
    WOTSOneTimeSigningKey,
    WOTS_PUBLIC_KEY_BYTES,
    WOTS_SIGNATURE_BYTES,
    verify_presentation_signature,
)


def test_wots_signs_one_presentation() -> None:
    key = WOTSOneTimeSigningKey.generate()
    statement = b"statement"
    proof = b"proof"

    signature, _ = key.sign(statement, proof)
    ok, _ = verify_presentation_signature(key.public_key, statement, proof, signature)

    assert len(key.public_key.encoded) == WOTS_PUBLIC_KEY_BYTES
    assert len(signature) == WOTS_SIGNATURE_BYTES
    assert ok


def test_wots_binds_statement_and_proof() -> None:
    key = WOTSOneTimeSigningKey.generate()
    signature, _ = key.sign(b"statement", b"proof")

    wrong_statement, _ = verify_presentation_signature(
        key.public_key, b"other statement", b"proof", signature
    )
    wrong_proof, _ = verify_presentation_signature(
        key.public_key, b"statement", b"other proof", signature
    )

    assert not wrong_statement
    assert not wrong_proof


def test_wots_refuses_key_reuse() -> None:
    key = WOTSOneTimeSigningKey.generate()
    key.sign(b"statement", b"proof")

    try:
        key.sign(b"statement", b"proof")
    except RuntimeError as error:
        assert "at most one" in str(error)
    else:
        raise AssertionError("WOTS+ key reuse was accepted")


def main() -> None:
    test_wots_signs_one_presentation()
    test_wots_binds_statement_and_proof()
    test_wots_refuses_key_reuse()
    print("BDAC WOTS+ checks: ok")


if __name__ == "__main__":
    main()
