from pathlib import Path

from histopathology_offline.build_camelyon17_official_manifest import TumorPolygon
from histopathology_offline.mine_camelyon17_false_positive_patches import (
    MinedCandidate,
    candidate_to_manifest_row,
    mined_hard_negative_type,
    patch_is_outside_tumor,
    select_top_candidates,
)


def qc_payload(stroma_fraction=0.05, nuclear_fraction=0.45):
    return {
        "status": "evaluable",
        "metrics": {
            "tissue_fraction": 0.95,
            "nuclear_fraction": nuclear_fraction,
            "white_fraction": 0.02,
            "stroma_fraction": stroma_fraction,
        },
        "checks": {
            "white_fraction_ok": True,
            "tissue_fraction_ok": True,
            "stroma_fraction_ok": True,
            "nuclear_fraction_ok": nuclear_fraction >= 0.02,
        },
    }


def polygon():
    points = ((100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0))
    return TumorPolygon(
        slide_id="patient_001_node_1.tif",
        annotation_id="tumor",
        points=points,
        bbox=(100.0, 100.0, 200.0, 200.0),
    )


def candidate(score=0.75, x=10):
    return MinedCandidate(
        slide_id="patient_001_node_1.tif",
        x=x,
        y=20,
        width=256,
        height=256,
        split="train",
        truth_source="outside_xml_tumor_polygon",
        tumor_score=score,
        predicted_class="metastasico",
        confidence=score,
        qc=qc_payload(),
    )


def test_patch_outside_tumor_rejects_bbox_overlap_with_margin():
    assert patch_is_outside_tumor(0, 0, 64, [polygon()], tumor_margin=0) is True
    assert patch_is_outside_tumor(90, 90, 64, [polygon()], tumor_margin=0) is False
    assert patch_is_outside_tumor(40, 40, 32, [polygon()], tumor_margin=32) is False


def test_select_top_candidates_sorts_by_tumor_score_and_caps():
    selected = select_top_candidates(
        [candidate(0.51, x=1), candidate(0.93, x=2), candidate(0.77, x=3)],
        limit=2,
    )
    assert [item.x for item in selected] == [2, 3]


def test_mined_hard_negative_type_preserves_stroma_class_names():
    assert mined_hard_negative_type(qc_payload(stroma_fraction=0.60)) == "stroma"
    assert mined_hard_negative_type(qc_payload(stroma_fraction=0.05)) == "lymphoid_or_mixed_negative"


def test_candidate_to_manifest_row_marks_xml_mined_negative():
    row = candidate_to_manifest_row(
        candidate(0.88),
        Path("artifacts/histopathology/stage13/train/0/patch.png"),
        row_index=4,
        source="camelyon17_xml_mined",
    )

    assert row.label == 0
    assert row.patch_id.startswith("stage13_patient_001_node_1_10_20_256x256_000004")
    assert row.annotation_status == "outside_xml_tumor_polygon"
    assert row.label_source == "xml_mined_false_positive"
    assert row.hard_negative_type == "lymphoid_or_mixed_negative"
