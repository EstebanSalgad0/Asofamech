import argparse
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from histopathology_offline.pcam_dataset import PCamDatasetAdapter


def parse_args():
    parser = argparse.ArgumentParser(description="Extract frozen CONCH embeddings from PCam.")
    parser.add_argument("--pcam-root", required=True)
    parser.add_argument("--output-dir", default="artifacts/histopathology/embeddings")
    parser.add_argument("--checkpoint-ref", default=os.getenv("HISTO_CONCH_CHECKPOINT_REF", "hf_hub:MahmoodLab/conch"))
    parser.add_argument("--source", default="auto", choices=["auto", "torchvision", "hdf5"])
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--download", action="store_true")
    parser.add_argument(
        "--splits",
        default="train,val,test",
        help="Comma-separated PCam splits to extract. Default: train,val,test.",
    )
    parser.add_argument(
        "--limit-per-split",
        type=int,
        help="Optional sample cap per split for smoke runs.",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=50,
        help="Print extraction progress every N batches. Default: 50.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip a split when its output embeddings file already exists.",
    )
    return parser.parse_args()


def load_runtime_dependencies():
    try:
        import torch
        from torch.utils.data import DataLoader, Subset
        from conch.open_clip_custom import create_model_from_pretrained
    except ImportError as exc:
        raise SystemExit(
            "PyTorch, torchvision and CONCH are required. "
            "Install backend/requirements-histopathology.txt first."
        ) from exc

    return torch, DataLoader, Subset, create_model_from_pretrained


def parse_splits(value: str) -> list[str]:
    splits = [split.strip() for split in value.split(",") if split.strip()]
    valid = {"train", "val", "test"}
    invalid = [split for split in splits if split not in valid]
    if invalid:
        raise SystemExit(f"Invalid PCam split(s): {', '.join(invalid)}")
    if not splits:
        raise SystemExit("At least one PCam split is required")
    return splits


def extract_split(torch, model, dataloader, device, split: str, log_every: int):
    features = []
    labels = []
    total_batches = len(dataloader)
    total_samples = len(dataloader.dataset)
    processed_samples = 0
    started_at = time.monotonic()

    with torch.inference_mode():
        for batch_index, (images, targets) in enumerate(dataloader, start=1):
            images = images.to(device)
            embeddings = model.encode_image(
                images,
                proj_contrast=False,
                normalize=False,
            )
            features.append(embeddings.cpu())
            labels.append(targets.long().cpu())
            processed_samples += int(images.size(0))

            if log_every > 0 and (batch_index == 1 or batch_index % log_every == 0 or batch_index == total_batches):
                elapsed = max(time.monotonic() - started_at, 1e-9)
                samples_per_second = processed_samples / elapsed
                remaining_samples = max(total_samples - processed_samples, 0)
                eta_seconds = remaining_samples / samples_per_second if samples_per_second > 0 else 0
                print(
                    "[histopathology] "
                    f"split={split} batch={batch_index}/{total_batches} "
                    f"samples={processed_samples}/{total_samples} "
                    f"rate={samples_per_second:.1f} samples/s "
                    f"elapsed={format_duration(elapsed)} "
                    f"eta={format_duration(eta_seconds)}",
                    flush=True,
                )

    return torch.cat(features), torch.cat(labels)


def format_duration(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{seconds:02d}s"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def main():
    args = parse_args()
    if args.limit_per_split is not None and args.limit_per_split < 1:
        raise SystemExit("--limit-per-split must be greater than zero")
    if args.log_every < 0:
        raise SystemExit("--log-every must be zero or greater")

    torch, DataLoader, Subset, create_model_from_pretrained = load_runtime_dependencies()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    hf_token = os.getenv("HF_TOKEN") or os.getenv("HISTO_HF_TOKEN")
    splits = parse_splits(args.splits)

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

    for split in splits:
        output_path = output_dir / f"pcam_{split}_embeddings.pt"
        if args.skip_existing and output_path.exists():
            print(f"[histopathology] Skipping {split}: {output_path} already exists", flush=True)
            continue

        dataset = PCamDatasetAdapter(
            root=args.pcam_root,
            split=split,
            transform=preprocess,
            source=args.source,
            download=args.download,
        )
        loader_dataset = dataset
        if args.limit_per_split is not None:
            sample_count = min(len(dataset), args.limit_per_split)
            loader_dataset = Subset(dataset, range(sample_count))

        loader = DataLoader(
            loader_dataset,
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=args.num_workers,
            pin_memory=torch.cuda.is_available(),
        )

        x, y = extract_split(
            torch=torch,
            model=model,
            dataloader=loader,
            device=device,
            split=split,
            log_every=args.log_every,
        )
        torch.save(
            {
                "x": x,
                "y": y,
                "metadata": {
                    "split": split,
                    "sample_count": int(x.shape[0]),
                    "feature_dim": int(x.shape[1]),
                    "checkpoint_ref": args.checkpoint_ref,
                    "source_requested": args.source,
                    "source_used": dataset.source_used,
                    "preprocess": "CONCH default image preprocess",
                },
            },
            output_path,
        )
        dataset.close()
        print(f"[histopathology] Saved {split}: {x.shape[0]} embeddings -> {output_path}", flush=True)


if __name__ == "__main__":
    main()
