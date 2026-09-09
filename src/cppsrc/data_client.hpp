#pragma once
#include <cmath>
#include <cpr/cpr.h>
#include <cstdint>
#include <limits>
#include <nlohmann/json.hpp>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace intproj {


using Order = std::pair<double, double>;
using Midprice = std::optional<double>;// None means not computed


// Parsed result returned to Python (kept simple for pybind)
struct DataResult
{
    std::vector<Order> buys;
    std::vector<Order> sells;
    Midprice midprice;
};

class DataClient
{
  public:
    // top-level entry point
    DataResult get_data(const std::string &symbol = "btcusd", bool sandbox = true) const
    {
        const std::string url = base_url(sandbox) + "/trades/" + symbol + "?limit_trades=50";

        cpr::Response res = cpr::Get(cpr::Url{ url });
        if (res.status_code < 200 || res.status_code >= 300) { return { {}, {}, std::nullopt }; }

        nlohmann::json j;
        try {
            j = nlohmann::json::parse(res.text);
        } catch (...) {
            return { {}, {}, std::nullopt };
        }

        std::vector<Order> buys, sells;

        // capacity planning pass
        std::size_t n_buys = 0, n_sells = 0;
        if (j.is_array()) {
            for (const auto &t : j) {
                if (!t.contains("type") || !t["type"].is_string()) continue;
                const auto &typ = t["type"].get_ref<const std::string &>();
                if (typ == "buy")
                    ++n_buys;
                else if (typ == "sell")
                    ++n_sells;
            }
        }
        buys.reserve(n_buys);
        sells.reserve(n_sells);

        // State to compute a tick-like mid from the latest buy/sell by timestamp
        bool have_latest_buy = false, have_latest_sell = false;
        double latest_buy_price = 0.0, latest_sell_price = 0.0;
        std::int64_t latest_buy_ts = -1, latest_sell_ts = -1;

        auto to_double = [](const nlohmann::json &v) -> double {
            if (v.is_string()) return std::stod(v.get_ref<const std::string &>());
            if (v.is_number_float()) return v.get<double>();
            if (v.is_number_integer()) return static_cast<double>(v.get<long long>());
            return std::numeric_limits<double>::quiet_NaN();// skip bad data
        };
        auto to_ts_ms = [](const nlohmann::json &obj) -> std::int64_t {
            if (obj.contains("timestampms")) {
                if (obj["timestampms"].is_number_integer()) return obj["timestampms"].get<long long>();
                if (obj["timestampms"].is_string())
                    return std::stoll(obj["timestampms"].get_ref<const std::string &>());
            }
            if (obj.contains("timestamp")) {
                if (obj["timestamp"].is_number_integer()) return obj["timestamp"].get<long long>() * 1000LL;
                if (obj["timestamp"].is_string())
                    return std::stoll(obj["timestamp"].get_ref<const std::string &>()) * 1000LL;
            }
            return -1;// unknown
        };

        if (j.is_array()) {
            for (const auto &t : j) {
                if (!t.contains("price") || !t.contains("amount") || !t.contains("type")) continue;

                double price = to_double(t["price"]);
                double amount = to_double(t["amount"]);
                if (!std::isfinite(price) || !std::isfinite(amount)) continue;

                const std::string typ = t["type"].is_string() ? t["type"].get<std::string>() : "";
                const auto ts = to_ts_ms(t);

                if (typ == "buy") {
                    buys.emplace_back(price, amount);
                    if (ts > latest_buy_ts) {
                        latest_buy_ts = ts;
                        latest_buy_price = price;
                        have_latest_buy = ts >= 0;
                    }
                } else if (typ == "sell") {
                    sells.emplace_back(price, amount);
                    if (ts > latest_sell_ts) {
                        latest_sell_ts = ts;
                        latest_sell_price = price;
                        have_latest_sell = ts >= 0;
                    }
                }
            }
        }

        Midprice mid = std::nullopt;
        if (have_latest_buy && have_latest_sell)
            mid = 0.5 * (latest_buy_price + latest_sell_price);
        else if (have_latest_buy)
            mid = latest_buy_price;
        else if (have_latest_sell)
            mid = latest_sell_price;

        // trim any over-reservation after filtering
        buys.shrink_to_fit();
        sells.shrink_to_fit();

        return { std::move(buys), std::move(sells), mid };
    }

  private:
    // Container to track the latest buy/sell seen while scanning trades
    struct Latest
    {
        bool have_buy = false;
        bool have_sell = false;
        double buy_px = 0.0;
        double sell_px = 0.0;
        std::int64_t buy_ts = -1;
        std::int64_t sell_ts = -1;
    };

    // Choose the base URL depending on environment
    static std::string base_url(bool sandbox)
    {
        return sandbox ? "https://api.sandbox.gemini.com/v1" : "https://api.gemini.com/v1";
    }

    // Parse JSON defensively; return nullopt if parsing fails
    static std::optional<nlohmann::json> parse_json(const std::string &s)
    {
        try {
            return nlohmann::json::parse(s);
        } catch (...) {
            return std::nullopt;
        }
    }

    // Convert Gemini's fields (sometimes strings) to double
    static double to_double(const nlohmann::json &v)
    {
        if (v.is_string()) return std::stod(v.get<std::string>());
        if (v.is_number_float()) return v.get<double>();
        if (v.is_number_integer()) return static_cast<double>(v.get<long long>());
        return std::numeric_limits<double>::quiet_NaN();// caller will skip NaNs
    }

    // Extract a millisecond timestamp
    static std::int64_t to_ts_ms(const nlohmann::json &obj)
    {
        if (obj.contains("timestampms")) {
            const auto &x = obj["timestampms"];
            if (x.is_number_integer()) return x.get<long long>();
            if (x.is_string()) return std::stoll(x.get<std::string>());
        }
        if (obj.contains("timestamp")) {
            const auto &x = obj["timestamp"];
            if (x.is_number_integer()) return x.get<long long>() * 1000LL;
            if (x.is_string()) return std::stoll(x.get<std::string>()) * 1000LL;
        }
        return -1;
    }

    // Ingest one trade JSON object into (buys/sells) and update 'latest'
    static void
      ingest_trade(const nlohmann::json &t, std::vector<Order> &buys, std::vector<Order> &sells, Latest &latest)
    {
        if (!t.contains("price") || !t.contains("amount") || !t.contains("type")) return;

        const double price = to_double(t["price"]);
        const double amount = to_double(t["amount"]);
        if (!std::isfinite(price) || !std::isfinite(amount)) return;

        const std::string typ = t["type"].is_string() ? t["type"].get<std::string>() : "";
        const std::int64_t ts = to_ts_ms(t);

        if (typ == "buy") {
            buys.emplace_back(price, amount);
            if (ts > latest.buy_ts) {
                latest.buy_ts = ts;
                latest.buy_px = price;
                latest.have_buy = (ts >= 0);
            }
        } else if (typ == "sell") {
            sells.emplace_back(price, amount);
            if (ts > latest.sell_ts) {
                latest.sell_ts = ts;
                latest.sell_px = price;
                latest.have_sell = (ts >= 0);
            }
        }
    }

    // Scan the array of trades and return accumulated orders
    static std::pair<std::vector<Order>, std::vector<Order>> extract_orders(const nlohmann::json &j, Latest &latest)
    {
        std::vector<Order> buys, sells;
        if (!j.is_array()) return { std::move(buys), std::move(sells) };

        buys.reserve(j.size());
        sells.reserve(j.size());
        for (const auto &t : j) { ingest_trade(t, buys, sells, latest); }
        return { std::move(buys), std::move(sells) };
    }

    // Decide the midprice from the most recent buy/sell seen
    static Midprice compute_mid(const Latest &latest)
    {
        if (latest.have_buy && latest.have_sell) return 0.5 * (latest.buy_px + latest.sell_px);
        if (latest.have_buy) return latest.buy_px;
        if (latest.have_sell) return latest.sell_px;
        return std::nullopt;
    }
};

}// namespace intproj
