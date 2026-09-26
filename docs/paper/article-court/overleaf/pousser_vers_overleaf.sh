#!/usr/bin/env bash
# Pousse le projet LaTeX de l'article court vers Overleaf.
# Écrit le 2026-09-22.
#
# PRÉREQUIS : l'intégration git d'Overleaf est une fonction payante. Au premier
# push, git demande un identifiant : le login est l'adresse du compte Overleaf,
# le mot de passe est un *jeton git* à créer dans Account Settings > Git
# Integration. Le trousseau macOS le retient ensuite.
#
# ⚠ CE SCRIPT REMPLACE LE CONTENU DU PROJET OVERLEAF VISÉ.
#   Vérifier d'abord que 6ab2b04d969f20feb19984f8 n'est pas le projet de
#   l'article long : les deux ont un main.tex et un dossier chapters/, et le
#   push écraserait l'article long sans prévenir. En cas de doute, créer un
#   projet Overleaf neuf et remplacer l'identifiant ci-dessous.

set -euo pipefail

PROJET="${1:-6ab2b04d969f20feb19984f8}"
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRAVAIL="$(mktemp -d)/overleaf"

echo "Projet visé   : https://www.overleaf.com/project/$PROJET"
echo "Source locale : $SOURCE"
echo

git clone "https://git.overleaf.com/$PROJET" "$TRAVAIL"

echo
echo "--- Contenu actuel du projet Overleaf, avant écrasement ---"
(cd "$TRAVAIL" && git ls-files | head -40)
echo "-----------------------------------------------------------"
read -r -p "Remplacer ce contenu par l'article court ? [oui/non] " reponse
[ "$reponse" = "oui" ] || { echo "Abandon."; exit 1; }

# On efface le suivi git de tout sauf .git, puis on recopie la source.
(cd "$TRAVAIL" && git rm -r --quiet --ignore-unmatch .)
rsync -a --exclude '.git' --exclude 'pousser_vers_overleaf.sh' \
      --exclude '*.aux' --exclude '*.log' --exclude '*.out' --exclude '*.bbl' \
      --exclude '*.blg' --exclude '*.pdf' --exclude 'nobib.tex' \
      --exclude '*.meta.md' \
      "$SOURCE"/ "$TRAVAIL"/

cd "$TRAVAIL"
git add -A
git commit -m "Article court AAMAS 2027 : sections 0-7, cinq figures, quatre tableaux"
git push origin master

echo
echo "Poussé. Ouvrir https://www.overleaf.com/project/$PROJET et recompiler."
