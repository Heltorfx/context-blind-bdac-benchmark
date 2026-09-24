#include <cstdint>
#include <fstream>

#include "libiop/snark/aurora_snark.hpp"
#include "capss/relations/r1cs_field.hpp"
#include "capss/relations/r1cs_capss.hpp"

template<typename FieldT>
bool aurora_verify_r1cs(const size_t security_parameter,
                        const bool make_zk,
                        const std::string& proof_in_path) {
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

    std::ifstream in(proof_in_path, std::ios::binary);
    if (!in.is_open()) throw std::runtime_error("cannot open " + proof_in_path);
    libiop::aurora_snark_argument<FieldT, hash_type> argument;
    argument.deserialize(in);

    const bool ok = libiop::aurora_snark_verifier<FieldT, hash_type>(
        r1cs_params.constraint_system_,
        r1cs_params.primary_input_,
        argument,
        params);

    printf(ok ? "[✓] VALID\n" : "[✗] INVALID\n");
    return ok;
}
