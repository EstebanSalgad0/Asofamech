from histopathology_offline.histology_augmentations import AUGMENTATION_CONFIG


def test_histology_augmentation_config_is_moderate_and_documents_stain_choice():
    assert AUGMENTATION_CONFIG["rotations_by_view"] == [90, 180, 270]
    assert AUGMENTATION_CONFIG["random_resized_crop_scale"][0] >= 0.9
    assert AUGMENTATION_CONFIG["color_jitter"]["brightness"] <= 0.1
    assert AUGMENTATION_CONFIG["stain_normalization"]["enabled"] is False
    assert AUGMENTATION_CONFIG["stain_normalization"]["reason"]
