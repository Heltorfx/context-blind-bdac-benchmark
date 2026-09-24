#ifndef R1CS_FIELD_HPP_
#define R1CS_FIELD_HPP_

#include <libff/algebra/fields/prime_base/fp.hpp>

namespace capss {

    const mp_size_t field256_bitcount = 256;
    const mp_size_t field256_limbs = (field256_bitcount+GMP_NUMB_BITS-1)/GMP_NUMB_BITS;
    extern libff::bigint<field256_limbs> field256_modulus;
    typedef libff::Fp_model<field256_limbs, field256_modulus> field256;

    const mp_size_t field128_bitcount = 128;
    const mp_size_t field128_limbs = (field128_bitcount+GMP_NUMB_BITS-1)/GMP_NUMB_BITS;
    extern libff::bigint<field128_limbs> field128_modulus;
    typedef libff::Fp_model<field128_limbs, field128_modulus> field128;

    const mp_size_t field64_bitcount = 64;
    const mp_size_t field64_limbs = (field64_bitcount+GMP_NUMB_BITS-1)/GMP_NUMB_BITS;
    extern libff::bigint<field64_limbs> field64_modulus;
    typedef libff::Fp_model<field64_limbs, field64_modulus> field64;

    int init_field256(std::string filename);
    int init_field128(std::string filename);    
    int init_field64(std::string filename);    
}

#endif /* R1CS_FIELD_HPP_ */