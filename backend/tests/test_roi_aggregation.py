from histopathology_offline.roi_aggregation import (
    aggregate_tile_probabilities,
    classify_roi,
)


TILES = [
    {"no_metastasico": 0.1, "metastasico": 0.8, "estroma": 0.1},
    {"no_metastasico": 0.7, "metastasico": 0.2, "estroma": 0.1},
    {"no_metastasico": 0.6, "metastasico": 0.3, "estroma": 0.1},
]


def test_tile_aggregation_strategies_return_expected_tumor_scores():
    assert aggregate_tile_probabilities(TILES, strategy="mean")["tumor_score"] == (0.8 + 0.2 + 0.3) / 3
    assert aggregate_tile_probabilities(TILES, strategy="max")["tumor_score"] == 0.8
    assert aggregate_tile_probabilities(TILES, strategy="top_k_mean", top_k=2)["tumor_score"] == 0.55
    assert aggregate_tile_probabilities(TILES, strategy="positive_fraction", tile_threshold=0.5)["tumor_score"] == 1 / 3


def test_roi_classification_exposes_uncertain_and_low_suspicion_states():
    aggregation = aggregate_tile_probabilities(TILES, strategy="mean")
    uncertain = classify_roi(aggregation, tumor_threshold=0.45, uncertainty_margin=0.05)
    low = classify_roi(aggregation, tumor_threshold=0.8, uncertainty_margin=0.05)
    assert uncertain["status"] == "incierto"
    assert low["status"] == "baja_sospecha"
