// src/cppsrc/test/utilities.hpp
#pragma once
#include <tuple>

namespace btcpipe::test {

// What our feature API expects everywhere:
using Trade = std::tuple<float, float, bool>;// {price, volume, is_buy}

// Readable factory for tests (replaces the vague "T"):
inline Trade make_trade(float price, float volume, bool is_buy) noexcept
{
    return Trade{ price, volume, is_buy };
}

}// namespace btcpipe::test
