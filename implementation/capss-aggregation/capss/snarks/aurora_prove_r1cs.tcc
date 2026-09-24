#include <cstdint>

#include "libiop/snark/aurora_snark.hpp"

#include "capss/relations/r1cs_field.hpp"
#include "capss/relations/r1cs_capss.hpp"

template<typename FieldT>
bool aurora_prove_r1cs(const size_t security_parameter, const bool make_zk) {
    typedef libiop::binary_hash_digest hash_type;

    //libff::inhibit_profiling_info = true;

    std::size_t num_constraints;
    std::size_t num_variables;
    std::size_t num_inputs;
    capss::r1cs_capss<FieldT> r1cs_params = capss::generate_r1cs_capss<FieldT>(num_constraints, num_inputs, num_variables);
    /*EXPECT_TRUE(r1cs_params.constraint_system_.is_satisfied(
        r1cs_params.primary_input_, r1cs_params.auxiliary_input_));*/

    const size_t RS_extra_dimensions = (make_zk==true) ? 2 : 3;
    const size_t FRI_localization_parameter = 3;
    const libiop::LDT_reducer_soundness_type ldt_reducer_soundness_type = libiop::LDT_reducer_soundness_type::optimistic_heuristic;
    const libiop::FRI_soundness_type fri_soundness_type = libiop::FRI_soundness_type::heuristic;
    //const field_subset_type domain_type = affine_subspace_type;
    const libiop::field_subset_type domain_type = libiop::multiplicative_coset_type;

    /* Actual SNARK test */
    libiop::aurora_snark_parameters<FieldT, hash_type> params(
        security_parameter,
        ldt_reducer_soundness_type,
        fri_soundness_type,
        libiop::blake2b_type,
        FRI_localization_parameter,
        RS_extra_dimensions,
        make_zk,
        domain_type,
        num_constraints,
        num_variables);
    const libiop::aurora_snark_argument<FieldT, hash_type> argument = libiop::aurora_snark_prover<FieldT>(
        r1cs_params.constraint_system_,
        r1cs_params.primary_input_,
        r1cs_params.auxiliary_input_,
        params);

    printf("iop size in bytes %lu\n", argument.IOP_size_in_bytes());
    printf("bcs size in bytes %lu\n", argument.BCS_size_in_bytes());
    printf("argument size in bytes %lu\n", argument.size_in_bytes());

    std::ofstream file_proof_transcript("proof-transcript.txt");
    if(!file_proof_transcript.is_open()) {
        throw std::invalid_argument("Impossible to open file with primary inputs.");
    }
    argument.serialize(file_proof_transcript);
    file_proof_transcript.close();

    const bool bit = libiop::aurora_snark_verifier<FieldT, hash_type>(
        r1cs_params.constraint_system_,
        r1cs_params.primary_input_,
        argument,
        params);

    if(bit) {
        printf("Everything in fine.\n");
    } else {
        printf(" ==> ERROR: VERIFICATION FAILED <==\n");
    }
    return bit;
}
