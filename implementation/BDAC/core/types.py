from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AttributeVector:
    """Attributes obtained before issuance from the governance layer."""

    values: tuple[bytes, ...]

    def __len__(self) -> int:
        return len(self.values)

    def disclose(self, indexes: tuple[int, ...]) -> tuple[bytes, ...]:
        return tuple(self.values[index] for index in indexes)


@dataclass(frozen=True)
class CredentialMessage:
    root: bytes
    device_public_key: bytes
    merkle_hash: str

    def to_bytes(self) -> bytes:
        return self.root + self.device_public_key

    def to_hex(self) -> dict[str, str]:
        return {
            "root": self.root.hex(),
            "device_public_key": self.device_public_key.hex(),
            "merkle_hash": self.merkle_hash,
            "message": self.to_bytes().hex(),
        }


@dataclass(frozen=True)
class CredentialSignature:
    scheme: str
    issuer_public_key: bytes | tuple[int, ...]
    signature: bytes | tuple[int, ...]
    message_field_elements: tuple[int, ...] = ()

    def to_hex(self) -> dict[str, str | list[str]]:
        def encode(value: bytes | tuple[int, ...]) -> str | list[str]:
            if isinstance(value, bytes):
                return value.hex()
            return [hex(x) for x in value]

        return {
            "scheme": self.scheme,
            "issuer_public_key": encode(self.issuer_public_key),
            "signature": encode(self.signature),
            "message_field_elements": [hex(x) for x in self.message_field_elements],
        }


@dataclass(frozen=True)
class IssuedCredential:
    """Credential and commitment state returned by direct issuance."""

    message: CredentialMessage
    signature: CredentialSignature
    commitment_state: Any


@dataclass(frozen=True)
class DeviceSignature:
    scheme: str
    device_public_key: tuple[int, ...]
    signature: tuple[int, ...]
    message_field_elements: tuple[int, ...]

    def to_hex(self) -> dict[str, object]:
        return {
            "scheme": self.scheme,
            "device_public_key": [hex(x) for x in self.device_public_key],
            "signature": [hex(x) for x in self.signature],
            "message_field_elements": [hex(x) for x in self.message_field_elements],
        }


@dataclass(frozen=True)
class SelectiveDisclosure:
    indexes: tuple[int, ...]
    attributes: tuple[bytes, ...]
    authentication_path: bytes | tuple[int, ...]
    merkle_hash: str

    def to_hex(self) -> dict[str, object]:
        if isinstance(self.authentication_path, bytes):
            authentication_path = self.authentication_path.hex()
        else:
            authentication_path = [hex(value) for value in self.authentication_path]
        return {
            "indexes": list(self.indexes),
            "attributes": [attribute.hex() for attribute in self.attributes],
            "authentication_path": authentication_path,
            "merkle_hash": self.merkle_hash,
        }


@dataclass(frozen=True)
class PresentationRequest:
    """Verifier challenge for the presentation protocol."""

    nonce: int
    disclosed_indexes: tuple[int, ...]


@dataclass(frozen=True)
class Credential:
    """Issuer credential bound to an attribute commitment and an SE public key."""

    message: Any
    signature: Any


@dataclass(frozen=True)
class CredentialRecord:
    """Credential stored in a user's wallet."""

    credential_id: str
    issuer_id: str
    issuer_public_key: bytes | tuple[int, ...]
    credential_type: str
    message: CredentialMessage
    signature: CredentialSignature
