// Configuración de runtime (sobreescrita por docker-entrypoint.sh en Docker).
// En desarrollo local esta variable queda vacía y authClient.js usa VITE_API_BASE de .env.local.
window.__ASOFAMECH_CONFIG__ = window.__ASOFAMECH_CONFIG__ || {};
