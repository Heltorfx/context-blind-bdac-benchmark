from __future__ import annotations

from dataclasses import dataclass
import sys

from BDAC.parameters import (
    CAPSS_FIELD_ORDER,
    CAPSS_GRIFFIN_ALPHA,
    PRESENTATION_DOMAIN_TAG,
    SECURITY_LEVEL,
    SMALLWOOD_PATH,
)


@dataclass(frozen=True)
class PresentationContextOpening:
    context: int
    randomness: int
    commitment: int


def commit_presentation_context(context: int, randomness: int) -> int:
    if str(SMALLWOOD_PATH) not in sys.path:
        sys.path.insert(0, str(SMALLWOOD_PATH))

    from capss.hash import JiveCompressionFunction
    from capss.hash.griffin import Griffin
    from sage.all import FiniteField

    field = FiniteField(CAPSS_FIELD_ORDER)
    permutation = Griffin.get(
        CAPSS_FIELD_ORDER,
        CAPSS_GRIFFIN_ALPHA,
        4,
        1,
        SECURITY_LEVEL,
    )
    compression = JiveCompressionFunction(permutation)
    return int(
        compression(
            [
                field(PRESENTATION_DOMAIN_TAG),
                field(context),
                field(randomness),
                field(0),
            ],
            output_size=1,
        )[0]
    )
