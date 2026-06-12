from dataclasses import replace

from histopathology_offline.manifest_dataset import PatchManifestRow
from histopathology_offline.split_manifest_grouped import (
    assign_groups,
    group_id_for_row,
    patient_id_for_row,
    summarize,
    validate_no_overlap,
)


def make_row(patient: int, node: int, index: int, *, label: int = 0, hard_type: str = ""):
    patch_id = f"patient_{patient:03d}_node_{node}_{index}"
    return PatchManifestRow(
        patch_id=patch_id,
        source="camelyon17",
        slide_id=f"patient_{patient:03d}_node_{node}.tif",
        path=f"patches/{patch_id}.png",
        label=label,
        hard_negative_type=hard_type,
        x=index,
        y=0,
        width=256,
        height=256,
        split="legacy",
    )


def test_patient_id_and_group_prefer_patient_over_slide():
    row = make_row(7, 2, 1)
    assert patient_id_for_row(row) == "patient_007"
    assert group_id_for_row(row) == ("patient", "patient_007")


def test_assign_groups_keeps_patient_and_slides_in_one_split():
    rows = []
    for patient in range(12):
        rows.extend(
            [
                make_row(patient, 0, 0),
                make_row(patient, 1, 1, label=1),
                make_row(patient, 1, 2, hard_type="stroma"),
            ]
        )

    assignment = assign_groups(
        rows,
        train_ratio=0.7,
        val_ratio=0.15,
        seed=9,
        search_trials=200,
    )
    split_rows = [replace(row, split=assignment[group_id_for_row(row)]) for row in rows]

    assert validate_no_overlap(split_rows)["valid"] is True
    for patient in range(12):
        assert len({row.split for row in split_rows if patient_id_for_row(row) == f"patient_{patient:03d}"}) == 1


def test_validation_detects_patient_and_slide_overlap():
    row = make_row(1, 0, 0)
    rows = [replace(row, split="train"), replace(row, patch_id="other", split="test")]
    validation = validate_no_overlap(rows)

    assert validation["valid"] is False
    assert validation["overlaps"]["train_vs_test"]["slides"] == ["patient_001_node_0.tif"]
    assert validation["overlaps"]["train_vs_test"]["patients"] == ["patient_001"]


def test_summary_reports_all_three_semantic_classes():
    rows = [
        replace(make_row(1, 0, 0), split="train"),
        replace(make_row(2, 0, 0, label=1), split="val"),
        replace(make_row(3, 0, 0, hard_type="stroma"), split="test"),
    ]
    summary = summarize(rows, source_manifest="source.csv", seed=1, ratios={"train": 0.7, "val": 0.15, "test": 0.15})

    assert summary["splits"]["train"]["class_counts"]["no_metastasico"] == 1
    assert summary["splits"]["val"]["class_counts"]["metastasico"] == 1
    assert summary["splits"]["test"]["class_counts"]["estroma"] == 1
    assert summary["overlap_validation"]["valid"] is True
