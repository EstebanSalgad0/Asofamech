import argparse
import datetime as dt
import json
import random
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.histopathology.ml.classifier_head import BinaryClassifierHead


def parse_args():
    parser = argparse.ArgumentParser(description="Train a binary classifier head over CONCH PCam embeddings.")
    parser.add_argument("--embeddings-dir", default="artifacts/histopathology/embeddings")
    parser.add_argument("--output", default="artifacts/histopathology/checkpoints/binary_head_pcam.pt")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    return parser.parse_args()


def load_runtime_dependencies():
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as exc:
        raise SystemExit(
            "PyTorch is required. Install backend/requirements-histopathology.txt first."
        ) from exc

    return torch, nn, DataLoader, TensorDataset


def resolve_device(torch, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA was requested but torch.cuda.is_available() is false")
    return requested


def set_seed(torch, seed: int) -> None:
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_split(torch, path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Embeddings file not found: {path}")
    payload = torch.load(path, map_location="cpu")
    return payload["x"].float(), payload["y"].long()


def run_epoch(head, loader, optimizer, criterion, device):
    head.train()
    total_loss = 0.0

    for features, labels in loader:
        features = features.to(device)
        labels = labels.to(device)

        logits = head(features)
        loss = criterion(logits, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * features.size(0)

    return total_loss / len(loader.dataset)


def validation_loss(torch, head, loader, criterion, device):
    head.eval()
    total_loss = 0.0

    with torch.inference_mode():
        for features, labels in loader:
            features = features.to(device)
            labels = labels.to(device)
            logits = head(features)
            loss = criterion(logits, labels)
            total_loss += loss.item() * features.size(0)

    return total_loss / len(loader.dataset)


def main():
    args = parse_args()
    if args.epochs < 1:
        raise SystemExit("--epochs must be greater than zero")

    torch, nn, DataLoader, TensorDataset = load_runtime_dependencies()
    set_seed(torch, args.seed)
    device = resolve_device(torch, args.device)
    embeddings_dir = Path(args.embeddings_dir)

    train_path = embeddings_dir / "pcam_train_embeddings.pt"
    val_path = embeddings_dir / "pcam_val_embeddings.pt"
    train_x, train_y = load_split(torch, train_path)
    val_x, val_y = load_split(torch, val_path)
    generator = torch.Generator()
    generator.manual_seed(args.seed)

    train_loader = DataLoader(
        TensorDataset(train_x, train_y),
        batch_size=args.batch_size,
        shuffle=True,
        generator=generator,
    )
    val_loader = DataLoader(
        TensorDataset(val_x, val_y),
        batch_size=args.batch_size,
        shuffle=False,
    )

    head = BinaryClassifierHead(train_x.shape[1]).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(
        head.parameters(),
        lr=args.lr,
        weight_decay=args.weight_decay,
    )

    best_state = None
    best_val_loss = float("inf")
    best_epoch = None
    history = []

    for epoch in range(1, args.epochs + 1):
        train_loss = run_epoch(head, train_loader, optimizer, criterion, device)
        val_loss = validation_loss(torch, head, val_loader, criterion, device)
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
        print(f"[histopathology] epoch={epoch} train_loss={train_loss:.4f} val_loss={val_loss:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            best_state = {key: value.cpu() for key, value in head.state_dict().items()}

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    torch.save(
        {
            "state_dict": best_state,
            "feature_dim": int(train_x.shape[1]),
            "labels": {"0": "no_metastasico", "1": "metastasico"},
            "training_mode": "frozen_conch_linear_probe",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "validation": {
                "best_epoch": best_epoch,
                "best_val_loss": best_val_loss,
            },
            "hyperparameters": {
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "lr": args.lr,
                "weight_decay": args.weight_decay,
                "seed": args.seed,
                "device": device,
            },
            "embedding_files": {
                "train": str(train_path),
                "val": str(val_path),
            },
        },
        output,
    )

    metrics_path = output.with_suffix(".training.json")
    metrics_path.write_text(
        json.dumps(
            {
                "history": history,
                "best_epoch": best_epoch,
                "best_val_loss": best_val_loss,
            },
            indent=2,
        )
    )
    print(f"[histopathology] saved classifier head: {output}")


if __name__ == "__main__":
    main()
