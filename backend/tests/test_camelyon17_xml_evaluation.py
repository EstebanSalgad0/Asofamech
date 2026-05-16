from histopathology_offline.evaluate_camelyon17_xml_predictions import (
    OfficialTruth,
    outcome_for_truth_prediction,
    official_truth_for_row,
    patch_matches_xml_tumor,
    rect_intersects_polygon,
)
from histopathology_offline.build_camelyon17_official_manifest import TumorPolygon
from histopathology_offline.manifest_dataset import PatchManifestRow


def polygon() -> TumorPolygon:
    return TumorPolygon(
        slide_id="patient_001_node_1.tif",
        annotation_id="tumor",
        points=((10.0, 10.0), (110.0, 10.0), (110.0, 110.0), (10.0, 110.0)),
        bbox=(10.0, 10.0, 110.0, 110.0),
    )


def row(slide_id="patient_001_node_1.tif", x=20, y=20, width=32, height=32):
    return PatchManifestRow(
        patch_id=f"{slide_id}:{x}:{y}",
        source="camelyon17",
        slide_id=slide_id,
        path=f"patches/{slide_id}_{x}_{y}.png",
        label=0,
        hard_negative_type="",
        x=x,
        y=y,
        width=width,
        height=height,
        split="test",
    )


def test_rect_intersects_polygon_when_patch_crosses_edge():
    assert rect_intersects_polygon(90, 90, 64, 64, polygon()) is True


def test_rect_intersects_polygon_rejects_distant_patch():
    assert rect_intersects_polygon(200, 200, 32, 32, polygon()) is False


def test_patch_matches_xml_tumor_center_mode():
    polygons = [polygon()]
    assert patch_matches_xml_tumor(row(x=20, y=20), polygons, "center") is True
    assert patch_matches_xml_tumor(row(x=100, y=100), polygons, "center") is False


def test_official_truth_uses_xml_when_available():
    truth = official_truth_for_row(
        row(x=20, y=20),
        {"patient_001_node_1.tif": [polygon()]},
        {"patient_001_node_1.tif": 1},
        "center",
    )

    assert truth == OfficialTruth(
        label=1,
        source="xml_tumor_polygon",
        xml_tumor_match=True,
        target=1,
    )


def test_official_truth_marks_negative_slide_without_xml():
    truth = official_truth_for_row(
        row(slide_id="patient_002_node_0.tif"),
        {},
        {"patient_002_node_0.tif": 0},
        "center",
    )

    assert truth.label == 0
    assert truth.source == "negative_slide"


def test_official_truth_keeps_positive_without_xml_unknown():
    truth = official_truth_for_row(
        row(slide_id="patient_003_node_0.tif"),
        {},
        {"patient_003_node_0.tif": 1},
        "center",
    )

    assert truth.label is None
    assert truth.source == "positive_slide_without_xml"


def test_outcome_for_truth_prediction():
    assert outcome_for_truth_prediction(1, True) == "true_positive"
    assert outcome_for_truth_prediction(1, False) == "false_negative"
    assert outcome_for_truth_prediction(0, True) == "false_positive"
    assert outcome_for_truth_prediction(0, False) == "true_negative"
    assert outcome_for_truth_prediction(None, False) == "unknown"
