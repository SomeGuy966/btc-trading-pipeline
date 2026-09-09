// src/cppsrc/feature_ratio_buys.hpp
#pragma once

#include "base_feature.hpp"

#include <cstddef>
#include <numeric>
#include <tuple>
#include <vector>

namespace btcpipe {

// Computes the ratio of buy-side trades within a tick.
// Returns 0.0f when there are no trades.
class FeatureRatioBuys : public BaseFeature
{
  public:
    float compute_feature(const Trades &data) override
    {
        const std::size_t total = data.size();
        if (total == 0) return 0.0f;

        std::size_t buy_count = 0;
        for (const auto &[price, volume, is_buy] : data) {
            (void)price;
            (void)volume;
            if (is_buy) ++buy_count;
        }

        return static_cast<float>(buy_count) / static_cast<float>(total);
    }
};

}// namespace btcpipe
