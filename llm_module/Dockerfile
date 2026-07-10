FROM python:3.12-slim

WORKDIR /app

# Couche de cache pip : les dépendances ne sont réinstallées que si requirements.txt change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source — copié en tant que package llm_module, puis installé (métadonnées +
# package-data) sans re-résoudre les dépendances.
COPY . ./llm_module/
RUN pip install --no-cache-dir --no-deps ./llm_module
