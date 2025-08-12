cmake_minimum_required(VERSION 3.10)
project(binmake C)

# Set compiler flags
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_COMPILER "gcc")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -Wall -Wextra -O2")

# Include paths (public headers + cJSON)
# Adjust these if your folders differ.
set(BINMAKE_PUBLIC_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/include")
set(CJSON_INCLUDE_DIR          "${CMAKE_CURRENT_SOURCE_DIR}/cjson")

# Sources
set(SOURCES
  src/binmake.c
  src/revision.c
  src/json_utils.c
  src/output_utils.c
  cjson/cJSON.c
)

add_executable(binmake ${SOURCES})

target_include_directories(binmake PRIVATE
  ${BINMAKE_PUBLIC_INCLUDE_DIR}
  ${CJSON_INCLUDE_DIR}
)

# Clean generated .bin artifacts from the build dir on `make clean`
set_directory_properties(PROPERTIES ADDITIONAL_MAKE_CLEAN_FILES "*.bin")

