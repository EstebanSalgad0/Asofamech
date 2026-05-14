import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from PIL import Image


MANIFEST_COLUMNS = [
    "patch_id",
    "source",
    "slide_id",
    "path",
    "label",
    "hard_negative_type",
    "x",
    "y",
    "width",
    "height",
    "split",
    "qc_status",
    "qc_tissue_fraction",
    "qc_nuclear_fraction",
    "qc_white_fraction",
    "qc_stroma_fraction",
    "annotation_status",
    "label_source",
]


@dataclass(frozen=True)
class PatchManifestRow:
    patch_id: str
    source: str
    slide_id: str
    path: str
    label: int
    hard_negative_type: str
    x: int
    y: int
    width: int
    height: int
    split: str
    qc_status: str = ""
    qc_tissue_fraction: str = ""
    qc_nuclear_fraction: str = ""
    qc_white_fraction: str = ""
    qc_stroma_fraction: str = ""
    annotation_status: str = ""
    label_source: str = ""

    @classmethod
    def from_dict(cls, payload: dict) -> "PatchManifestRow":
        return cls(
            patch_id=payload["patch_id"],
            source=payload["source"],
            slide_id=payload["slide_id"],
            path=payload["path"],
            label=int(payload["label"]),
            hard_negative_type=payload.get("hard_negative_type", ""),
            x=int(float(payload["x"])),
            y=int(float(payload["y"])),
            width=int(float(payload["width"])),
            height=int(float(payload["height"])),
            split=payload["split"],
            qc_status=payload.get("qc_status", ""),
            qc_tissue_fraction=payload.get("qc_tissue_fraction", ""),
            qc_nuclear_fraction=payload.get("qc_nuclear_fraction", ""),
            qc_white_fraction=payload.get("qc_white_fraction", ""),
            qc_stroma_fraction=payload.get("qc_stroma_fraction", ""),
            annotation_status=payload.get("annotation_status", ""),
            label_source=payload.get("label_source", ""),
        )

    def to_dict(self) -> dict:
        return {
            "patch_id": self.patch_id,
            "source": self.source,
            "slide_id": self.slide_id,
            "path": self.path,
            "label": self.label,
            "hard_negative_type": self.hard_negative_type,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "split": self.split,
            "qc_status": self.qc_status,
            "qc_tissue_fraction": self.qc_tissue_fraction,
            "qc_nuclear_fraction": self.qc_nuclear_fraction,
            "qc_white_fraction": self.qc_white_fraction,
            "qc_stroma_fraction": self.qc_stroma_fraction,
            "annotation_status": self.annotation_status,
            "label_source": self.label_source,
        }


class ManifestPatchDataset:
    def __init__(
        self,
        manifest_path: str | Path,
        split: Optional[str] = None,
        transform: Optional[Callable] = None,
        root_dir: str | Path | None = None,
    ):
        self.manifest_path = Path(manifest_path)
        self.root_dir = Path(root_dir) if root_dir is not None else self.manifest_path.parent
        self.transform = transform
        self.rows = [
            row
            for row in read_manifest(self.manifest_path)
            if split is None or row.split == split
        ]

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        image_path = Path(row.path)
        if not image_path.is_absolute():
            if not image_path.exists():
                image_path = self.root_dir / image_path

        image = Image.open(image_path).convert("RGB")
        if self.transform is not None:
            image = self.transform(image)
        return image, int(row.label), row


def read_manifest(path: str | Path) -> list[PatchManifestRow]:
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [PatchManifestRow.from_dict(row) for row in reader]


def write_manifest(path: str | Path, rows: Iterable[PatchManifestRow]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_dict())
