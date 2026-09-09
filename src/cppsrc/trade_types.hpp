#pragma once
#include <tuple>
#include <vector>

namespace intproj {
using Trade = std::tuple<float, float, bool>;// (price, volume, is_buy)
using Trades = std::vector<Trade>;
}// namespace intproj
