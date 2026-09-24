from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


BDAC_ENCODING_VERSION = 1
FIELD_ELEMENT_SIZE = 32
U32_SIZE = 4

CREDENTIAL_MESSAGE_DOMAIN = b"BDAC-v1:credential-message"
INDEX_SET_DOMAIN = b"BDAC-v1:index-set"
ATTRIBUTE_VECTOR_DOMAIN = b"BDAC-v1:attribute-vector"
PRESENTATION_CHALLENGE_DOMAIN = b"BDAC-v1:show-challenge"


class EncodingError(ValueError):
    """Raised when a value has no canonical BDAC encoding."""


@dataclass(frozen=True)
class CredentialMessageViews:
    """Canonical views of the credential message.

    ``signature_field_elements`` is the view signed by CAPSS and checked by the
    current Show circuit. ``signature_bytes`` is the same value serialized as
    fixed-width field elements, i.e. ``root || dpk`` for the current instance.
    ``transcript_bytes`` is length-delimited and versioned for logs or future
    wire formats; it is intentionally not the value signed by the current R1CS.
    """

    root: bytes
    device_public_key: bytes
    signature_field_elements: tuple[int, ...]
    signature_bytes: bytes
    transcript_bytes: bytes


def encode_u32(value: int) -> bytes:
    if value < 0 or value >= 2**32:
        raise EncodingError(f"u32 value out of range: {value}")
    return int(value).to_bytes(U32_SIZE, "big")


def encode_bytes_with_length(value: bytes) -> bytes:
    return encode_u32(len(value)) + value


def encode_field_element(value: int, field_order: int, size: int = FIELD_ELEMENT_SIZE) -> bytes:
    value = int(value)
    if value < 0 or value >= field_order:
        raise EncodingError("field element is outside the field order")
    return value.to_bytes(size, "big")


def decode_field_element(
    data: bytes,
    field_order: int,
    size: int = FIELD_ELEMENT_SIZE,
) -> int:
    if len(data) != size:
        raise EncodingError(
            f"field element must be {size} bytes, got {len(data)}"
        )
    value = int.from_bytes(data, "big")
    if value >= field_order:
        raise EncodingError("encoded field element is outside the field order")
    return value


def split_field_element_bytes(
    data: bytes,
    field_order: int,
    element_size: int = FIELD_ELEMENT_SIZE,
) -> tuple[int, ...]:
    if len(data) == 0 or len(data) % element_size != 0:
        raise EncodingError(
            f"field element byte string length must be a non-zero multiple of {element_size}"
        )
    return tuple(
        decode_field_element(data[i : i + element_size], field_order, element_size)
        for i in range(0, len(data), element_size)
    )


def encode_field_elements(
    values: Sequence[int],
    field_order: int,
    element_size: int = FIELD_ELEMENT_SIZE,
) -> bytes:
    if not values:
        raise EncodingError("at least one field element is required")
    return b"".join(
        encode_field_element(value, field_order, element_size) for value in values
    )


def normalize_attribute(
    attribute: bytes,
    field_order: int,
    attribute_size: int = FIELD_ELEMENT_SIZE,
) -> bytes:
    if not isinstance(attribute, bytes):
        raise EncodingError("attributes must be bytes")
    if len(attribute) != attribute_size:
        raise EncodingError(
            f"attribute must be {attribute_size} bytes, got {len(attribute)}"
        )
    decode_field_element(attribute, field_order, attribute_size)
    return attribute


def normalize_attribute_vector(
    attributes: Iterable[bytes],
    field_order: int,
    attribute_count: int,
    attribute_size: int = FIELD_ELEMENT_SIZE,
) -> tuple[bytes, ...]:
    values = tuple(
        normalize_attribute(attribute, field_order, attribute_size)
        for attribute in attributes
    )
    if len(values) != attribute_count:
        raise EncodingError(
            f"expected {attribute_count} attributes, got {len(values)}"
        )
    return values


def canonical_index_set(
    indexes: Iterable[int],
    attribute_count: int,
    *,
    allow_empty: bool = False,
) -> tuple[int, ...]:
    values = tuple(sorted(int(index) for index in indexes))
    if not values and not allow_empty:
        raise EncodingError("index set cannot be empty")
    if len(set(values)) != len(values):
        raise EncodingError("index set must not contain duplicates")
    if values and (values[0] < 0 or values[-1] >= attribute_count):
        raise EncodingError(
            f"index set must be contained in [0, {attribute_count - 1}]"
        )
    return values


def encode_index_set(
    indexes: Iterable[int],
    attribute_count: int,
    *,
    allow_empty: bool = False,
) -> bytes:
    values = canonical_index_set(
        indexes,
        attribute_count,
        allow_empty=allow_empty,
    )
    return (
        INDEX_SET_DOMAIN
        + encode_u32(BDAC_ENCODING_VERSION)
        + encode_u32(len(values))
        + b"".join(encode_u32(index) for index in values)
    )


def credential_message_field_elements(
    root: bytes,
    device_public_key: bytes,
    field_order: int,
    *,
    element_size: int = FIELD_ELEMENT_SIZE,
    expected_device_public_key_elements: int = 2,
) -> tuple[int, ...]:
    root_element = decode_field_element(root, field_order, element_size)
    device_public_key_elements = split_field_element_bytes(
        device_public_key,
        field_order,
        element_size,
    )
    if len(device_public_key_elements) != expected_device_public_key_elements:
        raise EncodingError(
            "device public key must contain "
            f"{expected_device_public_key_elements} field elements, "
            f"got {len(device_public_key_elements)}"
        )
    return (root_element, *device_public_key_elements)


def credential_message_signature_bytes(
    root: bytes,
    device_public_key: bytes,
    field_order: int,
    *,
    element_size: int = FIELD_ELEMENT_SIZE,
    expected_device_public_key_elements: int = 2,
) -> bytes:
    return encode_field_elements(
        credential_message_field_elements(
            root,
            device_public_key,
            field_order,
            element_size=element_size,
            expected_device_public_key_elements=expected_device_public_key_elements,
        ),
        field_order,
        element_size,
    )


def credential_message_transcript_bytes(
    root: bytes,
    device_public_key: bytes,
    merkle_hash: str,
) -> bytes:
    merkle_hash_bytes = merkle_hash.encode("ascii")
    return (
        CREDENTIAL_MESSAGE_DOMAIN
        + encode_u32(BDAC_ENCODING_VERSION)
        + encode_bytes_with_length(merkle_hash_bytes)
        + encode_bytes_with_length(root)
        + encode_bytes_with_length(device_public_key)
    )


def credential_message_views(
    root: bytes,
    device_public_key: bytes,
    merkle_hash: str,
    field_order: int,
    *,
    element_size: int = FIELD_ELEMENT_SIZE,
    expected_device_public_key_elements: int = 2,
) -> CredentialMessageViews:
    field_elements = credential_message_field_elements(
        root,
        device_public_key,
        field_order,
        element_size=element_size,
        expected_device_public_key_elements=expected_device_public_key_elements,
    )
    return CredentialMessageViews(
        root=root,
        device_public_key=device_public_key,
        signature_field_elements=field_elements,
        signature_bytes=encode_field_elements(field_elements, field_order, element_size),
        transcript_bytes=credential_message_transcript_bytes(
            root,
            device_public_key,
            merkle_hash,
        ),
    )


def encode_presentation_challenge(nonce: int, field_order: int) -> bytes:
    return (
        PRESENTATION_CHALLENGE_DOMAIN
        + encode_u32(BDAC_ENCODING_VERSION)
        + encode_field_element(nonce, field_order)
    )
