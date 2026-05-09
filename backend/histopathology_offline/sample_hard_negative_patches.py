import argparse
import csv
import hashlib
import random
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.histopathology.roi_quality import evaluate_roi_quality
from histopathology_offline.manifest_dataset import PatchManifestRow, write_manifest


@dataclass(frozen=True)
class SlideTarget:
    slide_id: str
    label: int
    path: Path


@dataclass(frozen=True)
class Annotation:
    slide_id: str
    label: int
    x: int
    y: int
    width: int
    height: int


class SlideReader:
    def __init__(self, path: Path):
        self.path = path
        self._slide = None
        self._image = None
        self.backend = "pil"

        try:
            import openslide

            self._slide = openslide.OpenSlide(str(path))
            self.backend = "openslide"
            return
        except Exception:
            pass

        from PIL import Image

        Image.MAX_IMAGE_PIXELS = None
        self._image = Image.open(path)

    @property
    def dimensions(self) -> tuple[int, int]:
        if self._slide is not None:
            return self._slide.dimensions
        return self._image.size

    def read_patch(self, x: int, y: int, width: int, height: int):
        if self._slide is not None:
            return self._slide.read_region((x, y), 0, (width, height)).convert("RGB")
        return self._image.crop((x, y, x + width, y + height)).convert("RGB")

    def close(self) -> None:
        if self._slide is not None:
            self._slide.close()
        if self._image is not None:
            self._image.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Sample histopathology patches and create a hard-negative manifest."
    )
    parser.add_argument("--slides-dir", required=True)
    parser.add_argument("--targets-csv", required=True)
    parser.add_argument("--annotations-csv")
    parser.add_argument("--output-dir", default="artifacts/histopathology/hard_negative_patches")
    parser.add_argument("--manifest", default="artifacts/histopathology/manifests/hard_negative_manifest.csv")
    parser.add_argument("--source", default="sln_breast")
    parser.add_argument(
        "--slide-ids",
        default="",
        help="Optional comma-separated slide IDs to process.",
    )
    parser.add_argument("--patch-size", type=int, default=256)
    parser.add_argument("--negative-per-slide", type=int, default=48)
    parser.add_argument("--positive-per-slide", type=int, default=48)
    parser.add_argument("--max-attempts-per-patch", type=int, default=40)
    parser.add_argument(
        "--preferred-negative-types",
        default="",
        help=(
            "Comma-separated hard negative types to keep before generic negatives, "
            "for example: stroma,background_or_adipose,low_cellularity."
        ),
    )
    parser.add_argument(
        "--stroma-fraction-threshold",
        type=float,
        default=0.45,
        help="Minimum stroma-like tissue fraction used to label a negative as stroma. Default: 0.45.",
    )
    parser.add_argument(
        "--allow-non-evaluable-negatives",
        action="store_true",
        help="Keep non-evaluable negative patches as hard negatives instead of skipping them.",
    )
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument(
        "--allow-weak-positive",
        action="store_true",
        help="Sample random patches from positive slides when no tumor annotation exists.",
    )
    return parser.parse_args()


def load_targets(slides_dir: Path, targets_csv: Path) -> list[SlideTarget]:
    targets = []
    with targets_csv.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            slide_id = row["slide"]
            path = slides_dir / slide_id
            if not path.exists():
                matches = sorted(slides_dir.glob(f"*{slide_id}"))
                path = matches[0] if matches else path
            if path.exists():
                targets.append(SlideTarget(slide_id=slide_id, label=int(row["target"]), path=path))
    return targets


def load_annotations(path: str | None) -> dict[str, list[Annotation]]:
    if not path:
        return {}

    annotations: dict[str, list[Annotation]] = {}
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            slide_id = row["slide_id"]
            annotation = Annotation(
                slide_id=slide_id,
                label=int(row["label"]),
                x=int(float(row["x"])),
                y=int(float(row["y"])),
                width=int(float(row["width"])),
                height=int(float(row["height"])),
            )
            annotations.setdefault(slide_id, []).append(annotation)
    return annotations


def split_for_slide(slide_id: str, train_ratio: float, val_ratio: float, seed: int) -> str:
    digest = hashlib.sha1(f"{seed}:{slide_id}".encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    if value < train_ratio:
        return "train"
    if value < train_ratio + val_ratio:
        return "val"
    return "test"


def classify_negative_type(qc: dict, stroma_fraction_threshold: float = 0.45) -> str:
    metrics = qc["metrics"]
    checks = qc["checks"]
    if not checks["white_fraction_ok"]:
        return "background_or_adipose"
    if not checks["tissue_fraction_ok"]:
        return "low_tissue"
    if not checks["stroma_fraction_ok"]:
        return "stroma_low_cellularity"
    if metrics["stroma_fraction"] >= stroma_fraction_threshold:
        if not checks["nuclear_fraction_ok"]:
            return "stroma_low_cellularity"
        return "stroma"
    if not checks["nuclear_fraction_ok"]:
        return "low_cellularity"
    return "lymphoid_or_mixed_negative"


def parse_preferred_negative_types(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def parse_slide_ids(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def format_metric(value: float) -> str:
    return f"{value:.6f}"


def save_manifest_row(
    rows: list[PatchManifestRow],
    patch,
    patch_dir: Path,
    source: str,
    slide: SlideTarget,
    label: int,
    x: int,
    y: int,
    width: int,
    height: int,
    split: str,
    qc: dict,
    hard_negative_type: str,
    annotation_status: str,
) -> None:
    patch_index = len(rows)
    patch_id = f"{Path(slide.slide_id).stem}_{x}_{y}_{width}x{height}_{patch_index:06d}"
    patch_path = patch_dir / split / str(label) / f"{patch_id}.png"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch.save(patch_path)
    metrics = qc["metrics"]

    rows.append(
        PatchManifestRow(
            patch_id=patch_id,
            source=source,
            slide_id=slide.slide_id,
            path=str(patch_path),
            label=label,
            hard_negative_type=hard_negative_type,
            x=x,
            y=y,
            width=width,
            height=height,
            split=split,
            qc_status=qc["status"],
            qc_tissue_fraction=format_metric(metrics["tissue_fraction"]),
            qc_nuclear_fraction=format_metric(metrics["nuclear_fraction"]),
            qc_white_fraction=format_metric(metrics["white_fraction"]),
            qc_stroma_fraction=format_metric(metrics["stroma_fraction"]),
            annotation_status=annotation_status,
        )
    )


def sample_random_patch(reader: SlideReader, patch_size: int, rng: random.Random):
    width, height = reader.dimensions
    if width < patch_size or height < patch_size:
        return None

    x = rng.randint(0, width - patch_size)
    y = rng.randint(0, height - patch_size)
    return x, y, patch_size, patch_size, reader.read_patch(x, y, patch_size, patch_size)


def sample_annotation_patch(reader: SlideReader, annotation: Annotation, patch_size: int, rng: random.Random):
    slide_width, slide_height = reader.dimensions
    max_x = min(annotation.x + max(annotation.width - patch_size, 0), slide_width - patch_size)
    max_y = min(annotation.y + max(annotation.height - patch_size, 0), slide_height - patch_size)
    min_x = max(0, min(annotation.x, max_x))
    min_y = max(0, min(annotation.y, max_y))
    if max_x < min_x or max_y < min_y:
        return None

    x = rng.randint(min_x, max_x)
    y = rng.randint(min_y, max_y)
    return x, y, patch_size, patch_size, reader.read_patch(x, y, patch_size, patch_size)


def main():
    args = parse_args()
    if args.patch_size < 1:
        raise SystemExit("--patch-size must be greater than zero")
    if args.stroma_fraction_threshold < 0.0 or args.stroma_fraction_threshold > 1.0:
        raise SystemExit("--stroma-fraction-threshold must be between 0 and 1")
    if args.negative_per_slide < 0 or args.positive_per_slide < 0:
        raise SystemExit("Patch counts must be zero or greater")
    if args.train_ratio <= 0 or args.val_ratio < 0 or args.train_ratio + args.val_ratio >= 1:
        raise SystemExit("Ratios must leave a non-empty test split")

    slides_dir = Path(args.slides_dir)
    targets = load_targets(slides_dir, Path(args.targets_csv))
    requested_slide_ids = parse_slide_ids(args.slide_ids)
    if requested_slide_ids:
        targets = [slide for slide in targets if slide.slide_id in requested_slide_ids]

    annotations = load_annotations(args.annotations_csv)
    rng = random.Random(args.seed)
    rows: list[PatchManifestRow] = []
    output_dir = Path(args.output_dir)
    preferred_negative_types = parse_preferred_negative_types(args.preferred_negative_types)

    for slide in targets:
        split = split_for_slide(slide.slide_id, args.train_ratio, args.val_ratio, args.seed)
        reader = SlideReader(slide.path)
        try:
            slide_annotations = annotations.get(slide.slide_id, [])
            requested = args.positive_per_slide if slide.label == 1 else args.negative_per_slide
            if requested == 0:
                continue

            saved = 0
            attempts = 0
            max_attempts = max(1, requested * args.max_attempts_per_patch)
            while saved < requested and attempts < max_attempts:
                attempts += 1
                annotation_status = "none"
                candidate = None
                label = slide.label

                if slide.label == 1 and slide_annotations:
                    annotation = rng.choice([item for item in slide_annotations if item.label == 1] or slide_annotations)
                    candidate = sample_annotation_patch(reader, annotation, args.patch_size, rng)
                    annotation_status = "annotated_positive"
                    label = annotation.label
                elif slide.label == 1 and not args.allow_weak_positive:
                    break
                else:
                    candidate = sample_random_patch(reader, args.patch_size, rng)
                    if slide.label == 1:
                        annotation_status = "weak_positive_slide_label"

                if candidate is None:
                    continue

                x, y, width, height, patch = candidate
                qc = evaluate_roi_quality(patch)
                hard_negative_type = ""
                if label == 0:
                    hard_negative_type = classify_negative_type(
                        qc,
                        stroma_fraction_threshold=args.stroma_fraction_threshold,
                    )
                    if qc["status"] != "evaluable" and not args.allow_non_evaluable_negatives:
                        continue
                    if preferred_negative_types and hard_negative_type not in preferred_negative_types:
                        continue

                save_manifest_row(
                    rows=rows,
                    patch=patch,
                    patch_dir=output_dir,
                    source=args.source,
                    slide=slide,
                    label=label,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    split=split,
                    qc=qc,
                    hard_negative_type=hard_negative_type,
                    annotation_status=annotation_status,
                )
                saved += 1

            print(
                "[histopathology] "
                f"slide={slide.slide_id} label={slide.label} split={split} "
                f"saved={saved}/{requested} attempts={attempts}",
                flush=True,
            )
        finally:
            reader.close()

    write_manifest(args.manifest, rows)
    print(f"[histopathology] saved manifest rows={len(rows)} -> {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
