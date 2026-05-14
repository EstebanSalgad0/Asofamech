from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from histopathology_offline.manifest_dataset import PatchManifestRow, write_manifest


POSITIVE_STAGES = {"itc", "micro", "macro"}
NEGATIVE_STAGES = {"negative"}
IMAGE_EXTENSIONS = {".tif", ".tiff", ".svs"}


@dataclass(frozen=True)
class TumorPolygon:
    slide_id: str
    annotation_id: str
    points: tuple[tuple[float, float], ...]
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class SlideRecord:
    slide_id: str
    path: Path
    target: int


class SlideReader:
    def __init__(self, path: Path):
        self.path = path
        self._slide = None
        self._image = None
        try:
            import openslide

            self._slide = openslide.OpenSlide(str(path))
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
        description=(
            "Build a CAMELYON17 official coordinate manifest from ASAP XML tumor "
            "annotations and negative slides."
        )
    )
    parser.add_argument("--images-dir", default="data/camelyon17/images")
    parser.add_argument("--annotations-dir", default="data/camelyon17/annotations")
    parser.add_argument("--targets-csv", default="")
    parser.add_argument(
        "--manifest",
        default="artifacts/histopathology/manifests/camelyon17_official_manifest.csv",
    )
    parser.add_argument(
        "--summary",
        default="artifacts/histopathology/reports/camelyon17_official_manifest_summary.json",
    )
    parser.add_argument("--source", default="camelyon17")
    parser.add_argument("--patch-size", type=int, default=256)
    parser.add_argument("--positive-per-slide", type=int, default=32)
    parser.add_argument("--negative-per-positive-slide", type=int, default=32)
    parser.add_argument("--negative-per-negative-slide", type=int, default=32)
    parser.add_argument("--max-attempts-per-patch", type=int, default=80)
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument(
        "--slide-ids",
        default="",
        help="Optional comma-separated slide IDs to process.",
    )
    parser.add_argument(
        "--negative-slide-ids",
        default="",
        help="Optional comma-separated slide IDs forced as negative slides.",
    )
    parser.add_argument(
        "--no-infer-unannotated-negatives",
        action="store_true",
        help="Do not treat local images without XML as negative when targets CSV is absent.",
    )
    parser.add_argument(
        "--evaluate-qc",
        action="store_true",
        help="Read sampled patches and store QC metrics in the manifest.",
    )
    parser.add_argument(
        "--save-patches",
        action="store_true",
        help="Also extract sampled patches to --patch-output-dir.",
    )
    parser.add_argument(
        "--patch-output-dir",
        default="artifacts/histopathology/camelyon17_official_patches",
    )
    return parser.parse_args()


def parse_slide_id_set(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def split_for_slide(slide_id: str, train_ratio: float, val_ratio: float, seed: int) -> str:
    digest = hashlib.sha1(f"{seed}:{slide_id}".encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    if value < train_ratio:
        return "train"
    if value < train_ratio + val_ratio:
        return "val"
    return "test"


def polygon_bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def parse_tumor_polygons(xml_path: Path) -> list[TumorPolygon]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    slide_id = xml_path.with_suffix(".tif").name
    polygons: list[TumorPolygon] = []
    for index, annotation in enumerate(root.findall(".//Annotation")):
        if annotation.attrib.get("PartOfGroup", "").lower() != "tumor":
            continue
        points = []
        for coordinate in annotation.findall(".//Coordinate"):
            points.append((float(coordinate.attrib["X"]), float(coordinate.attrib["Y"])))
        if len(points) < 3:
            continue
        polygons.append(
            TumorPolygon(
                slide_id=slide_id,
                annotation_id=annotation.attrib.get("Name", f"Annotation {index}"),
                points=tuple(points),
                bbox=polygon_bbox(points),
            )
        )
    return polygons


def load_polygons(annotations_dir: Path) -> dict[str, list[TumorPolygon]]:
    by_slide: dict[str, list[TumorPolygon]] = {}
    for xml_path in sorted(annotations_dir.glob("*.xml")):
        polygons = parse_tumor_polygons(xml_path)
        if polygons:
            by_slide.setdefault(polygons[0].slide_id, []).extend(polygons)
    return by_slide


def point_in_polygon(x: float, y: float, points: tuple[tuple[float, float], ...]) -> bool:
    inside = False
    j = len(points) - 1
    for i, point_i in enumerate(points):
        xi, yi = point_i
        xj, yj = points[j]
        intersects = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        if intersects:
            inside = not inside
        j = i
    return inside


def bbox_intersects(a: tuple[int, int, int, int], b: tuple[float, float, float, float]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def patch_overlaps_any_tumor(
    x: int,
    y: int,
    patch_size: int,
    polygons: list[TumorPolygon],
) -> bool:
    patch_bbox = (x, y, x + patch_size, y + patch_size)
    for polygon in polygons:
        if bbox_intersects(patch_bbox, polygon.bbox):
            return True
    return False


def sample_positive_xy(
    polygon: TumorPolygon,
    dimensions: tuple[int, int],
    patch_size: int,
    rng: random.Random,
) -> tuple[int, int] | None:
    slide_width, slide_height = dimensions
    if slide_width < patch_size or slide_height < patch_size:
        return None
    min_x, min_y, max_x, max_y = polygon.bbox
    left = max(0, int(min_x) - patch_size // 2)
    top = max(0, int(min_y) - patch_size // 2)
    right = min(slide_width - patch_size, int(max_x))
    bottom = min(slide_height - patch_size, int(max_y))
    if right < left or bottom < top:
        return None

    for _ in range(100):
        x = rng.randint(left, right)
        y = rng.randint(top, bottom)
        center_x = x + patch_size / 2
        center_y = y + patch_size / 2
        if point_in_polygon(center_x, center_y, polygon.points):
            return x, y
    return None


def sample_negative_xy(
    dimensions: tuple[int, int],
    polygons: list[TumorPolygon],
    patch_size: int,
    rng: random.Random,
    max_attempts: int,
) -> tuple[int, int] | None:
    slide_width, slide_height = dimensions
    if slide_width < patch_size or slide_height < patch_size:
        return None

    for _ in range(max_attempts):
        x = rng.randint(0, slide_width - patch_size)
        y = rng.randint(0, slide_height - patch_size)
        if not patch_overlaps_any_tumor(x, y, patch_size, polygons):
            return x, y
    return None


def load_targets_csv(path: Path) -> dict[str, int]:
    targets: dict[str, int] = {}
    if not path.exists():
        return targets
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            slide = row.get("slide") or row.get("patient") or row.get("slide_id")
            if not slide:
                continue
            if not Path(slide).suffix:
                slide = f"{slide}.tif"
            if row.get("target") not in (None, ""):
                targets[slide] = int(row["target"])
                continue
            stage = (row.get("stage") or "").strip().lower()
            if stage in POSITIVE_STAGES:
                targets[slide] = 1
            elif stage in NEGATIVE_STAGES:
                targets[slide] = 0
    return targets


def discover_slides(
    images_dir: Path,
    polygons_by_slide: dict[str, list[TumorPolygon]],
    targets: dict[str, int],
    negative_slide_ids: set[str],
    infer_unannotated_negatives: bool,
) -> list[SlideRecord]:
    records: list[SlideRecord] = []
    for image_path in sorted(images_dir.iterdir()):
        if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        slide_id = image_path.name
        if slide_id in targets:
            target = targets[slide_id]
        elif slide_id in polygons_by_slide:
            target = 1
        elif slide_id in negative_slide_ids or infer_unannotated_negatives:
            target = 0
        else:
            continue
        records.append(SlideRecord(slide_id=slide_id, path=image_path, target=target))
    return records


def format_metric(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"


def qc_fields(patch) -> dict:
    if patch is None:
        return {
            "qc_status": "",
            "qc_tissue_fraction": "",
            "qc_nuclear_fraction": "",
            "qc_white_fraction": "",
            "qc_stroma_fraction": "",
        }
    from app.histopathology.roi_quality import evaluate_roi_quality

    qc = evaluate_roi_quality(patch)
    metrics = qc["metrics"]
    return {
        "qc_status": qc["status"],
        "qc_tissue_fraction": format_metric(metrics.get("tissue_fraction")),
        "qc_nuclear_fraction": format_metric(metrics.get("nuclear_fraction")),
        "qc_white_fraction": format_metric(metrics.get("white_fraction")),
        "qc_stroma_fraction": format_metric(metrics.get("stroma_fraction")),
    }


def make_row(
    *,
    index: int,
    source: str,
    slide: SlideRecord,
    label: int,
    x: int,
    y: int,
    patch_size: int,
    split: str,
    hard_negative_type: str,
    annotation_status: str,
    label_source: str,
    patch_output_dir: Path,
    qc: dict,
) -> PatchManifestRow:
    kind = "tumor" if label == 1 else hard_negative_type or "negative"
    patch_id = f"{Path(slide.slide_id).stem}_{kind}_{x}_{y}_{patch_size}x{patch_size}_{index:06d}"
    patch_path = patch_output_dir / split / str(label) / f"{patch_id}.png"
    return PatchManifestRow(
        patch_id=patch_id,
        source=source,
        slide_id=slide.slide_id,
        path=str(patch_path),
        label=label,
        hard_negative_type=hard_negative_type,
        x=x,
        y=y,
        width=patch_size,
        height=patch_size,
        split=split,
        annotation_status=annotation_status,
        label_source=label_source,
        **qc,
    )


def maybe_read_patch(reader: SlideReader, x: int, y: int, patch_size: int, need_patch: bool):
    if not need_patch:
        return None
    return reader.read_patch(x, y, patch_size, patch_size)


def maybe_save_patch(patch, path: str, save_patches: bool) -> None:
    if not save_patches or patch is None:
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    patch.save(output)


def validate_args(args) -> None:
    if args.patch_size < 1:
        raise SystemExit("--patch-size must be greater than zero")
    if min(args.positive_per_slide, args.negative_per_positive_slide, args.negative_per_negative_slide) < 0:
        raise SystemExit("Patch counts must be zero or greater")
    if args.max_attempts_per_patch < 1:
        raise SystemExit("--max-attempts-per-patch must be greater than zero")
    if args.train_ratio <= 0 or args.val_ratio < 0 or args.train_ratio + args.val_ratio >= 1:
        raise SystemExit("Ratios must leave a non-empty test split")


def main():
    args = parse_args()
    validate_args(args)
    images_dir = Path(args.images_dir)
    annotations_dir = Path(args.annotations_dir)
    patch_output_dir = Path(args.patch_output_dir)
    polygons_by_slide = load_polygons(annotations_dir)
    targets = load_targets_csv(Path(args.targets_csv)) if args.targets_csv else {}
    negative_slide_ids = parse_slide_id_set(args.negative_slide_ids)
    requested_slide_ids = parse_slide_id_set(args.slide_ids)
    slides = discover_slides(
        images_dir=images_dir,
        polygons_by_slide=polygons_by_slide,
        targets=targets,
        negative_slide_ids=negative_slide_ids,
        infer_unannotated_negatives=not args.no_infer_unannotated_negatives,
    )
    if requested_slide_ids:
        slides = [slide for slide in slides if slide.slide_id in requested_slide_ids]

    rng = random.Random(args.seed)
    rows: list[PatchManifestRow] = []
    need_patch = args.evaluate_qc or args.save_patches
    summary = {
        "source": args.source,
        "slides": 0,
        "positive_rows": 0,
        "negative_rows": 0,
        "by_label_source": {},
        "manifest": args.manifest,
    }

    for slide in slides:
        polygons = polygons_by_slide.get(slide.slide_id, [])
        split = split_for_slide(slide.slide_id, args.train_ratio, args.val_ratio, args.seed)
        reader = SlideReader(slide.path)
        try:
            dimensions = reader.dimensions
            saved_positive = 0
            saved_negative = 0

            if slide.target == 1 and polygons:
                attempts = 0
                max_attempts = max(1, args.positive_per_slide * args.max_attempts_per_patch)
                while saved_positive < args.positive_per_slide and attempts < max_attempts:
                    attempts += 1
                    polygon = rng.choice(polygons)
                    xy = sample_positive_xy(polygon, dimensions, args.patch_size, rng)
                    if xy is None:
                        continue
                    x, y = xy
                    patch = maybe_read_patch(reader, x, y, args.patch_size, need_patch)
                    qc = qc_fields(patch) if args.evaluate_qc else qc_fields(None)
                    row = make_row(
                        index=len(rows),
                        source=args.source,
                        slide=slide,
                        label=1,
                        x=x,
                        y=y,
                        patch_size=args.patch_size,
                        split=split,
                        hard_negative_type="",
                        annotation_status="xml_tumor_polygon",
                        label_source="annotation_official",
                        patch_output_dir=patch_output_dir,
                        qc=qc,
                    )
                    maybe_save_patch(patch, row.path, args.save_patches)
                    rows.append(row)
                    saved_positive += 1

                attempts = 0
                max_attempts = max(1, args.negative_per_positive_slide * args.max_attempts_per_patch)
                while saved_negative < args.negative_per_positive_slide and attempts < max_attempts:
                    attempts += 1
                    xy = sample_negative_xy(dimensions, polygons, args.patch_size, rng, args.max_attempts_per_patch)
                    if xy is None:
                        break
                    x, y = xy
                    patch = maybe_read_patch(reader, x, y, args.patch_size, need_patch)
                    qc = qc_fields(patch) if args.evaluate_qc else qc_fields(None)
                    row = make_row(
                        index=len(rows),
                        source=args.source,
                        slide=slide,
                        label=0,
                        x=x,
                        y=y,
                        patch_size=args.patch_size,
                        split=split,
                        hard_negative_type="official_non_tumor",
                        annotation_status="outside_xml_tumor_polygon",
                        label_source="annotation_official_non_tumor",
                        patch_output_dir=patch_output_dir,
                        qc=qc,
                    )
                    maybe_save_patch(patch, row.path, args.save_patches)
                    rows.append(row)
                    saved_negative += 1

            if slide.target == 0:
                attempts = 0
                max_attempts = max(1, args.negative_per_negative_slide * args.max_attempts_per_patch)
                while saved_negative < args.negative_per_negative_slide and attempts < max_attempts:
                    attempts += 1
                    xy = sample_negative_xy(dimensions, [], args.patch_size, rng, args.max_attempts_per_patch)
                    if xy is None:
                        break
                    x, y = xy
                    patch = maybe_read_patch(reader, x, y, args.patch_size, need_patch)
                    qc = qc_fields(patch) if args.evaluate_qc else qc_fields(None)
                    row = make_row(
                        index=len(rows),
                        source=args.source,
                        slide=slide,
                        label=0,
                        x=x,
                        y=y,
                        patch_size=args.patch_size,
                        split=split,
                        hard_negative_type="negative_slide",
                        annotation_status="negative_slide",
                        label_source="negative_slide",
                        patch_output_dir=patch_output_dir,
                        qc=qc,
                    )
                    maybe_save_patch(patch, row.path, args.save_patches)
                    rows.append(row)
                    saved_negative += 1

            print(
                "[histopathology] "
                f"slide={slide.slide_id} target={slide.target} split={split} "
                f"positive={saved_positive} negative={saved_negative}",
                flush=True,
            )
            summary["slides"] += 1
            summary["positive_rows"] += saved_positive
            summary["negative_rows"] += saved_negative
        finally:
            reader.close()

    for row in rows:
        summary["by_label_source"].setdefault(row.label_source, 0)
        summary["by_label_source"][row.label_source] += 1

    write_manifest(args.manifest, rows)
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[histopathology] saved manifest rows={len(rows)} -> {args.manifest}", flush=True)
    print(f"[histopathology] saved summary -> {args.summary}", flush=True)


if __name__ == "__main__":
    main()
