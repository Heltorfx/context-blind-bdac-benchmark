#include <cstdint>
#include <fstream>

#include "libiop/snark/aurora_snark.hpp"
#include "capss/relations/r1cs_field.hpp"
#include "capss/relations/r1cs_capss.hpp"
#include "capss/snarks/aurora_v2.hpp"

template<typename FieldT>
bool aurora_verify_r1cs_bin(const size_t security_parameter,
                            const bool make_zk,
                            const std::string& proof_in_path, const bool use_v2 = false) {
    typedef libiop::binary_hash_digest hash_type;

    std::size_t num_constraints, num_variables, num_inputs;
    auto r1cs_params = capss::generate_r1cs_capss_verifier<FieldT>(
        num_constraints, num_inputs, num_variables);

    const size_t RS_extra_dimensions = make_zk ? 2 : 3;
    libiop::aurora_snark_parameters<FieldT, hash_type> params(
        security_parameter,
        libiop::LDT_reducer_soundness_type::optimistic_heuristic,
        libiop::FRI_soundness_type::heuristic,
        libiop::blake2b_type, 3, RS_extra_dimensions, make_zk,
        libiop::multiplicative_coset_type,
        num_constraints, num_variables);

    if (use_v2) {
        if (!make_zk) throw std::invalid_argument("BCS v2 requires ZK mode");
        capss::configure_aurora_v2(params, r1cs_params.constraint_system_, r1cs_params.primary_input_);
    }
    std::ifstream in(proof_in_path, std::ios::binary);
    if (!in.is_open()) throw std::runtime_error("cannot open " + proof_in_path);
    std::string magic(libiop::bcs_binary_transcript_magic_size(), '\0');
    in.read(&magic[0], magic.size());
    if (!in || magic != (use_v2 ? "LIBIOP_BCS_BIN_V2" : "LIBIOP_BCS_BIN_V1"))
        throw std::invalid_argument("proof/backend version mismatch");
    in.seekg(0);
    libiop::aurora_snark_argument<FieldT, hash_type> argument;
    argument.deserialize_binary(in);
    if (in.peek() != std::char_traits<char>::eof()) throw std::invalid_argument("trailing proof data");

    const bool ok = libiop::aurora_snark_verifier<FieldT, hash_type>(
        r1cs_params.constraint_system_,
        r1cs_params.primary_input_,
        argument,
        params);

    printf(ok ? "[OK] VALID\n" : "[FAIL] INVALID\n");
    return ok;
}
