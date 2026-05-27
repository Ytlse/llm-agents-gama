FROM python:3.12-slim
 
WORKDIR /app
 
# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*
 
# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# Code source — copié en tant que package llm_module
COPY . ./llm_module/

 