from __future__ import annotations

from BDAC.crypto.encoding import (
    EncodingError,
    canonical_index_set,
    credential_message_signature_bytes,
    credential_message_transcript_bytes,
    credential_message_views,
    encode_index_set,
    normalize_attribute_vector,
)
from BDAC.crypto.capss import credential_message_to_field_elements
from BDAC.entities.governance import GovernanceAuthority
from BDAC.entities.issuer import Issuer
from BDAC.entities.se import SE
from BDAC.entities.user import User
from BDAC.initialization import Setup


def _assert_raises(error_type, fn) -> None:
    try:
        fn()
    except error_type:
        return
    raise AssertionError(f"expected {error_type.__name__}")


def test_index_encoding() -> None:
    pp = Setup()
    indexes = canonical_index_set((7, 1, 4), pp.attribute_count)
    assert indexes == (1, 4, 7)
    assert encode_index_set(indexes, pp.attribute_count).startswith(b"BDAC-v1:index-set")
    _assert_raises(
        EncodingError,
        lambda: canonical_index_set((1, 1), pp.attribute_count),
    )
    _assert_raises(
        EncodingError,
        lambda: canonical_index_set((pp.attribute_count,), pp.attribute_count),
    )


def test_attribute_encoding() -> None:
    pp = Setup()
    governance = GovernanceAuthority(pp)
    attributes = governance.issue_attributes().values
    assert normalize_attribute_vector(
        attributes,
        pp.field_order,
        pp.attribute_count,
        pp.attribute_size,
    ) == attributes
    _assert_raises(
        EncodingError,
        lambda: normalize_attribute_vector(
            attributes[:-1],
            pp.field_order,
            pp.attribute_count,
            pp.attribute_size,
        ),
    )


def test_credential_message_encoding_matches_backend() -> None:
    pp = Setup()
    se = SE(pp)
    user = User(pp, se)
    attributes = GovernanceAuthority(pp).issue_attributes()
    user.receive_attributes(attributes)
    message = Issuer(pp).issue(user.attributes, user.device_public_key).message

    views = credential_message_views(
        message.root,
        message.device_public_key,
        message.merkle_hash,
        pp.field_order,
        element_size=pp.field_element_size,
    )
    assert views.signature_bytes == message.to_bytes()
    assert credential_message_signature_bytes(
        message.root,
        message.device_public_key,
        pp.field_order,
        element_size=pp.field_element_size,
    ) == message.to_bytes()
    assert credential_message_transcript_bytes(
        message.root,
        message.device_public_key,
        message.merkle_hash,
    ).startswith(b"BDAC-v1:credential-message")

    from sage.all import FiniteField

    field = FiniteField(pp.field_order)
    legacy = tuple(int(x) for x in credential_message_to_field_elements(field, message))
    assert views.signature_field_elements == legacy


def main() -> None:
    test_index_encoding()
    test_attribute_encoding()
    test_credential_message_encoding_matches_backend()
    print("BDAC encoding checks: ok")


if __name__ == "__main__":
    main()
