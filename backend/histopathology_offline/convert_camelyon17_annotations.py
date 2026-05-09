import argparse
import csv
import math
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


POSITIVE_STAGES = {"itc", "micro", "macro"}
NEGATIVE_STAGES = {"negative"}


@dataclass(frozen=True)
class TumorROI:
    slide_id: str
    label: int
    x: int
    y: int
    width: int
    height: int
    annotation_id: str
    group: str
    point_count: int


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert CAMELYON17 ASAP XML annotations to ROI and target CSV files."
    )
    parser.add_argument("--annotations-dir", required=True)
    parser.add_argument("--stages-csv", required=True)
    parser.add_argument("--output-rois", default="data/annotations/camelyon17_tumor_rois.csv")
    parser.add_argument("--output-targets", default="data/annotations/camelyon17_targets.csv")
    parser.add_argument(
        "--margin",
        type=int,
        default=256,
        help="Pixels added around each tumor polygon bounding box. Default: 256.",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=512,
        help="Minimum ROI width/height after margin. Default: 512.",
    )
    return parser.parse_args()


def parse_tumor_rois(xml_path: Path, margin: int, min_size: int) -> list[TumorROI]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    slide_id = xml_path.with_suffix(".tif").name
    rois = []

    for index, annotation in enumerate(root.findall(".//Annotation")):
        group = annotation.attrib.get("PartOfGroup", "")
        if group.lower() != "tumor":
            continue

        coordinates = []
        for coordinate in annotation.findall(".//Coordinate"):
            coordinates.append(
                (
                    float(coordinate.attrib["X"]),
                    float(coordinate.attrib["Y"]),
                )
            )
        if not coordinates:
            continue

        xs = [point[0] for point in coordinates]
        ys = [point[1] for point in coordinates]
        min_x = math.floor(min(xs)) - margin
        min_y = math.floor(min(ys)) - margin
        max_x = math.ceil(max(xs)) + margin
        max_y = math.ceil(max(ys)) + margin

        x = max(0, min_x)
        y = max(0, min_y)
        width = max(min_size, max_x - x)
        height = max(min_size, max_y - y)

        rois.append(
            TumorROI(
                slide_id=slide_id,
                label=1,
                x=x,
                y=y,
                width=width,
                height=height,
                annotation_id=annotation.attrib.get("Name", f"Annotation {index}"),
                group=group,
                point_count=len(coordinates),
            )
        )

    return rois


def write_rois(path: Path, rois: list[TumorROI]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "slide_id",
        "label",
        "x",
        "y",
        "width",
        "height",
        "annotation_id",
        "group",
        "point_count",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for roi in rois:
            writer.writerow(
                {
                    "slide_id": roi.slide_id,
                    "label": roi.label,
                    "x": roi.x,
                    "y": roi.y,
                    "width": roi.width,
                    "height": roi.height,
                    "annotation_id": roi.annotation_id,
                    "group": roi.group,
                    "point_count": roi.point_count,
                }
            )


def write_targets(stages_csv: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with stages_csv.open("r", newline="", encoding="utf-8") as source, output_path.open(
        "w", newline="", encoding="utf-8"
    ) as target:
        reader = csv.DictReader(source)
        writer = csv.DictWriter(target, fieldnames=["slide", "target", "stage", "center"])
        writer.writeheader()
        for row in reader:
            slide = row["patient"]
            if not slide.endswith(".tif"):
                continue

            stage = row["stage"].strip().lower()
            if stage in POSITIVE_STAGES:
                target_value = 1
            elif stage in NEGATIVE_STAGES:
                target_value = 0
            else:
                continue

            writer.writerow(
                {
                    "slide": slide,
                    "target": target_value,
                    "stage": row["stage"],
                    "center": row["center"],
                }
            )


def main():
    args = parse_args()
    if args.margin < 0:
        raise SystemExit("--margin must be zero or greater")
    if args.min_size < 1:
        raise SystemExit("--min-size must be greater than zero")

    annotations_dir = Path(args.annotations_dir)
    rois = []
    for xml_path in sorted(annotations_dir.glob("*.xml")):
        xml_rois = parse_tumor_rois(xml_path, margin=args.margin, min_size=args.min_size)
        rois.extend(xml_rois)
        print(f"[histopathology] {xml_path.name}: tumor_rois={len(xml_rois)}", flush=True)

    write_rois(Path(args.output_rois), rois)
    write_targets(Path(args.stages_csv), Path(args.output_targets))
    print(f"[histopathology] saved tumor ROIs: {len(rois)} -> {args.output_rois}", flush=True)
    print(f"[histopathology] saved targets -> {args.output_targets}", flush=True)


if __name__ == "__main__":
    main()
