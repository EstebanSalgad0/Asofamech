import os
import unittest
from unittest.mock import patch

from app.routers.histopathology import (
    LOW_SUSPICION_CLASS,
    LOW_SUSPICION_STATUS,
    _decision_from_prediction,
)


def prediction(predicted_class, probabilities):
    return {
        "predicted_class": predicted_class,
        "model_predicted_class": predicted_class,
        "confidence": max(probabilities.values()),
        "probabilities": probabilities,
    }


class HistopathologyDecisionTestCase(unittest.TestCase):
    def setUp(self):
        self.env_patch = patch.dict(
            os.environ,
            {
                "HISTO_LOW_SUSPICION_NO_METASTATIC_MIN": "0.55",
                "HISTO_LOW_SUSPICION_TUMOR_MAX": "0.25",
            },
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    def test_low_suspicion_non_metastatic_is_not_forced_to_uncertain(self):
        raw = prediction(
            "no_metastasico",
            {
                "no_metastasico": 0.69,
                "metastasico": 0.05,
                "estroma": 0.26,
            },
        )

        decision = _decision_from_prediction(raw, confidence_threshold=0.90)

        self.assertEqual(decision["status"], LOW_SUSPICION_STATUS)
        self.assertEqual(decision["predicted_class"], LOW_SUSPICION_CLASS)
        self.assertEqual(decision["prediction"]["model_predicted_class"], "no_metastasico")

    def test_high_tumor_uncertain_stays_uncertain(self):
        raw = prediction(
            "metastasico",
            {
                "no_metastasico": 0.38,
                "metastasico": 0.53,
                "estroma": 0.09,
            },
        )

        decision = _decision_from_prediction(raw, confidence_threshold=0.90)

        self.assertEqual(decision["status"], "resultado_incierto")
        self.assertEqual(decision["predicted_class"], "incierto")

    def test_confident_non_metastatic_remains_classified(self):
        raw = prediction(
            "no_metastasico",
            {
                "no_metastasico": 0.94,
                "metastasico": 0.03,
                "estroma": 0.03,
            },
        )

        decision = _decision_from_prediction(raw, confidence_threshold=0.90)

        self.assertEqual(decision["status"], "clasificado")
        self.assertEqual(decision["predicted_class"], "no_metastasico")

    def test_low_tumor_stroma_counts_as_low_suspicion_non_metastatic(self):
        raw = prediction(
            "estroma",
            {
                "no_metastasico": 0.10,
                "metastasico": 0.05,
                "estroma": 0.85,
            },
        )

        decision = _decision_from_prediction(raw, confidence_threshold=0.90)

        self.assertEqual(decision["status"], LOW_SUSPICION_STATUS)
        self.assertEqual(decision["predicted_class"], LOW_SUSPICION_CLASS)
        self.assertEqual(decision["prediction"]["model_predicted_class"], "estroma")

    def test_stroma_with_non_low_tumor_score_remains_not_evaluable(self):
        raw = prediction(
            "estroma",
            {
                "no_metastasico": 0.10,
                "metastasico": 0.30,
                "estroma": 0.60,
            },
        )

        decision = _decision_from_prediction(raw, confidence_threshold=0.90)

        self.assertEqual(decision["status"], "roi_no_evaluable")
        self.assertEqual(decision["predicted_class"], "roi_no_evaluable")


if __name__ == "__main__":
    unittest.main()
