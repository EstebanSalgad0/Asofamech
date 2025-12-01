FROM rasa/rasa-sdk:3.7.0

WORKDIR /app

# Copiamos únicamente las acciones (no hace falta copiar el resto del proyecto)
COPY actions ./actions

# Si más adelante necesitas librerías extra para las actions,
# puedes agregar un requirements.txt y descomentar estas líneas:
# COPY requirements-actions.txt .
# RUN pip install --no-cache-dir -r requirements-actions.txt

# La imagen rasa-sdk ya tiene el entrypoint configurado,
# solo indicamos que arranque el servidor de acciones
CMD ["start", "--actions", "actions", "--port", "5055", "--cors", "*"]
