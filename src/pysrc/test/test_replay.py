"""Tests for tick recording, replay, and bounded runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, List

import pytest

from pysrc import main as mainmod
from pysrc.main import RawTick, record, replay_ticks, run


def _sample_ticks(n: int) -> List[RawTick]:
    out: List[RawTick] = []
    for i in range(n):
        mid = 100.0 + i * 0.5
        buys = [(mid - 0.5, 1.0 + i * 0.1)]
        sells = [(mid + 0.5, 1.0)]
        out.append((buys, sells, mid))
    return out


def _as_source(ticks: List[RawTick]) -> Iterator[RawTick]:
    return iter(ticks)


def test_record_then_replay_round_trips(tmp_path: Path) -> None:
    original = _sample_ticks(5)
    path = tmp_path / "ticks.jsonl"

    # record() is a pass-through generator, so it must be drained to write.
    passed_through = list(record(_as_source(original), path))
    assert passed_through == original

    assert list(replay_ticks(path)) == original


def test_recorded_file_is_one_json_object_per_line(tmp_path: Path) -> None:
    path = tmp_path / "ticks.jsonl"
    list(record(_as_source(_sample_ticks(3)), path))

    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 3
    for line in lines:
        rec = json.loads(line)
        assert set(rec) == {"buys", "sells", "mid"}


def test_replay_preserves_absent_midprice(tmp_path: Path) -> None:
    path = tmp_path / "ticks.jsonl"
    ticks: List[RawTick] = [([(100.0, 1.0)], [], None)]
    list(record(_as_source(ticks), path))

    assert list(replay_ticks(path))[0][2] is None


def test_run_stops_at_max_ticks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mainmod, "PREDICTIONS_PATH", tmp_path / "predictions.txt")
    monkeypatch.setattr(mainmod, "TARGETS_PATH", tmp_path / "targets.txt")

    processed = run(_as_source(_sample_ticks(50)), max_ticks=7, verbose=False)
    assert processed == 7


def test_run_skips_ticks_with_no_midprice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mainmod, "PREDICTIONS_PATH", tmp_path / "predictions.txt")
    monkeypatch.setattr(mainmod, "TARGETS_PATH", tmp_path / "targets.txt")

    ticks: List[RawTick] = [([(100.0, 1.0)], [], None)] + _sample_ticks(4)
    processed = run(_as_source(ticks), verbose=False)
    assert processed == 4


def test_run_logs_aligned_predictions_and_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preds = tmp_path / "predictions.txt"
    targets = tmp_path / "targets.txt"
    monkeypatch.setattr(mainmod, "PREDICTIONS_PATH", preds)
    monkeypatch.setattr(mainmod, "TARGETS_PATH", targets)

    run(_as_source(_sample_ticks(30)), verbose=False)

    n_preds = len([ln for ln in preds.read_text().splitlines() if ln.strip()])
    n_targets = len([ln for ln in targets.read_text().splitlines() if ln.strip()])
    assert n_preds == n_targets
    assert n_preds > 0
