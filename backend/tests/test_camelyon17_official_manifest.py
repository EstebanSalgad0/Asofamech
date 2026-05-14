import csv
from pathlib import Path

from histopathology_offline.build_camelyon17_official_manifest import (
    TumorPolygon,
    bbox_intersects,
    load_targets_csv,
    parse_tumor_polygons,
    parse_slide_id_set,
    point_in_polygon,
    split_for_slide,
    patch_overlaps_any_tumor,
)
from histopathology_offline.manifest_dataset import PatchManifestRow, read_manifest, write_manifest
from histopathology_offline.sample_hard_negative_patches import label_source_for_row


def square_polygon() -> TumorPolygon:
    points = ((10.0, 10.0), (110.0, 10.0), (110.0, 110.0), (10.0, 110.0))
    return TumorPolygon(
        slide_id="patient_001_node_1.tif",
        annotation_id="_0",
        points=points,
        bbox=(10.0, 10.0, 110.0, 110.0),
    )


def test_point_in_polygon_detects_inside_and_outside_points():
    polygon = square_polygon()

    assert point_in_polygon(50.0, 50.0, polygon.points) is True
    assert point_in_polygon(150.0, 50.0, polygon.points) is False


def test_patch_overlap_uses_tumor_bbox_conservatively():
    polygon = square_polygon()

    assert patch_overlaps_any_tumor(0, 0, 32, [polygon]) is True
    assert patch_overlaps_any_tumor(200, 200, 32, [polygon]) is False


def test_bbox_intersects_handles_touching_edges_as_no_overlap():
    assert bbox_intersects((0, 0, 10, 10), (10.0, 0.0, 20.0, 10.0)) is False
    assert bbox_intersects((0, 0, 10, 10), (9.0, 0.0, 20.0, 10.0)) is True


def test_split_for_slide_is_deterministic():
    first = split_for_slide("patient_017_node_2.tif", 0.70, 0.15, 17)
    second = split_for_slide("patient_017_node_2.tif", 0.70, 0.15, 17)

    assert first == second
    assert first in {"train", "val", "test"}


def test_parse_slide_id_set_ignores_empty_items():
    assert parse_slide_id_set("a.tif, ,b.tif,,") == {"a.tif", "b.tif"}


def test_load_targets_csv_accepts_stage_labels(tmp_path: Path):
    targets_csv = tmp_path / "targets.csv"
    with targets_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["slide", "stage"])
        writer.writeheader()
        writer.writerow({"slide": "patient_001_node_1", "stage": "macro"})
        writer.writerow({"slide": "patient_001_node_0.tif", "stage": "negative"})

    assert load_targets_csv(targets_csv) == {
        "patient_001_node_1.tif": 1,
        "patient_001_node_0.tif": 0,
    }


def test_parse_tumor_polygons_reads_asap_xml(tmp_path: Path):
    xml_path = tmp_path / "patient_001_node_1.xml"
    xml_path.write_text(
        """
<ASAP_Annotations>
  <Annotations>
    <Annotation Name="_0" Type="Polygon" PartOfGroup="Tumor">
      <Coordinates>
        <Coordinate Order="0" X="10" Y="20" />
        <Coordinate Order="1" X="110" Y="20" />
        <Coordinate Order="2" X="110" Y="120" />
        <Coordinate Order="3" X="10" Y="120" />
      </Coordinates>
    </Annotation>
    <Annotation Name="_1" Type="Polygon" PartOfGroup="Exclusion">
      <Coordinates>
        <Coordinate Order="0" X="1" Y="1" />
        <Coordinate Order="1" X="2" Y="1" />
        <Coordinate Order="2" X="2" Y="2" />
      </Coordinates>
    </Annotation>
  </Annotations>
</ASAP_Annotations>
""",
        encoding="utf-8",
    )

    polygons = parse_tumor_polygons(xml_path)

    assert len(polygons) == 1
    assert polygons[0].slide_id == "patient_001_node_1.tif"
    assert polygons[0].bbox == (10.0, 20.0, 110.0, 120.0)


def test_patch_manifest_roundtrip_preserves_label_source(tmp_path: Path):
    manifest = tmp_path / "manifest.csv"
    row = PatchManifestRow(
        patch_id="p1",
        source="camelyon17",
        slide_id="patient_017_node_2.tif",
        path="patches/p1.png",
        label=1,
        hard_negative_type="",
        x=10,
        y=20,
        width=256,
        height=256,
        split="train",
        annotation_status="xml_tumor_polygon",
        label_source="annotation_official",
    )

    write_manifest(manifest, [row])
    loaded = read_manifest(manifest)

    assert len(loaded) == 1
    assert loaded[0].label_source == "annotation_official"
    assert loaded[0].annotation_status == "xml_tumor_polygon"


def test_sample_hard_negative_label_source_mapping():
    assert label_source_for_row(1, 1, "annotated_positive") == "annotation_official"
    assert label_source_for_row(0, 0, "none") == "negative_slide"
    assert label_source_for_row(1, 1, "weak_positive_slide_label") == "slide_label_weak"
    assert label_source_for_row(1, 0, "none") == "heuristic_qc"
