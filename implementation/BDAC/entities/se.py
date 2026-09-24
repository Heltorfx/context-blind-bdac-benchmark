from __future__ import annotations

from BDAC.core.types import DeviceSignature
from BDAC.crypto.capss import CapssDeviceBackend
from BDAC.initialization import KeyPair

from .base import KeyedEntity


class SE(KeyedEntity):
    def __init__(self, pp):
        super().__init__(pp)
        self.backend = CapssDeviceBackend(pp.capss_scheme_label)

    @property
    def public_key_bytes(self) -> bytes:
        return self.backend.public_key_bytes

    @property
    def public_key_elements(self) -> tuple[int, ...]:
        return self.backend.public_key_elements

    def keygen(self) -> KeyPair:
        self.key_pair = KeyPair(
            scheme_label=self.pp.capss_scheme_label,
            public_key=tuple(int(x) for x in self.backend.public_key),
            secret_key=tuple(int(x) for x in self.backend.secret_key),
        )
        return self.key_pair

    def sign_commitment(self, commitment: bytes) -> DeviceSignature:
        return self.sign_message(commitment)

    def sign_message(self, message: bytes) -> DeviceSignature:
        return self.backend.sign_bytes(message)

    def sign_field_elements(self, message: tuple[int, ...]) -> DeviceSignature:
        return self.backend.sign_field_elements(message)

    def verify_commitment_signature(
        self,
        commitment: bytes,
        signature: DeviceSignature,
    ) -> bool:
        return self.verify_message_signature(commitment, signature)

    def verify_message_signature(
        self,
        message: bytes,
        signature: DeviceSignature,
    ) -> bool:
        return self.backend.verify_bytes(message, signature)
