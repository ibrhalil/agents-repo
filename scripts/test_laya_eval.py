#!/usr/bin/env python3
"""Model-free regression tests for laya_eval metric correctness.

Covers the 2026-10-02 review findings: (1) noul/score confidence must be the
predicted class probability, never gold-derived; (2) sweep option sets must
always contain the gold route.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from laya_eval import ROUTE_OPTIONS, SWEEP_EXTRA, ece, hf_rate, noul_conf, pick_sweep_options, score_conf  # noqa: E402


def test_noul_conf_predicted_class():
    # Review case: p=0.99, gold=false -> predicted class confidence 0.99 (not 0.01)
    assert abs(noul_conf({"noul": 0.99}) - 0.99) < 1e-9
    assert abs(noul_conf({"noul": 0.01}) - 0.99) < 1e-9
    assert abs(noul_conf({"noul": 0.6}) - 0.6) < 1e-9
    # answer_confidence, when present, wins
    assert noul_conf({"noul": 0.9, "answer_confidence": 0.7}) == 0.7


def test_high_conf_failure_detectable():
    # p=0.99, gold=0: wrong prediction at high confidence -> HF=1, ECE~0.99
    pairs = [(False, noul_conf({"noul": 0.99}))]
    assert pairs == [(False, 0.99)]
    assert hf_rate(pairs) == 1.0
    e = ece(pairs)
    assert e is not None and e > 0.98
    # old gold-derived bug would give conf=0.01 -> HF 0, ECE 0.01
    assert hf_rate([(False, 0.01)]) == 0.0


def test_score_conf_from_distribution():
    answer = {"score": 1.16, "probabilities": {"0": 0.32, "1": 0.33, "2": 0.24, "3": 0.11}}
    assert abs(score_conf(answer, 1) - 0.33) < 1e-9
    assert abs(score_conf(answer, 3) - 0.11) < 1e-9
    assert score_conf({"score": 2.0}, 2) == 0.5  # no distribution: neutral fallback


def test_sweep_contains_gold():
    rng = random.Random(7)
    for size in (5, 10, 20, 40):
        for gold in ROUTE_OPTIONS:  # every route incl. chat must remain answerable
            opts = pick_sweep_options(gold, size, rng)
            assert len(opts) == size, (gold, size, len(opts))
            assert gold in opts, (gold, size)
            for key in opts:
                assert key in ROUTE_OPTIONS or key in SWEEP_EXTRA


def test_sweep_position_not_leaked():
    # A predictor that returns the FIRST option without reading the text must
    # score below 100%: gold is never systematically in position 0.
    for size in (5, 10, 20, 40):
        rng = random.Random(7)
        first_hits = 0
        combos = 0
        for gold in ROUTE_OPTIONS:
            opts = pick_sweep_options(gold, size, rng)
            combos += 1
            first_hits += list(opts)[0] == gold
        assert first_hits < combos, ("position leak", size, first_hits, combos)
    # Determinism: identical seed produces identical order
    a = pick_sweep_options("chat", 10, random.Random(3))
    b = pick_sweep_options("chat", 10, random.Random(3))
    assert list(a) == list(b)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
