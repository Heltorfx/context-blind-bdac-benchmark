#include <cstdint>
#include <fstream>

#include "libiop/snark/aurora_snark.hpp"
#include "capss/relations/r1cs_field.hpp"
#include "capss/relations/r1cs_capss.hpp"
#include "capss/snarks/aurora_v2.hpp"

template<typename FieldT>
bool aurora_prove_r1cs_save_bin(const size_t security_parameter,
                                const bool make_zk,
                                const std::string& proof_out_path, const bool use_v2 = false) {
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

    if (use_v2) {
        if (!make_zk) throw std::invalid_argument("BCS v2 requires ZK mode");
        capss::configure_aurora_v2(params, r1cs_params.constraint_system_, r1cs_params.primary_input_);
    }
    auto argument = libiop::aurora_snark_prover<FieldT>(
        r1cs_params.constraint_system_,
        r1cs_params.primary_input_,
        r1cs_params.auxiliary_input_,
        params);

    std::ofstream out(proof_out_path, std::ios::binary);
    if (!out.is_open()) throw std::runtime_error("cannot open " + proof_out_path);
    argument.serialize_binary(out);
    const std::streampos serialized_size = out.tellp();
    out.close();

    printf("[+] Wrote binary proof (%lu logical bytes, %lu serialized bytes) to %s\n",
           static_cast<unsigned long>(argument.size_in_bytes()),
           static_cast<unsigned long>(serialized_size),
           proof_out_path.c_str());
    return true;
}
