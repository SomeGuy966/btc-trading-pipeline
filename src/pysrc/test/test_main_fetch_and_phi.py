from __future__ import annotations

from typing import List, Tuple, Optional
import pytest

# Module under test
from pysrc import main as mainmod

# Try to import the pybind module for a fresh FeatureVolumeWindow
try:
    from pysrc import intern
except Exception:  # pragma: no cover
    intern = None


Trade = Tuple[float, float, bool]
Tick = List[Trade]
TradePair = Tuple[float, float]
GetDataRet = Tuple[List[TradePair], List[TradePair], Optional[float]]


def _tick(buys: list[tuple[float, float]], sells: list[tuple[float, float]]) -> Tick:
    """Replicate main._to_tick behavior notional = round(price * amount, 2)"""
    out: Tick = []
    for px, amt in buys:
        out.append((float(px), round(float(px) * float(amt), 2), True))
    for px, amt in sells:
        out.append((float(px), round(float(px) * float(amt), 2), False))
    return out


def _patch_data_client(monkeypatch: pytest.MonkeyPatch, fake_cls: type) -> None:
    patched = False

    # Symbol bound inside pysrc.main
    if hasattr(mainmod, "DataClient"):
        monkeypatch.setattr(mainmod, "DataClient", fake_cls, raising=True)
        patched = True

    if hasattr(mainmod, "intern"):
        try:
            monkeypatch.setattr(mainmod.intern, "DataClient", fake_cls, raising=False)
            patched = True
        except Exception:
            pass

    # patch the pybind module directly if it exists
    try:
        from pysrc import intern as _intern

        monkeypatch.setattr(_intern, "DataClient", fake_cls, raising=False)
        patched = True
    except Exception:
        pass

    # Fallback: patch python client module
    try:
        from pysrc import data_client as dcmod

        if hasattr(dcmod, "DataClient"):
            monkeypatch.setattr(dcmod, "DataClient", fake_cls, raising=True)
            patched = True
    except Exception:
        pass

    if not patched:
        raise RuntimeError("Could not locate a DataClient symbol to patch.")


def _reset_vol_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset stateful FeatureVolumeWindow used by _phi"""
    if intern is not None and hasattr(intern, "FeatureVolumeWindow"):
        monkeypatch.setattr(
            mainmod, "_VOL_WIN", intern.FeatureVolumeWindow(), raising=True
        )


def test_phi_matches_individual_feature_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    _phi should be the ordered list of individual features
    Use price=1.0 so notional == amount, and avoid double-advancing window
    """
    _reset_vol_window(monkeypatch)

    tick: Tick = _tick(buys=[(1.0, 1.0), (1.0, 0.5)], sells=[(1.0, 2.0)])

    c = mainmod._feat_count(tick)
    rb = mainmod._feat_ratio_buys(tick)
    rs = mainmod._feat_ratio_sells(tick)

    phi = mainmod._phi(tick)  # advances module window once
    assert isinstance(phi, list) and len(phi) == 4
    assert phi[0] == pytest.approx(c)
    assert phi[1] == pytest.approx(rb)
    assert phi[2] == pytest.approx(rs)

    if intern is not None and hasattr(intern, "FeatureVolumeWindow"):
        local_win = intern.FeatureVolumeWindow()
        expected_v5 = local_win.compute_feature(tick)
        assert phi[3] == pytest.approx(expected_v5)


def test_phi_window_rolls_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    rolling behavior over consecutive calls; use price=1.0 so notional == amount
    """
    _reset_vol_window(monkeypatch)

    t1: Tick = _tick(buys=[(1.0, 1.0)], sells=[])
    t2: Tick = _tick(buys=[], sells=[(1.0, 2.0)])
    t3: Tick = _tick(buys=[(1.0, 3.0)], sells=[])

    # expected values via a fresh local window
    expected_vals: List[float] = []
    if intern is not None and hasattr(intern, "FeatureVolumeWindow"):
        w = intern.FeatureVolumeWindow()
        expected_vals = [
            w.compute_feature(t1),
            w.compute_feature(t2),
            w.compute_feature(t3),
        ]

    v1 = mainmod._phi(t1)[3]
    v2 = mainmod._phi(t2)[3]
    v3 = mainmod._phi(t3)[3]

    if expected_vals:
        assert v1 == pytest.approx(expected_vals[0])
        assert v2 == pytest.approx(expected_vals[1])
        assert v3 == pytest.approx(expected_vals[2])
    else:
        assert v1 <= v2 <= v3
