// src/cppsrc/main.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "base_feature.hpp"
#include "data_client.hpp"
#include "feature_count_trades.hpp"
#include "feature_ratio_buys.hpp"
#include "feature_ratio_sells.hpp"
#include "feature_volume_window.hpp"

#include <tuple>
#include <vector>

namespace py = pybind11;
using Trade = std::tuple<float, float, bool>;// (price, volume, is_buy)

// Keep this so your current Python test passes.
int add(int a, int b)
{
    return a + b;
}

// Stub main so the executable target 'intern_project' links
int main()
{
    return 0;
}

// Pybind module name stays 'my_intern'
PYBIND11_MODULE(intern, m)
{
    m.doc() = "Step 2 features (friend-style binding, base first)";


    // 1) Bind the base FIRST so pybind knows it
    py::class_<intproj::BaseFeature>(m, "BaseFeature");// no __init__ needed

    // 2) Bind derived classes referencing the base
    py::class_<intproj::FeatureCountTrades, intproj::BaseFeature>(m, "FeatureCountTrades")
      .def(py::init<>())
      .def("compute_feature", &intproj::FeatureCountTrades::compute_feature);

    py::class_<intproj::FeatureRatioBuys, intproj::BaseFeature>(m, "FeatureRatioBuys")
      .def(py::init<>())
      .def("compute_feature", &intproj::FeatureRatioBuys::compute_feature);

    py::class_<intproj::FeatureRatioSells, intproj::BaseFeature>(m, "FeatureRatioSells")
      .def(py::init<>())
      .def("compute_feature", &intproj::FeatureRatioSells::compute_feature);

    py::class_<intproj::FeatureVolumeWindow, intproj::BaseFeature>(m, "FeatureVolumeWindow")
      .def(py::init<>())
      .def("compute_feature", &intproj::FeatureVolumeWindow::compute_feature);

    py::class_<intproj::DataClient>(m, "DataClient")
      .def(py::init<>())
      .def(
        "get_data",
        [](const intproj::DataClient &self, const std::string &symbol, bool sandbox) {
            intproj::DataResult r = self.get_data(symbol, sandbox);
            // Return None when midprice is not set
            py::object midobj = r.midprice.has_value() ? py::cast(*r.midprice) : py::none();
            return py::make_tuple(r.buys, r.sells, midobj);
        },
        py::arg("symbol") = "btcusd",
        py::arg("sandbox") = true);
}