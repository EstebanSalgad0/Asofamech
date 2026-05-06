import argparse
import json
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from app.histopathology.ml.classifier_head import BinaryClassifierHead


def parse_args():
    parser = argparse.ArgumentParser(description="Train a binary classifier head over CONCH PCam embeddings.")
    parser.add_argument("--embeddings-dir", default="artifacts/histopathology/embeddings")
    parser.add_argument("--output", default="artifacts/histopathology/checkpoints/binary_head_pcam.pt")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    return parser.parse_args()


def load_split(path: Path):
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


@torch.inference_mode()
def validation_loss(head, loader, criterion, device):
    head.eval()
    total_loss = 0.0

    for features, labels in loader:
        features = features.to(device)
        labels = labels.to(device)
        logits = head(features)
        loss = criterion(logits, labels)
        total_loss += loss.item() * features.size(0)

    return total_loss / len(loader.dataset)


def main():
    args = parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    embeddings_dir = Path(args.embeddings_dir)

    train_x, train_y = load_split(embeddings_dir / "pcam_train_embeddings.pt")
    val_x, val_y = load_split(embeddings_dir / "pcam_val_embeddings.pt")

    train_loader = DataLoader(
        TensorDataset(train_x, train_y),
        batch_size=args.batch_size,
        shuffle=True,
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
    history = []

    for epoch in range(1, args.epochs + 1):
        train_loss = run_epoch(head, train_loader, optimizer, criterion, device)
        val_loss = validation_loss(head, val_loader, criterion, device)
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
        print(f"[histopathology] epoch={epoch} train_loss={train_loss:.4f} val_loss={val_loss:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {key: value.cpu() for key, value in head.state_dict().items()}

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    torch.save(
        {
            "state_dict": best_state,
            "feature_dim": int(train_x.shape[1]),
            "labels": {"0": "no_metastasico", "1": "metastasico"},
            "training_mode": "frozen_conch_linear_probe",
        },
        output,
    )

    metrics_path = output.with_suffix(".training.json")
    metrics_path.write_text(json.dumps({"history": history, "best_val_loss": best_val_loss}, indent=2))
    print(f"[histopathology] saved classifier head: {output}")


if __name__ == "__main__":
    main()

