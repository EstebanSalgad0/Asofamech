import random
from pathlib import Path

from PIL import Image

from histopathology_offline.manifest_dataset import read_manifest


AUGMENTATION_CONFIG = {
    "preset": "histo_moderate_v1",
    "input_size": 448,
    "rotations_by_view": [90, 180, 270],
    "horizontal_flip_probability": 0.5,
    "vertical_flip_probability": 0.5,
    "random_resized_crop_scale": [0.90, 1.0],
    "random_resized_crop_ratio": [0.95, 1.05],
    "color_jitter": {
        "brightness": 0.08,
        "contrast": 0.08,
        "saturation": 0.06,
        "hue": 0.02,
    },
    "stain_normalization": {
        "enabled": False,
        "reason": "No validated reference slide or stain target is available.",
    },
}


class ModerateHistologyTransform:
    def __init__(self, torch, preprocess, view_index: int):
        from torchvision import transforms
        from torchvision.transforms import InterpolationMode

        rotation_values = AUGMENTATION_CONFIG["rotations_by_view"]
        self.torch = torch
        self.preprocess = preprocess
        self.rotation = rotation_values[(view_index - 1) % len(rotation_values)]
        self.transform = transforms.Compose(
            [
                transforms.RandomResizedCrop(
                    AUGMENTATION_CONFIG["input_size"],
                    scale=tuple(AUGMENTATION_CONFIG["random_resized_crop_scale"]),
                    ratio=tuple(AUGMENTATION_CONFIG["random_resized_crop_ratio"]),
                    interpolation=InterpolationMode.BICUBIC,
                ),
                transforms.RandomHorizontalFlip(
                    p=AUGMENTATION_CONFIG["horizontal_flip_probability"]
                ),
                transforms.RandomVerticalFlip(
                    p=AUGMENTATION_CONFIG["vertical_flip_probability"]
                ),
                transforms.ColorJitter(**AUGMENTATION_CONFIG["color_jitter"]),
            ]
        )

    def __call__(self, image):
        from torchvision.transforms import functional as functional

        image = self.transform(image)
        image = functional.rotate(image, self.rotation)
        return self.preprocess(image)


class AugmentedManifestPatchDataset:
    def __init__(
        self,
        torch,
        manifest_path: str | Path,
        split: str,
        preprocess,
        augmented_views: int,
        seed: int,
        root_dir: str | Path | None = None,
    ):
        self.torch = torch
        self.manifest_path = Path(manifest_path)
        self.root_dir = Path(root_dir) if root_dir else self.manifest_path.parent
        self.rows = [row for row in read_manifest(self.manifest_path) if row.split == split]
        self.preprocess = preprocess
        self.augmented_views = augmented_views if split == "train" else 0
        self.seed = seed
        self.transforms = {
            view: ModerateHistologyTransform(torch, preprocess, view)
            for view in range(1, self.augmented_views + 1)
        }

    def __len__(self):
        return len(self.rows) * (1 + self.augmented_views)

    def __getitem__(self, index):
        views_per_patch = 1 + self.augmented_views
        row_index, view_index = divmod(index, views_per_patch)
        row = self.rows[row_index]
        image_path = Path(row.path)
        if not image_path.is_absolute() and not image_path.exists():
            image_path = self.root_dir / image_path
        image = Image.open(image_path).convert("RGB")

        if view_index == 0:
            tensor = self.preprocess(image)
        else:
            python_state = random.getstate()
            with self.torch.random.fork_rng(devices=[]):
                deterministic_seed = self.seed + row_index * 1009 + view_index * 9176
                random.seed(deterministic_seed)
                self.torch.manual_seed(deterministic_seed)
                tensor = self.transforms[view_index](image)
            random.setstate(python_state)

        record = row.to_dict()
        record["source_patch_id"] = row.patch_id
        record["augmentation_view"] = view_index
        if view_index:
            record["patch_id"] = f"{row.patch_id}::aug{view_index}"
        return tensor, int(row.label), record
