from __future__ import annotations

import importlib.util
import sys
from typing import Iterable, Sequence

from BDAC.crypto.capss import ensure_smallwood_path
from BDAC.parameters import (
    ATTRIBUTE_COUNT,
    CAPSS_FIELD_ORDER,
    CAPSS_GRIFFIN_ALPHA,
    MERKLE_ARITY,
    MERKLE_HASH_GRIFFIN,
    MERKLE_HASH_SHAKE,
    MERKLE_PACKAGE_PATH,
    SECURITY_LEVEL,
)


def load_merkle_factory_with_shake():
    module_name = "_bdac_smallwood_merkle"
    if module_name in sys.modules:
        return sys.modules[module_name].MerkleTreeFactoryWithShake

    spec = importlib.util.spec_from_file_location(
        module_name,
        MERKLE_PACKAGE_PATH / "__init__.py",
        submodule_search_locations=[str(MERKLE_PACKAGE_PATH)],
    )
    if spec is None or spec.loader is None:
        raise ImportError("could not load the SmallWood Merkle package")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.MerkleTreeFactoryWithShake


def field_vector_to_int_tuple(values: Sequence) -> tuple[int, ...]:
    return tuple(int(x) for x in values)


def expect_int_tuple(value: bytes | tuple[int, ...]) -> tuple[int, ...]:
    if isinstance(value, bytes):
        raise TypeError("expected Griffin authentication path as field elements")
    return value


class MerkleSuite:
    def __init__(
        self,
        hash_name: str = MERKLE_HASH_SHAKE,
        *,
        attribute_count: int = ATTRIBUTE_COUNT,
        arity: tuple[int, ...] = MERKLE_ARITY,
        field_order: int = CAPSS_FIELD_ORDER,
        griffin_alpha: int = CAPSS_GRIFFIN_ALPHA,
        security_level: int = SECURITY_LEVEL,
    ):
        if hash_name not in {MERKLE_HASH_SHAKE, MERKLE_HASH_GRIFFIN}:
            raise ValueError(f"unsupported Merkle hash: {hash_name}")
        self.hash_name = hash_name
        self.attribute_count = attribute_count
        self.arity = arity
        self.field_order = field_order

        if hash_name == MERKLE_HASH_SHAKE:
            self.field = None
            factory = load_merkle_factory_with_shake()
            self.factory = factory(
                security_level=security_level,
                nb_leaves=attribute_count,
                arity=arity,
            )
            return

        ensure_smallwood_path()

        from capss.hash import JiveCompressionFunction
        from capss.hash.griffin import Griffin
        from sage.all import FiniteField
        from smallwood.commit.merkle.aohash import MerkleTreeFactoryWithAOHash

        self.field = FiniteField(field_order)
        perm = Griffin.get(field_order, griffin_alpha, 4, 1, security_level)
        compression = {4: JiveCompressionFunction(perm)}
        self.factory = MerkleTreeFactoryWithAOHash(
            nb_leaves=attribute_count,
            arity=arity,
            compression_method=compression,
            output_size=1,
            is_expanded=True,
        )

    def build_tree(self, attributes: Iterable[bytes]):
        return self.factory([self.encode_leaf(attribute) for attribute in attributes])

    def get_root_bytes(self, tree) -> bytes:
        return self.digest_to_bytes(tree.get_root())

    def get_authentication_path(self, tree, indexes: Iterable[int]) -> bytes | tuple[int, ...]:
        auth = tree.get_authentication_path(indexes)
        if isinstance(auth, bytes):
            return auth
        return field_vector_to_int_tuple(auth)

    def root_from_authentication_path(
        self,
        indexes: Iterable[int],
        attributes: Iterable[bytes],
        authentication_path: bytes | tuple[int, ...],
    ) -> bytes:
        opened_leaves = [
            (index, self.encode_leaf(attribute))
            for index, attribute in zip(indexes, attributes)
        ]
        auth = self.decode_authentication_path(authentication_path)
        return self.digest_to_bytes(
            self.factory.get_root_from_authentication_path(opened_leaves, auth)
        )

    def encode_leaf(self, attribute: bytes):
        if self.hash_name == MERKLE_HASH_SHAKE:
            return attribute
        return [self.field(int.from_bytes(attribute, "big"))]

    def decode_authentication_path(self, authentication_path: bytes | tuple[int, ...]):
        if self.hash_name == MERKLE_HASH_SHAKE:
            return authentication_path
        return [self.field(value) for value in expect_int_tuple(authentication_path)]

    def digest_to_bytes(self, digest) -> bytes:
        if isinstance(digest, bytes):
            return digest
        return b"".join(int(value).to_bytes(32, "big") for value in digest)

    @staticmethod
    def authentication_path_size(authentication_path: bytes | tuple[int, ...]) -> str:
        if isinstance(authentication_path, bytes):
            return f"{len(authentication_path)} bytes"
        return f"{len(authentication_path)} field elements"
