cmake_minimum_required(VERSION 3.16)
project(rag_gateway LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Drogon CONFIG REQUIRED)

add_executable(rag_gateway src/main.cc)
target_link_libraries(rag_gateway PRIVATE Drogon::Drogon)
target_compile_options(rag_gateway PRIVATE -Wall -Wextra -Wpedantic)
