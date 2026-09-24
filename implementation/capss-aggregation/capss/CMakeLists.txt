add_library(
  iop

  ../libiop/libiop/common/common.cpp
  
  ../libiop/libiop/bcs/hashing/blake2b.cpp
  ../libiop/libiop/protocols/ldt/ldt_reducer.cpp
  ../libiop/libiop/protocols/ldt/fri/fri_ldt.cpp
  ../libiop/libiop/protocols/ldt/fri/fri_aux.cpp
  ../libiop/libiop/relations/sparse_matrix.cpp
  ../libiop/libiop/iop/utilities/batching.cpp
  ../libiop/libiop/algebra/utils.cpp
  relations/r1cs_field.cpp
)

# Cmake find modules
list(APPEND CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}/cmake")

find_package(sodium)

target_link_libraries(
  iop

  sodium

  ff
)

target_include_directories(
  iop

  PUBLIC
  ../libiop
  ../libiop/libiop/../depends/libfqfft
  ../libiop/libiop/../depends/libff
)

add_executable(aurora_prove_r1cs_256 executables/aurora_prove_r1cs_256.cpp)
target_link_libraries(aurora_prove_r1cs_256 iop gtest)

add_executable(aurora_prove_r1cs_256_zk executables/aurora_prove_r1cs_256_zk.cpp)
target_link_libraries(aurora_prove_r1cs_256_zk iop gtest)

add_executable(aurora_prove_r1cs_256_zk_save executables/aurora_prove_r1cs_256_zk_save.cpp)
target_link_libraries(aurora_prove_r1cs_256_zk_save iop gtest)

add_executable(aurora_prove_r1cs_256_zk_save_bin executables/aurora_prove_r1cs_256_zk_save_bin.cpp)
target_link_libraries(aurora_prove_r1cs_256_zk_save_bin iop gtest)

add_executable(aurora_verify_r1cs_256 executables/aurora_verify_r1cs_256.cpp)
target_link_libraries(aurora_verify_r1cs_256 iop gtest)

add_executable(aurora_verify_r1cs_256_zk executables/aurora_verify_r1cs_256_zk.cpp)
target_link_libraries(aurora_verify_r1cs_256_zk iop gtest)

add_executable(aurora_verify_r1cs_256_zk_bin executables/aurora_verify_r1cs_256_zk_bin.cpp)
target_link_libraries(aurora_verify_r1cs_256_zk_bin iop gtest)

add_executable(test_blake2b_absorption executables/test_blake2b_absorption.cpp)
target_link_libraries(test_blake2b_absorption iop)

add_executable(test_bcs_v2 executables/test_bcs_v2.cpp)
target_link_libraries(test_bcs_v2 iop)

add_executable(test_bcs_query_binding executables/test_bcs_query_binding.cpp)
target_link_libraries(test_bcs_query_binding iop)

add_executable(aurora_prove_r1cs_128 executables/aurora_prove_r1cs_128.cpp)
target_link_libraries(aurora_prove_r1cs_128 iop gtest)

add_executable(aurora_prove_r1cs_128_zk executables/aurora_prove_r1cs_128_zk.cpp)
target_link_libraries(aurora_prove_r1cs_128_zk iop gtest)

add_executable(aurora_prove_r1cs_64 executables/aurora_prove_r1cs_64.cpp)
target_link_libraries(aurora_prove_r1cs_64 iop gtest)

add_executable(aurora_prove_r1cs_64_zk executables/aurora_prove_r1cs_64_zk.cpp)
target_link_libraries(aurora_prove_r1cs_64_zk iop gtest)
