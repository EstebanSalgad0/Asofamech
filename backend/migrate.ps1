# Ejecuta comandos de Alembic dentro del contenedor backend.
# El contenedor debe estar corriendo (docker compose up -d backend).
#
# Uso:
#   .\migrate.ps1                                   # aplica migraciones pendientes
#   .\migrate.ps1 current                           # muestra la revision actual
#   .\migrate.ps1 history                           # lista todas las migraciones
#   .\migrate.ps1 revision --autogenerate -m "msg"  # genera nueva migracion
#   .\migrate.ps1 downgrade -1                      # revierte la ultima migracion
#   .\migrate.ps1 stamp head                        # marca BD existente como head

$AlembicArgs = if ($args.Count -gt 0) { $args } else { @("upgrade", "head") }
docker compose exec backend alembic @AlembicArgs
