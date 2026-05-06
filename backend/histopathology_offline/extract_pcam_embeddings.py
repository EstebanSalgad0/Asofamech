import argparse
import os
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from conch.open_clip_custom import create_model_from_pretrained

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
    return parser.parse_args()


@torch.inference_mode()
def extract_split(model, dataloader, device):
    features = []
    labels = []

    for images, targets in dataloader:
        images = images.to(device)
        embeddings = model.encode_image(
            images,
            proj_contrast=False,
            normalize=False,
        )
        features.append(embeddings.cpu())
        labels.append(targets.long().cpu())

    return torch.cat(features), torch.cat(labels)


def main():
    args = parse_args()
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

    for split in ("train", "val", "test"):
        dataset = PCamDatasetAdapter(
            root=args.pcam_root,
            split=split,
            transform=preprocess,
            source=args.source,
            download=args.download,
        )
        loader = DataLoader(
            dataset,
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=args.num_workers,
            pin_memory=torch.cuda.is_available(),
        )

        x, y = extract_split(model, loader, device)
        torch.save({"x": x, "y": y}, output_dir / f"pcam_{split}_embeddings.pt")
        dataset.close()
        print(f"[histopathology] Saved {split}: {x.shape[0]} embeddings")


if __name__ == "__main__":
    main()

