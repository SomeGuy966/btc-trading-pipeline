// src/cppsrc/main.cpp
// pybind11 bindings for the C++ core: order-flow features and the REST client.
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "base_feature.hpp"
#include "data_client.hpp"
#include "feature_count_trades.hpp"
#include "feature_ratio_buys.hpp"
#include "feature_ratio_sells.hpp"
#include "feature_set.hpp"
#include "feature_volume_window.hpp"

#include <string>
#include <tuple>
#include <vector>

namespace py = pybind11;

PYBIND11_MODULE(cppcore, m)
{
    m.doc() = "C++ core: order-flow feature computation and Gemini REST client.";

    // Bind the abstract base first so the derived bindings can reference it.
    py::class_<btcpipe::BaseFeature>(m, "BaseFeature");

    py::class_<btcpipe::FeatureCountTrades, btcpipe::BaseFeature>(m, "FeatureCountTrades")
      .def(py::init<>())
      .def("compute_feature", &btcpipe::FeatureCountTrades::compute_feature);

    py::class_<btcpipe::FeatureRatioBuys, btcpipe::BaseFeature>(m, "FeatureRatioBuys")
      .def(py::init<>())
      .def("compute_feature", &btcpipe::FeatureRatioBuys::compute_feature);

    py::class_<btcpipe::FeatureRatioSells, btcpipe::BaseFeature>(m, "FeatureRatioSells")
      .def(py::init<>())
      .def("compute_feature", &btcpipe::FeatureRatioSells::compute_feature);

    // Stateful: keeps a rolling window across calls, so each pass over a tick
    // sequence needs its own instance.
    py::class_<btcpipe::FeatureVolumeWindow, btcpipe::BaseFeature>(m, "FeatureVolumeWindow")
      .def(py::init<>())
      .def("compute_feature", &btcpipe::FeatureVolumeWindow::compute_feature);

    // Computes all four features in a single boundary crossing.
    py::class_<btcpipe::FeatureSet>(m, "FeatureSet")
      .def(py::init<>())
      .def("compute", &btcpipe::FeatureSet::compute, py::arg("data"));

    py::class_<btcpipe::DataClient>(m, "DataClient")
      .def(py::init<>())
      .def(
        "get_data",
        [](const btcpipe::DataClient &self, const std::string &symbol, bool sandbox) {
            btcpipe::DataResult r = self.get_data(symbol, sandbox);
            // Midprice is absent when either side of the book had no trades.
            py::object midobj = r.midprice.has_value() ? py::cast(*r.midprice) : py::none();
            return py::make_tuple(r.buys, r.sells, midobj);
        },
        py::arg("symbol") = "btcusd",
        py::arg("sandbox") = true);
}
