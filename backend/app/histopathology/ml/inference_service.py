import os
from functools import lru_cache
from pathlib import Path

from .classifier_head import BinaryClassifierHead, TriClassifierHead
from .conch_feature_extractor import ConchConfig, ConchFeatureExtractor, ModelUnavailableError


DEFAULT_LABELS = {
    "0": "no_metastasico",
    "1": "metastasico",
}

DEFAULT_TRI_LABELS = {
    "0": "no_metastasico",
    "1": "metastasico",
    "2": "estroma",
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
        state_dict = checkpoint["state_dict"]
        self.num_classes = int(
            checkpoint.get("num_classes")
            or state_dict["classifier.weight"].shape[0]
        )
        self.classifier_kind = "tri" if self.num_classes == 3 else "binary"
        default_labels = DEFAULT_TRI_LABELS if self.num_classes == 3 else DEFAULT_LABELS
        checkpoint_labels = checkpoint.get("labels") or checkpoint.get("class_names") or {}
        self.labels = {
            **default_labels,
            **{str(key): str(value) for key, value in checkpoint_labels.items()},
        }
        self.class_mapping = {
            str(index): self.labels[str(index)] for index in range(self.num_classes)
        }
        self.confidence_threshold = _float_env("HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD", 0.90)
        self.training_mode = checkpoint.get("training_mode", "unknown")
        self.validation = checkpoint.get("validation")
        self.created_at = checkpoint.get("created_at")
        if self.num_classes == 2:
            self.head = BinaryClassifierHead(feature_dim).to(self.device)
        elif self.num_classes == 3:
            self.head = TriClassifierHead(feature_dim).to(self.device)
        else:
            raise ModelUnavailableError(
                f"Unsupported classifier class count: {self.num_classes}"
            )
        self.head.load_state_dict(state_dict)
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
                self.labels[str(index)]: float(probabilities[index].item())
                for index in range(self.num_classes)
            },
            "class_mapping": self.class_mapping,
            "num_classes": self.num_classes,
            "classifier_kind": self.classifier_kind,
            "decision_threshold": self.confidence_threshold,
        }


@lru_cache(maxsize=1)
def get_inference_service() -> HistopathologyInferenceService:
    return HistopathologyInferenceService()
