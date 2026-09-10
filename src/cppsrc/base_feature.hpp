// src/cppsrc/base_feature.hpp
#pragma once

#include "trade_types.hpp"

namespace btcpipe {

class BaseFeature
{
  public:
    // Taken by const reference: passing by value copied the whole tick on every
    // call, which dominated the cost of the arithmetic itself.
    virtual float compute_feature(const Trades &data) = 0;

    virtual ~BaseFeature() = default;
};

}// namespace btcpipe
