import os
from functools import lru_cache
from pathlib import Path

from .classifier_head import BinaryClassifierHead
from .conch_feature_extractor import ConchConfig, ConchFeatureExtractor, ModelUnavailableError


DEFAULT_LABELS = {
    "0": "no_metastasico",
    "1": "metastasico",
}


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
        self.labels = checkpoint.get("labels", DEFAULT_LABELS)
        self.head = BinaryClassifierHead(feature_dim).to(self.device)
        self.head.load_state_dict(checkpoint["state_dict"])
        self.head.eval()

    def predict_patch(self, patch_rgb):
        features = self.extractor.encode_pil(patch_rgb)

        with self.torch.inference_mode():
            logits = self.head(features)
            probabilities = self.torch.softmax(logits, dim=1)[0]

        predicted_index = int(self.torch.argmax(probabilities).item())
        predicted_class = self.labels[str(predicted_index)]
        confidence = float(probabilities[predicted_index].item())

        return {
            "predicted_class": predicted_class,
            "confidence": confidence,
            "probabilities": {
                self.labels["0"]: float(probabilities[0].item()),
                self.labels["1"]: float(probabilities[1].item()),
            },
        }


@lru_cache(maxsize=1)
def get_inference_service() -> HistopathologyInferenceService:
    return HistopathologyInferenceService()

