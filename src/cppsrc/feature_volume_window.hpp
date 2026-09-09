// src/cppsrc/feature_volume_window.hpp
#pragma once

#include "base_feature.hpp"

#include <array>
#include <cstddef>
#include <numeric>
#include <tuple>
#include <vector>

namespace btcpipe {

// Maintains a sliding window (last 5 ticks) of total traded volume.
// Each call consumes one tick (vector of trades) and returns the window sum.
class FeatureVolumeWindow : public BaseFeature
{
  public:
    float compute_feature(const Trades &data) override
    {
        // Sum volume for the current tick (second element of the tuple).
        float this_tick_volume = 0.0f;
        for (const auto &[price, volume, is_buy] : data) {
            (void)price;
            (void)is_buy;
            this_tick_volume += volume;
        }

        push_volume(this_tick_volume);
        return running_sum_;
    }

  private:
    static constexpr std::size_t kWindow = 5;

    // Circular buffer of per-tick volumes.
    std::array<float, kWindow> buf_{};
    std::size_t head_ = 0;// next position to overwrite
    std::size_t count_ = 0;// number of valid entries (<= kWindow)
    float running_sum_ = 0.0f;// sum over valid entries

    void push_volume(float v)
    {
        if (count_ < kWindow) {
            buf_[head_] = v;
            head_ = (head_ + 1) % kWindow;
            ++count_;
            running_sum_ += v;
        } else {
            // Overwrite oldest element at head_
            const float old = buf_[head_];
            buf_[head_] = v;
            head_ = (head_ + 1) % kWindow;
            running_sum_ += (v - old);
        }
    }
};

}// namespace btcpipe
