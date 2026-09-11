# Points de consolidation — retirés de l'introduction, à reprendre plus tard

**Objet :** éléments du protocole que l'auteur a retirés de l'introduction le 8 septembre 2026 faute de temps, mais qui restent scientifiquement utiles. Chaque point dit ce qu'il apporte, ce qu'il coûte, et ce qu'il faudrait faire pour le réintégrer. À reprendre si le calendrier le permet, sinon à mentionner en travaux futurs.
**Fichiers liés :** [`REMARQUES_INTRODUCTION.md`](relecture/01_introduction.md) (décisions), [`PROTOCOLE_SCIENTIFIQUE.md`](../methode/PROTOCOLE_SCIENTIFIQUE.md) et [`PLAN_ARTICLE_2026.md`](plan/PLAN.md) (qui portent encore ces éléments : à aligner), [`experience_plan/experiments.yaml`](../methode/experience_plan/experiments.yaml).

---

## 1. Effectif publié avec chaque score, et témoin sans modèle (ex‑règle 4 du contrat)

**Ce que c'était.** La quatrième règle du contrat d'évaluation : aucun score sans son nombre de décisions, et toute comparaison entre substrats accompagnée d'un « témoin sans modèle » qui rejoue la comparaison à décisions inchangées pour isoler l'effet de l'échantillon. Motivation : les divergences (L1, JSD, EMD) sont biaisées vers le haut sur les petites strates ; le protocole § 3.2 cite un passage de 881 à 81 personnes qui dégrade le composite de 5,02 points à décisions identiques.
**Ce qui est gratuit.** Publier l'effectif : `scores.json` de chaque exécution contient déjà `couverture.decides` et `global.n_agents`. Une colonne dans les tableaux suffit.
**Ce qui coûte.** Le témoin sans modèle : une exécution supplémentaire par comparaison de substrats, et une règle de rédaction à tenir.
**Pour réintégrer.** Rétablir la règle en deux phrases dans C1 ; ajouter la colonne d'effectif à l'export des tableaux ; décider si le témoin est produit pour la seule comparaison de substrats prévue (population scellée contre vivier).
**Décision du 8 septembre 2026.** Retiré de l'introduction (REMARQUES 4.3). Le protocole § 3.2 règle 3 le garde : à aligner.

## 2. Condition « temps terminal » et hypothèse H1, primauté de l'impédance physique

**Ce que c'était.** H1 : un changement des temps terminaux que le calculateur d'itinéraires attribue à l'accès et au stationnement déplace la répartition modale des agents davantage que l'enrichissement du prompt. Test : sur les mêmes personas, comparer le déplacement dû au passage nu → calibré au déplacement dû au changement des temps terminaux, par test apparié, avec dispersion inter‑graines.
**Ce qu'on sait déjà.** Sur le run GAMA du 24 août 2026, abaisser le temps terminal voiture de 7,93 à 0,55 min a fait gagner 4,52 points de composite, périmètre partiel ; la variante adoptée en production (voiture et vélo alignés) en gagne 2,17. Ces mesures sont sur un autre substrat que la population scellée et ne sont pas publiables telles quelles (`docs/changelog.md`, 24–25 août).
**Ce qui coûte.** Une exécution sur le substrat scellé avec des temps terminaux modifiés : environ 100 requêtes groupées, un cinquième du quota journalier d'une clé Google. Et une entrée dans `experiments.yaml` (aucune n'existe aujourd'hui).
**Pour réintégrer.** Créer l'expérience `exp_02c_terminal_time` (même gabarit que `exp_01a`, tolérances de temps terminal modifiées), la jouer, rétablir H1 dans C2 et le tag **[xx.y | exp_02c]**.
**Décision du 8 septembre 2026.** Retiré de l'introduction (REMARQUES 4.7). Le manuscrit § 4.2 et le protocole gardent l'argument : à aligner.

## 3. Condition few‑shot : *k* exemples réels de l'enquête dans le prompt

**Ce que c'était.** Un palier 2 bis : le même LLM reçoit *k* trajets réels de l'enquête (persona et mode observé) en contexte. Elle sépare « le LLM ne peut pas » de « le LLM n'a pas été informé » : si la condition few‑shot rejoint la marge d'équivalence de la référence tabulaire, le plafond est informationnel ; sinon il est structurel. C'était le critère de réfutation de H0 le plus net, et la littérature d'alignement (Kambhatla et al., 2025 ; Huang, Li & Shao, 2025) montre que ce type de supervision légère déplace les distributions.
**Ce qui coûte.** Une exécution : `exp_02b_few_shot_emc2_gemini` existe déjà dans `experiments.yaml` (1 000 trajets, 100 requêtes, prompt d'environ 1 350 jetons). Le coût principal est de choisir et de figer les *k* exemples sans fuite vers le jeu évalué.
**Ce qui change sans elle.** H0 se réfute désormais seulement si la condition calibrée entre dans la marge d'équivalence. Un relecteur pourra objecter que l'écart mesuré tient au manque d'information locale, pas à une limite du modèle. *Mise à jour du 10 septembre 2026 :* la phrase « l'introduction déclare que les agents ne sont pas supervisés par des données d'enquête » n'est plus vraie — depuis la v0.13, la section 3 nomme la calibration au lieu de la nier (REMARQUES 3.1).
**Pour réintégrer.** Jouer `exp_02b`, rétablir la phrase dans C2, le tag et le critère de réfutation « informationnel contre structurel ».
**Décision du 8 septembre 2026.** Retiré de l'introduction à la demande de l'auteur (REMARQUES 4.5). Le protocole § 4 « palier 2 bis » et `experiments.yaml` le gardent : à aligner ou à conserver comme travail futur.

---

## 4. Version forte : le prompt ne contient aucune formule de décision

**Ce que c'est.** Un énoncé de deux phrases, à placer dans un chapitre à venir : *le prompt système ne contient aucune formule de décision, aucun seuil et aucun coefficient ; ses seuls nombres décrivent la procédure d'analyse et le format de sortie.* Il répond de front au reproche que l'article adresse lui-même aux approches classiques en section 1 §3, « rigid models with fixed heuristics » : notre palier calibré n'est pas un modèle de règles déguisé.

**Ce qui est vérifié (10 septembre 2026).** Relevé exhaustif des nombres du `content` de la variante active `expert_chaine` de `mobility_llm/src/mobility_llm/prompts/prompts.yaml` : numérotation de la procédure (« en 4 étapes », 1 à 4), format de sortie (probabilité de 0 à 100, somme valant exactement 100), et le nom « règle des 48 heures », glosé aussitôt en question qualitative (« l'effort est-il soutenable si le trajet est répété sur deux jours ? »). **Aucun opérateur de comparaison, aucun seuil sur une quantité calculée, aucun coefficient, aucune unité chiffrée hors « 48 heures ».** Aucune variante ne porte de pourcentage ni de part modale dans son `content` ; les valeurs mesurées du fichier vivent dans les blocs `_provenance` / `_neutralite`, qui ne sont pas envoyés au modèle. Les variantes non actives `expert_chaine_m5` à `m7.1` ajoutent une bande de température descriptive (« entre 3 et 25 °C »), sans prescription de mode.

**Où le placer — trois candidats, à trancher au moment d'écrire le chapitre.**
1. *Méthodes, description du palier 2.* Le plus naturel : l'énoncé qualifie le prompt là où il est présenté. Dans le manuscrit détaillé, cela tombe à côté de [`MANUSCRIT_DETAILLE_2026.md`](../archive/MANUSCRIT_DETAILLE_2026_v1.6.md) § 3.1 « Définition du Modèle Nu », qui décrit déjà le palier voisin, ou en tête de § 4.1 « Étude d'Ablation en 4 Paliers ».
2. *Annexe portant le texte intégral du prompt.* Le plus solide : l'énoncé se vérifie sous les yeux du lecteur. Aucune annexe ne porte encore le prompt ; ce serait une annexe à créer, voisine de l'Annexe D « Bilan de la Calibration ».
3. *Discussion ou limites.* À réserver au cas où un relecteur soulève l'objection : la réponse y gagne en force d'être donnée en défense, mais elle arrive tard.
**Recommandation :** l'écrire une fois en méthodes (candidat 1), et laisser l'annexe du prompt (candidat 2) la porter en vérification.

**Ce que ça coûte.** Rien à mesurer, tout est vérifié. Le seul coût est de tenir l'énoncé à jour : il devient faux si une future version du prompt introduit un seuil ou un coefficient. À revérifier avant soumission par la même recherche (`[<>]=?\d`, « seuil », « supérieur », « inférieur », « au-delà », `\d+ *(km|min|€)`) sur la variante active.

**Pourquoi ce n'est pas dans l'introduction.** La section 3 dit déjà ce qui compte pour son argument, qu'aucun chiffre de l'enquête n'atteint le modèle. La version forte porte sur une autre question, la parenté avec les modèles de règles, qui n'a pas sa place dans le verrou.

**Décision du 10 septembre 2026.** Offert et retenu par l'auteur pour un chapitre à venir, emplacement non tranché (REMARQUES 3.6, point abandonné pour l'introduction).

---

## Journal

- 8 septembre 2026 — création du fichier avec trois points, issus des décisions 4.3, 4.5 et 4.7 de la relecture de l'introduction.
- 10 septembre 2026 — point 4 ajouté : version forte sur l'absence de formule dans le prompt, vérifiée, à écrire dans un chapitre à venir (trois emplacements candidats, méthodes recommandé). Point 3 rafraîchi : il décrivait un état de l'introduction périmé depuis la v0.13.
