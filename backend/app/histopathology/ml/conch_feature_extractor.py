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
        tensor = self.preprocess_tensor(image)

        with self.torch.inference_mode():
            return self.model.encode_image(
                tensor,
                proj_contrast=False,
                normalize=False,
            )

    def preprocess_tensor(self, image):
        return self.preprocess(image).unsqueeze(0).to(self.device)

    def preprocess_debug_image(self, image):
        """Return a PNG-friendly visualization of CONCH preprocessing."""
        from PIL import Image

        tensor = self.preprocess(image).detach().cpu().float()
        if tensor.ndim != 3 or tensor.shape[0] != 3:
            raise ModelUnavailableError("Unexpected CONCH preprocess tensor shape")

        min_value = float(tensor.min().item())
        max_value = float(tensor.max().item())
        if min_value < 0.0 or max_value > 1.0:
            denominator = max(max_value - min_value, 1e-6)
            tensor = (tensor - min_value) / denominator

        tensor = tensor.clamp(0.0, 1.0).mul(255).byte()
        array = tensor.permute(1, 2, 0).numpy()
        return Image.fromarray(array)
