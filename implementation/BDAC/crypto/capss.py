from __future__ import annotations

import sys
from typing import Sequence

from BDAC.core.types import CredentialMessage, CredentialSignature, DeviceSignature
from BDAC.crypto.encoding import credential_message_field_elements
from BDAC.parameters import (
    ATTRIBUTE_SIZE,
    CAPSS_FIELD_ORDER,
    CAPSS_SCHEME_LABEL,
    MERKLE_HASH_GRIFFIN,
    SMALLWOOD_PATH,
)


def ensure_smallwood_path() -> None:
    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))


def get_capss_scheme(scheme_label: str = CAPSS_SCHEME_LABEL):
    ensure_smallwood_path()

    from capss.sign.instances import get_scheme
    from utils.log import Log

    Log.set_verbose(False)
    return get_scheme(scheme_label)


def chunk_bytes(data: bytes, chunk_size: int) -> list[bytes]:
    return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]


def encode_bytes_to_field_elements(field, data: bytes) -> list:
    chunks = chunk_bytes(data, chunk_size=16)
    return [field(int.from_bytes(chunk, "big")) for chunk in chunks]


def credential_message_to_field_elements(field, message: CredentialMessage) -> list:
    if (
        message.merkle_hash == MERKLE_HASH_GRIFFIN
        and len(message.root) == ATTRIBUTE_SIZE
        and len(message.device_public_key) % ATTRIBUTE_SIZE == 0
    ):
        values = credential_message_field_elements(
            message.root,
            message.device_public_key,
            CAPSS_FIELD_ORDER,
            element_size=ATTRIBUTE_SIZE,
        )
        return [field(value) for value in values]
    return encode_bytes_to_field_elements(field, message.to_bytes())


def field_vector_to_int_tuple(values: Sequence) -> tuple[int, ...]:
    return tuple(int(x) for x in values)


def field_vector_to_bytes(values: Sequence, byte_size: int = ATTRIBUTE_SIZE) -> bytes:
    return b"".join(int(value).to_bytes(byte_size, "big") for value in values)


def expect_int_vector(value: bytes | tuple[int, ...]) -> tuple[int, ...]:
    if isinstance(value, bytes):
        raise TypeError("expected a CAPSS integer vector, got bytes")
    return value


class CapssIssuerSignatureBackend:
    def __init__(self, scheme_label: str = CAPSS_SCHEME_LABEL):
        self.scheme_label = scheme_label
        self.scheme = get_capss_scheme(scheme_label)
        self.field = self.scheme.get_field()
        self.public_key, self.secret_key = self.scheme.keygen()

    @classmethod
    def encode_message(cls, field, message: CredentialMessage) -> list:
        return credential_message_to_field_elements(field, message)

    def sign(self, message: CredentialMessage) -> CredentialSignature:
        field_message = self.encode_message(self.field, message)
        signature = self.scheme.sign(self.secret_key, field_message)
        return CredentialSignature(
            scheme=f"CAPSS:{self.scheme_label}",
            issuer_public_key=field_vector_to_int_tuple(self.public_key),
            signature=field_vector_to_int_tuple(signature),
            message_field_elements=field_vector_to_int_tuple(field_message),
        )

    def verify(self, message: CredentialMessage, signature: CredentialSignature) -> bool:
        if signature.scheme != f"CAPSS:{self.scheme_label}":
            return False
        public_key = [self.field(x) for x in expect_int_vector(signature.issuer_public_key)]
        sig = [self.field(x) for x in expect_int_vector(signature.signature)]
        field_message = self.encode_message(self.field, message)
        return bool(self.scheme.verify(public_key, field_message, sig))


class CapssDeviceBackend:
    def __init__(self, scheme_label: str = CAPSS_SCHEME_LABEL):
        self.scheme_label = scheme_label
        self.scheme = get_capss_scheme(scheme_label)
        self.field = self.scheme.get_field()
        self.public_key, self.secret_key = self.scheme.keygen()

    @property
    def public_key_elements(self) -> tuple[int, ...]:
        return field_vector_to_int_tuple(self.public_key)

    @property
    def public_key_bytes(self) -> bytes:
        return field_vector_to_bytes(self.public_key)

    def sign_bytes(self, message: bytes) -> DeviceSignature:
        field_message = encode_bytes_to_field_elements(self.field, message)
        signature = self.scheme.sign(self.secret_key, field_message)
        return DeviceSignature(
            scheme=f"CAPSS:{self.scheme_label}",
            device_public_key=self.public_key_elements,
            signature=field_vector_to_int_tuple(signature),
            message_field_elements=field_vector_to_int_tuple(field_message),
        )

    def sign_field_elements(self, message: Sequence[int]) -> DeviceSignature:
        field_message = [self.field(value) for value in message]
        signature = self.scheme.sign(self.secret_key, field_message)
        return DeviceSignature(
            scheme=f"CAPSS:{self.scheme_label}",
            device_public_key=self.public_key_elements,
            signature=field_vector_to_int_tuple(signature),
            message_field_elements=field_vector_to_int_tuple(field_message),
        )

    def verify_bytes(self, message: bytes, signature: DeviceSignature) -> bool:
        if signature.scheme != f"CAPSS:{self.scheme_label}":
            return False
        public_key = [self.field(x) for x in signature.device_public_key]
        sig = [self.field(x) for x in signature.signature]
        field_message = encode_bytes_to_field_elements(self.field, message)
        return bool(self.scheme.verify(public_key, field_message, sig))

    def verify_field_elements(
        self,
        message: Sequence[int],
        signature: DeviceSignature,
    ) -> bool:
        if signature.scheme != f"CAPSS:{self.scheme_label}":
            return False
        public_key = [self.field(x) for x in signature.device_public_key]
        sig = [self.field(x) for x in signature.signature]
        field_message = [self.field(value) for value in message]
        return bool(self.scheme.verify(public_key, field_message, sig))


def verify_capss_device_signature(message: bytes, signature: DeviceSignature) -> bool:
    if not signature.scheme.startswith("CAPSS:"):
        return False
    scheme_label = signature.scheme[len("CAPSS:") :]
    scheme = get_capss_scheme(scheme_label)
    field = scheme.get_field()
    public_key = [field(x) for x in signature.device_public_key]
    sig = [field(x) for x in signature.signature]
    field_message = encode_bytes_to_field_elements(field, message)
    return bool(scheme.verify(public_key, field_message, sig))
