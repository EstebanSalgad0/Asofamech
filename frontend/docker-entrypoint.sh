#!/bin/sh
set -e

# Genera /env-config.js en runtime para que el navegador pueda leerlo.
# Esto permite cambiar API_BASE sin reconstruir la imagen Docker.
cat > /usr/share/nginx/html/env-config.js <<EOF
window.__ASOFAMECH_CONFIG__ = { "API_BASE": "${API_BASE:-http://localhost:8001}" };
EOF

exec nginx -g "daemon off;"
