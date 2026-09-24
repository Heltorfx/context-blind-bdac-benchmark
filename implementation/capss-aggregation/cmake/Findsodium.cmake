# Findsodium.cmake
# Locates libsodium and defines an imported target named `sodium`.
#
# Search order:
#   1. pkg-config (preferred; works for Homebrew, apt, etc.)
#   2. Manual search of common prefixes (Homebrew on arm64/x86_64, /usr/local, /usr)
#
# Provides:
#   sodium_FOUND
#   sodium_INCLUDE_DIRS
#   sodium_LIBRARIES
#   Imported target: sodium
 
find_package(PkgConfig QUIET)
if(PkgConfig_FOUND)
  pkg_check_modules(PC_sodium QUIET libsodium)
endif()
 
find_path(sodium_INCLUDE_DIR
  NAMES sodium.h
  HINTS
    ${PC_sodium_INCLUDEDIR}
    ${PC_sodium_INCLUDE_DIRS}
  PATHS
    /opt/homebrew/include
    /usr/local/include
    /usr/include
)
 
find_library(sodium_LIBRARY
  NAMES sodium libsodium
  HINTS
    ${PC_sodium_LIBDIR}
    ${PC_sodium_LIBRARY_DIRS}
  PATHS
    /opt/homebrew/lib
    /usr/local/lib
    /usr/lib
)
 
include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(sodium
  REQUIRED_VARS sodium_LIBRARY sodium_INCLUDE_DIR
)
 
if(sodium_FOUND)
  set(sodium_INCLUDE_DIRS ${sodium_INCLUDE_DIR})
  set(sodium_LIBRARIES ${sodium_LIBRARY})
 
  if(NOT TARGET sodium)
    add_library(sodium UNKNOWN IMPORTED)
    set_target_properties(sodium PROPERTIES
      IMPORTED_LOCATION "${sodium_LIBRARY}"
      INTERFACE_INCLUDE_DIRECTORIES "${sodium_INCLUDE_DIR}"
    )
  endif()
endif()
 
mark_as_advanced(sodium_INCLUDE_DIR sodium_LIBRARY)
