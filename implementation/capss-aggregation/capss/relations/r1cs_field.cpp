#include <iostream>
#include <fstream>
#include <string>

#include "capss/relations/r1cs_field.hpp"
#include "libff/algebra/field_utils/bigint.hpp"

namespace capss {

libff::bigint<field256_limbs> field256_modulus;
libff::bigint<field128_limbs> field128_modulus;
libff::bigint<field64_limbs> field64_modulus;

int init_field256(std::string filename) {
    using bigint256 = libff::bigint<field256_limbs>;

    assert(sizeof(mp_limb_t) == 8 || sizeof(mp_limb_t) == 4); // Montgomery assumes this

    std::ifstream file_params(filename);
    if(!file_params.is_open()) {
        throw std::invalid_argument("Impossible to open file with field parameters.");
    }

    unsigned int num_bits, s;
    std::string modulus_prime_str, euler_str, t_str, t_minus_1_over_2_str, multiplicative_generator_str, root_of_unity_str, nqr_str, nqr_to_t_str;
    file_params >> num_bits;
    file_params >> modulus_prime_str;
    file_params >> euler_str;
    file_params >> s;
    file_params >> t_str;
    file_params >> t_minus_1_over_2_str;
    file_params >> multiplicative_generator_str;
    file_params >> root_of_unity_str;
    file_params >> nqr_str;
    file_params >> nqr_to_t_str;

    std::string Rsquared_64_bits_str, Rcubed_64_bits_str;
    uint64_t inv_64_bits;
    file_params >> Rsquared_64_bits_str;
    file_params >> Rcubed_64_bits_str;
    file_params >> inv_64_bits;

    std::string Rsquared_32_bits_str, Rcubed_32_bits_str;
    uint64_t inv_32_bits;
    file_params >> Rsquared_32_bits_str;
    file_params >> Rcubed_32_bits_str;
    file_params >> inv_32_bits;
    file_params.close();

    if(num_bits > 256) {
        throw std::invalid_argument("Field too large for field256.");
    }
    field256_modulus = bigint256(modulus_prime_str.c_str());
    assert(field256::modulus_is_valid());
    if (sizeof(mp_limb_t) == 8)
    {
        field256::Rsquared = bigint256(Rsquared_64_bits_str.c_str());
        field256::Rcubed = bigint256(Rcubed_64_bits_str.c_str());
        field256::inv = inv_64_bits;
    }
    if (sizeof(mp_limb_t) == 4)
    {
        field256::Rsquared = bigint256(Rsquared_32_bits_str.c_str());
        field256::Rcubed = bigint256(Rcubed_32_bits_str.c_str());
        field256::inv = inv_32_bits;
    }
    field256::num_bits = num_bits;
    field256::euler = bigint256(euler_str.c_str());
    field256::s = s;
    field256::t = bigint256(t_str.c_str());
    field256::t_minus_1_over_2 = bigint256(t_minus_1_over_2_str.c_str());
    field256::multiplicative_generator = field256(multiplicative_generator_str.c_str());
    field256::root_of_unity = field256(root_of_unity_str.c_str());
    field256::nqr = field256(nqr_str.c_str());
    field256::nqr_to_t = field256(nqr_to_t_str.c_str());

    return 0;
}

int init_field128(std::string filename) {
    using bigint128 = libff::bigint<field128_limbs>;

    assert(sizeof(mp_limb_t) == 8 || sizeof(mp_limb_t) == 4); // Montgomery assumes this

    std::ifstream file_params(filename);
    if(!file_params.is_open()) {
        throw std::invalid_argument("Impossible to open file with field parameters.");
    }

    unsigned int num_bits, s;
    std::string modulus_prime_str, euler_str, t_str, t_minus_1_over_2_str, multiplicative_generator_str, root_of_unity_str, nqr_str, nqr_to_t_str;
    file_params >> num_bits;
    file_params >> modulus_prime_str;
    file_params >> euler_str;
    file_params >> s;
    file_params >> t_str;
    file_params >> t_minus_1_over_2_str;
    file_params >> multiplicative_generator_str;
    file_params >> root_of_unity_str;
    file_params >> nqr_str;
    file_params >> nqr_to_t_str;

    std::string Rsquared_64_bits_str, Rcubed_64_bits_str;
    uint64_t inv_64_bits;
    file_params >> Rsquared_64_bits_str;
    file_params >> Rcubed_64_bits_str;
    file_params >> inv_64_bits;

    std::string Rsquared_32_bits_str, Rcubed_32_bits_str;
    uint64_t inv_32_bits;
    file_params >> Rsquared_32_bits_str;
    file_params >> Rcubed_32_bits_str;
    file_params >> inv_32_bits;
    file_params.close();

    if(num_bits > 128) {
        throw std::invalid_argument("Field too large for field128.");
    }
    field128_modulus = bigint128(modulus_prime_str.c_str());
    assert(field128::modulus_is_valid());
    if (sizeof(mp_limb_t) == 8)
    {
        field128::Rsquared = bigint128(Rsquared_64_bits_str.c_str());
        field128::Rcubed = bigint128(Rcubed_64_bits_str.c_str());
        field128::inv = inv_64_bits;
    }
    if (sizeof(mp_limb_t) == 4)
    {
        field128::Rsquared = bigint128(Rsquared_32_bits_str.c_str());
        field128::Rcubed = bigint128(Rcubed_32_bits_str.c_str());
        field128::inv = inv_32_bits;
    }
    field128::num_bits = num_bits;
    field128::euler = bigint128(euler_str.c_str());
    field128::s = s;
    field128::t = bigint128(t_str.c_str());
    field128::t_minus_1_over_2 = bigint128(t_minus_1_over_2_str.c_str());
    field128::multiplicative_generator = field128(multiplicative_generator_str.c_str());
    field128::root_of_unity = field128(root_of_unity_str.c_str());
    field128::nqr = field128(nqr_str.c_str());
    field128::nqr_to_t = field128(nqr_to_t_str.c_str());

    return 0;
}

int init_field64(std::string filename) {
    using bigint64 = libff::bigint<field64_limbs>;

    assert(sizeof(mp_limb_t) == 8 || sizeof(mp_limb_t) == 4); // Montgomery assumes this

    std::ifstream file_params(filename);
    if(!file_params.is_open()) {
        throw std::invalid_argument("Impossible to open file with field parameters.");
    }

    unsigned int num_bits, s;
    std::string modulus_prime_str, euler_str, t_str, t_minus_1_over_2_str, multiplicative_generator_str, root_of_unity_str, nqr_str, nqr_to_t_str;
    file_params >> num_bits;
    file_params >> modulus_prime_str;
    file_params >> euler_str;
    file_params >> s;
    file_params >> t_str;
    file_params >> t_minus_1_over_2_str;
    file_params >> multiplicative_generator_str;
    file_params >> root_of_unity_str;
    file_params >> nqr_str;
    file_params >> nqr_to_t_str;

    std::string Rsquared_64_bits_str, Rcubed_64_bits_str;
    uint64_t inv_64_bits;
    file_params >> Rsquared_64_bits_str;
    file_params >> Rcubed_64_bits_str;
    file_params >> inv_64_bits;

    std::string Rsquared_32_bits_str, Rcubed_32_bits_str;
    uint64_t inv_32_bits;
    file_params >> Rsquared_32_bits_str;
    file_params >> Rcubed_32_bits_str;
    file_params >> inv_32_bits;
    file_params.close();

    if(num_bits > 64) {
        throw std::invalid_argument("Field too large for field64.");
    }
    field64_modulus = bigint64(modulus_prime_str.c_str());
    assert(field64::modulus_is_valid());
    if (sizeof(mp_limb_t) == 8)
    {
        field64::Rsquared = bigint64(Rsquared_64_bits_str.c_str());
        field64::Rcubed = bigint64(Rcubed_64_bits_str.c_str());
        field64::inv = inv_64_bits;
    }
    if (sizeof(mp_limb_t) == 4)
    {
        field64::Rsquared = bigint64(Rsquared_32_bits_str.c_str());
        field64::Rcubed = bigint64(Rcubed_32_bits_str.c_str());
        field64::inv = inv_32_bits;
    }
    field64::num_bits = num_bits;
    field64::euler = bigint64(euler_str.c_str());
    field64::s = s;
    field64::t = bigint64(t_str.c_str());
    field64::t_minus_1_over_2 = bigint64(t_minus_1_over_2_str.c_str());
    field64::multiplicative_generator = field64(multiplicative_generator_str.c_str());
    field64::root_of_unity = field64(root_of_unity_str.c_str());
    field64::nqr = field64(nqr_str.c_str());
    field64::nqr_to_t = field64(nqr_to_t_str.c_str());

    return 0;
}

}