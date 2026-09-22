#!/usr/bin/env bash
# Campagne du ticket 095 — les deux bras que la relecture AAMAS réclame.
#
# Bras 1, ABLATION : le choc est déclaré, mais le bloc « ce qui a changé récemment » est coupé.
#   Il répond à « l'effet observé tient donc au seul bloc de texte », qui n'est aujourd'hui
#   qu'une déduction par absence : le bloc n'a jamais été coupé. Si la part modale ne bouge pas,
#   la déduction devient une mesure.
#
# Bras 2, SEUIL : le seuil d'entrée passe de 0,70 à 0,49.
#   Il répond à « le négatif central est peut-être un artefact de seuil ». Si le concept né du
#   choc reste absent des prompts à 0,49, ce n'est pas le seuil qui l'écarte mais le classement.
#
# Les deux se comparent au bras traité du 2026-09-21 (archive 2026-09-21_15_13), qui sert de
# référence : même persona, mêmes graines, même choc, seul le réglage testé change.
set -euo pipefail
cd "$(dirname "$0")/../.."

PERSONA="${PERSONA:-861500}"
JOURS="${JOURS:-42}"
# Enquête QUOTIDIENNE (décision du 2026-09-21) : six questionnaires par jour simulé.
# Coût : ~252 appels par bras contre 24, soit environ +90 % du budget d'un bras.
export EXPERIMENT_SURVEY_DAYS="$(seq -s, 1 "$JOURS")"
export EXPERIMENT_SURVEY_MODES="voiture,transports_collectifs,velo,marche,train"

lancer() {  # $1 = identifiant, $2… = réglages à exporter
  local id="$1"; shift
  echo "════════ $id ════════"
  ( for kv in "$@"; do export "$kv"; done
    python3 scripts/experiment/run_sequential_cohort.py \
      --personas "$PERSONA" --branch treated --experiment-id "$id" )
}

# Bras 1 — le bloc de changements est coupé. Mode `fixe` + fenêtre 0 = ablation DÉCLARÉE :
# aucun souvenir de choc n'entre dans le bloc, y compris celui de l'instant même.
# La mémoire longue, elle, reste active — c'est tout l'intérêt du bras.
lancer "e3_ablation_bloc_${PERSONA}" \
  MEMOIRE__MODE_FENETRE_CHANGEMENTS=fixe \
  MEMOIRE__FENETRE_CHANGEMENTS_JOURS=0

# Bras 2 — seuil d'entrée abaissé, tout le reste identique à la référence du 21 septembre.
lancer "e3_seuil049_${PERSONA}" \
  MEMOIRE__IMPORTANCE_CHOC=0.49

echo "Les deux bras sont joués. Référence : experiments/archive/2026-09-21_15_13"
