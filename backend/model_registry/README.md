# Registro del modelo histopatologico

El checkpoint productivo no fue reemplazado. Docker sigue usando Stage 16 salvo
que se defina explicitamente `HISTO_CLASSIFIER_CHECKPOINT`.

## Candidato Stage 17

- Archivo: `checkpoints/tri_head_stage17_variant_c_augmented.pt`
- SHA-256: `1984A6A5EAAB068166098BEF5CC4833F0355C7B2C4ED9986F2B9DBF26B931080`
- Split: agrupado por paciente, semilla `20260607`, sin solapamiento.
- Umbral seleccionado en validacion: `0.35`.
- Temperature scaling: disponible, pero desactivado por defecto porque no mejoro
  de manera consistente en test.

Activacion controlada:

```dotenv
HISTO_CLASSIFIER_CHECKPOINT=/app/model_registry/checkpoints/tri_head_stage17_variant_c_augmented.pt
HISTO_CLASSIFIER_CONFIDENCE_THRESHOLD=0.90
HISTO_TUMOR_OPERATING_THRESHOLD=0.35
HISTO_USE_CHECKPOINT_CALIBRATION=false
```

Para volver al baseline basta con eliminar esas variables o restaurar la ruta
Stage 16 indicada en `model_manifest.json`.

Los resultados son una evaluacion tecnica interna de un componente educativo.
No constituyen validacion clinica, diagnostica, prospectiva ni regulatoria.

El manifest reproducible se conserva en
`manifests/camelyon17_manifest_stage17_patient_split_v1.csv`. Los reportes JSON
de A-D, distribucion del split y agregacion ROI estan en `reports/`.

La comparacion directa Stage 16 versus Stage 17 se encuentra en
`reports/stage16_vs_stage17_same_test.json`. Debe interpretarse con cautela:
las imagenes son comunes, pero Stage 16 habia visto parte de esos pacientes y
laminas durante su entrenamiento historico.
