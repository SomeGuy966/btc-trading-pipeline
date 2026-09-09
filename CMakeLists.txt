cmake_minimum_required(VERSION 3.20)

project(btc_trading_pipeline LANGUAGES CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3")


list(APPEND CMAKE_PREFIX_PATH
     "${CMAKE_BINARY_DIR}/Release/generators"
     "${CMAKE_BINARY_DIR}/generators")

find_package(Python3 3.12 COMPONENTS Interpreter Development EXACT REQUIRED)
find_package(pybind11 CONFIG REQUIRED)
find_package(cpr CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(GTest CONFIG REQUIRED)

enable_testing()


add_library(cpp_core INTERFACE)
target_include_directories(cpp_core INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cppsrc
)


pybind11_add_module(cppcore src/cppsrc/main.cpp)
target_link_libraries(cppcore PRIVATE
    pybind11::module
    pybind11::headers
    cpr::cpr
    nlohmann_json::nlohmann_json
    cpp_core
)

get_target_property(_cpr_inc cpr::cpr INTERFACE_INCLUDE_DIRECTORIES)
if(_cpr_inc)
  target_include_directories(cppcore PRIVATE ${_cpr_inc})
endif()
get_target_property(_py_inc pybind11::headers INTERFACE_INCLUDE_DIRECTORIES)
if(_py_inc)
  target_include_directories(cppcore PRIVATE ${_py_inc})
endif()
get_target_property(_json_inc nlohmann_json::nlohmann_json INTERFACE_INCLUDE_DIRECTORIES)
if(_json_inc)
  target_include_directories(cppcore PRIVATE ${_json_inc})
endif()

set_target_properties(cppcore PROPERTIES
    PREFIX ""
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/src/pysrc"
)


file(GLOB_RECURSE CPP_TEST_SOURCES src/cppsrc/test/*.cpp)
add_executable(cpp_tests ${CPP_TEST_SOURCES})
target_link_libraries(cpp_tests PRIVATE
    GTest::gtest_main
    GTest::gtest
    cpp_core
)

get_target_property(_gt_inc GTest::gtest INTERFACE_INCLUDE_DIRECTORIES)
if(_gt_inc)
  target_include_directories(cpp_tests PRIVATE ${_gt_inc})
endif()

add_test(NAME cpp_tests COMMAND cpp_tests)

install(TARGETS cppcore DESTINATION btc_trading_pipeline)
