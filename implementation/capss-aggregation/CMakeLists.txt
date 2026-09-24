set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
cmake_minimum_required(VERSION 3.1)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(PROJECT_VERSION 0.2.0)
project (libiop
  DESCRIPTION "Library for building IOP based SNARKs"
  LANGUAGES CXX C)

# Performance options
option(PERFORMANCE "Enable link-time and aggressive optimizations" OFF)
option(MULTICORE "Enable parallelized execution, using OpenMP" OFF)
option(USE_ASM "Use architecture-specific optimized assembly code" ON)
option(
  ASM_MINIMIZE_CLMULS
  "When USE_ASM is on, minimize the number of CLMUL instructions in binary fields (for CPUs where CLMUL is slow)"
  OFF
)

set(
  OPT_FLAGS
  ""
  CACHE
  STRING
  "Override C++ compiler optimization flags"
)

# Profiling
option(WITH_PROCPS "Use procps for memory profiling" OFF)
# TODO: Expose the libff opcount flag here

# Debugging flags
option(DEBUG "Enable debugging mode" OFF)
option(CPPDEBUG "Enable debugging of C++ STL (does not imply DEBUG)" OFF)
# Should these be part of DEBUG/CPPDebug?
option(USE_ASAN "Enable Clang address sanitizer" OFF)
option(USE_UBSAN "Enable Clang undefined behavior sanitizer" OFF)


string(TOLOWER ${CMAKE_CXX_COMPILER_ID} compiler_id_lower)
if(CMAKE_COMPILER_IS_GNUCXX OR "${compiler_id_lower}" MATCHES ".*clang.*")
  # Common compilation flags and warning configuration
  # TODO: upstream -Wno-... patches in libff, libfqfft
  set(DISABLED_WARNINGS
    "-Wno-sign-compare -Wno-shadow -Wno-unused-variable -Wno-unused-parameter"
    )
  set(DISABLED_WARNINGS_CLANG
    "-Wno-delete-non-virtual-dtor"
    )
  set(DISABLED_WARNINGS_NOT_CLANG
    "-Wno-unused-but-set-variable"
    )
  set(
    CMAKE_CXX_FLAGS
    "${CMAKE_CXX_FLAGS} -std=c++14 -Wall -Wextra -Wfatal-errors ${DISABLED_WARNINGS}"
    )
  # Default optimizations flags (to override, use -DOPT_FLAGS=...)
  if("${OPT_FLAGS}" STREQUAL "")
    set(
      OPT_FLAGS
      "-ggdb3 -O3 -march=native -mtune=native"
    )
  endif()
endif()

set(
  CMAKE_CXX_FLAGS
  "${CMAKE_CXX_FLAGS} ${OPT_FLAGS}"
)

# TODO: figure out a fix and unsilence this
if(compiler_id_lower MATCHES ".*clang.*")
    EXECUTE_PROCESS( COMMAND ${CMAKE_CXX_COMPILER} --version OUTPUT_VARIABLE clang_full_version_string )
    string (REGEX REPLACE ".*clang version ([0-9]+\\.[0-9]+).*" "\\1" CLANG_VERSION_STRING ${clang_full_version_string})
    if(CLANG_VERSION_STRING GREATER_EQUAL 13.0)
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-unused-but-set-variable -Wno-error=unused-but-set-variable")
    else()
      if(NOT CMAKE_CXX_FLAGS MATCHES "-Werror")
        set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Werror")
      endif(NOT CMAKE_CXX_FLAGS MATCHES "-Werror")
    endif()
else()
  set(
    CMAKE_CXX_FLAGS
    "${CMAKE_CXX_FLAGS} ${DISABLED_WARNINGS_NOT_CLANG}"
    )
endif()

message(CMAKE_CXX_FLAGS=${CMAKE_CXX_FLAGS})

enable_testing()

if("${DEBUG}")
  add_definitions(-DDEBUG)
endif()

if("${MULTICORE}")
  add_definitions(-DMULTICORE)
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fopenmp")
endif()

if("${CPPDEBUG}")
  add_definitions(-D_GLIBCXX_DEBUG -D_GLIBCXX_DEBUG_PEDANTIC -DCPPDEBUG)
endif()

if("${USE_ASAN}" OR "${USE_UBSAN}")
  if("${CMAKE_CXX_COMPILER_ID}" STREQUAL "Clang")
    if("${USE_ASAN}")
      set(CMAKE_CXX_FLAGS
        "${CMAKE_CXX_FLAGS} -fsanitize=address -fsanitize-address-use-after-scope")
    endif()
    if("${USE_UBSAN}")
      set(CMAKE_CXX_FLAGS
        "${CMAKE_CXX_FLAGS} -fsanitize=integer,undefined")
    endif()
    set(CMAKE_CXX_FLAGS
      "${CMAKE_CXX_FLAGS} -fno-omit-frame-pointer")
  else()
    message(SEND_ERROR "libstark make files only have sanitizer support for clang. Patches welcome!")
  endif()
endif()

if("${PERFORMANCE}")
  add_definitions(-DNDEBUG)
  if(CMAKE_CXX_COMPILER_ID STREQUAL GNU)
    set(CMAKE_AR gcc-ar)
    set(CMAKE_RANLIB gcc-ranlib)
  endif()
  set(
    CMAKE_CXX_FLAGS
    "${CMAKE_CXX_FLAGS} -flto -Wno-unused-variable -Wno-lto-type-mismatch"
    )
  set(
    CMAKE_EXE_LINKER_FLAGS
    "${CMAKE_EXE_LINKER_FLAGS} -flto"
    )
  set(BENCHMARK_ENABLE_LTO ON CACHE BOOL "Enable link time optimisation of the benchmark library.")
endif()

# Detect architecture
if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|AMD64|i[3-6]86")
  set(IS_X86 TRUE)
else()
  set(IS_X86 FALSE)
endif()

# Disable USE_ASM on non-x86 (asm paths are x86-only in libff)
if(NOT IS_X86)
  set(USE_ASM OFF CACHE BOOL "Use architecture-specific optimized assembly code" FORCE)
endif()

if("${USE_ASM}")
  add_definitions(-DUSE_ASM)
  if("${ASM_MINIMIZE_CLMULS}")
    add_definitions(-DASM_MINIMIZE_CLMULS)
  endif()
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -mpclmul -msse4.1")
endif()

# Enable Boost for program_options
if("${CPPDEBUG}")
else()
  FIND_PACKAGE( Boost 1.40 COMPONENTS program_options REQUIRED )
  INCLUDE_DIRECTORIES( ${Boost_INCLUDE_DIR} )
endif()

# Configure CCache if available
find_program(CCACHE_FOUND ccache)
if(CCACHE_FOUND)
        set_property(GLOBAL PROPERTY RULE_LAUNCH_COMPILE ccache)
        set_property(GLOBAL PROPERTY RULE_LAUNCH_LINK ccache)
endif(CCACHE_FOUND)

# Add a `make check` target that builds and tests
enable_testing()
add_custom_target(check COMMAND ${CMAKE_CTEST_COMMAND})

include_directories(.)
include_directories(libiop)

add_subdirectory(libiop/depends)
add_subdirectory(capss)
