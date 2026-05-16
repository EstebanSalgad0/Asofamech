import csv
from pathlib import Path

from histopathology_offline.build_stage9_manifest_from_xml_errors import (
    parse_caps,
    row_to_manifest_row,
    select_rows,
)


def eval_row(outcome="false_positive", split="train", x=10, y=20):
    return {
        "patch_id": f"p-{outcome}-{x}-{y}",
        "split": split,
        "slide_id": "patient_001_node_1.tif",
        "x": str(x),
        "y": str(y),
        "width": "256",
        "height": "256",
        "truth_source": "outside_xml_tumor_polygon",
        "outcome": outcome,
        "path": f"patches/{x}_{y}.png",
    }


def test_false_positive_becomes_hard_negative_manifest_row():
    row = row_to_manifest_row(eval_row("false_positive"))

    assert row.label == 0
    assert row.hard_negative_type == "xml_false_positive_hard_negative"
    assert row.label_source == "xml_evaluation_false_positive"
    assert row.annotation_status == "outside_xml_tumor_polygon"
    assert row.split == "train"


def test_false_negative_becomes_difficult_positive_manifest_row():
    row = row_to_manifest_row(eval_row("false_negative", split="val"))

    assert row.label == 1
    assert row.hard_negative_type == "xml_false_negative_tumor"
    assert row.label_source == "xml_evaluation_false_negative"
    assert row.split == "val"


def test_force_split_overrides_source_split():
    row = row_to_manifest_row(eval_row("false_negative", split="val"), force_split="train")

    assert row.split == "train"


def test_parse_caps_accepts_outcome_count_pairs():
    assert parse_caps(["false_positive=3", "false_negative=4"]) == {
        "false_positive": 3,
        "false_negative": 4,
    }


def test_select_rows_filters_dedupes_and_caps():
    rows = [
        eval_row("false_positive", x=1),
        eval_row("false_positive", x=1),
        eval_row("false_positive", x=2),
        eval_row("false_negative", x=3),
        eval_row("true_negative", x=4),
    ]

    selected = select_rows(
        rows,
        {"false_positive", "false_negative"},
        {"false_positive": 1},
    )

    assert [row["outcome"] for row in selected] == ["false_positive", "false_negative"]
    assert selected[0]["x"] == "1"


def test_manifest_csv_roundtrip(tmp_path: Path):
    from histopathology_offline.manifest_dataset import read_manifest, write_manifest

    output = tmp_path / "stage9.csv"
    rows = [
        row_to_manifest_row(eval_row("false_positive")),
        row_to_manifest_row(eval_row("false_negative", x=40)),
    ]
    write_manifest(output, rows)

    loaded = read_manifest(output)
    assert [row.label for row in loaded] == [0, 1]
    assert loaded[0].slide_id == "patient_001_node_1.tif"
