#include "capss/relations/r1cs_field.hpp"
#include "capss/snarks/aurora_verify_r1cs_bin.tcc"

int main(int argc, char** argv) {
    capss::init_field256("r1cs-field.txt");
    const std::string in_path = argc > 1 ? argv[1] : "proof.bin";
    try {
        return aurora_verify_r1cs_bin<capss::field256>(128, true, in_path, capss::aurora_v2_mode(argc, argv)) ? 0 : 1;
    } catch (const std::exception &error) {
        std::cerr << error.what() << std::endl;
        return 1;
    }
}
