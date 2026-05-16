from pathlib import Path

import pytest

from histopathology_offline.manifest_dataset import PatchManifestRow, write_manifest
from histopathology_offline.reuse_manifest_embeddings import (
    materialize_split,
    row_identity_key,
    write_aligned_embeddings,
)


torch = pytest.importorskip("torch")


def row(
    patch_id="p1",
    path="patches\\a.png",
    label=0,
    hard_negative_type="",
    split="train",
):
    return PatchManifestRow(
        patch_id=patch_id,
        source="camelyon17",
        slide_id="patient_001_node_1.tif",
        path=path,
        label=label,
        hard_negative_type=hard_negative_type,
        x=10,
        y=20,
        width=256,
        height=256,
        split=split,
    )


def test_identity_key_ignores_label_and_normalizes_path():
    base = row(label=0, hard_negative_type="", path="patches\\a.png")
    relabeled = row(label=1, hard_negative_type="xml_false_negative_tumor", path="patches/a.png")

    assert row_identity_key(base) == row_identity_key(relabeled)


def test_materialize_split_duplicates_existing_vector_for_relabeled_row():
    base = row(label=0)
    relabeled = row(patch_id="xml-fn", label=1, hard_negative_type="xml_false_negative_tumor")
    index = {
        row_identity_key(base): type(
            "Indexed",
            (),
            {
                "vector": torch.tensor([1.0, 2.0]),
                "source_label": 0,
                "record": base.to_dict(),
            },
        )()
    }

    payload = materialize_split(torch, [base, relabeled], index, "train")

    assert payload["x"].tolist() == [[1.0, 2.0], [1.0, 2.0]]
    assert payload["y"].tolist() == [0, 1]
    assert payload["records"][1]["hard_negative_type"] == "xml_false_negative_tumor"


def test_materialize_split_raises_when_patch_is_not_in_source_index():
    with pytest.raises(SystemExit, match="Could not reuse embeddings"):
        materialize_split(torch, [row()], {}, "train")


def test_write_aligned_embeddings_roundtrip(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    target_manifest = tmp_path / "target.csv"
    output_dir = tmp_path / "out"
    base = row(patch_id="base", label=0)
    relabeled = row(patch_id="extra", label=1, hard_negative_type="xml_false_negative_tumor")
    write_manifest(target_manifest, [base, relabeled])
    torch.save(
        {
            "x": torch.tensor([[3.0, 4.0]]),
            "y": torch.tensor([0]),
            "records": [base.to_dict()],
            "metadata": {"split": "train"},
        },
        source_dir / "manifest_train_embeddings.pt",
    )

    summary = write_aligned_embeddings(
        torch=torch,
        target_manifest=target_manifest,
        source_embeddings_dir=source_dir,
        output_dir=output_dir,
        source_splits=["train"],
        target_splits=["train"],
        skip_existing=False,
    )

    payload = torch.load(output_dir / "manifest_train_embeddings.pt", map_location="cpu")
    assert summary["splits"]["train"]["rows"] == 2
    assert payload["x"].tolist() == [[3.0, 4.0], [3.0, 4.0]]
    assert payload["records"][1]["patch_id"] == "extra"
