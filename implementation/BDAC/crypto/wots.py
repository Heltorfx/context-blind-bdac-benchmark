from __future__ import annotations

from dataclasses import dataclass
from hashlib import shake_256
from pathlib import Path
import secrets
from time import perf_counter


WOTS_PUBLIC_KEY_BYTES = 32
WOTS_SECRET_KEY_BYTES = 32
WOTS_SIGNATURE_BYTES = 560
WOTS_DIGEST_BYTES = 16
_DIGEST_DOMAIN = b"BDAC-WOTS+-PRESENTATION-v1"
_RUST_MODULE = None


def _native_backend():
    global _RUST_MODULE
    if _RUST_MODULE is not None:
        return _RUST_MODULE

    try:
        import rust_wots
    except ImportError:
        import sys

        rust_dir = Path(__file__).resolve().parents[2] / "rust-wots"
        sys.path.insert(0, str(rust_dir))
        try:
            import rust_wots
        except ImportError as error:
            raise RuntimeError(
                "The native WOTS+ backend is unavailable. Build "
                "Implementation/rust-wots with maturin or cargo first."
            ) from error
    _RUST_MODULE = rust_wots
    return rust_wots


def _frame(value: bytes) -> bytes:
    return len(value).to_bytes(8, "big") + value


def presentation_digest(statement: bytes, proof: bytes) -> bytes:
    encoded = _frame(_DIGEST_DOMAIN) + _frame(statement) + _frame(proof)
    return shake_256(encoded).digest(WOTS_DIGEST_BYTES)


def aurora_proof_bytes(result: dict[str, object]) -> bytes:
    proof_path = result.get("proof_path")
    if proof_path is not None:
        return Path(proof_path).read_bytes()
    output_dir = Path(result["output_dir"])
    return (output_dir / "proof-transcript.txt").read_bytes()


def encode_presentation_statement(instance) -> bytes:
    parts = [
        b"BDAC-PRESENTATION-STATEMENT-v1",
        int(instance.verifier_nonce).to_bytes(32, "big"),
        len(instance.disclosure.indexes).to_bytes(4, "big"),
    ]
    parts.extend(int(index).to_bytes(4, "big") for index in instance.disclosure.indexes)
    parts.extend(instance.disclosure.attributes)
    parts.extend(int(value).to_bytes(32, "big") for value in instance.issuer_public_key)
    parts.append(instance.ots_public_key)
    return b"".join(len(part).to_bytes(4, "big") + part for part in parts)


@dataclass(frozen=True)
class WOTSPublicKey:
    encoded: bytes

    def __post_init__(self) -> None:
        if len(self.encoded) != WOTS_PUBLIC_KEY_BYTES:
            raise ValueError("invalid WOTS+ public-key length")


@dataclass
class WOTSOneTimeSigningKey:
    public_key: WOTSPublicKey
    _secret_key: bytearray
    _used: bool = False

    @classmethod
    def generate(cls) -> "WOTSOneTimeSigningKey":
        backend = _native_backend()
        public_key, secret_key = backend.keypair_from_seed(
            secrets.token_bytes(WOTS_SECRET_KEY_BYTES)
        )
        return cls(WOTSPublicKey(bytes(public_key)), bytearray(secret_key))

    def sign(self, statement: bytes, proof: bytes) -> tuple[bytes, float]:
        if self._used:
            raise RuntimeError("a WOTS+ key must sign at most one presentation")
        digest = presentation_digest(statement, proof)
        started = perf_counter()
        try:
            signature = bytes(_native_backend().sign(bytes(self._secret_key), digest))
        finally:
            self._used = True
            self._secret_key[:] = b"\x00" * len(self._secret_key)
        return signature, perf_counter() - started


def verify_presentation_signature(
    public_key: WOTSPublicKey,
    statement: bytes,
    proof: bytes,
    signature: bytes,
) -> tuple[bool, float]:
    digest = presentation_digest(statement, proof)
    started = perf_counter()
    ok = bool(_native_backend().verify(public_key.encoded, digest, signature))
    return ok, perf_counter() - started
