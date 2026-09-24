#include <cassert>
#include <stdexcept>

#include <iostream>
#include <fstream>
#include <string>

#include "libiop/algebra/utils.hpp"
#include "libff/algebra/field_utils/bigint.hpp"
#include "capss/relations/r1cs_field.hpp"

namespace capss {

template<typename FieldT>
FieldT to_field_element(const std::string& s); // déclaration du template primaire

template<>
field256 to_field_element<field256>(const std::string& s) {
    return field256(s.c_str());
}

template<>
field128 to_field_element<field128>(const std::string& s) {
    return field128(s.c_str());
}

template<>
field64 to_field_element<field64>(const std::string& s) {
    return field64(s.c_str());
}

template<typename FieldT>
void read_primary_inputs(std::string filename, libiop::r1cs_primary_input<FieldT>& primary_input, size_t& nb_batched, size_t& num_inputs_per_inst, size_t& num_inputs) {
    std::string felt_str;
    std::ifstream file_primary_inputs(filename);
    if(!file_primary_inputs.is_open()) {
        throw std::invalid_argument("Impossible to open file with primary inputs.");
    }
    file_primary_inputs >> nb_batched;
    file_primary_inputs >> num_inputs_per_inst;
    for(size_t j=0; j<nb_batched; j++) {
        for(size_t i=0; i<num_inputs_per_inst; i++) {
            file_primary_inputs >> felt_str;
            primary_input.push_back(to_field_element<FieldT>(felt_str));
        }
    }
    file_primary_inputs.close();
    num_inputs = 1;
    while(num_inputs < nb_batched*num_inputs_per_inst) {
        num_inputs = ((num_inputs+1)<<1)-1;
    }
    for(size_t i=nb_batched*num_inputs_per_inst; i<num_inputs; i++) {
        primary_input.push_back(FieldT::zero());
    }
}

template<typename FieldT>
void read_auxiliary_inputs(std::string filename, size_t nb_batched, size_t num_inputs_per_inst, size_t num_inputs, libiop::r1cs_auxiliary_input<FieldT>& auxiliary_input, size_t& num_variables_per_inst, size_t& num_variables) {
    std::string felt_str;
    std::ifstream file_auxiliary_inputs(filename);
    if(!file_auxiliary_inputs.is_open()) {
        throw std::invalid_argument("Impossible to open r1cs-auxiliary-inputs.txt.");
    }
    size_t auxiliary_input_size;
    size_t nb_batched_2;
    file_auxiliary_inputs >> nb_batched_2;
    if(nb_batched != nb_batched_2) {
        throw std::invalid_argument("Imcompatible nb batched.");
    }
    file_auxiliary_inputs >> auxiliary_input_size;
    for(size_t j=0; j<nb_batched; j++) {
        for(size_t i=0; i<auxiliary_input_size; i++) {
            file_auxiliary_inputs >> felt_str;
            auxiliary_input.push_back(to_field_element<FieldT>(felt_str));
        }
    }
    file_auxiliary_inputs.close();
    num_variables_per_inst = num_inputs_per_inst + auxiliary_input_size;
    size_t unpadded_num_variables = num_inputs+auxiliary_input_size*nb_batched;
    num_variables = 1;
    while(num_variables < unpadded_num_variables) {
        num_variables = ((num_variables+1)<<1)-1;
    }
    for(size_t i=unpadded_num_variables; i<num_variables; i++) {
        auxiliary_input.push_back(FieldT::zero());
    }
}

template<typename FieldT>
void read_r1cs(std::string filename, size_t nb_batched, size_t num_inputs_per_inst, size_t num_variables_per_inst, size_t num_inputs, size_t num_variables, libiop::r1cs_constraint_system<FieldT>& cs, size_t& num_constraints_per_inst) {
    std::string felt_str;
    cs.primary_input_size_ = num_inputs;
    cs.auxiliary_input_size_ = num_variables - num_inputs;

    for(uint32_t num_inst=0; num_inst<nb_batched; num_inst++) {
        std::ifstream file_constraints(filename);
        if(!file_constraints.is_open()) {
            throw std::invalid_argument("Impossible to open the R1CS file.");
        }
        if(num_inst == 0) {
            size_t num_inputs_r1cs, num_variables_r1cs;
            file_constraints >> num_inputs_r1cs;
            file_constraints >> num_variables_r1cs;
            file_constraints >> num_constraints_per_inst;
            if(num_inputs_r1cs != num_inputs_per_inst) {
                throw std::invalid_argument("num_inputs_r1cs != num_inputs_per_inst.");
            }
            if(num_variables_r1cs != num_variables_per_inst) {
                throw std::invalid_argument("num_variables_r1cs != num_variables_per_inst.");
            }
        } else {
            size_t tmp;
            file_constraints >> tmp;
            file_constraints >> tmp;
            file_constraints >> tmp;
        }
        for(size_t i=0; i<num_constraints_per_inst; i++) {
            libiop::linear_combination<FieldT> A, B, C;

            size_t size_a;
            file_constraints >> size_a;
            for(size_t j=0; j<size_a; j++) {
                uint64_t idx;
                file_constraints >> idx;
                file_constraints >> felt_str;
                if(idx > 0) {
                    if(idx-1 < num_inputs_per_inst) {
                        idx = (idx-1) + num_inputs_per_inst*num_inst + 1;
                    } else {
                        idx = (idx-1-num_inputs_per_inst) + (num_variables_per_inst-num_inputs_per_inst)*num_inst + num_inputs + 1;
                    }
                }
                if(idx > num_variables) {
                    throw std::invalid_argument("Alert A.");
                }
                A.add_term(idx, to_field_element<FieldT>(felt_str));
            }

            size_t size_b;
            file_constraints >> size_b;
            for(size_t j=0; j<size_b; j++) {
                uint64_t idx;
                file_constraints >> idx;
                file_constraints >> felt_str;
                uint64_t pr_idx = idx;
                if(idx > 0) {
                    if(idx-1 < num_inputs_per_inst) {
                        idx = (idx-1) + num_inputs_per_inst*num_inst + 1;
                    } else {
                        idx = (idx-1-num_inputs_per_inst) + (num_variables_per_inst-num_inputs_per_inst)*num_inst + num_inputs + 1;
                    }
                }
                if(idx > num_variables) {
                    std::cout << num_variables << " " << num_inputs << " " << num_variables_per_inst << " " << num_inputs_per_inst << " " << std::endl;
                    std::cout << num_inst << " " << i << std::endl;
                    std::cout << pr_idx << " -> " << idx << std::endl;
                    to_field_element<FieldT>(felt_str).print();
                    throw std::invalid_argument("Alert B.");
                }
                B.add_term(idx, to_field_element<FieldT>(felt_str));
            }

            size_t size_c;
            file_constraints >> size_c;
            for(size_t j=0; j<size_c; j++) {
                uint64_t idx;
                file_constraints >> idx;
                file_constraints >> felt_str;
                if(idx > 0) {
                    if(idx-1 < num_inputs_per_inst) {
                        idx = (idx-1) + num_inputs_per_inst*num_inst + 1;
                    } else {
                        idx = (idx-1-num_inputs_per_inst) + (num_variables_per_inst-num_inputs_per_inst)*num_inst + num_inputs + 1;
                    }
                }
                if(idx > num_variables) {
                    throw std::invalid_argument("Alert C.");
                }
                C.add_term(idx, to_field_element<FieldT>(felt_str));
            }

            cs.add_constraint(libiop::r1cs_constraint<FieldT>(A, B, C));
        }
        file_constraints.close();
    }

    size_t unpadded_num_constraints = cs.num_constraints();
    size_t num_constraints = 1;
    while(num_constraints < unpadded_num_constraints) {
        num_constraints = (num_constraints<<1);
    }
    for(size_t i=unpadded_num_constraints; i<num_constraints; i++) {
        libiop::linear_combination<FieldT> A, B, C;
        A.add_term(1, FieldT(1));
        B.add_term(0, FieldT(1));
        C.add_term(1, FieldT(1));
        cs.add_constraint(libiop::r1cs_constraint<FieldT>(A, B, C));
    }
}

template<typename FieldT>
r1cs_capss<FieldT> generate_r1cs_capss(size_t& num_constraints,
                                           size_t& num_inputs,
                                           size_t& num_variables)
{
    size_t nb_batched, num_inputs_per_inst, num_variables_per_inst, num_constraints_per_inst;

    libiop::r1cs_primary_input<FieldT> primary_input;
    read_primary_inputs("r1cs-primary-inputs.txt", primary_input, nb_batched, num_inputs_per_inst, num_inputs);
    if(primary_input.size() != num_inputs) {
        throw std::invalid_argument("primary_input.size() != num_inputs.");
    }

    libiop::r1cs_auxiliary_input<FieldT> auxiliary_input;
    read_auxiliary_inputs("r1cs-auxiliary-inputs.txt", nb_batched, num_inputs_per_inst, num_inputs, auxiliary_input, num_variables_per_inst, num_variables);
    if(auxiliary_input.size() != num_variables-num_inputs) {
        throw std::invalid_argument("auxiliary_input.size() != num_variables-num_inputs.");
    }

    libiop::r1cs_constraint_system<FieldT> cs;
    read_r1cs("r1cs-constraints.txt", nb_batched, num_inputs_per_inst, num_variables_per_inst, num_inputs, num_variables, cs, num_constraints_per_inst);
    num_constraints = cs.num_constraints();
    
    /* sanity checks */
    assert(cs.num_variables() == num_variables);
    assert(cs.num_variables() >= num_inputs);
    assert(cs.num_inputs() == num_inputs);
    assert(cs.is_satisfied(primary_input, auxiliary_input));
    std::cout << "nb_batched = " << nb_batched << std::endl;
    std::cout << "num_inputs_per_inst = " << num_inputs_per_inst << std::endl;
    std::cout << "num_inputs = " << num_inputs << std::endl;
    std::cout << "num_variables_per_inst = " << num_variables_per_inst << std::endl;
    std::cout << "num_variables = " << num_variables << std::endl;
    std::cout << "num_constraints_per_inst = " << num_constraints_per_inst << std::endl;
    std::cout << "num_constraints = " << num_constraints << std::endl;
    
    return r1cs_capss<FieldT>(std::move(cs), std::move(primary_input), std::move(auxiliary_input));
}

template<typename FieldT>
r1cs_capss<FieldT> generate_r1cs_capss_verifier(size_t& num_constraints,
                                                size_t& num_inputs,
                                                size_t& num_variables)
{
    size_t nb_batched, num_inputs_per_inst;
    libiop::r1cs_primary_input<FieldT> primary_input;
    read_primary_inputs(
        "r1cs-primary-inputs.txt",
        primary_input,
        nb_batched,
        num_inputs_per_inst,
        num_inputs);
    if (primary_input.size() != num_inputs) {
        throw std::invalid_argument("primary_input.size() != num_inputs.");
    }

    std::ifstream file_constraints("r1cs-constraints.txt");
    if (!file_constraints.is_open()) {
        throw std::invalid_argument("Impossible to open the R1CS file.");
    }
    size_t header_inputs, num_variables_per_inst, num_constraints_per_inst;
    file_constraints >> header_inputs >> num_variables_per_inst >> num_constraints_per_inst;
    if (!file_constraints || header_inputs != num_inputs_per_inst ||
        num_variables_per_inst < num_inputs_per_inst) {
        throw std::invalid_argument("Invalid R1CS dimensions.");
    }
    file_constraints.close();

    const size_t auxiliary_variables_per_inst =
        num_variables_per_inst - num_inputs_per_inst;
    const size_t unpadded_num_variables =
        num_inputs + auxiliary_variables_per_inst * nb_batched;
    num_variables = 1;
    while (num_variables < unpadded_num_variables) {
        num_variables = ((num_variables + 1) << 1) - 1;
    }

    libiop::r1cs_constraint_system<FieldT> cs;
    read_r1cs(
        "r1cs-constraints.txt",
        nb_batched,
        num_inputs_per_inst,
        num_variables_per_inst,
        num_inputs,
        num_variables,
        cs,
        num_constraints_per_inst);
    num_constraints = cs.num_constraints();

    if (cs.num_variables() != num_variables || cs.num_inputs() != num_inputs) {
        throw std::invalid_argument("Loaded R1CS dimensions are inconsistent.");
    }

    return r1cs_capss<FieldT>(
        std::move(cs),
        std::move(primary_input),
        libiop::r1cs_auxiliary_input<FieldT>());
}

} // libiop
