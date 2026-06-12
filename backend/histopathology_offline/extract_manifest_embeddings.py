import argparse
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from histopathology_offline.manifest_dataset import ManifestPatchDataset
from histopathology_offline.histology_augmentations import (
    AUGMENTATION_CONFIG,
    AugmentedManifestPatchDataset,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Extract frozen CONCH embeddings from a patch manifest.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", default="artifacts/histopathology/embeddings-hard-negative")
    parser.add_argument("--checkpoint-ref", default=os.getenv("HISTO_CONCH_CHECKPOINT_REF", "hf_hub:MahmoodLab/conch"))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--splits", default="train,val,test")
    parser.add_argument("--log-every", type=int, default=25)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument(
        "--augmentation-preset",
        default="none",
        choices=["none", "histo_moderate"],
        help="Augment only the training split; validation and test remain deterministic.",
    )
    parser.add_argument(
        "--augmented-train-views",
        type=int,
        default=3,
        help="Additional deterministic augmented views per training patch.",
    )
    parser.add_argument("--seed", type=int, default=20260607)
    return parser.parse_args()


def load_runtime_dependencies():
    try:
        import torch
        from torch.utils.data import DataLoader
        from conch.open_clip_custom import create_model_from_pretrained
    except ImportError as exc:
        raise SystemExit(
            "PyTorch and CONCH are required. Install backend/requirements-histopathology.txt first."
        ) from exc
    return torch, DataLoader, create_model_from_pretrained


def parse_splits(value: str) -> list[str]:
    splits = [split.strip() for split in value.split(",") if split.strip()]
    if not splits:
        raise SystemExit("At least one split is required")
    return splits


def collate_manifest_batch(batch):
    images, labels, rows = zip(*batch)
    return list(images), list(labels), list(rows)


def format_duration(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{seconds:02d}s"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def extract_split(torch, model, loader, device: str, split: str, log_every: int):
    features = []
    labels = []
    records = []
    processed = 0
    started_at = time.monotonic()
    total_batches = len(loader)
    total_samples = len(loader.dataset)

    with torch.inference_mode():
        for batch_index, (images, batch_labels, batch_rows) in enumerate(loader, start=1):
            image_tensor = torch.stack(images).to(device)
            embeddings = model.encode_image(
                image_tensor,
                proj_contrast=False,
                normalize=False,
            )
            features.append(embeddings.cpu())
            labels.append(torch.tensor(batch_labels, dtype=torch.long))
            records.extend(
                [row if isinstance(row, dict) else row.to_dict() for row in batch_rows]
            )
            processed += len(batch_labels)

            if log_every > 0 and (batch_index == 1 or batch_index % log_every == 0 or batch_index == total_batches):
                elapsed = max(time.monotonic() - started_at, 1e-9)
                rate = processed / elapsed
                eta = max(total_samples - processed, 0) / rate if rate > 0 else 0
                print(
                    "[histopathology] "
                    f"split={split} batch={batch_index}/{total_batches} "
                    f"samples={processed}/{total_samples} "
                    f"rate={rate:.1f} samples/s "
                    f"elapsed={format_duration(elapsed)} eta={format_duration(eta)}",
                    flush=True,
                )

    if not features:
        return None
    return torch.cat(features), torch.cat(labels), records


def main():
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be greater than zero")
    if args.log_every < 0:
        raise SystemExit("--log-every must be zero or greater")
    if args.augmented_train_views < 0:
        raise SystemExit("--augmented-train-views must be zero or greater")

    torch, DataLoader, create_model_from_pretrained = load_runtime_dependencies()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    hf_token = os.getenv("HF_TOKEN") or os.getenv("HISTO_HF_TOKEN")
    kwargs = {}
    if hf_token:
        kwargs["hf_auth_token"] = hf_token

    model, preprocess = create_model_from_pretrained(
        "conch_ViT-B-16",
        args.checkpoint_ref,
        **kwargs,
    )
    model.to(device)
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad = False

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for split in parse_splits(args.splits):
        output_path = output_dir / f"manifest_{split}_embeddings.pt"
        if args.skip_existing and output_path.exists():
            print(f"[histopathology] Skipping {split}: {output_path} already exists", flush=True)
            continue

        if args.augmentation_preset == "histo_moderate" and split == "train":
            dataset = AugmentedManifestPatchDataset(
                torch,
                args.manifest,
                split=split,
                preprocess=preprocess,
                augmented_views=args.augmented_train_views,
                seed=args.seed,
            )
        else:
            dataset = ManifestPatchDataset(args.manifest, split=split, transform=preprocess)
        if len(dataset) == 0:
            print(f"[histopathology] split={split} has no rows; skipping", flush=True)
            continue

        loader = DataLoader(
            dataset,
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=args.num_workers,
            collate_fn=collate_manifest_batch,
            pin_memory=torch.cuda.is_available(),
        )
        result = extract_split(torch, model, loader, device, split, args.log_every)
        if result is None:
            continue

        x, y, records = result
        torch.save(
            {
                "x": x,
                "y": y,
                "records": records,
                "metadata": {
                    "split": split,
                    "sample_count": int(x.shape[0]),
                    "feature_dim": int(x.shape[1]),
                    "checkpoint_ref": args.checkpoint_ref,
                    "manifest": str(args.manifest),
                    "preprocess": "CONCH default image preprocess",
                    "augmentation_preset": (
                        args.augmentation_preset if split == "train" else "none"
                    ),
                    "augmented_train_views": (
                        args.augmented_train_views
                        if split == "train" and args.augmentation_preset != "none"
                        else 0
                    ),
                    "augmentation_config": (
                        AUGMENTATION_CONFIG
                        if split == "train" and args.augmentation_preset == "histo_moderate"
                        else None
                    ),
                    "seed": args.seed,
                },
            },
            output_path,
        )
        print(f"[histopathology] saved {split}: {x.shape[0]} embeddings -> {output_path}", flush=True)


if __name__ == "__main__":
    main()
