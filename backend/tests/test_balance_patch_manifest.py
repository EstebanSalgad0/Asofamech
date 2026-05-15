from histopathology_offline.balance_patch_manifest import (
    balance_rows,
    class_name_for_row,
    dedupe_rows,
    parse_cap,
    select_stratified,
    summarize,
)
from histopathology_offline.manifest_dataset import PatchManifestRow


def make_row(
    patch_id: str,
    *,
    label: int = 0,
    split: str = "train",
    hard_negative_type: str = "",
    label_source: str = "",
    x: int = 0,
) -> PatchManifestRow:
    return PatchManifestRow(
        patch_id=patch_id,
        source="camelyon17",
        slide_id="slide.tif",
        path=f"patches/{patch_id}.png",
        label=label,
        hard_negative_type=hard_negative_type,
        x=x,
        y=0,
        width=256,
        height=256,
        split=split,
        label_source=label_source,
    )


def test_class_name_for_row_maps_tumor_stroma_and_negative():
    assert class_name_for_row(make_row("tumor", label=1)) == "metastasico"
    assert class_name_for_row(make_row("stroma", hard_negative_type="stroma")) == "estroma"
    assert class_name_for_row(make_row("negative", hard_negative_type="negative_slide")) == "no_metastasico"


def test_parse_cap_validates_expected_format():
    assert parse_cap("train:no_metastasico=700") == ("train", "no_metastasico", 700)


def test_dedupe_rows_removes_duplicate_coordinates():
    rows = [
        make_row("a", x=10, hard_negative_type="negative_slide"),
        make_row("b", x=10, hard_negative_type="negative_slide"),
        make_row("c", x=11, hard_negative_type="negative_slide"),
    ]

    assert [row.patch_id for row in dedupe_rows(rows)] == ["a", "c"]


def test_select_stratified_preserves_subgroup_variety():
    rows = [
        make_row("a1", hard_negative_type="negative_slide"),
        make_row("a2", hard_negative_type="negative_slide"),
        make_row("b1", hard_negative_type="official_non_tumor"),
        make_row("b2", hard_negative_type="official_non_tumor"),
    ]

    selected = select_stratified(rows, cap=2, rng=__import__("random").Random(1))

    assert {row.hard_negative_type for row in selected} == {"negative_slide", "official_non_tumor"}


def test_balance_rows_applies_caps_by_split_and_class():
    rows = [
        make_row("n1", hard_negative_type="negative_slide"),
        make_row("n2", hard_negative_type="official_non_tumor"),
        make_row("n3", hard_negative_type="low_cellularity"),
        make_row("t1", label=1, label_source="annotation_official"),
        make_row("t2", label=1),
        make_row("s1", hard_negative_type="stroma"),
    ]

    balanced = balance_rows(rows, {("train", "no_metastasico"): 2}, seed=1)
    counts = summarize(balanced)["by_split_class"]

    assert counts["train:no_metastasico"] == 2
    assert counts["train:metastasico"] == 2
    assert counts["train:estroma"] == 1
