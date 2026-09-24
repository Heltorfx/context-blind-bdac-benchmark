 #ifndef RELATIONS__CAPSS__R1CS_CAPSS_HPP_
 #define RELATIONS__CAPSS__R1CS_CAPSS_HPP_
 
 #include "libiop/relations/r1cs.hpp"
 
 namespace capss {
 
 template<typename FieldT>
 struct r1cs_capss {
     libiop::r1cs_constraint_system<FieldT> constraint_system_;
     libiop::r1cs_primary_input<FieldT> primary_input_;
     libiop::r1cs_auxiliary_input<FieldT> auxiliary_input_;
 
     r1cs_capss<FieldT>() = default;
     r1cs_capss<FieldT>(const r1cs_capss<FieldT> &other) = default;
     r1cs_capss<FieldT>(const libiop::r1cs_constraint_system<FieldT> &constraint_system,
                          const libiop::r1cs_primary_input<FieldT> &primary_input,
                          const libiop::r1cs_auxiliary_input<FieldT> &auxiliary_input) :
         constraint_system_(constraint_system),
         primary_input_(primary_input),
         auxiliary_input_(auxiliary_input)
     {};
     r1cs_capss<FieldT>(libiop::r1cs_constraint_system<FieldT> &&constraint_system,
                          libiop::r1cs_primary_input<FieldT> &&primary_input,
                          libiop::r1cs_auxiliary_input<FieldT> &&auxiliary_input) :
         constraint_system_(std::move(constraint_system)),
         primary_input_(std::move(primary_input)),
         auxiliary_input_(std::move(auxiliary_input))
     {};
 };
 
template<typename FieldT>
 r1cs_capss<FieldT> generate_r1cs_capss(size_t& num_constraints,
                                            size_t& num_inputs,
                                            size_t& num_variables);

template<typename FieldT>
r1cs_capss<FieldT> generate_r1cs_capss_verifier(size_t& num_constraints,
                                                size_t& num_inputs,
                                                size_t& num_variables);
 
 } // libiop
 
 #include "capss/relations/r1cs_capss.tcc"
 
 #endif // RELATIONS__CAPSS__R1CS_CAPSS_HPP_
 
