#!/bin/sh
set -e

# Genera /env-config.js en runtime para que el navegador pueda leerlo.
# API_BASE vacio usa el mismo origen y permite que nginx reenvie /api al backend.
cat > /usr/share/nginx/html/env-config.js <<EOF
window.__ASOFAMECH_CONFIG__ = { "API_BASE": "${API_BASE-}" };
EOF

exec nginx -g "daemon off;"
