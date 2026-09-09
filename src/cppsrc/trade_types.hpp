#pragma once
#include <tuple>
#include <vector>

namespace btcpipe {
using Trade = std::tuple<float, float, bool>;// (price, volume, is_buy)
using Trades = std::vector<Trade>;
}// namespace btcpipe
