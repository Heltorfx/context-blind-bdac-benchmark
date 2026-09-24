#pragma once
#include "libiop/bcs/hashing/bcs_v2.hpp"
#include "libiop/snark/aurora_snark.hpp"

namespace capss {
inline bool aurora_v2_mode(int argc, char **argv) {
    if (argc <= 2) return false;
    if (argc != 3 || (std::string(argv[2]) != "normal" && std::string(argv[2]) != "v2"))
        throw std::invalid_argument("usage: executable proof.bin [normal|v2]");
    return std::string(argv[2]) == "v2";
}
template<typename FieldT>
void configure_aurora_v2(libiop::aurora_snark_parameters<FieldT, libiop::binary_hash_digest> &params,
                         const libiop::r1cs_constraint_system<FieldT> &cs,
                         const libiop::r1cs_primary_input<FieldT> &primary) {
    using namespace libiop::bcs_v2;
    if (params.bcs_params_.security_parameter != 128 || FieldT::mod.num_bits() > 256)
        throw std::invalid_argument("this BCS v2 implementation supports the 128-bit/256-bit-field profile");
    std::string statement;
    integer(statement, FieldT::mod, (FieldT::mod.num_bits()+7)/8);
    u64(statement, cs.num_inputs()); u64(statement, cs.num_variables()); u64(statement, cs.num_constraints());
    for (const auto &constraint : cs.constraints_) {
        for (const auto *lc : {&constraint.a_, &constraint.b_, &constraint.c_}) {
            u64(statement, lc->terms.size());
            for (const auto &term : lc->terms) { u64(statement, term.index_); field(statement, term.coeff_); }
        }
    }
    bytes(statement, fields(primary));
    bytes(statement, "aurora-v2-heuristic-fri-optimistic-ldt");
    const auto &iop = params.iop_params_;
    u64(statement, params.bcs_params_.security_parameter);
    u64(statement, iop.make_zk()); u64(statement, iop.RS_extra_dimensions());
    u64(statement, static_cast<size_t>(iop.domain_type()));
    u64(statement, iop.constraint_domain_dim()); u64(statement, iop.variable_domain_dim());
    u64(statement, iop.codeword_domain_dim()); u64(statement, iop.query_bound());
    const auto localization = iop.FRI_params_.get_localization_parameters();
    u64(statement, localization.size());
    for (const auto value : localization) u64(statement, value);
    u64(statement, iop.FRI_params_.query_repetitions());
    u64(statement, iop.FRI_params_.interactive_repetitions());
    u64(statement, iop.FRI_params_.poly_degree_bound());
    u64(statement, iop.LDT_reducer_params_.num_output_LDT_instances());
    u64(statement, iop.LDT_reducer_params_.absolute_proximity_parameter());
    u64(statement, params.bcs_params_.pow_params_.work_parameter());
    u64(statement, params.bcs_params_.pow_params_.pow_bitlen());
    auto &bcs = params.bcs_params_;
    bcs.use_v2 = true;
    bcs.hashchain_ = std::make_shared<transcript<FieldT>>(hash("public-instance", statement));
    bcs.leafhasher_ = std::make_shared<leafhash_v2<FieldT>>();
    bcs.compression_hasher = node;
    bcs.pow_hasher = [](const std::string &challenge, const std::string &answer, size_t width) {
        if (width != 32 || challenge.size() != 32 || answer.size() != 32)
            throw std::invalid_argument("invalid BCS v2 proof of work");
        return hash("pow-work", challenge + answer);
    };
}
}
