import os
from functools import lru_cache
from pathlib import Path

from .classifier_head import BinaryClassifierHead
from .conch_feature_extractor import ConchConfig, ConchFeatureExtractor, ModelUnavailableError


DEFAULT_LABELS = {
    "0": "no_metastasico",
    "1": "metastasico",
}


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        parsed = float(value)
    except ValueError:
        return default

    if parsed <= 0.0 or parsed > 1.0:
        return default
    return parsed


class HistopathologyInferenceService:
    def __init__(self):
        try:
            import torch
        except ImportError as exc:
            raise ModelUnavailableError("PyTorch is not installed") from exc

        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        checkpoint_ref = os.getenv("HISTO_CONCH_CHECKPOINT_REF", "hf_hub:MahmoodLab/conch")
        hf_token = os.getenv("HF_TOKEN") or os.getenv("HISTO_HF_TOKEN")
        classifier_path = os.getenv("HISTO_CLASSIFIER_CHECKPOINT")
        self.checkpoint_ref = checkpoint_ref
        self.classifier_path = classifier_path

        if not classifier_path:
            raise ModelUnavailableError("HISTO_CLASSIFIER_CHECKPOINT is not configured")

        if not Path(classifier_path).exists():
            raise ModelUnavailableError(f"Classifier checkpoint not found: {classifier_path}")

        self.extractor = ConchFeatureExtractor(
            ConchConfig(
                checkpoint_ref=checkpoint_ref,
                hf_auth_token=hf_token,
                device=self.device,
            )
        )

        checkpoint = torch.load(classifier_path, map_location=self.device)
        feature_dim = int(checkpoint["feature_dim"])
        self.feature_dim = feature_dim
        checkpoint_labels = checkpoint.get("labels", DEFAULT_LABELS)
        self.labels = {**DEFAULT_LABELS, **{str(key): str(value) for key, value in checkpoint_labels.items()}}
        self.class_mapping = {
            "0": self.labels["0"],
            "1": self.labels["1"],
        }
        self.confidence_threshold = _float_env("HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD", 0.90)
        self.training_mode = checkpoint.get("training_mode", "unknown")
        self.validation = checkpoint.get("validation")
        self.created_at = checkpoint.get("created_at")
        self.head = BinaryClassifierHead(feature_dim).to(self.device)
        self.head.load_state_dict(checkpoint["state_dict"])
        self.head.eval()

    def preprocess_debug_image(self, patch_rgb):
        return self.extractor.preprocess_debug_image(patch_rgb)

    def preprocess_debug_tensor(self, patch_rgb):
        return self.extractor.preprocess_tensor(patch_rgb).detach().cpu()

    def predict_patch(self, patch_rgb):
        features = self.extractor.encode_pil(patch_rgb)

        with self.torch.inference_mode():
            logits = self.head(features)
            probabilities = self.torch.softmax(logits, dim=1)[0]

        predicted_index = int(self.torch.argmax(probabilities).item())
        predicted_class = self.labels[str(predicted_index)]
        confidence = float(probabilities[predicted_index].item())

        return {
            "predicted_index": predicted_index,
            "predicted_class": predicted_class,
            "model_predicted_class": predicted_class,
            "confidence": confidence,
            "probabilities": {
                self.labels["0"]: float(probabilities[0].item()),
                self.labels["1"]: float(probabilities[1].item()),
            },
            "class_mapping": self.class_mapping,
            "decision_threshold": self.confidence_threshold,
        }


@lru_cache(maxsize=1)
def get_inference_service() -> HistopathologyInferenceService:
    return HistopathologyInferenceService()
