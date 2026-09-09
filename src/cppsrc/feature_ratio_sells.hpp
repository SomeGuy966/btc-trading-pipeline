// src/cppsrc/feature_ratio_sells.hpp
#pragma once

#include "base_feature.hpp"

#include <algorithm>// std::count_if
#include <cstddef>// std::size_t
#include <tuple>
#include <vector>

namespace intproj {

// Computes the fraction of sell-side trades within a tick.
// Returns 0.0f if there are no trades.
class FeatureRatioSells : public BaseFeature
{
  public:
    float compute_feature(std::vector<std::tuple<float, float, bool>> data) override
    {
        const std::size_t total = data.size();
        if (total == 0) return 0.0f;

        std::size_t sells = 0;
        for (const auto &[price, volume, is_buy] : data) {
            (void)price;
            (void)volume;
            if (!is_buy) ++sells;
        }

        return static_cast<float>(sells) / static_cast<float>(total);
    }
};

}// namespace intproj
