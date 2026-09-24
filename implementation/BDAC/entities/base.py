from __future__ import annotations

from dataclasses import dataclass

from BDAC.initialization import KeyGen, KeyPair, PublicParameters


@dataclass
class Entity:
    pp: PublicParameters


class KeyedEntity(Entity):
    key_pair: KeyPair | None

    def __init__(self, pp: PublicParameters):
        super().__init__(pp)
        self.key_pair = None

    def keygen(self) -> KeyPair:
        self.key_pair = KeyGen(self.pp)
        return self.key_pair
