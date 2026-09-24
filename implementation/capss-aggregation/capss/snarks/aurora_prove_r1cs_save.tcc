#include <cstdint>
#include <fstream>

#include "libiop/snark/aurora_snark.hpp"
#include "capss/relations/r1cs_field.hpp"
#include "capss/relations/r1cs_capss.hpp"

template<typename FieldT>
bool aurora_prove_r1cs_save(const size_t security_parameter,
                            const bool make_zk,
                            const std::string& proof_out_path) {
    typedef libiop::binary_hash_digest hash_type;

    std::size_t num_constraints, num_variables, num_inputs;
    auto r1cs_params = capss::generate_r1cs_capss<FieldT>(
        num_constraints, num_inputs, num_variables);

    const size_t RS_extra_dimensions = make_zk ? 2 : 3;
    libiop::aurora_snark_parameters<FieldT, hash_type> params(
        security_parameter,
        libiop::LDT_reducer_soundness_type::optimistic_heuristic,
        libiop::FRI_soundness_type::heuristic,
        libiop::blake2b_type,
        /*FRI_localization_parameter=*/ 3,
        RS_extra_dimensions,
        make_zk,
        libiop::multiplicative_coset_type,
        num_constraints, num_variables);

    auto argument = libiop::aurora_snark_prover<FieldT>(
        r1cs_params.constraint_system_,
        r1cs_params.primary_input_,
        r1cs_params.auxiliary_input_,
        params);

    std::ofstream out(proof_out_path, std::ios::binary);
    if (!out.is_open()) throw std::runtime_error("cannot open " + proof_out_path);
    argument.serialize(out);
    printf("[+] Wrote proof (%lu bytes) to %s\n",
           argument.size_in_bytes(), proof_out_path.c_str());
    return true;
}
