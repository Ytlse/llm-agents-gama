# Générateurs de planches

**On modifie le générateur, jamais le `.pptx`.** Un jeu de planches sans générateur se périme
en silence : `memoire_agents_mobilite.pptx` l'a démontré en trois jours, en continuant à
présenter comme des « angles morts » des manques déjà comblés.

## Les deux jeux

| Générateur | Sortie | Ce qu'il raconte |
|---|---|---|
| `architecture_memoire.js` | `Divers/architecture_proposée.pptx` | La spécification mémoire en **8 planches** — la version compacte, pour qui veut le mécanisme d'un coup d'œil. |
| `memoire_agents_mobilite.js` | `Divers/memoire_agents_mobilite.pptx` | **La vie d'un souvenir**, en **20 planches** — un seul cas (30 min de retard, mardi 17 h) suivi du trajet qui le crée à la décision du vendredi. |

`_charte.js` porte la palette, les polices, le gabarit et les quatre aides de tracé. Les deux
générateurs en dépendent : **une retouche y change les deux jeux**.

## Lancer

```bash
npm install pptxgenjs
node scripts/slides/memoire_agents_mobilite.js
```

La sortie par défaut est `Divers/<nom>.pptx`, quel que soit le répertoire d'où l'on lance. Un
chemin peut être passé en argument. *(Avant le 2026-09-21, le défaut était le répertoire
courant, ce qui déposait un `.pptx` orphelin à la racine du dépôt.)*

⚠ **Si la présentation est ouverte dans PowerPoint**, un fichier `~$<nom>.pptx` traîne à côté :
régénérer écraserait un fichier verrouillé. Fermer d'abord.

## L'épreuve à rejouer après toute retouche de `_charte.js`

Une modification de la charte ne doit rien changer à ce qu'elle ne vise pas. La vérification
porte sur le **XML des planches**, pas sur la taille du fichier : deux `.pptx` de même poids
peuvent différer, et deux `.pptx` identiques diffèrent toujours par leurs horodatages.

```bash
node scripts/slides/architecture_memoire.js /tmp/apres.pptx
mkdir -p /tmp/ref /tmp/new
unzip -qq -o "Divers/architecture_proposée.pptx" -d /tmp/ref
unzip -qq -o /tmp/apres.pptx -d /tmp/new
diff -rq /tmp/ref/ppt/slides /tmp/new/ppt/slides
```

Sortie vide = rien n'a bougé. Seuls `docProps/core.xml` et les classeurs Excel embarqués
diffèrent légitimement : ils portent l'horodatage de génération.

## Vérifier le rendu, et pas seulement le XML

Un texte qui déborde de sa carte ne se voit pas dans le XML. Trois débordements ont été
trouvés ainsi le 2026-09-21, dont une formule que Courier rendait plus large que prévu :

```bash
soffice --headless --convert-to pdf --outdir /tmp/render Divers/memoire_agents_mobilite.pptx
pdftoppm -png -r 72 -f 4 -l 4 /tmp/render/memoire_agents_mobilite.pdf /tmp/render/p
```

Commencer par les planches les plus denses en caractères — ce sont elles qui débordent.

## Les chiffres des planches

Ceux du deck « vie d'un souvenir » sont réunis dans l'objet `CAS`, en tête du générateur, et
ont été relevés **en exécutant** `llm/gravite.py`, pas recalculés à la main. Les revérifier
après toute modification des constantes de `settings.py` :

```bash
services/llm-agents/.venv/bin/python -c "from llm import gravite as g; I,_ = g.gravite_deterministe(retard_s=1800, incident_reseau=True); print(I, g.force_initiale(I), g.poids_temporel(3, g.force_initiale(I)))"
```

Attendu au 2026-09-21 : `0.7 14.56 0.8138…` — soit une gravité de 0,70, une durée de vie de
14,56 jours, et 81,4 % du poids restant trois jours après.

## Source de vérité du contenu

`docs/arch/memory-stm-ltm.md`, partie II, et `specs/ticket_071/`. Une planche qui avance un
chiffre le prend au code ou à ces documents, jamais à une planche antérieure.
