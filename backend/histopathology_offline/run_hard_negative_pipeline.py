"""
Pipeline completo para mejorar el reconocimiento de zonas sin metastasis.

Pasos:
  1. Minar falsos positivos de CAMELYON17 (mine_camelyon17_false_positive_patches)
  2. Extraer embeddings CONCH del manifest minado (extract_manifest_embeddings)
  3. Entrenar cabeza 3-class MLP con hard negatives (train_manifest_head_3class)

Uso rapido:
  python run_hard_negative_pipeline.py \\
      --images-dir data/camelyon17/images \\
      --annotations-dir data/camelyon17/annotations \\
      --checkpoint artifacts/histopathology/checkpoints/tri_head_camelyon17_stage10_balanced_v1_weighted.pt

Para saltar pasos ya completados:
  --skip-mine        (ya tienes el manifest minado)
  --skip-extract     (ya tienes los embeddings)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
OFFLINE_DIR = Path(__file__).resolve().parent
DEFAULT_CONCH_REF = os.getenv("HISTO_CONCH_CHECKPOINT_REF", "hf_hub:MahmoodLab/conch")


def run(cmd: list[str], label: str) -> None:
    print(f"\n{'='*60}")
    print(f"[pipeline] {label}")
    print(f"[pipeline] cmd: {' '.join(str(c) for c in cmd)}")
    print("=" * 60)
    result = subprocess.run(cmd, cwd=BACKEND_DIR)
    if result.returncode != 0:
        raise SystemExit(f"[pipeline] FALLO en '{label}' (exit={result.returncode})")
    print(f"[pipeline] OK: {label}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline: minar hard negatives → embeddings → entrenar 3-class MLP."
    )
    # Paths
    parser.add_argument("--images-dir", default="data/camelyon17/images")
    parser.add_argument("--annotations-dir", default="data/camelyon17/annotations")
    parser.add_argument("--artifacts-root", default="artifacts/histopathology")
    parser.add_argument("--checkpoint", required=True, help="Checkpoint actual del modelo (para minar FP).")
    parser.add_argument("--conch-ref", default=DEFAULT_CONCH_REF)
    parser.add_argument("--output-checkpoint",
                        default="artifacts/histopathology/checkpoints/tri_head_hard_neg_mlp.pt")
    parser.add_argument("--output-report",
                        default="artifacts/histopathology/reports/tri_head_hard_neg_mlp_metrics.json")

    # Control de pasos
    parser.add_argument("--skip-mine", action="store_true", help="Omitir minado; usar manifest existente.")
    parser.add_argument("--skip-extract", action="store_true", help="Omitir extraccion; usar embeddings existentes.")
    parser.add_argument("--slide-ids", default="", help="IDs de slides a minar (CSV). Vacio = todos.")
    parser.add_argument("--negative-slide-ids", default="", help="Slides conocidas como negativas sin XML.")

    # Parametros de minado
    parser.add_argument("--patch-size", type=int, default=256)
    parser.add_argument("--sampled-per-slide", type=int, default=120)
    parser.add_argument("--hard-neg-per-slide", type=int, default=30)
    parser.add_argument("--min-tumor-score", type=float, default=0.45,
                        help="Score minimo para considerar patch como hard negative.")
    parser.add_argument("--tumor-margin", type=int, default=512)

    # Parametros de entrenamiento
    parser.add_argument("--manifest", default="")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--dropout", type=float, default=0.25)
    parser.add_argument("--label-smoothing", type=float, default=0.05)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--lr-scheduler", default="cosine", choices=["none", "cosine", "step"])
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--seed", type=int, default=37)

    # Extraccion de embeddings
    parser.add_argument("--extract-batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=0)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.artifacts_root)
    python = sys.executable

    mined_patches_dir = root / "camelyon17_patches_hard_neg_pipeline"
    manifest_path = (
        Path(args.manifest) if args.manifest
        else root / "manifests" / "hard_neg_pipeline_manifest.csv"
    )
    candidates_csv = root / "reports" / "hard_neg_pipeline_candidates.csv"
    report_mine = root / "reports" / "hard_neg_pipeline_mine_summary.json"
    embeddings_dir = root / "embeddings-hard-neg-pipeline"

    # ── Paso 1: Minar hard negatives ────────────────────────────────────────
    if not args.skip_mine:
        mine_cmd = [
            python, str(OFFLINE_DIR / "mine_camelyon17_false_positive_patches.py"),
            "--images-dir", args.images_dir,
            "--annotations-dir", args.annotations_dir,
            "--output-dir", str(mined_patches_dir),
            "--manifest", str(manifest_path),
            "--candidates-csv", str(candidates_csv),
            "--report", str(report_mine),
            "--classifier-checkpoint", args.checkpoint,
            "--conch-checkpoint-ref", args.conch_ref,
            "--patch-size", str(args.patch_size),
            "--sampled-patches-per-slide", str(args.sampled_per_slide),
            "--hard-negatives-per-slide", str(args.hard_neg_per_slide),
            "--min-tumor-score", str(args.min_tumor_score),
            "--tumor-margin", str(args.tumor_margin),
            "--seed", str(args.seed),
        ]
        if args.slide_ids:
            mine_cmd += ["--slide-ids", args.slide_ids]
        if args.negative_slide_ids:
            mine_cmd += ["--negative-slide-ids", args.negative_slide_ids]
        run(mine_cmd, "Paso 1: Minar hard negatives de CAMELYON17")

        # Mostrar resumen del minado
        if report_mine.exists():
            summary = json.loads(report_mine.read_text())
            print(f"  Slides procesadas : {summary.get('num_slides', '?')}")
            print(f"  Filas en manifest : {summary.get('rows', '?')}")
            print(f"  Por tipo negativo : {summary.get('by_hard_negative_type', {})}")
    else:
        print(f"[pipeline] Paso 1 omitido. Usando manifest: {manifest_path}")

    if not manifest_path.exists():
        raise SystemExit(f"[pipeline] Manifest no encontrado: {manifest_path}")

    # ── Paso 2: Extraer embeddings CONCH ────────────────────────────────────
    if not args.skip_extract:
        extract_cmd = [
            python, str(OFFLINE_DIR / "extract_manifest_embeddings.py"),
            "--manifest", str(manifest_path),
            "--output-dir", str(embeddings_dir),
            "--checkpoint-ref", args.conch_ref,
            "--batch-size", str(args.extract_batch_size),
            "--num-workers", str(args.num_workers),
        ]
        run(extract_cmd, "Paso 2: Extraer embeddings CONCH")
    else:
        print(f"[pipeline] Paso 2 omitido. Usando embeddings en: {embeddings_dir}")

    # ── Paso 3: Entrenar cabeza 3-class MLP ─────────────────────────────────
    train_cmd = [
        python, str(OFFLINE_DIR / "train_manifest_head_3class.py"),
        "--manifest", str(manifest_path),
        "--embeddings-dir", str(embeddings_dir),
        "--output", args.output_checkpoint,
        "--report", args.output_report,
        "--head-type", "mlp",
        "--hidden-dim", str(args.hidden_dim),
        "--dropout", str(args.dropout),
        "--epochs", str(args.epochs),
        "--batch-size", str(args.batch_size),
        "--lr", str(args.lr),
        "--selection-metric", "tumor_recall_minus_stroma_fp",
        "--class-weights",
        "--class-weight-power", "0.75",
        "--label-smoothing", str(args.label_smoothing),
        "--patience", str(args.patience),
        "--lr-scheduler", args.lr_scheduler,
        "--device", args.device,
        "--seed", str(args.seed),
    ]
    run(train_cmd, "Paso 3: Entrenar clasificador 3-class MLP con hard negatives")

    print("\n" + "=" * 60)
    print("[pipeline] Pipeline completado.")
    print(f"  Checkpoint: {args.output_checkpoint}")
    print(f"  Reporte   : {args.output_report}")
    print("=" * 60)
    print("\nPara activar el nuevo modelo, configura la variable de entorno:")
    print(f"  HISTO_CLASSIFIER_CHECKPOINT={args.output_checkpoint}")
    print("Y reinicia el backend:")
    print("  docker restart asofamech_backend")


if __name__ == "__main__":
    main()
