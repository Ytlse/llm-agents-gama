#!/usr/bin/env bash
# Enchaîne des expériences mémoire, une à la fois, pour une nuit sans surveillance.
#
#   make experience-memoire-nuit                  # toutes les expériences déclarées non terminées
#   make experience-memoire-nuit EXP="EXP1 EXP2"  # ou une file explicite, dans cet ordre
#
# Sans argument, la file est lue dans data/experiences_memoire/ : toute expérience déclarée
# depuis l'onglet « 🧠 Expériences Mémoire » dont l'état n'est pas « terminee », dans l'ordre de
# création. Une seule campagne à la fois (règle du 2026-09-16) : refus de démarrer si un
# orchestrateur tourne déjà. Chaque expérience passe par `make experience-memoire-lancer`, qui
# joue le bras traité puis le témoin et reprend un bras suspendu là où il s'était arrêté.
#
# Sur un code 7 (bras suspendu par le garde-fou du ticket 105), la cause se lit dans
# experiments/current/en_attente_quota.json :
#   - quota_journalier : passage à l'expérience suivante (elle peut appeler d'autres clés) ;
#   - replis_consecutifs ou decision_en_retard (saturation amont, HTTP 503 : le modèle ne
#     décide plus, ou pas avant l'heure d'un départ) : nouvel essai dans ATTENTE_S secondes ;
#     après ESSAIS_MAX suspensions de suite sans jour simulé gagné, passage à la suivante.
# Tout autre code : échec de cette expérience, passage à la suivante. La chaîne s'arrête au
# bout de la file. Une expérience suspendue se reprend en relançant la même commande.
#
# Journal : experiments/enchainement_nuit_<AAAAMMJJ_HHMM>.log (une ligne par étape, bilan final)
# et .detail.txt (sortie complète de make).
set -u

RACINE=${RACINE:-$(cd "$(dirname "$0")/../.." && pwd)}
ATTENTE_S=${ATTENTE_S:-1800}
ESSAIS_MAX=${ESSAIS_MAX:-6}

HORODATAGE=$(date +%Y%m%d_%H%M)
JOURNAL="$RACINE/experiments/enchainement_nuit_$HORODATAGE.log"          # résumé, une ligne par étape
DETAIL="$RACINE/experiments/enchainement_nuit_$HORODATAGE.detail.txt"    # sortie complète de make

log() { echo "$(date '+%F %T') $*" | tee -a "$JOURNAL"; }

if pgrep -f "orchestrateur_memoire.py|run_sequential_cohort.py|experiences (lancer|campagne)" >/dev/null; then
  log "[ALARME] une campagne tourne déjà (orchestrateur vivant) — refus : une seule à la fois."
  exit 1
fi

if [ $# -gt 0 ]; then
  EXPERIENCES=("$@")
else
  EXPERIENCES=()
  while IFS= read -r nom; do EXPERIENCES+=("$nom"); done < <(python3 - "$RACINE/data/experiences_memoire" <<'EOF'
import json, sys
from pathlib import Path
file = []
for d in Path(sys.argv[1]).iterdir():
    if not (d / "experience_memoire.yaml").is_file():
        continue
    try:
        etat = json.loads((d / "etat.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        etat = {}
    if etat.get("etat") == "terminee":
        continue
    file.append((etat.get("cree_le") or etat.get("debut") or "", d.stat().st_mtime, d.name))
for _, _, nom in sorted(file):
    print(nom)
EOF
)
fi
if [ ${#EXPERIENCES[@]} -eq 0 ]; then
  log "Aucune expérience à jouer : rien de déclaré, ou tout est terminé."
  exit 0
fi

reussies=(); echecs=(); suspendues=(); ignorees=()
debut_nuit=$(date +%s)

bilan() {
  log "BILAN — terminée(s) : ${#reussies[@]} ${reussies[*]:-}"
  log "BILAN — suspendue(s), à relancer : ${#suspendues[@]} ${suspendues[*]:-}"
  log "BILAN — en échec : ${#echecs[@]} ${echecs[*]:-} | ignorée(s) : ${#ignorees[@]} ${ignorees[*]:-}"
  log "BILAN — durée totale $(( ($(date +%s) - debut_nuit) / 60 )) min. Détail : $DETAIL"
}

# Imprime « motif|resume_at|jour_simule » du marqueur d'attente, s'il a été écrit après $1.
cause_suspension() {
  python3 - "$RACINE/experiments/current/en_attente_quota.json" "$1" <<'EOF'
import json, os, sys
chemin, depuis = sys.argv[1], float(sys.argv[2])
try:
    if os.path.getmtime(chemin) < depuis:
        raise FileNotFoundError(chemin)
    with open(chemin, encoding="utf-8") as f:
        d = json.load(f)
    print(f"{d.get('motif') or ''}|{d.get('resume_at') or ''}|{d.get('jour_simule') or ''}")
except (OSError, ValueError):
    print("||")
EOF
}

log "DÉBUT — ${#EXPERIENCES[@]} expérience(s) en file : ${EXPERIENCES[*]}"
log "réglages : ATTENTE_S=${ATTENTE_S} ESSAIS_MAX=${ESSAIS_MAX}"

for exp in "${EXPERIENCES[@]}"; do
  if [ ! -f "$RACINE/data/experiences_memoire/$exp/experience_memoire.yaml" ]; then
    log "[ALARME] $exp absente de data/experiences_memoire/ — ignorée"
    ignorees+=("$exp")
    continue
  fi

  sans_progres=0
  dernier_jour=""
  while :; do
    t0=$(date +%s)
    log "▶ $exp — lancement (suspensions sans progrès : ${sans_progres}/${ESSAIS_MAX})"
    (cd "$RACINE" && make experience-memoire-lancer EXP="$exp") >>"$DETAIL" 2>&1
    code=$?
    duree=$(( ($(date +%s) - t0) / 60 ))

    if [ $code -eq 0 ]; then
      log "✅ $exp TERMINÉE (bras traité puis témoin) en ${duree} min"
      reussies+=("$exp")
      break
    fi
    if [ $code -ne 7 ]; then
      log "[ALARME] ❌ $exp en ÉCHEC (code ${code}) après ${duree} min — voir $DETAIL ; expérience suivante"
      echecs+=("$exp")
      break
    fi

    IFS='|' read -r motif reprise jour <<<"$(cause_suspension "$t0")"
    log "⏸ $exp suspendue après ${duree} min — motif=${motif:-inconnu} jour_simulé=${jour:-?} réouverture=${reprise:-non annoncée}"

    if [ "$motif" = "quota_journalier" ]; then
      log "[ALARME] quota du jour épuisé pour $exp — expérience suivante"
      suspendues+=("$exp")
      break
    fi

    # Une suspension qui survient plus loin dans le run que la précédente n'est pas un blocage :
    # chaque reprise repart du dernier point de reprise, le compteur repart donc à un.
    if [ -n "$jour" ] && [ -n "$dernier_jour" ] && [ "$jour" -gt "$dernier_jour" ] 2>/dev/null; then
      sans_progres=1
    else
      sans_progres=$((sans_progres + 1))
    fi
    dernier_jour=$jour

    if [ "$sans_progres" -ge "$ESSAIS_MAX" ]; then
      log "[ALARME] $exp : ${ESSAIS_MAX} suspensions de suite sans jour simulé gagné — le modèle ne répond plus ; expérience suivante"
      suspendues+=("$exp")
      break
    fi
    log "nouvel essai de $exp dans $((ATTENTE_S / 60)) min"
    sleep "$ATTENTE_S"
  done
done

log "FIN — file épuisée"
bilan
