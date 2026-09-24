#include <iostream>
#include "capss/relations/r1cs_field.hpp"
#include "libiop/bcs/bcs_prover.hpp"
#include "libiop/bcs/bcs_verifier.hpp"
#include "libiop/bcs/common_bcs_parameters.hpp"
#include "libiop/bcs/hashing/bcs_v2.hpp"
#include "libiop/tests/bcs/dummy_bcs_protocol.hpp"

using Field = capss::field256;
using Digest = libiop::binary_hash_digest;

bool check_binding(size_t coset_size, bool v2) {
    using namespace libiop;
    auto params = default_bcs_params<Field, Digest>(blake2b_type, 128, 3);
    if (v2) {
        params.use_v2 = true;
        params.hashchain_ = std::make_shared<bcs_v2::transcript<Field>>("query-binding-test");
        params.leafhasher_ = std::make_shared<bcs_v2::leafhash_v2<Field>>();
        params.compression_hasher = bcs_v2::node;
        params.pow_hasher = [](const Digest &c, const Digest &a, size_t) {
            return bcs_v2::hash("pow-work", c + a);
        };
    }
    const field_subset<Field> domain(8);
    const auto round = coset_size == 1 ? round_parameters<Field>() :
        round_parameters<Field>(domain.get_subset_of_order(coset_size));
    const std::vector<round_parameters<Field>> rounds{round};
    bcs_prover<Field, Digest> prover(params);
    auto dh = prover.register_domain(domain);
    dummy_protocol<Field> protocol(prover, 1, 1, rounds, dh, true, false);
    prover.seal_interaction_registrations();
    prover.seal_query_registrations();
    protocol.calculate_and_submit_response();
    const auto handle = protocol.get_oracle_handles_for_round(0).at(0);
    for (size_t i = 0; i < coset_size; ++i)
        prover.get_oracle_evaluation_at_point(handle, i * (8 / coset_size), true);
    auto proof = prover.get_transcript();
    {
        bcs_verifier<Field, Digest> honest(params, proof);
        auto vd = honest.register_domain(domain);
        dummy_protocol<Field> vp(honest, 1, 1, rounds, vd, true, false);
        honest.seal_interaction_registrations();
        if (!honest.transcript_is_valid()) throw std::runtime_error("honest opening rejected");
    }
    // Keep the root, opened leaf and path; claim they answer the next coset instead.
    for (auto &position : proof.query_positions_.at(0)) ++position;
    try {
        bcs_verifier<Field, Digest> verifier(params, proof);
        auto vd = verifier.register_domain(domain);
        dummy_protocol<Field> vp(verifier, 1, 1, rounds, vd, true, false);
        verifier.seal_interaction_registrations();
        if (!verifier.transcript_is_valid()) return true;
        const auto result = verifier.get_oracle_evaluation_at_point(
            vp.get_oracle_handles_for_round(0).at(0), 1, false);
        if (result == Field::zero()) {
            std::cerr << "FAIL: authenticated leaf 0 returned as oracle position 1; coset size "
                      << coset_size << std::endl;
            return false;
        }
        throw std::runtime_error("unexpected relabelled response");
    } catch (const std::invalid_argument &) {
        return true;
    }
}

bool check_multiple_domains(bool v2) {
    using namespace libiop;
    auto params = default_bcs_params<Field, Digest>(blake2b_type, 128, 3);
    if (v2) {
        params.use_v2 = true;
        params.hashchain_ = std::make_shared<bcs_v2::transcript<Field>>("multi-domain-test");
        params.leafhasher_ = std::make_shared<bcs_v2::leafhash_v2<Field>>();
        params.compression_hasher = bcs_v2::node;
        params.pow_hasher = [](const Digest &c, const Digest &a, size_t) {
            return bcs_v2::hash("pow-work", c + a);
        };
    }

    const field_subset<Field> first_domain(8), second_domain(16);
    bcs_prover<Field, Digest> prover(params);
    const auto first_handle = prover.register_domain(first_domain);
    const auto second_handle = prover.register_domain(second_domain);
    prover.set_round_parameters(round_parameters<Field>());
    auto first_oracle = std::make_shared<oracle_handle>(
        prover.register_oracle("first", first_handle, 7, false));
    auto second_oracle = std::make_shared<oracle_handle>(
        prover.register_oracle("second", second_handle, 15, false));
    prover.seal_interaction_registrations();
    prover.seal_query_registrations();
    std::vector<Field> first_values(8), second_values(16);
    for (size_t i = 0; i < first_values.size(); ++i) first_values[i] = Field(10 + i);
    for (size_t i = 0; i < second_values.size(); ++i) second_values[i] = Field(100 + i);
    prover.submit_oracle(first_oracle, std::move(first_values));
    prover.submit_oracle(second_oracle, std::move(second_values));
    prover.signal_prover_round_done();
    prover.get_oracle_evaluation_at_point(first_oracle, 3, true);
    prover.get_oracle_evaluation_at_point(second_oracle, 11, true);
    const auto proof = prover.get_transcript();

    bcs_verifier<Field, Digest> verifier(params, proof);
    const auto verifier_first_domain = verifier.register_domain(first_domain);
    const auto verifier_second_domain = verifier.register_domain(second_domain);
    verifier.set_round_parameters(round_parameters<Field>());
    auto verifier_first_oracle = std::make_shared<oracle_handle>(
        verifier.register_oracle("first", verifier_first_domain, 7, false));
    auto verifier_second_oracle = std::make_shared<oracle_handle>(
        verifier.register_oracle("second", verifier_second_domain, 15, false));
    verifier.seal_interaction_registrations();
    return verifier.transcript_is_valid() &&
        verifier.get_oracle_evaluation_at_point(verifier_first_oracle, 3, false) == Field(13) &&
        verifier.get_oracle_evaluation_at_point(verifier_second_oracle, 11, false) == Field(111);
}

int main() {
    capss::init_field256("r1cs-field.txt");
    bool passed = true;
    for (const bool v2 : {false, true})
        for (const size_t size : {1, 2, 4})
            passed = check_binding(size, v2) && passed;
    for (const bool v2 : {false, true})
        passed = check_multiple_domains(v2) && passed;
    if (!passed) return 1;
    std::cout << "PASS: oracle indexes bound to authenticated leaves, plain, grouped and multi-domain\n";
}
