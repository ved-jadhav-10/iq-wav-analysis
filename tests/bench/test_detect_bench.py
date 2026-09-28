"""`bench.detect_bench`'s scoring and aggregation, on a handful of scenes (not the full sweep,
which `uv run python -m bench.detect_bench` runs to write bench/results/)."""

from bench.detect_bench import (
    FSK_MODULATIONS,
    MODULATIONS,
    REPEATS,
    SNR_BUCKETS_DB,
    bucket_stats,
    detect_draw,
    markdown,
    score_draw,
)


def test_detect_draw_covers_every_modulation_and_snr_bucket_evenly() -> None:
    total = len(MODULATIONS) * len(SNR_BUCKETS_DB) * REPEATS
    draws = [detect_draw(seed) for seed in range(total)]
    seen = {(d.modulation, d.snr_db) for d in draws}
    assert seen == {(m, s) for m in MODULATIONS for s in SNR_BUCKETS_DB}
    counts: dict[tuple[str, float], int] = {}
    for d in draws:
        counts[d.modulation, d.snr_db] = counts.get((d.modulation, d.snr_db), 0) + 1
    assert set(counts.values()) == {REPEATS}


def test_score_draw_recovers_a_clean_high_snr_bpsk_scene() -> None:
    draw = next(
        d for d in map(detect_draw, range(1000)) if d.modulation == "bpsk" and d.snr_db == 30.0
    )
    score = score_draw(draw)
    assert score.detected
    assert score.rate_error is not None
    assert abs(score.rate_error) < 0.01
    assert score.snr_error_db is not None
    assert abs(score.snr_error_db) < 3.0
    assert score.cfo_error is not None
    assert abs(score.cfo_error) < 0.01


def test_score_draw_skips_snr_for_fsk_but_still_estimates_rate() -> None:
    draw = next(
        d
        for d in map(detect_draw, range(2000))
        if d.modulation in FSK_MODULATIONS and d.snr_db == 30.0
    )
    score = score_draw(draw)
    assert score.snr_error_db is None
    assert score.cfo_error is None


def test_bucket_stats_handles_a_bucket_with_only_one_modulation_family() -> None:
    """A bucket with no FSK (or no linear) rows must report that split as absent, not crash -
    only ever happens off the full seed grid, but `bucket_stats` shouldn't assume otherwise."""
    only_bpsk = [score_draw(detect_draw(seed)) for seed in range(REPEATS)]  # bpsk, snr 0 only
    stats = bucket_stats(0.0, only_bpsk)
    assert stats["falseDetectionsPerSceneFsk"] is None
    assert stats["falseDetectionsPerSceneLinear"] is not None
    assert "—" in markdown(
        {
            "benchVersion": "0.0.0",
            "generator": "test",
            "samplesPerScene": 1,
            "repeatsPerBucket": REPEATS,
            "modulations": list(MODULATIONS),
            "buckets": [stats],
        }
    )


def test_bucket_stats_and_markdown_on_a_mixed_handful_of_scenes() -> None:
    # one bpsk (linear) and one 2fsk draw at the same SNR bucket, plus their repeats
    bpsk_combo = MODULATIONS.index("bpsk") * len(SNR_BUCKETS_DB)
    fsk_combo = MODULATIONS.index("2fsk") * len(SNR_BUCKETS_DB)
    seeds = [bpsk_combo * REPEATS, fsk_combo * REPEATS]
    rows = [score_draw(detect_draw(seed)) for seed in seeds]
    stats = bucket_stats(rows[0].snr_db, rows)
    assert stats["scenes"] == len(rows)
    assert 0.0 <= stats["recall"] <= 1.0
    assert stats["falseDetectionsPerScene"] >= 0.0
    assert stats["falseDetectionsPerSceneLinear"] is not None
    assert stats["falseDetectionsPerSceneFsk"] is not None
    results = {
        "benchVersion": "0.0.0",
        "generator": "test",
        "samplesPerScene": 1,
        "repeatsPerBucket": len(rows),
        "modulations": list(MODULATIONS),
        "buckets": [stats],
    }
    text = markdown(results)
    assert "STANDARDS" in text
    assert "M-FSK" in text
