#!/usr/bin/env bash
# =============================================================================
#  run_daily.sh — Lance (ou reprend) la campagne de calibration.
#  Conçu pour être appelé une fois par jour par cron, mais lançable à la main.
#
#  Comportement : la campagne consomme le quota Gemini du jour puis s'arrête
#  d'elle-même ; la reprise (store SQLite) fait que le lendemain elle repart
#  exactement au point d'arrêt. Rien à surveiller.
#
#  Sortie journalisée dans ~/calib-logs/AAAA-MM-JJ.log
# =============================================================================
set -uo pipefail

REPO_DIR="${REPO_DIR:-$HOME/llm-agents-gama}"
VENV_DIR="${VENV_DIR:-$HOME/calib-venv}"
ENV_FILE="${ENV_FILE:-$HOME/calib.env}"
CONFIG="${CONFIG:-config/cloud.yaml}"
LOG_DIR="${LOG_DIR:-$HOME/calib-logs}"

CALIB_DIR="$REPO_DIR/scripts/prompt_calibration"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date +%F).log"

{
  echo "===== $(date -Is) : démarrage run_daily ====="

  # 1) Clé API (PROVIDER_KEYS__google_gemini31=...)
  if [ -f "$ENV_FILE" ]; then
    set -a; # shellcheck disable=SC1090
    source "$ENV_FILE"; set +a
  else
    echo "!! Fichier de clé absent : $ENV_FILE — voir cloud/env.example"; exit 1
  fi

  # 2) Environnement Python
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  # 3) Lancement depuis le dossier de calibration (chemins relatifs de la config)
  cd "$CALIB_DIR"
  python -m calibration.cli run --config "$CONFIG"
  code=$?

  echo "===== $(date -Is) : fin (code de sortie $code) ====="
  # Un code != 0 est ATTENDU quand le quota du jour est épuisé (429). Le cron
  # relancera demain ; la reprise repart au bon endroit.
} >> "$LOG_FILE" 2>&1
