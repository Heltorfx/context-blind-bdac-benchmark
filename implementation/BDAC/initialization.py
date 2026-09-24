from __future__ import annotations

from dataclasses import dataclass

from BDAC.crypto.encoding import BDAC_ENCODING_VERSION, FIELD_ELEMENT_SIZE
from BDAC.parameters import (
    ATTRIBUTE_COUNT,
    ATTRIBUTE_SIZE,
    CAPSS_FIELD_ORDER,
    CAPSS_GRIFFIN_ALPHA,
    CAPSS_SCHEME_LABEL,
    DISCLOSURE_COUNT,
    MERKLE_ARITY,
    MERKLE_HASH_GRIFFIN,
    SECURITY_LEVEL,
    SMALLWOOD_PATH,
)


@dataclass(frozen=True)
class PublicParameters:
    security_parameter: int
    attribute_count: int
    attribute_size: int
    default_disclosure_count: int
    encoding_version: int
    field_element_size: int
    merkle_arity: tuple[int, ...]
    merkle_hash: str
    field_order: int
    griffin_alpha: int
    capss_scheme_label: str


@dataclass(frozen=True)
class KeyPair:
    scheme_label: str
    public_key: tuple[int, ...]
    secret_key: tuple[int, ...]


def Setup(lambda_security: int = SECURITY_LEVEL, l: int = ATTRIBUTE_COUNT) -> PublicParameters:
    if lambda_security != SECURITY_LEVEL:
        raise NotImplementedError(
            f"The current prototype is parameterized for lambda={SECURITY_LEVEL}."
        )
    if l != ATTRIBUTE_COUNT:
        raise NotImplementedError(
            f"The current Merkle/R1CS backend is parameterized for l={ATTRIBUTE_COUNT}."
        )
    return PublicParameters(
        security_parameter=lambda_security,
        attribute_count=l,
        attribute_size=ATTRIBUTE_SIZE,
        default_disclosure_count=DISCLOSURE_COUNT,
        encoding_version=BDAC_ENCODING_VERSION,
        field_element_size=FIELD_ELEMENT_SIZE,
        merkle_arity=MERKLE_ARITY,
        merkle_hash=MERKLE_HASH_GRIFFIN,
        field_order=CAPSS_FIELD_ORDER,
        griffin_alpha=CAPSS_GRIFFIN_ALPHA,
        capss_scheme_label=CAPSS_SCHEME_LABEL,
    )


def setup(lambda_security: int = SECURITY_LEVEL, l: int = ATTRIBUTE_COUNT) -> PublicParameters:
    return Setup(lambda_security, l)


def KeyGen(pp: PublicParameters) -> KeyPair:
    import sys

    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))

    from capss.sign.instances import get_scheme
    from utils.log import Log

    Log.set_verbose(False)
    scheme = get_scheme(pp.capss_scheme_label)
    public_key, secret_key = scheme.keygen()
    return KeyPair(
        scheme_label=pp.capss_scheme_label,
        public_key=tuple(int(x) for x in public_key),
        secret_key=tuple(int(x) for x in secret_key),
    )


def IssuerKeyGen(pp: PublicParameters) -> KeyPair:
    return KeyGen(pp)


def SEKeyGen(pp: PublicParameters) -> KeyPair:
    return KeyGen(pp)
