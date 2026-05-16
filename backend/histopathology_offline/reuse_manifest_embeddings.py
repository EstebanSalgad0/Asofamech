import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from histopathology_offline.manifest_dataset import PatchManifestRow, read_manifest


DEFAULT_SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class IndexedEmbedding:
    vector: Any
    source_label: int
    record: dict[str, Any]


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Build aligned embedding files for a target manifest by reusing embeddings "
            "already extracted from the same patch image coordinates."
        )
    )
    parser.add_argument("--source-embeddings-dir", required=True)
    parser.add_argument("--target-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-splits", default="train,val,test")
    parser.add_argument("--target-splits", default="train,val,test")
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def load_runtime_dependencies():
    try:
        import torch
    except ImportError as exc:
        raise SystemExit("PyTorch is required to reuse saved embedding tensors.") from exc
    return torch


def parse_splits(value: str) -> list[str]:
    splits = [split.strip() for split in value.split(",") if split.strip()]
    if not splits:
        raise SystemExit("At least one split is required.")
    return splits


def normalize_path(path: str) -> str:
    return str(path or "").replace("\\", "/")


def row_identity_key(row: PatchManifestRow | dict[str, Any]) -> tuple[str, str, int, int, int, int]:
    if isinstance(row, PatchManifestRow):
        slide_id = row.slide_id
        path = row.path
        x = row.x
        y = row.y
        width = row.width
        height = row.height
    else:
        slide_id = str(row.get("slide_id", ""))
        path = str(row.get("path", ""))
        x = int(float(row.get("x", 0)))
        y = int(float(row.get("y", 0)))
        width = int(float(row.get("width", 0)))
        height = int(float(row.get("height", 0)))
    return (slide_id, normalize_path(path), int(x), int(y), int(width), int(height))


def build_embedding_index(torch, source_embeddings_dir: Path, source_splits: list[str]) -> dict:
    index = {}
    duplicates = 0
    for split in source_splits:
        path = source_embeddings_dir / f"manifest_{split}_embeddings.pt"
        if not path.exists():
            raise FileNotFoundError(f"Missing source embeddings file: {path}")
        payload = torch.load(path, map_location="cpu")
        features = payload["x"]
        labels = payload.get("y")
        records = payload["records"]
        if len(features) != len(records):
            raise SystemExit(f"{path}: {len(features)} embeddings vs {len(records)} records.")
        for position, record in enumerate(records):
            key = row_identity_key(record)
            if key in index:
                duplicates += 1
                continue
            source_label = int(labels[position].item()) if labels is not None else int(record.get("label", 0))
            index[key] = IndexedEmbedding(
                vector=features[position].detach().cpu(),
                source_label=source_label,
                record=record,
            )
    index["_metadata"] = {"duplicates_skipped": duplicates}
    return index


def materialize_split(torch, rows: list[PatchManifestRow], embedding_index: dict, split: str) -> dict:
    features = []
    labels = []
    records = []
    missing = []

    for row in rows:
        key = row_identity_key(row)
        found = embedding_index.get(key)
        if found is None:
            missing.append(row.to_dict())
            continue
        features.append(found.vector.clone())
        labels.append(int(row.label))
        records.append(row.to_dict())

    if missing:
        preview = ", ".join(
            f"{row['slide_id']}@{row['x']},{row['y']}" for row in missing[:5]
        )
        raise SystemExit(
            f"Could not reuse embeddings for {len(missing)} rows in split '{split}'. "
            f"First missing rows: {preview}"
        )

    if features:
        x = torch.stack(features)
    else:
        x = torch.empty((0, 0))
    y = torch.tensor(labels, dtype=torch.long)
    return {
        "x": x,
        "y": y,
        "records": records,
        "metadata": {
            "split": split,
            "sample_count": len(records),
            "feature_dim": int(x.shape[1]) if len(features) else 0,
            "source": "reused_existing_manifest_embeddings",
        },
    }


def write_aligned_embeddings(
    torch,
    target_manifest: Path,
    source_embeddings_dir: Path,
    output_dir: Path,
    source_splits: list[str],
    target_splits: list[str],
    skip_existing: bool,
) -> dict:
    all_rows = read_manifest(target_manifest)
    embedding_index = build_embedding_index(torch, source_embeddings_dir, source_splits)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "target_manifest": str(target_manifest),
        "source_embeddings_dir": str(source_embeddings_dir),
        "output_dir": str(output_dir),
        "source_splits": source_splits,
        "target_splits": target_splits,
        "duplicates_skipped_in_source": embedding_index.get("_metadata", {}).get("duplicates_skipped", 0),
        "splits": {},
    }

    for split in target_splits:
        output_path = output_dir / f"manifest_{split}_embeddings.pt"
        if skip_existing and output_path.exists():
            summary["splits"][split] = {"status": "skipped_existing", "path": str(output_path)}
            continue
        split_rows = [row for row in all_rows if row.split == split]
        if not split_rows:
            summary["splits"][split] = {"status": "no_rows", "rows": 0}
            continue
        payload = materialize_split(torch, split_rows, embedding_index, split)
        payload["metadata"].update(
            {
                "target_manifest": str(target_manifest),
                "source_embeddings_dir": str(source_embeddings_dir),
            }
        )
        torch.save(payload, output_path)
        summary["splits"][split] = {
            "status": "written",
            "rows": len(split_rows),
            "path": str(output_path),
            "feature_dim": payload["metadata"]["feature_dim"],
        }
    return summary


def main():
    args = parse_args()
    torch = load_runtime_dependencies()
    summary = write_aligned_embeddings(
        torch=torch,
        target_manifest=Path(args.target_manifest),
        source_embeddings_dir=Path(args.source_embeddings_dir),
        output_dir=Path(args.output_dir),
        source_splits=parse_splits(args.source_splits),
        target_splits=parse_splits(args.target_splits),
        skip_existing=args.skip_existing,
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
