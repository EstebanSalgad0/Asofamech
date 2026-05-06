from pathlib import Path
from PIL import Image


class PCamDatasetAdapter:
    """Adapter that avoids coupling the module to one PCam loading mechanism."""

    def __init__(
        self,
        root: str,
        split: str,
        transform=None,
        source: str = "auto",
        download: bool = False,
    ):
        self.root = Path(root)
        self.split = split
        self.transform = transform
        self.source = source
        self.download = download
        self._dataset = None
        self._images = None
        self._labels = None
        self._x_path = None
        self._y_path = None
        self._length = None

        if source in ("auto", "torchvision"):
            try:
                from torchvision.datasets import PCAM

                self._dataset = PCAM(
                    root=str(self.root),
                    split=split,
                    transform=transform,
                    download=download,
                )
                return
            except Exception:
                if source == "torchvision":
                    raise

        self._load_hdf5()

    def _load_hdf5(self) -> None:
        try:
            import h5py
        except ImportError as exc:
            raise RuntimeError("h5py is required to load PCam from HDF5 files") from exc

        candidates_x = [
            self.root / f"camelyonpatch_level_2_split_{self.split}_x.h5",
            self.root / "pcam" / f"camelyonpatch_level_2_split_{self.split}_x.h5",
        ]
        candidates_y = [
            self.root / f"camelyonpatch_level_2_split_{self.split}_y.h5",
            self.root / "pcam" / f"camelyonpatch_level_2_split_{self.split}_y.h5",
        ]

        x_path = next((path for path in candidates_x if path.exists()), None)
        y_path = next((path for path in candidates_y if path.exists()), None)

        if x_path is None or y_path is None:
            raise FileNotFoundError(
                "PCam HDF5 files were not found. Expected files like "
                f"camelyonpatch_level_2_split_{self.split}_x.h5 and "
                f"camelyonpatch_level_2_split_{self.split}_y.h5"
            )

        self._x_path = x_path
        self._y_path = y_path

        with h5py.File(y_path, "r") as y_file:
            self._length = len(y_file["y"])

    def _ensure_hdf5_open(self) -> None:
        if self._images is not None and self._labels is not None:
            return

        import h5py

        self._x_file = h5py.File(self._x_path, "r")
        self._y_file = h5py.File(self._y_path, "r")
        self._images = self._x_file["x"]
        self._labels = self._y_file["y"]

    def __len__(self) -> int:
        if self._dataset is not None:
            return len(self._dataset)
        return self._length

    def __getitem__(self, index: int):
        if self._dataset is not None:
            return self._dataset[index]

        self._ensure_hdf5_open()
        image = Image.fromarray(self._images[index]).convert("RGB")
        label = int(self._labels[index].reshape(-1)[0])

        if self.transform is not None:
            image = self.transform(image)

        return image, label

    def close(self) -> None:
        for handle_name in ("_x_file", "_y_file"):
            handle = getattr(self, handle_name, None)
            if handle is not None:
                handle.close()
