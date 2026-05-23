#!/bin/sh
set -e

echo "[backend] Aplicando migraciones de base de datos..."
alembic upgrade head
echo "[backend] Migraciones aplicadas."

exec uvicorn app.main:app --host 0.0.0.0 --port 8001 "$@"
