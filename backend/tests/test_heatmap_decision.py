from app.histopathology.heatmap_decision import (
    FOCAL_STATUS,
    MIXED_STATUS,
    NOT_EVALUABLE_STATUS,
    POSITIVE_STATUS,
    SANE_STATUS,
    aggregate_heatmap_roi_decision,
)


def _tile(index, x, y, *, klass="no_metastasico", status="clasificado", score=0.05):
    return {
        "index": index,
        "roi": {"x": x, "y": y, "width": 512, "height": 512},
        "status": status,
        "class": klass,
        "tumor_score": score,
    }


def test_clustered_tumor_tiles_are_metastasis_probable():
    decision = aggregate_heatmap_roi_decision(
        [
            _tile(0, 0, 0, klass="metastasico", score=0.96),
            _tile(1, 512, 0, klass="metastasico", score=0.94),
            _tile(2, 0, 512, score=0.04),
            _tile(3, 512, 512, score=0.03),
        ]
    )

    assert decision["status"] == POSITIVE_STATUS
    assert decision["metrics"]["max_connected_tumor_cluster"] == 2


def test_isolated_strong_tumor_tile_is_focal_suspicion_not_whole_roi_positive():
    decision = aggregate_heatmap_roi_decision(
        [
            _tile(0, 0, 0, klass="metastasico", score=0.97),
            _tile(1, 512, 0, score=0.08),
            _tile(2, 0, 512, score=0.06),
            _tile(3, 512, 512, score=0.05),
        ]
    )

    assert decision["status"] == FOCAL_STATUS
    assert decision["metrics"]["strong_tumor_tiles"] == 1


def test_mostly_low_tumor_tiles_are_sane_probable():
    decision = aggregate_heatmap_roi_decision(
        [
            _tile(0, 0, 0, score=0.03),
            _tile(1, 512, 0, score=0.09),
            _tile(2, 0, 512, klass="no_metastasico_probable", score=0.12),
            _tile(3, 512, 512, score=0.04),
        ]
    )

    assert decision["status"] == SANE_STATUS
    assert decision["metrics"]["negative_fraction"] == 1.0


def test_low_evaluable_fraction_is_not_evaluable():
    decision = aggregate_heatmap_roi_decision(
        [
            _tile(0, 0, 0, klass="roi_no_evaluable", status="roi_no_evaluable", score=0.0),
            _tile(1, 512, 0, klass="roi_no_evaluable", status="roi_no_evaluable", score=0.0),
            _tile(2, 0, 512, klass="roi_no_evaluable", status="roi_no_evaluable", score=0.0),
            _tile(3, 512, 512, score=0.05),
        ]
    )

    assert decision["status"] == NOT_EVALUABLE_STATUS
    assert decision["metrics"]["evaluable_tiles"] == 1


def test_intermediate_tumor_scores_are_mixed_or_uncertain():
    decision = aggregate_heatmap_roi_decision(
        [
            _tile(0, 0, 0, score=0.82),
            _tile(1, 512, 0, score=0.10),
            _tile(2, 0, 512, score=0.07),
            _tile(3, 512, 512, score=0.05),
        ]
    )

    assert decision["status"] == MIXED_STATUS
    assert decision["metrics"]["suspicious_tiles"] == 1
