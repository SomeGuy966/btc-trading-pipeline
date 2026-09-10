// src/cppsrc/test/test_feature_count_trades.cpp
#include "../feature_count_trades.hpp"
#include "utilities.hpp"
#include "gtest/gtest.h"
#include <algorithm>
#include <tuple>
#include <vector>

using btcpipe::FeatureCountTrades;
using btcpipe::test::make_trade;


static std::tuple<float, float, bool> T(float price, float vol, bool is_buy)
{
    return std::make_tuple(price, vol, is_buy);
}

// counts trades in the tick regardless of side or price
TEST(FeatureCountTradesTest, CountsTradesSimple)
{
    FeatureCountTrades f;

    float c0 = f.compute_feature({});
    EXPECT_FLOAT_EQ(c0, 0.f);

    float c1 = f.compute_feature({ make_trade(100.f, 1.f, true) });
    EXPECT_FLOAT_EQ(c1, 1.f);

    float c3 = f.compute_feature({
      T(101.f, 1.f, true),
      T(101.1f, 2.f, false),
      T(101.2f, 3.f, true),
    });
    EXPECT_FLOAT_EQ(c3, 3.f);
}


TEST(FeatureCountTradesTest, OrderInvariantAndSideAgnostic)
{
    FeatureCountTrades f;

    std::vector<decltype(T(0, 0, false))> tick = {
        T(100.f, 0.5f, true),
        T(101.f, 1.0f, false),
        T(102.f, 2.0f, true),
        T(103.f, 3.0f, false),
        T(104.f, 4.0f, true),
    };// 5 trades

    const float a = f.compute_feature(tick);

    std::reverse(tick.begin(), tick.end());
    const float b = f.compute_feature(tick);

    EXPECT_FLOAT_EQ(a, 5.f);
    EXPECT_FLOAT_EQ(b, 5.f);
}


TEST(FeatureCountTradesTest, HandlesLargeTickCounts)
{
    FeatureCountTrades f;

    std::vector<decltype(T(0, 0, false))> big;
    big.reserve(4000);

    for (int i = 0; i < 2500; ++i) big.push_back(T(100.f + i * 0.01f, 1.f, true));
    for (int i = 0; i < 1500; ++i) big.push_back(T(200.f + i * 0.02f, 2.f, false));

    const float r = f.compute_feature(big);
    EXPECT_FLOAT_EQ(r, 4000.f);
}

// duplicates and weird prices shouldn’t change the count
TEST(FeatureCountTradesTest, IgnoresDuplicatesInCounting)
{
    FeatureCountTrades f;

    const float c = f.compute_feature({
      T(100.f, 1.f, true),
      T(100.f, 1.f, true),
      T(100.f, 1.f, true),
      T(20000.f, 0.0f, false),
    });// 4 trades total

    EXPECT_FLOAT_EQ(c, 4.f);
}
