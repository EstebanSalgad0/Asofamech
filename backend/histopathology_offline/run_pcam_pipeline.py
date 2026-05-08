from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONCH_REF = os.getenv("HISTO_CONCH_CHECKPOINT_REF", "hf_hub:MahmoodLab/conch")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the PCam -> CONCH embeddings -> binary head training pipeline."
    )
    parser.add_argument(
        "--pcam-root",
        help="PCam dataset root. Required unless --skip-extract is used.",
    )
    parser.add_argument("--artifacts-root", default="artifacts/histopathology")
    parser.add_argument("--checkpoint-ref", default=DEFAULT_CONCH_REF)
    parser.add_argument("--source", default="auto", choices=["auto", "torchvision", "hdf5"])
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--extract-batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--log-every", type=int, default=50)
    parser.add_argument("--limit-per-split", type=int)
    parser.add_argument(
        "--skip-existing-embeddings",
        action="store_true",
        help="Do not re-extract a split when pcam_<split>_embeddings.pt already exists.",
    )
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--train-batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument(
        "--skip-conch-smoke",
        action="store_true",
        help="Validate imports only; skip loading the CONCH checkpoint before extraction.",
    )
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--skip-train", action="store_true")
    parser.add_argument("--skip-evaluate", action="store_true")
    return parser.parse_args()


def backend_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BACKEND_DIR / path


def run_step(name: str, command: list[str]) -> None:
    print(f"[histopathology] step={name}", flush=True)
    print("[histopathology] command=" + " ".join(command), flush=True)

    env = os.environ.copy()
    python_path = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(BACKEND_DIR)
        if not python_path
        else os.pathsep.join([str(BACKEND_DIR), python_path])
    )

    completed = subprocess.run(command, cwd=BACKEND_DIR, env=env)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def maybe_add(command: list[str], flag: str, value) -> None:
    if value is not None:
        command.extend([flag, str(value)])


def write_manifest(args: argparse.Namespace, checkpoint: Path, metrics: Path) -> None:
    manifest_path = backend_path(args.artifacts_root) / "pcam_pipeline_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "checkpoint": str(checkpoint),
        "metrics": str(metrics),
        "checkpoint_ref": args.checkpoint_ref,
        "source": args.source,
        "histopathology_status_env": {
            "HISTO_CLASSIFIER_CHECKPOINT": str(checkpoint),
            "HISTO_CONCH_CHECKPOINT_REF": args.checkpoint_ref,
        },
    }
    manifest_path.write_text(json.dumps(payload, indent=2))
    print(f"[histopathology] manifest={manifest_path}")
    print(f"[histopathology] set HISTO_CLASSIFIER_CHECKPOINT={checkpoint}")


def main() -> int:
    args = parse_args()
    if not args.skip_extract and not args.pcam_root:
        raise SystemExit("--pcam-root is required unless --skip-extract is used")

    artifacts_root = backend_path(args.artifacts_root)
    embeddings_dir = artifacts_root / "embeddings"
    checkpoint = artifacts_root / "checkpoints" / "binary_head_pcam.pt"
    metrics = artifacts_root / "reports" / "metrics_test.json"
    python_executable = sys.executable

    if not args.skip_validate:
        command = [
            python_executable,
            "-m",
            "histopathology_offline.validate_ai_environment",
            "--checkpoint-ref",
            args.checkpoint_ref,
            "--device",
            args.device,
        ]
        if not args.skip_conch_smoke:
            command.append("--load-conch")
        run_step("validate_ai_environment", command)

    if not args.skip_extract:
        command = [
            python_executable,
            "-m",
            "histopathology_offline.extract_pcam_embeddings",
            "--pcam-root",
            str(args.pcam_root),
            "--output-dir",
            str(embeddings_dir),
            "--checkpoint-ref",
            args.checkpoint_ref,
            "--source",
            args.source,
            "--batch-size",
            str(args.extract_batch_size),
            "--num-workers",
            str(args.num_workers),
            "--log-every",
            str(args.log_every),
        ]
        if args.download:
            command.append("--download")
        if args.skip_existing_embeddings:
            command.append("--skip-existing")
        maybe_add(command, "--limit-per-split", args.limit_per_split)
        run_step("extract_pcam_embeddings", command)

    if not args.skip_train:
        command = [
            python_executable,
            "-m",
            "histopathology_offline.train_binary_head",
            "--embeddings-dir",
            str(embeddings_dir),
            "--output",
            str(checkpoint),
            "--epochs",
            str(args.epochs),
            "--batch-size",
            str(args.train_batch_size),
            "--lr",
            str(args.lr),
            "--weight-decay",
            str(args.weight_decay),
            "--seed",
            str(args.seed),
            "--device",
            args.device,
        ]
        run_step("train_binary_head", command)

    if not args.skip_evaluate:
        command = [
            python_executable,
            "-m",
            "histopathology_offline.evaluate_binary_head",
            "--embeddings",
            str(embeddings_dir / "pcam_test_embeddings.pt"),
            "--checkpoint",
            str(checkpoint),
            "--output",
            str(metrics),
            "--batch-size",
            str(args.train_batch_size),
            "--device",
            args.device,
        ]
        run_step("evaluate_binary_head", command)

    write_manifest(args, checkpoint, metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
