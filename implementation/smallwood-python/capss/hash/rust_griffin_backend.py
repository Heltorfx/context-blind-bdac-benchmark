from pathlib import Path


_RUST_MODULE = None
_RUST_IMPORT_ATTEMPTED = False
_PARAM_CACHE = {}
FIELD_BYTES = 32


def _hex_vec(values):
    return [hex(int(value)) for value in values]


def _append_field_bytes(out, value):
    out.extend(int(value).to_bytes(FIELD_BYTES, "big"))


def _field_vec_to_bytes(values):
    out = bytearray()
    for value in values:
        _append_field_bytes(out, value)
    return bytes(out)


def _field_rows_to_bytes(rows):
    out = bytearray()
    for row in rows:
        for value in row:
            _append_field_bytes(out, value)
    return bytes(out)


def _bytes_to_field_values(data, field):
    if len(data) % FIELD_BYTES != 0:
        raise ValueError(f"field byte buffer length must be a multiple of {FIELD_BYTES}")
    return [
        field(int.from_bytes(data[pos:pos + FIELD_BYTES], "big"))
        for pos in range(0, len(data), FIELD_BYTES)
    ]


def _bytes_tree_to_field_tree(levels, field, output_size):
    tree = []
    for level in levels:
        values = _bytes_to_field_values(level, field)
        if len(values) % output_size != 0:
            raise ValueError("tree level has an invalid number of field elements")
        tree.append([
            values[pos:pos + output_size]
            for pos in range(0, len(values), output_size)
        ])
    return tree


def _load_rust_module():
    global _RUST_IMPORT_ATTEMPTED, _RUST_MODULE
    import os
    if os.environ.get("CAPSS_DISABLE_RUST_GRIFFIN"):
        return None

    if _RUST_IMPORT_ATTEMPTED:
        return _RUST_MODULE

    _RUST_IMPORT_ATTEMPTED = True
    try:
        import rust_griffin
        _RUST_MODULE = rust_griffin
        return _RUST_MODULE
    except ImportError:
        pass

    rust_dir = Path(__file__).resolve().parents[3] / "rust-griffin"
    if not rust_dir.exists():
        return None

    import sys
    sys.path.insert(0, str(rust_dir))
    try:
        import rust_griffin
        _RUST_MODULE = rust_griffin
    except ImportError:
        _RUST_MODULE = None
    return _RUST_MODULE


def _select_sponge(hash_function, input_size, output_size):
    if hasattr(hash_function, "_perms") and hasattr(hash_function, "_selector"):
        state_size = hash_function._selector(input_size, output_size)
        return hash_function._perms[state_size]
    if hasattr(hash_function, "perm") and hasattr(hash_function, "get_rate"):
        return hash_function
    return None


def _extract_griffin_perm_params(perm):
    cache_key = id(perm)
    if cache_key in _PARAM_CACHE:
        return _PARAM_CACHE[cache_key]

    if perm is None or perm.__class__.__name__ != "Griffin":
        return None

    from sage.all import xgcd

    modulus = int(perm.get_field().order())
    _, root_exponent, _ = xgcd(int(perm.alpha), modulus - 1)
    params = {
        "modulus": hex(modulus),
        "alpha": int(perm.alpha),
        "root_exponent": hex(int(root_exponent % (modulus - 1))),
        "round_constants": _hex_vec(perm.round_constants),
        "mds": [_hex_vec(row) for row in perm.MDS_matrix.rows()],
        "alphas": _hex_vec(perm.alphas),
        "betas": _hex_vec(perm.betas),
        "field": perm.get_field(),
    }
    _PARAM_CACHE[cache_key] = params
    return params


def _extract_griffin_params(sponge):
    perm_params = _extract_griffin_perm_params(getattr(sponge, "perm", None))
    if perm_params is None:
        return None
    return {
        **perm_params,
        "rate": int(sponge.get_rate()),
        "capacity": int(sponge.get_capacity()),
        "using_tweak_hir18": bool(sponge.using_tweak_hir18),
        "capacity_last": bool(sponge.capacity_last),
    }


def batch_decs_leaf_hashes(hash_function, commitment_size, salt, leaves_data):
    rust_griffin = _load_rust_module()
    if rust_griffin is None:
        return None
    if len(leaves_data) == 0:
        return []

    input_size = len(salt) + len(leaves_data[0])
    sponge = _select_sponge(hash_function, input_size, commitment_size)
    if sponge is None:
        return None

    params = _extract_griffin_params(sponge)
    if params is None:
        return None

    rust_outputs = rust_griffin.griffin_decs_leaf_hashes(
        params["modulus"],
        params["alpha"],
        params["root_exponent"],
        params["round_constants"],
        params["mds"],
        params["alphas"],
        params["betas"],
        _hex_vec(salt),
        [_hex_vec(leaf_data) for leaf_data in leaves_data],
        commitment_size,
        params["rate"],
        params["capacity"],
        params["using_tweak_hir18"],
        params["capacity_last"],
    )
    field = params["field"]
    return [
        [field(int(value, 0)) for value in leaf_hash]
        for leaf_hash in rust_outputs
    ]


def sponge_hash(sponge, inputs, output_size):
    import os
    if os.environ.get("CAPSS_DISABLE_RUST_SPONGE"):
        return None

    rust_griffin = _load_rust_module()
    if rust_griffin is None:
        return None

    params = _extract_griffin_params(sponge)
    if params is None:
        return None

    rust_output = rust_griffin.griffin_sponge_bytes(
        params["modulus"],
        params["alpha"],
        params["root_exponent"],
        params["round_constants"],
        params["mds"],
        params["alphas"],
        params["betas"],
        _field_vec_to_bytes(inputs),
        output_size,
        params["rate"],
        params["capacity"],
        params["using_tweak_hir18"],
        params["capacity_last"],
    )
    return _bytes_to_field_values(rust_output, params["field"])


def build_truncated_merkle_tree(compression_functions, arity, output_size, leaves):
    rust_griffin = _load_rust_module()
    if rust_griffin is None:
        return None
    if len(leaves) == 0:
        return None
    if len(set(arity)) != 1:
        return None

    tree_arity = arity[0]
    compression = compression_functions.get(tree_arity)
    if compression is None:
        return None
    if compression.__class__.__name__ != "TruncationCompressionFunction":
        return None

    params = _extract_griffin_perm_params(getattr(compression, "perm", None))
    if params is None:
        return None

    rust_tree = rust_griffin.griffin_truncated_merkle_tree(
        params["modulus"],
        params["alpha"],
        params["root_exponent"],
        params["round_constants"],
        params["mds"],
        params["alphas"],
        params["betas"],
        [_hex_vec(leaf) for leaf in leaves],
        tree_arity,
        output_size,
    )
    field = params["field"]
    return [
        [
            [field(int(value, 0)) for value in node]
            for node in level
        ]
        for level in rust_tree
    ]


def build_decs_commit_tree(hash_function, compression_functions, arity, output_size, salt, leaves_data):
    import os
    if os.environ.get("CAPSS_DISABLE_RUST_COMMIT_TREE"):
        return None

    rust_griffin = _load_rust_module()
    if rust_griffin is None:
        return None
    if len(leaves_data) == 0:
        return None
    if len(set(arity)) != 1:
        return None

    tree_arity = arity[0]
    compression = compression_functions.get(tree_arity)
    if compression is None:
        return None
    if compression.__class__.__name__ != "TruncationCompressionFunction":
        return None

    leaf_len = len(leaves_data[0])
    input_size = len(salt) + leaf_len
    sponge = _select_sponge(hash_function, input_size, output_size)
    if sponge is None:
        return None

    leaf_params = _extract_griffin_params(sponge)
    compression_params = _extract_griffin_perm_params(getattr(compression, "perm", None))
    if leaf_params is None or compression_params is None:
        return None
    if leaf_params["field"] != compression_params["field"]:
        return None

    rust_tree = rust_griffin.griffin_decs_commit_tree_bytes(
        leaf_params["modulus"],
        leaf_params["alpha"],
        leaf_params["root_exponent"],
        leaf_params["round_constants"],
        leaf_params["mds"],
        leaf_params["alphas"],
        leaf_params["betas"],
        compression_params["modulus"],
        compression_params["alpha"],
        compression_params["root_exponent"],
        compression_params["round_constants"],
        compression_params["mds"],
        compression_params["alphas"],
        compression_params["betas"],
        _field_vec_to_bytes(salt),
        _field_rows_to_bytes(leaves_data),
        leaf_len,
        len(leaves_data),
        output_size,
        leaf_params["rate"],
        leaf_params["capacity"],
        leaf_params["using_tweak_hir18"],
        leaf_params["capacity_last"],
        tree_arity,
    )
    return _bytes_tree_to_field_tree(rust_tree, leaf_params["field"], output_size)


def recompute_expanded_merkle_root(compression_functions, arity, output_size, truncated, opened_leaves, auth):
    import os
    if os.environ.get("CAPSS_DISABLE_RUST_AUTH_PATH"):
        return None

    rust_griffin = _load_rust_module()
    if rust_griffin is None:
        return None
    if len(opened_leaves) == 0:
        return None
    if len(set(arity)) != 1:
        return None

    tree_arity = arity[0]
    compression = compression_functions.get(tree_arity)
    if compression is None:
        return None
    if compression.__class__.__name__ != "TruncationCompressionFunction":
        return None

    params = _extract_griffin_perm_params(getattr(compression, "perm", None))
    if params is None:
        return None

    opened_indexes = [int(index) for index, _ in opened_leaves]
    opened_leaf_values = [leaf for _, leaf in opened_leaves]
    root_bytes = rust_griffin.griffin_expanded_merkle_root_from_auth_path_bytes(
        params["modulus"],
        params["alpha"],
        params["root_exponent"],
        params["round_constants"],
        params["mds"],
        params["alphas"],
        params["betas"],
        list(arity),
        0 if truncated is None else int(truncated),
        output_size,
        opened_indexes,
        _field_rows_to_bytes(opened_leaf_values),
        _field_vec_to_bytes(auth),
    )
    if root_bytes is None:
        return None
    return _bytes_to_field_values(root_bytes, params["field"])
