use ark_bn254::Fr;
use ark_ff::{BigInteger, Field, PrimeField};
use num_bigint::BigUint;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rayon::prelude::*;

const FIELD_BYTES: usize = 32;

#[derive(Clone)]
struct GriffinParams {
    alpha: u64,
    root_exponent: Vec<u64>,
    round_constants: Vec<Fr>,
    mds: Vec<Vec<Fr>>,
    alphas: Vec<Fr>,
    betas: Vec<Fr>,
}

impl GriffinParams {
    fn state_size(&self) -> usize {
        self.mds.len()
    }

    fn rounds(&self) -> PyResult<usize> {
        let t = self.state_size();
        if t == 0 {
            return Err(PyValueError::new_err("MDS matrix must not be empty"));
        }
        if self.round_constants.len() % t != 0 {
            return Err(PyValueError::new_err(
                "round_constants length must be a multiple of the state size",
            ));
        }
        Ok(self.round_constants.len() / t + 1)
    }

    fn validate(&self) -> PyResult<()> {
        let t = self.state_size();
        if t < 3 {
            return Err(PyValueError::new_err(
                "Griffin state size must be at least 3",
            ));
        }
        if self.mds.iter().any(|row| row.len() != t) {
            return Err(PyValueError::new_err("MDS matrix must be square"));
        }
        if self.alphas.len() != t - 2 || self.betas.len() != t - 2 {
            return Err(PyValueError::new_err(
                "alphas and betas must have length state_size - 2",
            ));
        }
        self.rounds()?;
        Ok(())
    }
}

fn parse_biguint(value: &str) -> PyResult<BigUint> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return Err(PyValueError::new_err("empty integer string"));
    }
    let parsed = if let Some(hex) = trimmed
        .strip_prefix("0x")
        .or_else(|| trimmed.strip_prefix("0X"))
    {
        BigUint::parse_bytes(hex.as_bytes(), 16)
    } else {
        BigUint::parse_bytes(trimmed.as_bytes(), 10)
    };
    parsed.ok_or_else(|| PyValueError::new_err(format!("invalid integer: {trimmed}")))
}

fn fr_modulus() -> BigUint {
    BigUint::from_bytes_be(&Fr::MODULUS.to_bytes_be())
}

fn parse_fr(value: &str) -> PyResult<Fr> {
    let value = parse_biguint(value)?;
    Ok(Fr::from_be_bytes_mod_order(&value.to_bytes_be()))
}

fn parse_vec(values: Vec<String>) -> PyResult<Vec<Fr>> {
    values.iter().map(|value| parse_fr(value)).collect()
}

fn parse_matrix(values: Vec<Vec<String>>) -> PyResult<Vec<Vec<Fr>>> {
    values.into_iter().map(parse_vec).collect()
}

fn format_hex(values: Vec<Fr>) -> Vec<String> {
    values
        .into_iter()
        .map(|value| {
            let value = BigUint::from_bytes_be(&value.into_bigint().to_bytes_be());
            format!("0x{}", value.to_str_radix(16))
        })
        .collect()
}

fn parse_flat_field_bytes(bytes: &[u8]) -> PyResult<Vec<Fr>> {
    if bytes.len() % FIELD_BYTES != 0 {
        return Err(PyValueError::new_err(format!(
            "field byte buffer length must be a multiple of {FIELD_BYTES}"
        )));
    }
    Ok(bytes
        .chunks_exact(FIELD_BYTES)
        .map(Fr::from_be_bytes_mod_order)
        .collect())
}

fn append_field_bytes(out: &mut Vec<u8>, value: &Fr) -> PyResult<()> {
    let raw = value.into_bigint().to_bytes_be();
    if raw.len() > FIELD_BYTES {
        return Err(PyValueError::new_err(format!(
            "field element does not fit in {FIELD_BYTES} bytes"
        )));
    }
    out.extend(std::iter::repeat(0).take(FIELD_BYTES - raw.len()));
    out.extend_from_slice(&raw);
    Ok(())
}

fn encode_level_bytes(level: &[Vec<Fr>]) -> PyResult<Vec<u8>> {
    let value_count: usize = level.iter().map(Vec::len).sum();
    let mut out = Vec::with_capacity(value_count * FIELD_BYTES);
    for node in level {
        for value in node {
            append_field_bytes(&mut out, value)?;
        }
    }
    Ok(out)
}

fn parse_nodes_bytes(bytes: &[u8], output_size: usize) -> PyResult<Vec<Vec<Fr>>> {
    if output_size == 0 {
        return Err(PyValueError::new_err("output_size must not be zero"));
    }
    let values = parse_flat_field_bytes(bytes)?;
    if values.len() % output_size != 0 {
        return Err(PyValueError::new_err(
            "node byte buffer has an invalid number of field elements",
        ));
    }
    Ok(values
        .chunks(output_size)
        .map(|chunk| chunk.to_vec())
        .collect())
}

fn encode_node_bytes(node: Vec<Fr>) -> PyResult<Vec<u8>> {
    encode_level_bytes(&[node])
}

fn parse_params(
    modulus: String,
    alpha: u64,
    root_exponent: String,
    round_constants: Vec<String>,
    mds: Vec<Vec<String>>,
    alphas: Vec<String>,
    betas: Vec<String>,
) -> PyResult<GriffinParams> {
    let modulus = parse_biguint(&modulus)?;
    if modulus != fr_modulus() {
        return Err(PyValueError::new_err(
            "the optimized Griffin backend currently supports only ark_bn254::Fr",
        ));
    }
    let params = GriffinParams {
        root_exponent: parse_biguint(&root_exponent)?.to_u64_digits(),
        round_constants: parse_vec(round_constants)?,
        mds: parse_matrix(mds)?,
        alphas: parse_vec(alphas)?,
        betas: parse_vec(betas)?,
        alpha,
    };
    params.validate()?;
    Ok(params)
}

fn run_griffin_round(params: &GriffinParams, state: &[Fr], round_constants: &[Fr]) -> Vec<Fr> {
    let t = params.state_size();

    let mut nonlinear = state.to_vec();
    nonlinear[0] = state[0].pow(&params.root_exponent);
    nonlinear[1] = state[1].pow([params.alpha]);

    let l2 = nonlinear[0] + nonlinear[1];
    let l2_sq = l2.square();
    let alpha_l2 = params.alphas[0] * l2;
    let factor2 = l2_sq + alpha_l2 + params.betas[0];
    nonlinear[2] = state[2] * factor2;

    for i in 3..t {
        let coeff = Fr::from((i - 1) as u64);
        let l = coeff * nonlinear[0] + nonlinear[1] + state[i - 1];
        let factor = l.square() + params.alphas[i - 2] * l + params.betas[i - 2];
        nonlinear[i] = state[i] * factor;
    }

    let mut out = vec![Fr::ZERO; t];
    for row in 0..t {
        let mut acc = Fr::ZERO;
        for col in 0..t {
            acc += params.mds[row][col] * nonlinear[col];
        }
        out[row] = acc + round_constants[row];
    }
    out
}

fn run_griffin_permutation(params: &GriffinParams, input_state: Vec<Fr>) -> PyResult<Vec<Fr>> {
    let t = params.state_size();
    if input_state.len() != t {
        return Err(PyValueError::new_err(format!(
            "state has length {}, expected {t}",
            input_state.len()
        )));
    }

    let rounds = params.rounds()?;
    let zero_constants = vec![Fr::ZERO; t];
    let mut state = input_state;
    for round in 0..rounds {
        let constants = if round < rounds - 1 {
            &params.round_constants[round * t..(round + 1) * t]
        } else {
            &zero_constants
        };
        state = run_griffin_round(params, &state, constants);
    }
    Ok(state)
}

fn run_sponge(
    params: &GriffinParams,
    mut inputs: Vec<Fr>,
    output_size: usize,
    rate: usize,
    capacity: usize,
    using_tweak_hir18: bool,
    capacity_last: bool,
) -> PyResult<Vec<Fr>> {
    if inputs.is_empty() {
        return Err(PyValueError::new_err("cannot hash the empty string"));
    }
    if rate + capacity != params.state_size() {
        return Err(PyValueError::new_err(
            "rate + capacity must equal Griffin state size",
        ));
    }
    if output_size == 0 {
        return Ok(Vec::new());
    }

    let offset_capacity = if !using_tweak_hir18 || inputs.len() % rate != 0 {
        let missing = rate - (inputs.len() % rate);
        inputs.push(Fr::ONE);
        for _ in 1..missing {
            inputs.push(Fr::ZERO);
        }
        Fr::ZERO
    } else {
        Fr::ONE
    };

    let mut state = vec![Fr::ZERO; rate + capacity];
    let nb_input_blocks = inputs.len() / rate;
    for (num_block, block) in inputs.chunks(rate).enumerate() {
        for (i, value) in block.iter().enumerate() {
            let pos = if capacity_last { i } else { capacity + i };
            state[pos] += value;
        }
        let capacity_pos = if capacity_last { state.len() - 1 } else { 0 };
        if num_block == nb_input_blocks - 1 {
            state[capacity_pos] += offset_capacity;
        }
        state = run_griffin_permutation(params, state)?;
    }

    let mut outputs = Vec::with_capacity(output_size);
    loop {
        let visible = if capacity_last {
            &state[..state.len() - capacity]
        } else {
            &state[capacity..]
        };
        for value in visible {
            if outputs.len() == output_size {
                return Ok(outputs);
            }
            outputs.push(value.clone());
        }
        state = run_griffin_permutation(params, state)?;
    }
}

fn run_truncation_compression(
    params: &GriffinParams,
    inputs: Vec<Fr>,
    output_size: usize,
) -> PyResult<Vec<Fr>> {
    if inputs.len() != params.state_size() {
        return Err(PyValueError::new_err(format!(
            "compression input has length {}, expected {}",
            inputs.len(),
            params.state_size()
        )));
    }
    if output_size >= inputs.len() {
        return Err(PyValueError::new_err(
            "truncation output_size must be smaller than input size",
        ));
    }

    let perm_output = run_griffin_permutation(params, inputs.clone())?;
    let mut output = Vec::with_capacity(output_size);
    for i in 0..output_size {
        output.push(perm_output[i] + inputs[i]);
    }
    Ok(output)
}

fn build_truncated_merkle_levels(
    params: &GriffinParams,
    leaves: Vec<Vec<Fr>>,
    arity: usize,
    output_size: usize,
) -> PyResult<Vec<Vec<Vec<Fr>>>> {
    if arity == 0 {
        return Err(PyValueError::new_err("arity must not be zero"));
    }
    if leaves.is_empty() {
        return Err(PyValueError::new_err("leaves must not be empty"));
    }
    if leaves.iter().any(|leaf| leaf.len() != output_size) {
        return Err(PyValueError::new_err(
            "all leaves must have length output_size",
        ));
    }

    let mut current = leaves;
    let mut levels = vec![current.clone()];
    while current.len() > 1 {
        if current.len() % arity != 0 {
            return Err(PyValueError::new_err(
                "number of nodes is not divisible by arity",
            ));
        }
        current = current
            .par_chunks(arity)
            .map(|children| {
                let mut input = Vec::with_capacity(arity * output_size);
                for child in children {
                    input.extend(child.iter().cloned());
                }
                run_truncation_compression(params, input, output_size)
            })
            .collect::<PyResult<_>>()?;
        levels.push(current.clone());
    }

    levels.reverse();
    Ok(levels)
}

fn recompute_single_merkle_root_from_auth(
    params: &GriffinParams,
    arity: &[usize],
    output_size: usize,
    open_index: usize,
    open_leaf: Vec<Fr>,
    auth: &[Fr],
    auth_pos: &mut usize,
) -> PyResult<Vec<Fr>> {
    let depth = arity.len();
    let mut index = open_index;
    let mut value = open_leaf;

    for dp in (0..depth).rev() {
        let local_arity = arity[dp];
        if local_arity == 0 {
            return Err(PyValueError::new_err("arity must not be zero"));
        }
        let selected_child = index % local_arity;
        let mut children = Vec::with_capacity(local_arity * output_size);
        for child_pos in 0..local_arity {
            if child_pos == selected_child {
                if value.len() != output_size {
                    return Err(PyValueError::new_err(
                        "opened leaf or intermediate node has invalid length",
                    ));
                }
                children.extend(value.iter().cloned());
            } else {
                if *auth_pos + output_size > auth.len() {
                    return Err(PyValueError::new_err("authentication path is too short"));
                }
                children.extend(auth[*auth_pos..*auth_pos + output_size].iter().cloned());
                *auth_pos += output_size;
            }
        }
        value = run_truncation_compression(params, children, output_size)?;
        index /= local_arity;
    }

    Ok(value)
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn griffin_permutation(
    modulus: String,
    alpha: u64,
    root_exponent: String,
    round_constants: Vec<String>,
    mds: Vec<Vec<String>>,
    alphas: Vec<String>,
    betas: Vec<String>,
    state: Vec<String>,
) -> PyResult<Vec<String>> {
    let params = parse_params(
        modulus,
        alpha,
        root_exponent,
        round_constants,
        mds,
        alphas,
        betas,
    )?;
    let input_state = parse_vec(state)?;
    let output = run_griffin_permutation(&params, input_state)?;
    Ok(format_hex(output))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn griffin_sponge(
    modulus: String,
    alpha: u64,
    root_exponent: String,
    round_constants: Vec<String>,
    mds: Vec<Vec<String>>,
    alphas: Vec<String>,
    betas: Vec<String>,
    inputs: Vec<String>,
    output_size: usize,
    rate: usize,
    capacity: usize,
    using_tweak_hir18: bool,
    capacity_last: bool,
) -> PyResult<Vec<String>> {
    let params = parse_params(
        modulus,
        alpha,
        root_exponent,
        round_constants,
        mds,
        alphas,
        betas,
    )?;
    let inputs = parse_vec(inputs)?;
    let output = run_sponge(
        &params,
        inputs,
        output_size,
        rate,
        capacity,
        using_tweak_hir18,
        capacity_last,
    )?;
    Ok(format_hex(output))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn griffin_sponge_bytes(
    modulus: String,
    alpha: u64,
    root_exponent: String,
    round_constants: Vec<String>,
    mds: Vec<Vec<String>>,
    alphas: Vec<String>,
    betas: Vec<String>,
    inputs_bytes: Vec<u8>,
    output_size: usize,
    rate: usize,
    capacity: usize,
    using_tweak_hir18: bool,
    capacity_last: bool,
) -> PyResult<Vec<u8>> {
    let params = parse_params(
        modulus,
        alpha,
        root_exponent,
        round_constants,
        mds,
        alphas,
        betas,
    )?;
    let inputs = parse_flat_field_bytes(&inputs_bytes)?;
    let output = run_sponge(
        &params,
        inputs,
        output_size,
        rate,
        capacity,
        using_tweak_hir18,
        capacity_last,
    )?;
    encode_level_bytes(&[output])
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn griffin_decs_leaf_hashes(
    modulus: String,
    alpha: u64,
    root_exponent: String,
    round_constants: Vec<String>,
    mds: Vec<Vec<String>>,
    alphas: Vec<String>,
    betas: Vec<String>,
    salt: Vec<String>,
    leaves: Vec<Vec<String>>,
    output_size: usize,
    rate: usize,
    capacity: usize,
    using_tweak_hir18: bool,
    capacity_last: bool,
) -> PyResult<Vec<Vec<String>>> {
    let params = parse_params(
        modulus,
        alpha,
        root_exponent,
        round_constants,
        mds,
        alphas,
        betas,
    )?;
    let salt = parse_vec(salt)?;
    if salt.is_empty() {
        return Err(PyValueError::new_err("salt must not be empty"));
    }

    leaves
        .into_par_iter()
        .enumerate()
        .map(|(idx, leaf)| {
            let mut domain_separator = salt.clone();
            let last = domain_separator.len() - 1;
            domain_separator[last] += Fr::from(idx as u64);
            let mut input = domain_separator;
            input.extend(parse_vec(leaf)?);
            let hash = run_sponge(
                &params,
                input,
                output_size,
                rate,
                capacity,
                using_tweak_hir18,
                capacity_last,
            )?;
            Ok(format_hex(hash))
        })
        .collect()
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn griffin_truncated_merkle_tree(
    modulus: String,
    alpha: u64,
    root_exponent: String,
    round_constants: Vec<String>,
    mds: Vec<Vec<String>>,
    alphas: Vec<String>,
    betas: Vec<String>,
    leaves: Vec<Vec<String>>,
    arity: usize,
    output_size: usize,
) -> PyResult<Vec<Vec<Vec<String>>>> {
    let params = parse_params(
        modulus,
        alpha,
        root_exponent,
        round_constants,
        mds,
        alphas,
        betas,
    )?;
    let current: Vec<Vec<Fr>> = leaves.into_iter().map(parse_vec).collect::<PyResult<_>>()?;
    let levels = build_truncated_merkle_levels(&params, current, arity, output_size)?;
    Ok(levels
        .into_iter()
        .map(|level| level.into_iter().map(format_hex).collect())
        .collect())
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn griffin_decs_commit_tree_bytes(
    leaf_modulus: String,
    leaf_alpha: u64,
    leaf_root_exponent: String,
    leaf_round_constants: Vec<String>,
    leaf_mds: Vec<Vec<String>>,
    leaf_alphas: Vec<String>,
    leaf_betas: Vec<String>,
    compression_modulus: String,
    compression_alpha: u64,
    compression_root_exponent: String,
    compression_round_constants: Vec<String>,
    compression_mds: Vec<Vec<String>>,
    compression_alphas: Vec<String>,
    compression_betas: Vec<String>,
    salt_bytes: Vec<u8>,
    leaves_bytes: Vec<u8>,
    leaf_len: usize,
    nb_leaves: usize,
    output_size: usize,
    leaf_rate: usize,
    leaf_capacity: usize,
    leaf_using_tweak_hir18: bool,
    leaf_capacity_last: bool,
    tree_arity: usize,
) -> PyResult<Vec<Vec<u8>>> {
    if leaf_len == 0 {
        return Err(PyValueError::new_err("leaf_len must not be zero"));
    }
    if nb_leaves == 0 {
        return Err(PyValueError::new_err("nb_leaves must not be zero"));
    }
    let expected_leaves_bytes = nb_leaves
        .checked_mul(leaf_len)
        .and_then(|count| count.checked_mul(FIELD_BYTES))
        .ok_or_else(|| PyValueError::new_err("leaf byte buffer length overflow"))?;
    if leaves_bytes.len() != expected_leaves_bytes {
        return Err(PyValueError::new_err(format!(
            "leaves byte buffer has length {}, expected {}",
            leaves_bytes.len(),
            expected_leaves_bytes
        )));
    }

    let leaf_params = parse_params(
        leaf_modulus,
        leaf_alpha,
        leaf_root_exponent,
        leaf_round_constants,
        leaf_mds,
        leaf_alphas,
        leaf_betas,
    )?;
    let compression_params = parse_params(
        compression_modulus,
        compression_alpha,
        compression_root_exponent,
        compression_round_constants,
        compression_mds,
        compression_alphas,
        compression_betas,
    )?;

    let salt = parse_flat_field_bytes(&salt_bytes)?;
    if salt.is_empty() {
        return Err(PyValueError::new_err("salt must not be empty"));
    }

    let leaf_byte_len = leaf_len * FIELD_BYTES;
    let hashed_leaves = (0..nb_leaves)
        .into_par_iter()
        .map(|idx| {
            let start = idx * leaf_byte_len;
            let end = start + leaf_byte_len;
            let mut domain_separator = salt.clone();
            let last = domain_separator.len() - 1;
            domain_separator[last] += Fr::from(idx as u64);
            let mut input = domain_separator;
            input.extend(parse_flat_field_bytes(&leaves_bytes[start..end])?);
            run_sponge(
                &leaf_params,
                input,
                output_size,
                leaf_rate,
                leaf_capacity,
                leaf_using_tweak_hir18,
                leaf_capacity_last,
            )
        })
        .collect::<PyResult<Vec<_>>>()?;

    let levels =
        build_truncated_merkle_levels(&compression_params, hashed_leaves, tree_arity, output_size)?;
    levels
        .iter()
        .map(|level| encode_level_bytes(level))
        .collect()
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn griffin_expanded_merkle_root_from_auth_path_bytes(
    modulus: String,
    alpha: u64,
    root_exponent: String,
    round_constants: Vec<String>,
    mds: Vec<Vec<String>>,
    alphas: Vec<String>,
    betas: Vec<String>,
    arity: Vec<usize>,
    truncated: usize,
    output_size: usize,
    opened_indexes: Vec<usize>,
    opened_leaves_bytes: Vec<u8>,
    auth_bytes: Vec<u8>,
) -> PyResult<Option<Vec<u8>>> {
    if opened_indexes.is_empty() {
        return Err(PyValueError::new_err("opened_indexes must not be empty"));
    }
    if truncated > arity.len() {
        return Err(PyValueError::new_err("truncated depth exceeds tree depth"));
    }

    let params = parse_params(
        modulus,
        alpha,
        root_exponent,
        round_constants,
        mds,
        alphas,
        betas,
    )?;
    let opened_leaves = parse_nodes_bytes(&opened_leaves_bytes, output_size)?;
    if opened_leaves.len() != opened_indexes.len() {
        return Err(PyValueError::new_err(
            "opened_leaves and opened_indexes length mismatch",
        ));
    }
    let auth = parse_flat_field_bytes(&auth_bytes)?;

    let mut depth_width = Vec::with_capacity(arity.len() + 1);
    depth_width.push(1usize);
    for local_arity in &arity {
        if *local_arity == 0 {
            return Err(PyValueError::new_err("arity must not be zero"));
        }
        let next = depth_width
            .last()
            .unwrap()
            .checked_mul(*local_arity)
            .ok_or_else(|| PyValueError::new_err("depth width overflow"))?;
        depth_width.push(next);
    }

    let nb_root_preimages = depth_width[truncated];
    let mut auth_pos = 0usize;
    let needed_root_values = nb_root_preimages
        .checked_mul(output_size)
        .ok_or_else(|| PyValueError::new_err("root preimage size overflow"))?;
    if auth.len() < needed_root_values {
        return Err(PyValueError::new_err("authentication path is too short"));
    }
    let root_preimages: Vec<Vec<Fr>> = auth[..needed_root_values]
        .chunks(output_size)
        .map(|chunk| chunk.to_vec())
        .collect();
    auth_pos += needed_root_values;

    let root = if truncated == 0 {
        root_preimages[0].clone()
    } else {
        let top_levels =
            build_truncated_merkle_levels(&params, root_preimages.clone(), arity[0], output_size)?;
        top_levels[0][0].clone()
    };

    let nb_total_leaves = *depth_width.last().unwrap();
    if nb_total_leaves % nb_root_preimages != 0 {
        return Err(PyValueError::new_err("invalid expanded tree shape"));
    }
    let nb_subtree_leaves = nb_total_leaves / nb_root_preimages;
    let subtree_arity = &arity[truncated..];

    for (open_index, open_leaf) in opened_indexes.into_iter().zip(opened_leaves.into_iter()) {
        if open_index >= nb_total_leaves {
            return Err(PyValueError::new_err("opened index is out of range"));
        }
        let preimage_selector = open_index / nb_subtree_leaves;
        let sub_open_index = open_index % nb_subtree_leaves;
        let preimage = recompute_single_merkle_root_from_auth(
            &params,
            subtree_arity,
            output_size,
            sub_open_index,
            open_leaf,
            &auth,
            &mut auth_pos,
        )?;
        if preimage != root_preimages[preimage_selector] {
            return Ok(None);
        }
    }

    if auth_pos != auth.len() {
        return Err(PyValueError::new_err(
            "authentication path has trailing field elements",
        ));
    }

    Ok(Some(encode_node_bytes(root)?))
}

#[pymodule]
fn rust_griffin(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(griffin_permutation, m)?)?;
    m.add_function(wrap_pyfunction!(griffin_sponge, m)?)?;
    m.add_function(wrap_pyfunction!(griffin_sponge_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(griffin_decs_leaf_hashes, m)?)?;
    m.add_function(wrap_pyfunction!(griffin_truncated_merkle_tree, m)?)?;
    m.add_function(wrap_pyfunction!(griffin_decs_commit_tree_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(
        griffin_expanded_merkle_root_from_auth_path_bytes,
        m
    )?)?;
    Ok(())
}
