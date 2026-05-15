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


class TriClassifierHead(nn.Module if nn is not None else object):
    """3-class linear probe over frozen CONCH embeddings."""

    def __init__(self, feature_dim: int):
        if nn is None:
            raise RuntimeError("PyTorch is required to instantiate TriClassifierHead")

        super().__init__()
        self.classifier = nn.Linear(feature_dim, 3)

    def forward(self, features):
        return self.classifier(features)


class TriMLPClassifierHead(nn.Module if nn is not None else object):
    """Small non-linear 3-class head over frozen CONCH embeddings."""

    def __init__(self, feature_dim: int, hidden_dim: int = 128, dropout: float = 0.20):
        if nn is None:
            raise RuntimeError("PyTorch is required to instantiate TriMLPClassifierHead")

        super().__init__()
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 3),
        )

    def forward(self, features):
        return self.classifier(features)
