// src/cppsrc/test/test_feature_ratio_buys.cpp
#include "../feature_ratio_buys.hpp"
#include "utilities.hpp"
#include "gtest/gtest.h"
#include <algorithm>
#include <tuple>
#include <vector>

using intproj::FeatureRatioBuys;
using intproj::test::make_trade;

// alias
static std::tuple<float, float, bool> T(float price, float vol, bool is_buy)
{
    return std::make_tuple(price, vol, is_buy);
}

// counts only, not prices or volumes
TEST(FeatureRatioBuysTest, IgnoresPriceAndVolumeWeights)
{
    FeatureRatioBuys f;

    const float r1 = f.compute_feature({
      T(100.f, 0.1f, true),
      T(200.f, 5.0f, false),
      T(150.f, 10.0f, true),
      T(120.f, 0.0f, false),
      T(130.f, 7.7f, true),
    });// 3 buys, 2 sells -> 3/5

    const float r2 = f.compute_feature({
      // same buy/sell pattern, wacky weights and prices
      T(9999.f, 9999.f, true),
      T(1.f, 0.0001f, false),
      T(42.f, 3.1415f, true),
      T(0.5f, 1e6f, false),
      T(777.f, 2.718f, true),
    });// still 3/5

    EXPECT_FLOAT_EQ(r1, 3.0f / 5.0f);// 0.6
    EXPECT_FLOAT_EQ(r2, 3.0f / 5.0f);// 0.6
}

// order shouldn’t matter and no hidden state
TEST(FeatureRatioBuysTest, OrderInvariantAndStateless)
{
    FeatureRatioBuys f;

    std::vector<decltype(T(0, 0, false))> tick = {
        T(100.f, 1.f, true),
        T(101.f, 1.f, false),
        T(102.f, 1.f, true),
        T(103.f, 1.f, false),
        T(104.f, 1.f, false),
        T(105.f, 1.f, true),
    };// 3 buys, 3 sells -> 0.5

    const float a = f.compute_feature(tick);

    std::reverse(tick.begin(), tick.end());
    const float b = f.compute_feature(tick);

    const float c = f.compute_feature({
      T(9.f, 1.f, true),
      T(10.f, 1.f, true),
      T(11.f, 1.f, false),
    });// 2/3

    EXPECT_FLOAT_EQ(a, 0.5f);
    EXPECT_FLOAT_EQ(b, 0.5f);
    EXPECT_FLOAT_EQ(c, 2.0f / 3.0f);
}


TEST(FeatureRatioBuysTest, HandlesLargeTickCounts)
{
    FeatureRatioBuys f;

    std::vector<decltype(T(0, 0, false))> big;
    big.reserve(5000);

    // 3500 buys then 1500 sells
    for (int i = 0; i < 3500; ++i) big.push_back(T(100.f + i, 1.f + i % 7, true));
    for (int i = 0; i < 1500; ++i) big.push_back(T(200.f + i, 2.f + i % 5, false));

    const float r = f.compute_feature(big);
    EXPECT_FLOAT_EQ(r, 7.0f / 10.0f);// 0.7
}


TEST(FeatureRatioBuysTest, AllBuysIsOne)
{
    FeatureRatioBuys f;
    const float r = f.compute_feature({
      make_trade(100.f, 1.f, true),
      make_trade(101.f, 2.f, true),
      make_trade(102.f, 3.f, true),
    });
    EXPECT_FLOAT_EQ(r, 1.f);
}

TEST(FeatureRatioBuysTest, AllSellsIsZero)
{
    FeatureRatioBuys f;
    const float r = f.compute_feature({
      make_trade(100.f, 1.f, false),
      make_trade(101.f, 2.f, false),
      make_trade(102.f, 3.f, false),
      make_trade(103.f, 4.f, false),
    });
    EXPECT_FLOAT_EQ(r, 0.f);
}
