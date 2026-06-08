import numpy as np

from histopathology_offline.rigorous_evaluation import (
    calibration_metrics,
    recommend_threshold,
    softmax_with_temperature,
    threshold_sweep,
)


def test_softmax_temperature_returns_probabilities():
    probabilities = softmax_with_temperature([[2.0, 1.0, 0.0]], temperature=2.0)
    assert probabilities.shape == (1, 3)
    assert np.isclose(probabilities.sum(), 1.0)


def test_threshold_sweep_reports_binary_counts_and_abstention():
    labels = [1, 1, 0, 2]
    probabilities = np.array(
        [
            [0.05, 0.90, 0.05],
            [0.35, 0.55, 0.10],
            [0.80, 0.10, 0.10],
            [0.10, 0.60, 0.30],
        ]
    )
    row = threshold_sweep(labels, probabilities, thresholds=[0.5])[0]
    assert (row["tp"], row["fp"], row["fn"], row["tn"]) == (2, 1, 0, 1)
    assert row["sensitivity"] == 1.0
    assert 0.0 <= row["abstention_rate"] <= 1.0


def test_recommend_threshold_honors_precision_constraint():
    rows = [
        {"threshold": 0.5, "precision": 0.8, "sensitivity": 0.9, "f1": 0.85, "balanced_accuracy": 0.8},
        {"threshold": 0.7, "precision": 0.9, "sensitivity": 0.75, "f1": 0.82, "balanced_accuracy": 0.84},
    ]
    selected = recommend_threshold(rows, minimum_precision=0.85)
    assert selected["threshold"] == 0.7
    assert selected["selected_on"] == "validation"


def test_calibration_metrics_include_brier_ece_and_nll():
    labels = [0, 1, 2]
    probabilities = np.array(
        [
            [0.8, 0.1, 0.1],
            [0.1, 0.8, 0.1],
            [0.1, 0.2, 0.7],
        ]
    )
    metrics = calibration_metrics(labels, probabilities)
    assert metrics["multiclass_brier"] >= 0
    assert metrics["tumor_ovr_brier"] >= 0
    assert metrics["expected_calibration_error"] >= 0
    assert metrics["negative_log_likelihood"] >= 0
