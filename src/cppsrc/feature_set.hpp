// src/cppsrc/feature_set.hpp
#pragma once

#include "feature_count_trades.hpp"
#include "feature_ratio_buys.hpp"
#include "feature_ratio_sells.hpp"
#include "feature_volume_window.hpp"
#include "trade_types.hpp"

#include <array>
#include <cstddef>

namespace btcpipe {

// Computes the whole feature vector for a tick in one call.
//
// Marshalling a tick's trade list across the Python/C++ boundary costs far more
// than the arithmetic performed on it, so calling four separate feature methods
// spends most of its time rebuilding the same vector four times. This crosses
// once per tick instead.
//
// Owns FeatureVolumeWindow and is therefore stateful: use one instance per pass
// over a tick sequence.
class FeatureSet
{
  public:
    static constexpr std::size_t kSize = 4;

    // Braced initialisation guarantees left-to-right evaluation, which keeps the
    // stateful window's update deterministic.
    std::array<float, kSize> compute(const Trades &data)
    {
        return {
            count_.compute_feature(data),
            ratio_buys_.compute_feature(data),
            ratio_sells_.compute_feature(data),
            volume_window_.compute_feature(data),
        };
    }

  private:
    FeatureCountTrades count_;
    FeatureRatioBuys ratio_buys_;
    FeatureRatioSells ratio_sells_;
    FeatureVolumeWindow volume_window_;
};

}// namespace btcpipe
