from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import sys
from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_CONCH_REF = os.getenv("HISTO_CONCH_CHECKPOINT_REF", "hf_hub:MahmoodLab/conch")


@dataclass
class EnvironmentCheck:
    name: str
    ok: bool
    detail: str
    required: bool = True
    version: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the optional histopathology AI runtime."
    )
    parser.add_argument(
        "--checkpoint-ref",
        default=DEFAULT_CONCH_REF,
        help="CONCH checkpoint reference. Defaults to HISTO_CONCH_CHECKPOINT_REF or hf_hub:MahmoodLab/conch.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="Device used only by --load-conch. Default: auto.",
    )
    parser.add_argument(
        "--load-conch",
        action="store_true",
        help="Load CONCH and run a one-image embedding smoke test.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a compact text report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings, such as unsupported Python versions, as failures.",
    )
    return parser.parse_args()


def import_check(module_name: str, label: str, required: bool = True) -> EnvironmentCheck:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return EnvironmentCheck(
            name=label,
            ok=False,
            detail=f"{type(exc).__name__}: {exc}",
            required=required,
        )

    version = getattr(module, "__version__", None)
    return EnvironmentCheck(
        name=label,
        ok=True,
        detail="import ok",
        required=required,
        version=str(version) if version is not None else None,
    )


def python_runtime_check() -> EnvironmentCheck:
    version = platform.python_version()
    if sys.version_info >= (3, 13):
        return EnvironmentCheck(
            name="python_runtime",
            ok=False,
            detail=(
                "Python 3.13+ detected. PyTorch and CONCH wheels may be unavailable; "
                "use Python 3.10, 3.11, or 3.12 for this module."
            ),
            required=False,
            version=version,
        )

    return EnvironmentCheck(
        name="python_runtime",
        ok=True,
        detail="runtime version is suitable for PyTorch/CONCH",
        required=False,
        version=version,
    )


def torch_device_check() -> EnvironmentCheck:
    try:
        torch = importlib.import_module("torch")
    except Exception as exc:
        return EnvironmentCheck(
            name="torch_device",
            ok=False,
            detail=f"torch unavailable: {type(exc).__name__}: {exc}",
        )

    cuda_available = bool(torch.cuda.is_available())
    detail = "cuda available" if cuda_available else "cuda unavailable; CPU mode will be used"
    return EnvironmentCheck(
        name="torch_device",
        ok=True,
        detail=detail,
        required=False,
        version=getattr(torch.version, "cuda", None),
    )


def torchvision_pcam_check() -> EnvironmentCheck:
    try:
        torchvision = importlib.import_module("torchvision")
        getattr(torchvision.datasets, "PCAM")
    except Exception as exc:
        return EnvironmentCheck(
            name="torchvision_pcam",
            ok=False,
            detail=f"{type(exc).__name__}: {exc}",
        )

    return EnvironmentCheck(
        name="torchvision_pcam",
        ok=True,
        detail="torchvision.datasets.PCAM is available",
        version=getattr(torchvision, "__version__", None),
    )


def token_check() -> EnvironmentCheck:
    token_present = bool(os.getenv("HF_TOKEN") or os.getenv("HISTO_HF_TOKEN"))
    return EnvironmentCheck(
        name="hf_token",
        ok=True,
        detail=(
            "HF_TOKEN/HISTO_HF_TOKEN is configured"
            if token_present
            else "token not set; required for the default gated CONCH checkpoint"
        ),
        required=False,
    )


def resolve_device(torch: Any, requested: str) -> str:
    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is false")
    return requested


def conch_checkpoint_smoke_check(checkpoint_ref: str, requested_device: str) -> EnvironmentCheck:
    try:
        torch = importlib.import_module("torch")
        image_module = importlib.import_module("PIL.Image")
        conch_module = importlib.import_module("conch.open_clip_custom")
        create_model_from_pretrained = getattr(conch_module, "create_model_from_pretrained")

        device = resolve_device(torch, requested_device)
        kwargs = {}
        hf_token = os.getenv("HF_TOKEN") or os.getenv("HISTO_HF_TOKEN")
        if hf_token:
            kwargs["hf_auth_token"] = hf_token

        model, preprocess = create_model_from_pretrained(
            "conch_ViT-B-16",
            checkpoint_ref,
            **kwargs,
        )
        model.to(device)
        model.eval()

        image = image_module.new("RGB", (224, 224), color=(255, 255, 255))
        tensor = preprocess(image).unsqueeze(0).to(device)
        with torch.inference_mode():
            features = model.encode_image(
                tensor,
                proj_contrast=False,
                normalize=False,
            )

        return EnvironmentCheck(
            name="conch_checkpoint",
            ok=True,
            detail=f"loaded {checkpoint_ref} on {device}; embedding_shape={tuple(features.shape)}",
        )
    except Exception as exc:
        return EnvironmentCheck(
            name="conch_checkpoint",
            ok=False,
            detail=f"{type(exc).__name__}: {exc}",
        )


def collect_checks(load_conch: bool, checkpoint_ref: str, device: str) -> list[EnvironmentCheck]:
    checks = [
        python_runtime_check(),
        import_check("torch", "torch"),
        torch_device_check(),
        import_check("torchvision", "torchvision"),
        torchvision_pcam_check(),
        import_check("h5py", "h5py"),
        import_check("sklearn", "scikit_learn"),
        import_check("numpy", "numpy"),
        import_check("PIL", "pillow"),
        import_check("conch.open_clip_custom", "conch"),
        token_check(),
    ]

    if load_conch:
        checks.append(conch_checkpoint_smoke_check(checkpoint_ref, device))

    return checks


def build_payload(args: argparse.Namespace, checks: list[EnvironmentCheck]) -> dict[str, Any]:
    required_failures = [check for check in checks if check.required and not check.ok]
    warnings = [check for check in checks if not check.required and not check.ok]
    return {
        "ok": not required_failures and not (args.strict and warnings),
        "checkpoint_ref": args.checkpoint_ref,
        "load_conch": args.load_conch,
        "checks": [asdict(check) for check in checks],
    }


def print_text_report(payload: dict[str, Any]) -> None:
    print("[histopathology] AI environment validation")
    for check in payload["checks"]:
        marker = "OK" if check["ok"] else ("WARN" if not check["required"] else "FAIL")
        version = f" ({check['version']})" if check.get("version") else ""
        print(f"  [{marker}] {check['name']}{version}: {check['detail']}")
    print(f"[histopathology] overall: {'PASS' if payload['ok'] else 'FAIL'}")


def main() -> int:
    args = parse_args()
    checks = collect_checks(
        load_conch=args.load_conch,
        checkpoint_ref=args.checkpoint_ref,
        device=args.device,
    )
    payload = build_payload(args, checks)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print_text_report(payload)

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
