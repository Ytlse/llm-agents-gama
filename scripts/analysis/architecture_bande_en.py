#!/usr/bin/env python3
"""Traduit en anglais la bande basse de la figure d'architecture (figure 1 de l'article court).

Règle de langue, posée par l'auteur le 2026-09-22 : une figure anglaise dans la version
française ne gêne personne, une figure française dans la version anglaise se voit. Le corps
du schéma est déjà en anglais ; seule la bande de légende du bas portait cinq chaînes
françaises.

On les remplace sur place : la bande est à fond plat, donc un aplat prélevé sur le voisinage
suffit à effacer, et le texte est redessiné au même point de départ, à la même taille.

La source reste docs/paper/article/images/ (verrouillée, lue seulement). Le script écrit dans
les deux projets de l'article court et dans docs/paper/figures/.

⚠ Les coordonnées sont accordées à la version 3000x1688 de l'image. Si le schéma est
réexporté depuis Divers/architecture_proposée.pptx, il faut les reprendre — ou, mieux,
corriger la langue dans le pptx et jeter ce script.
"""
import os
from pathlib import Path

import matplotlib
from PIL import Image, ImageDraw, ImageFont

RACINE = Path("/Users/yvesb/Documents/Projects/llm-agents-gama")
TTF = Path(matplotlib.__file__).parent / "mpl-data/fonts/ttf"
SRC = RACINE / "docs/paper/article/images/architecture_GAMA_Agents.jpg"

# (x, y_haut, x_fin_effacement, y_bas, texte, gras, taille, couleur, point_de_prelevement)
REMPLACEMENTS = [
    (470, 1444, 760, 1490, "GAMA Agent",                        True,  46, "#1F4E79", (450, 1460)),
    (470, 1506, 860, 1543, "physical body · position · network",
                                                                False, 26, "#3C4450", (450, 1520)),
    (1470, 1418, 1545, 1452, "state",                           False, 26, "#3C4450", (1440, 1430)),
    (1864, 1444, 2320, 1490, "Python Server (LLM)",             True,  46, "#1F4E79", (1840, 1460)),
    (1864, 1506, 2280, 1543, "memory · reasoning · decision",
                                                                False, 26, "#3C4450", (1840, 1520)),
]

im = Image.open(SRC).convert("RGB")
d = ImageDraw.Draw(im)
for x, y0, x1, y1, texte, gras, taille, couleur, prelev in REMPLACEMENTS:
    fond = im.getpixel(prelev)
    d.rectangle([x - 6, y0 - 6, x1 + 6, y1], fill=fond)
    police = ImageFont.truetype(str(TTF / ("DejaVuSans-Bold.ttf" if gras else "DejaVuSans.ttf")), taille)
    # centrage vertical sur la boîte d'origine
    bbox = d.textbbox((0, 0), texte, font=police)
    dy = ((y1 - y0) - (bbox[3] - bbox[1])) // 2 - bbox[1]
    d.text((x, y0 + dy), texte, font=police, fill=couleur)

for dest in ("docs/paper/article-court/overleaf/images/architecture_GAMA_Agents.jpg",
             "docs/paper/article-court/overleaf-fr/images/architecture_GAMA_Agents.jpg",
             "docs/paper/figures/architecture_GAMA_Agents_en.jpg"):
    p = RACINE / dest
    p.parent.mkdir(parents=True, exist_ok=True)
    im.save(p, quality=95)
    print("écrit :", dest)
