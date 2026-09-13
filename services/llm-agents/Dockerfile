FROM python:3.12-slim
 
WORKDIR /app
 
# Dépendances système minimales.
# libgomp1 : runtime OpenMP exigé par le wheel manylinux de lightgbm (décideur « modèle »).
# Sans lui le paquet s'installe mais `import lightgbm` échoue.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*
 
# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt
 
# Code source
COPY . .

 