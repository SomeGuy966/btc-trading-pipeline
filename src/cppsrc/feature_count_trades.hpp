// src/cppsrc/feature_count_trades.hpp
#pragma once

#include "base_feature.hpp"

#include <iterator>// std::distance
#include <tuple>
#include <vector>

namespace btcpipe {

// Counts how many trades are present in the current tick.
class FeatureCountTrades : public BaseFeature
{
  public:
    float compute_feature(const Trades &data) override
    {
        // Use std::distance for variety (equivalent to data.size()).
        return static_cast<float>(data.size());
    }
};

}// namespace btcpipe
