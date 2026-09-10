// src/cppsrc/test/test_feature_edge_invariants.cpp
#include "../feature_ratio_buys.hpp"
#include "../feature_ratio_sells.hpp"
#include "../feature_volume_window.hpp"
#include "utilities.hpp"
#include "gtest/gtest.h"

#include <array>
#include <cmath>
#include <limits>
#include <tuple>
#include <vector>

using btcpipe::FeatureVolumeWindow;
using btcpipe::FeatureRatioBuys;
using btcpipe::FeatureRatioSells;
using btcpipe::test::make_trade;


using TradeTriple = std::tuple<float, float, bool>;

static TradeTriple make_trade_tuple(float price, float vol, bool is_buy)
{
    return std::make_tuple(price, vol, is_buy);
}

// zero-trade policy for ratio features
TEST(FeatureEdgeInvariants, Ratios_ZeroTradePolicy)
{
    FeatureRatioBuys rb;
    FeatureRatioSells rs;

    bool threw_b = false;
    bool threw_s = false;
    float vb = std::numeric_limits<float>::quiet_NaN();
    float vs = std::numeric_limits<float>::quiet_NaN();

    try {
        vb = rb.compute_feature({});
    } catch (...) {
        threw_b = true;
    }
    try {
        vs = rs.compute_feature({});
    } catch (...) {
        threw_s = true;
    }

    if (!threw_b) {
        bool okb = std::isnan(vb) || (vb >= 0.f && vb <= 1.f);
        EXPECT_TRUE(okb) << "ratio buys on empty tick must throw, be NaN, or be in [0,1]";
    }
    if (!threw_s) {
        bool oks = std::isnan(vs) || (vs >= 0.f && vs <= 1.f);
        EXPECT_TRUE(oks) << "ratio sells on empty tick must throw, be NaN, or be in [0,1]";
    }
}

// parity invariant when the tick has trades
TEST(FeatureEdgeInvariants, Ratios_ParityInvariant)
{
    FeatureRatioBuys rb;
    FeatureRatioSells rs;

    std::vector<std::tuple<float, float, bool>> tick = {
        make_trade_tuple(100.f, 1.f, true),
        make_trade_tuple(101.f, 2.f, false),
        make_trade_tuple(102.f, 3.f, true),
        make_trade_tuple(103.f, 4.f, false),
        make_trade_tuple(104.f, 0.f, true),
        make_trade_tuple(105.f, 0.5f, false),
        make_trade_tuple(106.f, 7.f, true),
    };// mixed buys and sells

    float b = rb.compute_feature(tick);
    float s = rs.compute_feature(tick);

    if (std::isfinite(b) && std::isfinite(s)) {
        EXPECT_NEAR(b + s, 1.f, 1e-6f);
        EXPECT_GE(b, 0.f);
        EXPECT_LE(b, 1.f);
        EXPECT_GE(s, 0.f);
        EXPECT_LE(s, 1.f);
    } else {
        EXPECT_TRUE(std::isnan(b) && std::isnan(s));
    }
}

// input validation for NaN, Inf, negative values
TEST(FeatureEdgeInvariants, InputValidation_NaN_Inf_Negative)
{
    FeatureRatioBuys rb;
    FeatureRatioSells rs;
    FeatureVolumeWindow vw;

    const float NaN = std::numeric_limits<float>::quiet_NaN();
    const float Inf = std::numeric_limits<float>::infinity();

    bool threw_rb = false;
    bool threw_rs = false;
    bool threw_vw = false;

    try {
        (void)rb.compute_feature({ make_trade_tuple(100.f, NaN, true), make_trade_tuple(101.f, 1.f, false) });
    } catch (...) {
        threw_rb = true;
    }
    try {
        (void)rs.compute_feature({ make_trade_tuple(100.f, Inf, false), make_trade_tuple(101.f, -2.f, true) });
    } catch (...) {
        threw_rs = true;
    }

    if (!threw_rb) {
        float r = rb.compute_feature({ make_trade_tuple(1.f, -3.f, true), make_trade_tuple(2.f, 0.f, false) });
        EXPECT_TRUE(std::isnan(r) || (r >= 0.f && r <= 1.f));
    }
    if (!threw_rs) {
        float r = rs.compute_feature({ make_trade_tuple(1.f, -3.f, false), make_trade_tuple(2.f, 0.f, true) });
        EXPECT_TRUE(std::isnan(r) || (r >= 0.f && r <= 1.f));
    }

    try {
        (void)vw.compute_feature({
          make_trade_tuple(100.f, 1.f, true),
          make_trade_tuple(101.f, NaN, false),
          make_trade_tuple(102.f, -5.f, true),
          make_trade_tuple(103.f, Inf, false),
        });
    } catch (...) {
        threw_vw = true;
    }

    if (!threw_vw) {
        // Just verify subsequent calls do not throw, regardless of numeric policy
        EXPECT_NO_THROW({
            (void)vw.compute_feature({ /* empty tick */ });
            (void)vw.compute_feature({ make_trade_tuple(200.f, 1.f, true) });
        });
    }
}

// Copy and move semantics for the rolling window
TEST(FeatureEdgeInvariants, Volume_CopyMoveSemantics)
{
    FeatureVolumeWindow base;
    (void)base.compute_feature({ make_trade_tuple(100.f, 1.f, true) });
    (void)base.compute_feature({ make_trade_tuple(101.f, 2.f, false) });
    (void)base.compute_feature({ make_trade_tuple(102.f, 3.f, true) });

    FeatureVolumeWindow f_copy = base;// copy
    FeatureVolumeWindow temp = base;// prep for move
    FeatureVolumeWindow f_moved = std::move(temp);// move

    const float v = 4.f;
    float a = base.compute_feature({ make_trade_tuple(103.f, v, false) });
    float b = f_copy.compute_feature({ make_trade_tuple(103.f, v, false) });
    float c = f_moved.compute_feature({ make_trade_tuple(103.f, v, false) });

    EXPECT_FLOAT_EQ(a, b);
    EXPECT_FLOAT_EQ(a, c);
}

// Batch eviction edge around multiple drops
TEST(FeatureEdgeInvariants, Volume_BatchEvictionEdge)
{
    FeatureVolumeWindow f;

    std::vector<float> vols;
    for (int i = 1; i <= 10; ++i) vols.push_back(static_cast<float>(i));

    std::vector<float> obs;
    obs.reserve(vols.size());
    for (float x : vols) { obs.push_back(f.compute_feature({ make_trade_tuple(100.f + x, x, true) })); }

    auto naive_last5 = [&](int idx) -> float {
        int start = std::max(0, idx - 4);
        float s = 0.f;
        for (int j = start; j <= idx; ++j) s += vols[static_cast<std::size_t>(j)];
        return s;
    };

    std::array<int, 5> idxs{ 4, 5, 6, 8, 9 };
    for (int idx : idxs) { EXPECT_NEAR(obs[static_cast<std::size_t>(idx)], naive_last5(idx), 1e-6f); }
}

// Drift guard long run of tiny then one huge
TEST(FeatureEdgeInvariants, Volume_DriftGuard_LongTinyThenHuge)
{
    FeatureVolumeWindow f;

    for (int i = 0; i < 2000; ++i) {
        (void)f.compute_feature({ make_trade_tuple(100.f + i * 0.01f, 1e-6f, (i % 2) == 0) });
    }
    float out = f.compute_feature({ make_trade_tuple(12345.f, 1000.f, true) });

    // assume default window size is 5 like the rest of the suite
    EXPECT_NEAR(out, 1000.f + 4e-6f, 1e-3f);
}
