from __future__ import annotations

import secrets
from typing import Iterable

from BDAC.crypto.encoding import canonical_index_set


def random_bytes(size: int) -> bytes:
    if size <= 0:
        raise ValueError("random byte length must be positive")
    return secrets.token_bytes(size)


def random_field_element_int(field_order: int, byte_size: int = 32) -> int:
    while True:
        value = int.from_bytes(random_bytes(byte_size), "big")
        if value < field_order:
            return value


def random_field_element_bytes(field_order: int, byte_size: int = 32) -> bytes:
    return random_field_element_int(field_order, byte_size).to_bytes(byte_size, "big")


def random_field_attribute(field_order: int, attribute_size: int = 32) -> bytes:
    return random_field_element_bytes(field_order, attribute_size)


def random_attribute_vector(
    field_order: int,
    attribute_count: int,
    attribute_size: int = 32,
) -> tuple[bytes, ...]:
    if attribute_count <= 0:
        raise ValueError("attribute_count must be positive")
    return tuple(
        random_field_attribute(field_order, attribute_size)
        for _ in range(attribute_count)
    )


def sample_index_set(
    attribute_count: int,
    disclosure_count: int,
) -> tuple[int, ...]:
    if disclosure_count <= 0:
        raise ValueError("disclosure_count must be positive")
    if disclosure_count > attribute_count:
        raise ValueError("cannot disclose more attributes than available")
    indexes: Iterable[int] = secrets.SystemRandom().sample(
        range(attribute_count),
        disclosure_count,
    )
    return canonical_index_set(indexes, attribute_count)

