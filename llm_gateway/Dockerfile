# Image du gateway LLM (services api, worker, flower du docker-compose).
# Contexte de build = racine du dépôt : l'image embarque les trois paquets, car le worker
# a besoin du bundle de catégories (mobility_llm) et de son domaine (mobility_core).
#   docker build -f llm_gateway/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

# Couche de cache pip : les dépendances tierces ne sont réinstallées que si
# requirements.txt change.
COPY llm_gateway/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Les trois paquets, installés sans re-résoudre les dépendances (déjà dans la couche
# précédente). Les métadonnées (entry point llm_gateway.categories) viennent de là ; en
# développement, docker-compose monte les sources par-dessus sous /app/<paquet>, qui
# précède site-packages sur le sys.path (WORKDIR).
COPY mobility_core ./build/mobility_core
COPY llm_gateway   ./build/llm_gateway
COPY mobility_llm  ./build/mobility_llm
RUN pip install --no-cache-dir --no-deps ./build/mobility_core ./build/llm_gateway ./build/mobility_llm \
 && rm -rf ./build

# Utilisateur non privilégié : rien dans l'image n'exige root.
RUN useradd --create-home --uid 1000 gateway
USER gateway

EXPOSE 8000
CMD ["uvicorn", "llm_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
