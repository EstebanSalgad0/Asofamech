from app.histopathology.ml.inference_service import (
    _bool_env,
    _float_env,
    _optional_probability_env,
    _positive_float_env,
)


def test_probability_threshold_rejects_values_over_one(monkeypatch):
    monkeypatch.setenv("TEST_THRESHOLD", "1.5")
    assert _float_env("TEST_THRESHOLD", 0.9) == 0.9


def test_temperature_accepts_values_over_one(monkeypatch):
    monkeypatch.setenv("TEST_TEMPERATURE", "1.5")
    assert _positive_float_env("TEST_TEMPERATURE", 1.0) == 1.5


def test_temperature_rejects_non_positive_values(monkeypatch):
    monkeypatch.setenv("TEST_TEMPERATURE", "0")
    assert _positive_float_env("TEST_TEMPERATURE", 1.0) == 1.0


def test_checkpoint_calibration_flag_is_opt_in(monkeypatch):
    monkeypatch.delenv("TEST_CALIBRATION", raising=False)
    assert _bool_env("TEST_CALIBRATION", False) is False
    monkeypatch.setenv("TEST_CALIBRATION", "true")
    assert _bool_env("TEST_CALIBRATION", False) is True


def test_optional_tumor_threshold_is_disabled_when_empty(monkeypatch):
    monkeypatch.setenv("TEST_TUMOR_THRESHOLD", "")
    assert _optional_probability_env("TEST_TUMOR_THRESHOLD") is None
    monkeypatch.setenv("TEST_TUMOR_THRESHOLD", "0.35")
    assert _optional_probability_env("TEST_TUMOR_THRESHOLD") == 0.35
