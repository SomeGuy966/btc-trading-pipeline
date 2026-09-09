// src/cppsrc/ntrades_feature.hpp
#pragma once

#include "base_feature.hpp"

#include <cstddef>// std::size
#include <tuple>
#include <vector>

namespace intproj {

// Counts the number of trades present in a single tick.
// Keeps the BaseFeature interface so downstream code/tests remain compatible.
class NTradesFeature : public BaseFeature
{
  public:
    float compute_feature(std::vector<std::tuple<float, float, bool>> data) override
    {
        return static_cast<float>(std::size(data));
    }
};

}// namespace intproj
