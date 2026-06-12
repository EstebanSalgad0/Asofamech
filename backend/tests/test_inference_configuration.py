from contextlib import nullcontext

from app.histopathology.ml.inference_service import (
    HistopathologyInferenceService,
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


def test_predict_patch_returns_checkpoint_calibration_metadata():
    class Scalar:
        def __init__(self, value):
            self.value = value

        def item(self):
            return self.value

    class ProbabilityVector:
        values = (0.1, 0.8, 0.1)

        def __getitem__(self, index):
            return Scalar(self.values[index])

    class ProbabilityBatch:
        def __getitem__(self, index):
            assert index == 0
            return ProbabilityVector()

    class Logits:
        def __truediv__(self, value):
            assert value == 1.5
            return self

    class TorchStub:
        @staticmethod
        def inference_mode():
            return nullcontext()

        @staticmethod
        def softmax(logits, dim):
            assert isinstance(logits, Logits)
            assert dim == 1
            return ProbabilityBatch()

        @staticmethod
        def argmax(probabilities):
            assert isinstance(probabilities, ProbabilityVector)
            return Scalar(1)

    class ExtractorStub:
        @staticmethod
        def encode_pil(_patch):
            return object()

    service = HistopathologyInferenceService.__new__(HistopathologyInferenceService)
    service.torch = TorchStub()
    service.extractor = ExtractorStub()
    service.head = lambda _features: Logits()
    service.temperature = 1.5
    service.labels = {
        "0": "no_metastasico",
        "1": "metastasico",
        "2": "estroma",
    }
    service.num_classes = 3
    service.class_mapping = dict(service.labels)
    service.classifier_kind = "tri"
    service.confidence_threshold = 0.9
    service.tumor_operating_threshold = 0.35
    service.calibration_method = "temperature_scaling"
    service.checkpoint_temperature = 1.5
    service.use_checkpoint_calibration = True

    result = service.predict_patch(object())

    assert result["predicted_class"] == "metastasico"
    assert result["calibration"] == {
        "method": "temperature_scaling",
        "temperature": 1.5,
        "configured": True,
        "checkpoint_temperature": 1.5,
        "checkpoint_calibration_enabled": True,
    }
