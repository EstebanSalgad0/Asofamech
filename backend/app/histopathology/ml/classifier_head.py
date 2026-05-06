try:
    import torch
    import torch.nn as nn
except ImportError:  # pragma: no cover - handled at runtime by the inference service
    torch = None
    nn = None


class BinaryClassifierHead(nn.Module if nn is not None else object):
    """Linear probe trained over frozen CONCH image embeddings."""

    def __init__(self, feature_dim: int):
        if nn is None:
            raise RuntimeError("PyTorch is required to instantiate BinaryClassifierHead")

        super().__init__()
        self.classifier = nn.Linear(feature_dim, 2)

    def forward(self, features):
        return self.classifier(features)

