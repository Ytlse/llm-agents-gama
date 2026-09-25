# ──────────────────────────────────────────────────────────────────────────────
# Article court — chaîne de traduction et de rendu LaTeX (agent article-translator)
# ──────────────────────────────────────────────────────────────────────────────
#
# L'anglais fait foi (consigne R17). La traduction ne passe pas par un modèle de
# langue : elle se fait dehors et revient par fichier. Ces cibles ne font que
# déplacer du texte et vérifier qu'il n'a rien perdu en route.
#
# Chaîne : sections/NN.en.md → lot → traducteur → sections/NN.fr.md → les deux .tex

COURT      := docs/paper/article-court
COURT_OUT  := $(COURT)/outils
FR_MD       = $(shell ls $(COURT)/sections | grep '^$(S)_' | head -1 | sed 's/\.en\.md/.fr.md/')

## Sort le texte d'une section à confier à un traducteur. Usage: make paper-court-extraire S=01
paper-court-extraire:
	python3 $(COURT_OUT)/extraire_blocs.py --section $(S)

## Repose une traduction reçue dans le français. Usage: make paper-court-injecter S=01 FR=<fichier>
paper-court-injecter:
	python3 $(COURT_OUT)/injecter_traduction.py --section $(S) \
		--texte $(or $(FR),$(COURT)/traductions/$(shell ls $(COURT)/sections | grep '^$(S)_' | head -1 | sed 's/\.en\.md//').traduit.txt)

## Passe complète : injection de la traduction. Usage: make paper-court-passe S=01 FR=<fichier>
#
# AUCUN contrôle de forme sur le français. Les consignes R1, R2, R10, R11 et le détecteur
# d'écriture générée portent sur l'ANGLAIS, qui est le texte soumis ; le français est une
# version de lecture, faite pour comprendre l'anglais (décision de l'auteur, 2026-09-23).
# Le seul contrôle gardé est celui qui protège la FIDÉLITÉ, et il bloque :
#   · les chiffres du master se retrouvent tous dans le rendu   (injecter_traduction.py)
#
# LE REPORT VERS LE LATEX N'EST PLUS OUTILLÉ. md_vers_tex.py a été supprimé le 2026-09-23 :
# il ne savait traiter que deux chapitres sur huit, et sur un troisième il proposait un
# report qui cassait les renvois. Les .tex se tiennent à la main, et la date d'en-tête de
# chaque chapitre dit s'il est en phase avec son master (docs/paper/article-court/sections/
# README.md). Sont partis avec lui : paper-court-tex, paper-court-tex-ecrire et
# paper-court-tex-verifier — ce dernier était le seul contrôle automatique des citations et
# des renvois sur les seize chapitres, et rien ne le remplace aujourd'hui.
paper-court-passe:
	@$(MAKE) --no-print-directory paper-court-injecter S=$(S) FR=$(FR)

.PHONY: paper-court-extraire paper-court-injecter paper-court-passe
