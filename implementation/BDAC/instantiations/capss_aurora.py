from __future__ import annotations

from BDAC.scheme import BDACScheme, SchemeConfig


class CapssAuroraBDAC(BDACScheme):
    """Concrete BDAC instantiation using CAPSS, Griffin Merkle trees, and Aurora."""

    name = "BDAC-CAPSS-Aurora"


def create_scheme(config: SchemeConfig | None = None) -> CapssAuroraBDAC:
    return CapssAuroraBDAC(config)
