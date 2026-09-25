#!/usr/bin/env bash
# Script pour lancer la seconde graine (graine 123) sur la cohorte c1
# pour obtenir exactement deux graines par expérience (42 et 123)
# sur les 4 conditions du Tableau 1 :
# - Minimal prompt x mistral-large  (graine 123 à lancer)
# - Minimal prompt x gemini-3.1     (graine 123 à lancer)
# - Expert prompt x gemini-3.1      (graine 123 à lancer)
# - Expert prompt x mistral-large   (graine 123 DÉJÀ TERMINÉE le 24/09)
set -euo pipefail

RACINE="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RACINE"

EXPERIENCES=(
  "exp_gemini-31-fl_proexp05_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_go123_gt123_gc123_t0_nosim"
  "exp_gemini-31-fl_promin02_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_go123_gt123_gc123_t0_nosim"
  "exp_mistral-l-25_promin02_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_c_go123_gt123_gc123_t0_nosim"
)

echo "════════════════════════════════════════════════════════════════════════════════"
echo " Lancement de la 2e graine (graine 123) — 2 graines par expérience au total"
echo " (Note: Expert prompt x mistral-large a déjà ses 2 graines 42 et 123 terminées)"
echo "════════════════════════════════════════════════════════════════════════════════"

for exp in "${EXPERIENCES[@]}"; do
  echo ""
  echo "▶ Vérification / Lancement de : $exp"
  make experience-lancer EXP="$exp" ATTENDRE_FENETRE=1
done

echo ""
echo "✅ Toutes les 2es graines sont traitées."
