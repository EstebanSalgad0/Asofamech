FROM python:3.11-slim

WORKDIR /app

ARG INSTALL_HISTOPATHOLOGY_AI=false
ARG INSTALL_RAG_NEURAL=false

# System dependencies:
# - OpenSlide for whole-slide image access.
# - git is needed only when installing the optional CONCH package from GitHub.
RUN apt-get update && apt-get install -y \
    git \
    openslide-tools \
    libopenslide0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY requirements-histopathology.txt .
COPY requirements-rag-neural.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN if [ "$INSTALL_HISTOPATHOLOGY_AI" = "true" ]; then \
      pip install --no-cache-dir -r requirements-histopathology.txt; \
    fi
RUN if [ "$INSTALL_RAG_NEURAL" = "true" ]; then \
      pip install --no-cache-dir -r requirements-rag-neural.txt; \
    fi

COPY app ./app
COPY histopathology_offline ./histopathology_offline

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload", "--reload-dir", "/app/app"]
