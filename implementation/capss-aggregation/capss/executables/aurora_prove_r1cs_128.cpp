#include "capss/relations/r1cs_field.hpp"
#include "capss/snarks/aurora_prove_r1cs.tcc"

int main() {
    /* Set up R1CS */
    capss::init_field128("r1cs-field.txt");
    typedef capss::field128 FieldT;

    const size_t security_parameter = 128;
    const bool make_zk = false;
    const bool bit = aurora_prove_r1cs<FieldT>(security_parameter, make_zk);

    return 0;
}
