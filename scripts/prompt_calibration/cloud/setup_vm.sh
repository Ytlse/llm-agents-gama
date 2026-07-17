#!/usr/bin/env bash
# =============================================================================
#  setup_vm.sh — Installe la calibration de prompt sur une VM Ubuntu vierge.
#  À lancer UNE SEULE FOIS, après s'être connecté en SSH à la VM.
#
#  Usage :
#     bash setup_vm.sh
#
#  Ce que le script fait :
#    1. installe git + python + venv (paquets système)
#    2. clone le dépôt du projet
#    3. crée un environnement Python isolé (venv) et installe les dépendances
#    4. rappelle les 2 étapes manuelles restantes (données + clé API)
#
#  Il ne touche à RIEN d'autre sur la machine et peut être relancé sans danger.
# =============================================================================
set -euo pipefail

# --- Réglages (modifiables) --------------------------------------------------
REPO_URL="${REPO_URL:-https://github.com/Ytlse/llm-agents-gama.git}"
REPO_DIR="${REPO_DIR:-$HOME/llm-agents-gama}"
VENV_DIR="${VENV_DIR:-$HOME/calib-venv}"
# -----------------------------------------------------------------------------

echo "==> 1/4  Paquets système (git, python, venv)"
sudo apt-get update -y
sudo apt-get install -y git python3 python3-venv python3-pip

echo "==> 2/4  Récupération du code"
if [ -d "$REPO_DIR/.git" ]; then
  echo "    Dépôt déjà présent — mise à jour (git pull)"
  git -C "$REPO_DIR" pull --ff-only || true
else
  git clone "$REPO_URL" "$REPO_DIR"
fi

echo "==> 3/4  Environnement Python isolé + dépendances"
python3 -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
# llm_module apporte les adaptateurs provider + ses dépendances (httpx, pydantic, ...)
pip install -e "$REPO_DIR/llm_module"
# dépendances propres à la calibration
pip install pandas numpy tqdm pyyaml
echo "    (dashboard optionnel : 'pip install streamlit' si tu veux l'IHM sur la VM)"

echo
echo "============================================================"
echo " Installation OK. Il reste 2 choses à faire À LA MAIN :"
echo "============================================================"
echo
echo " (A) Envoyer les jeux de données gelés (depuis TON PC, pas la VM) :"
echo "       gcloud compute scp data_to_upload.tar.gz calib-vm:~ --zone=<ZONE>"
echo "     puis, ici sur la VM :"
echo "       tar xzf ~/data_to_upload.tar.gz -C $REPO_DIR/scripts/prompt_calibration/"
echo
echo " (B) Renseigner la clé API Gemini :"
echo "       cp $REPO_DIR/scripts/prompt_calibration/cloud/env.example ~/calib.env"
echo "       nano ~/calib.env      # coller la clé, puis Ctrl+O, Entrée, Ctrl+X"
echo "       chmod 600 ~/calib.env"
echo
echo " Ensuite, tester un lancement :"
echo "       bash $REPO_DIR/scripts/prompt_calibration/cloud/run_daily.sh"
echo "============================================================"
