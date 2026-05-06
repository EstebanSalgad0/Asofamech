from dataclasses import dataclass
from typing import Optional


class ModelUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class ConchConfig:
    checkpoint_ref: str
    hf_auth_token: Optional[str] = None
    device: str = "cpu"


class ConchFeatureExtractor:
    """Frozen CONCH vision encoder used only for feature extraction."""

    def __init__(self, config: ConchConfig):
        try:
            import torch
            from conch.open_clip_custom import create_model_from_pretrained
        except ImportError as exc:
            raise ModelUnavailableError(
                "PyTorch and CONCH are required for histopathology inference"
            ) from exc

        self.torch = torch
        self.device = config.device

        kwargs = {}
        if config.hf_auth_token:
            kwargs["hf_auth_token"] = config.hf_auth_token

        try:
            self.model, self.preprocess = create_model_from_pretrained(
                "conch_ViT-B-16",
                config.checkpoint_ref,
                **kwargs,
            )
        except Exception as exc:
            raise ModelUnavailableError(f"Could not load CONCH checkpoint: {exc}") from exc

        self.model.to(self.device)
        self.model.eval()

        for parameter in self.model.parameters():
            parameter.requires_grad = False

    def encode_pil(self, image):
        tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        with self.torch.inference_mode():
            return self.model.encode_image(
                tensor,
                proj_contrast=False,
                normalize=False,
            )

