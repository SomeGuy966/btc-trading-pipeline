// src/cppsrc/test/test_feature_volume_window.cpp
#include "../feature_volume_window.hpp"
#include "utilities.hpp"
#include "gtest/gtest.h"


using intproj::FeatureVolumeWindow;
using intproj::test::make_trade;


static std::tuple<float, float, bool> T(float price, float vol, bool is_buy)
{
    return std::make_tuple(price, vol, is_buy);
}

TEST(FeatureVolumeWindowTest, RollsOverLastFiveTicks)
{
    FeatureVolumeWindow f;

    // Each call is one "tick" (a vector of trades)
    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(100.f, 1.f, true) }), 1.f);
    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(101.f, 2.f, false) }), 3.f);
    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(102.f, 3.f, true) }), 6.f);
    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(103.f, 4.f, false) }), 10.f);
    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(104.f, 5.f, true) }), 15.f);
    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(105.f, 6.f, false) }), 20.f);
    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(106.f, 10.f, true) }), 28.f);
}

TEST(FeatureVolumeWindowTest, MultipleTradesWithinATick)
{
    FeatureVolumeWindow f;


    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(100.f, 1.f, true), T(100.5f, 2.f, false) }), 3.f);
    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(101.f, 4.f, true) }), 7.f);
    EXPECT_FLOAT_EQ(
      f.compute_feature({ make_trade(102.f, 2.f, true), make_trade(102.1f, 2.f, false), T(102.2f, 1.f, true) }), 12.f);
    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(103.f, 6.f, false) }), 18.f);
    EXPECT_FLOAT_EQ(f.compute_feature({ /* zero-volume tick */ }), 18.f);
    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(104.f, 10.f, true) }), 25.f);
}


// wraps at multiples of five
TEST(FeatureVolumeWindowTest, WrapsAfterExactMultiplesOfFive)
{
    FeatureVolumeWindow f;

    for (int i = 0; i < 5; ++i) {
        const float got = f.compute_feature({ make_trade(100.f + i, 1.f, (i % 2) == 0) });
        EXPECT_FLOAT_EQ(got, static_cast<float>(i + 1));
    }
    for (int i = 0; i < 5; ++i) {
        const float got = f.compute_feature({ make_trade(200.f + i, 2.f, (i % 2) != 0) });
        if (i == 4) { EXPECT_FLOAT_EQ(got, 10.f); }
    }
    for (int i = 0; i < 5; ++i) {
        const float got = f.compute_feature({ make_trade(300.f + i, 3.f, (i % 2) == 0) });
        if (i == 4) { EXPECT_FLOAT_EQ(got, 15.f); }
    }
}

// empty ticks count as zero
TEST(FeatureVolumeWindowTest, IncludesEmptyTicksAsZero)
{
    FeatureVolumeWindow f;

    float s1 = f.compute_feature({ make_trade(100.f, 5.f, true) });
    EXPECT_FLOAT_EQ(s1, 5.f);

    float s2 = f.compute_feature({ /* empty tick */ });
    EXPECT_FLOAT_EQ(s2, 5.f);

    float s3 = f.compute_feature({ /* empty tick */ });
    EXPECT_FLOAT_EQ(s3, 5.f);

    float s4 = f.compute_feature({ make_trade(101.f, 7.f, false) });
    EXPECT_FLOAT_EQ(s4, 12.f);

    float s5 = f.compute_feature({ /* empty tick */ });
    EXPECT_FLOAT_EQ(s5, 12.f);

    float s6 = f.compute_feature({ make_trade(102.f, 4.f, true) });
    EXPECT_FLOAT_EQ(s6, 11.f);
}

// price and side don't affect volume sum
TEST(FeatureVolumeWindowTest, IgnoresPriceAndSideWhenSumming)
{
    FeatureVolumeWindow f1;
    FeatureVolumeWindow f2;

    std::array<float, 6> volumes{ 1.f, 3.f, 2.f, 5.f, 0.f, 4.f };
    for (std::size_t i = 0; i < volumes.size(); ++i) {
        const float v = volumes[i];

        const float a = f1.compute_feature({ make_trade(100.f + static_cast<float>(i), v, true) });

        const float price = 10000.f - static_cast<float>(i) * 13.7f;
        const bool side = (i % 2) == 0 ? false : true;
        const float b = f2.compute_feature({ T(price, v, side) });

        EXPECT_FLOAT_EQ(a, b);
    }
}

// long stream matches naive window
TEST(FeatureVolumeWindowTest, LongSequenceMatchesNaiveRecalc)
{
    FeatureVolumeWindow f;

    std::vector<float> vols;
    vols.reserve(50);
    for (int i = 0; i < 50; ++i) { vols.push_back(static_cast<float>((i % 7) + 1)); }

    std::vector<float> got;
    got.reserve(50);
    for (int i = 0; i < 50; ++i) {
        const float g = f.compute_feature({ make_trade(100.f + i, vols[static_cast<std::size_t>(i)], (i % 2) == 0) });
        got.push_back(g);
    }

    auto naive_last5 = [&](int idx) -> double {
        const int start = std::max(0, idx - 4);
        double s = 0.0;
        for (int j = start; j <= idx; ++j) s += static_cast<double>(vols[static_cast<std::size_t>(j)]);
        return s;
    };

    const std::array<int, 6> idxs{ 4, 5, 12, 25, 30, 49 };
    for (int idx : idxs) {
        const double expected = naive_last5(idx);
        const float observed = got[static_cast<std::size_t>(idx)];
        EXPECT_NEAR(observed, static_cast<float>(expected), 1e-5f);
    }
}

// tiny and huge volumes
TEST(FeatureVolumeWindowTest, HandlesVerySmallAndVeryLargeVolumes)
{
    FeatureVolumeWindow f;

    std::vector<float> vols{ 1e-7f, 1e6f, 3e-7f, 2e6f, 5e-8f, 4e6f };
    std::vector<float> obs;
    obs.reserve(vols.size());

    for (std::size_t i = 0; i < vols.size(); ++i) {
        const float g = f.compute_feature({ make_trade(1000.f + static_cast<float>(i), vols[i], (i % 2) == 0) });
        obs.push_back(g);
    }

    auto window_sum = [&](std::size_t upto) -> double {
        const std::size_t start = (upto + 1 >= 5) ? (upto + 1 - 5) : 0;
        double s = 0.0;
        for (std::size_t j = start; j <= upto; ++j) s += static_cast<double>(vols[j]);
        return s;
    };

    for (std::size_t i = 0; i < obs.size(); ++i) {
        const double expd = window_sum(i);
        EXPECT_NEAR(obs[i], static_cast<float>(expd), 1e-2f);
    }
}

// zeros then spike then decay
TEST(FeatureVolumeWindowTest, AllZerosThenSpikeThenDecay)
{
    FeatureVolumeWindow f;

    for (int i = 0; i < 5; ++i) {
        const float s = f.compute_feature({ /* empty tick */ });
        EXPECT_FLOAT_EQ(s, 0.f);
    }

    const float spike = 100.f;
    EXPECT_FLOAT_EQ(f.compute_feature({ make_trade(9999.f, spike, true) }), spike);

    for (int i = 0; i < 4; ++i) {
        const float s = f.compute_feature({ /* empty tick */ });
        EXPECT_FLOAT_EQ(s, spike);
    }

    const float s_final = f.compute_feature({ /* empty tick */ });
    EXPECT_FLOAT_EQ(s_final, 0.f);
}

// edge cases with mixed trade counts
TEST(FeatureVolumeWindowTest, MultipleTradesPerTickEdgeCases)
{
    FeatureVolumeWindow f;

    float s = f.compute_feature({ make_trade(100.f, 2.f, true) });
    EXPECT_FLOAT_EQ(s, 2.f);

    s = f.compute_feature({
      T(101.f, 0.5f, true),
      T(101.1f, 0.5f, false),
      T(101.2f, 1.0f, true),
      T(101.3f, 2.0f, false),
    });
    EXPECT_FLOAT_EQ(s, 6.f);

    s = f.compute_feature({ /* empty tick */ });
    EXPECT_FLOAT_EQ(s, 6.f);

    s = f.compute_feature({
      T(102.f, 1e-7f, true),
      T(102.1f, 3e-7f, false),
      T(102.2f, 5e5f, true),
    });
    EXPECT_NEAR(s, 500006.f, 1e-2f);

    s = f.compute_feature({ make_trade(103.f, 7.f, true) });
    EXPECT_NEAR(s, 500013.f, 1e-2f);

    s = f.compute_feature({ make_trade(104.f, 1.f, false) });
    EXPECT_NEAR(s, 500012.f, 1e-2f);
}
