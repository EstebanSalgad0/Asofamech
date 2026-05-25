# Histopathology Offline Training Pipeline

Scripts for training and evaluating the CONCH-based patch classifier used by the ASOFAMECH histopathology module. All scripts run outside Docker on a machine with GPU access.

**Scope:** This classifier is trained on CAMELYON-style lymph node patches and is strictly for educational use. It does not produce diagnostic-grade predictions.

---

## Requirements

```bash
pip install -r backend/requirements-histopathology.txt
```

Requires:
- PyTorch ≥ 2.0 with CUDA (CPU works but is slow for extraction)
- `conch` package (MahmoodLab) — requires HuggingFace token for `MahmoodLab/conch`
- `scikit-learn`, `Pillow`, `openslide-python`
- CAMELYON17 whole-slide images or PCam HDF5 dataset

Verify the environment before starting:

```bash
cd backend
python -m histopathology_offline.validate_ai_environment
```

---

## Pipelines

### A — PCam (quick binary baseline)

Trains a binary classifier (metastatic / non-metastatic) directly from the PCam patch dataset.

```bash
python -m histopathology_offline.run_pcam_pipeline \
  --pcam-root /data/pcam \
  --artifacts-root artifacts/histopathology \
  --checkpoint-ref hf_hub:MahmoodLab/conch \
  --epochs 20 \
  --train-batch-size 256
```

Output: `artifacts/histopathology/checkpoints/pcam_binary_head.pt`

### B — CAMELYON17 manifest (3-class with stroma abstention)

This is the production pipeline used by the ASOFAMECH deployment.

**Step 1 — Build manifest from CAMELYON17 slides**

```bash
python -m histopathology_offline.build_camelyon17_official_manifest \
  --slides-dir /data/camelyon17/images \
  --annotations-dir /data/camelyon17/annotations \
  --output artifacts/histopathology/manifests/camelyon17_manifest.csv
```

**Step 2 — Convert XML tumor annotations**

```bash
python -m histopathology_offline.convert_camelyon17_annotations \
  --annotations-dir /data/camelyon17/annotations \
  --output-dir artifacts/histopathology/annotations_converted
```

**Step 3 — Extract CONCH embeddings**

```bash
python -m histopathology_offline.extract_manifest_embeddings \
  --manifest artifacts/histopathology/manifests/camelyon17_manifest.csv \
  --output-dir artifacts/histopathology/embeddings \
  --checkpoint-ref hf_hub:MahmoodLab/conch
```

To reuse embeddings already on disk without re-running CONCH:

```bash
python -m histopathology_offline.reuse_manifest_embeddings \
  --source artifacts/histopathology/embeddings \
  --target artifacts/histopathology/embeddings-hard-negative
```

**Step 4 — Mine hard negative stroma patches**

```bash
python -m histopathology_offline.run_hard_negative_pipeline \
  --slides-dir /data/camelyon17/images \
  --manifest artifacts/histopathology/manifests/camelyon17_manifest.csv
```

**Step 5 — Balance classes and merge manifests**

```bash
python -m histopathology_offline.balance_patch_manifest \
  --manifest artifacts/histopathology/manifests/camelyon17_manifest.csv \
  --output artifacts/histopathology/manifests/balanced_manifest.csv

python -m histopathology_offline.merge_patch_manifests \
  --manifests artifacts/histopathology/manifests/balanced_manifest.csv \
              artifacts/histopathology/manifests/hard_negatives.csv \
  --output artifacts/histopathology/manifests/final_manifest.csv
```

**Step 6 — Train the 3-class classifier**

```bash
python -m histopathology_offline.train_manifest_head_3class \
  --manifest artifacts/histopathology/manifests/final_manifest.csv \
  --embeddings-dir artifacts/histopathology/embeddings-hard-negative \
  --output artifacts/histopathology/checkpoints/tri_head_manifest.pt \
  --report artifacts/histopathology/reports/tri_head_metrics.json \
  --epochs 40 \
  --batch-size 256 \
  --lr 1e-3 \
  --head-type mlp \
  --hidden-dim 256 \
  --dropout 0.25 \
  --selection-metric tumor_recall_minus_stroma_fp \
  --class-weights \
  --label-smoothing 0.05 \
  --patience 8 \
  --lr-scheduler cosine
```

`--selection-metric tumor_recall_minus_stroma_fp` selects the epoch that maximises tumour recall while minimising stroma false positives — the recommended metric for this task.

---

## Evaluation

### Model + QC pipeline evaluation

```bash
python -m histopathology_offline.evaluate_manifest_model_with_qc \
  --manifest artifacts/histopathology/manifests/final_manifest.csv \
  --embeddings artifacts/histopathology/embeddings-hard-negative/manifest_test_embeddings.pt \
  --checkpoint artifacts/histopathology/checkpoints/tri_head_manifest.pt \
  --output artifacts/histopathology/reports/model_qc_eval.json \
  --splits test
```

Output includes: per-class precision/recall/F1, confusion matrix, QC rejection rate, and overall accuracy on evaluable patches only.

### CAMELYON17 slide-level evaluation

```bash
python -m histopathology_offline.evaluate_camelyon17_xml_predictions \
  --manifest artifacts/histopathology/manifests/final_manifest.csv \
  --checkpoint artifacts/histopathology/checkpoints/tri_head_manifest.pt
```

### QC thresholds audit (no model needed)

```bash
python -m histopathology_offline.evaluate_manifest_qc \
  --manifest artifacts/histopathology/manifests/final_manifest.csv
```

---

## Checkpoint format

The `torch.save()` checkpoint dict contains:

| Key | Type | Description |
|---|---|---|
| `state_dict` | dict | Model weights (compatible with `TriMLPClassifierHead`) |
| `feature_dim` | int | CONCH embedding dimension (512 for ViT-B-16) |
| `num_classes` | int | 2 or 3 |
| `head_type` | str | `"linear"` or `"mlp"` |
| `labels` | dict | `{"0": "no_metastasico", "1": "metastasico", "2": "estroma"}` |
| `class_names` | dict | Alias for `labels` |
| `training_mode` | str | Free-form training description |
| `validation` | dict\|None | Validation metrics at best epoch |
| `created_at` | str\|None | ISO-8601 timestamp |
| `hyperparameters` | dict | Training hyperparameters |

The `model_version` field exposed by the `/api/histopathology/status` endpoint is derived from the checkpoint filename stem (e.g. `tri_head_manifest`).

---

## Environment variables (runtime)

| Variable | Required | Description |
|---|---|---|
| `HISTO_CLASSIFIER_CHECKPOINT` | Yes | Absolute path to the `.pt` checkpoint |
| `HISTO_CONCH_CHECKPOINT_REF` | No | CONCH ref, default `hf_hub:MahmoodLab/conch` |
| `HF_TOKEN` or `HISTO_HF_TOKEN` | If private | HuggingFace token for CONCH |
| `HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD` | No | Min confidence (default 0.90) |

---

## Artifact directory layout

```
artifacts/histopathology/
├── checkpoints/
│   ├── tri_head_manifest.pt       # production checkpoint
│   └── pcam_binary_head.pt        # PCam baseline
├── embeddings/
│   └── manifest_{split}_embeddings.pt
├── embeddings-hard-negative/
│   └── manifest_{split}_embeddings.pt
├── manifests/
│   ├── camelyon17_manifest.csv
│   ├── balanced_manifest.csv
│   └── final_manifest.csv
└── reports/
    ├── tri_head_metrics.json
    └── model_qc_eval.json
```
