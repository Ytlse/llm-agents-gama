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

**Ce qui est vérifié (relevé du 10 septembre 2026, refait le 14 sur le texte anglais).** Relevé exhaustif des nombres du `content` de la variante active `prompt_expert_16` (ex-`expert_m4`) de `mobility_llm/src/mobility_llm/prompts/prompts.yaml` : numérotation de la procédure (« in 4 steps », 1 à 4), format de sortie (probabilité de 0 à 100, somme valant exactement 100), et le nom « 48-hour rule », glosé aussitôt en question qualitative (« is the effort sustainable if the trip is repeated over two days? »). Le prompt a basculé en anglais au [ticket 074](../../tickets/ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md) ; le relevé a été refait sur le texte servi aujourd'hui, avec le même résultat. **Aucun opérateur de comparaison, aucun seuil sur une quantité calculée, aucun coefficient, aucune unité chiffrée hors « 48 heures ».** Aucune variante ne porte de pourcentage ni de part modale dans son `content` ; les valeurs mesurées du fichier vivent dans les blocs `_provenance` / `_neutralite`, qui ne sont pas envoyés au modèle. Les variantes non actives `prompt_expert_17` à `20` (ex-`expert_chaine_m5` à `m7.1`) ajoutent une bande de température descriptive (« between 3 and 25 °C »), sans prescription de mode.

**Où le placer — trois candidats, à trancher au moment d'écrire le chapitre.**
1. *Méthodes, description du palier 2.* Le plus naturel : l'énoncé qualifie le prompt là où il est présenté. Dans le manuscrit détaillé, cela tombe à côté de la description du palier 1 sous prompt factuel neutre et circonstancié, qui décrit déjà le palier voisin, ou en tête de § 4.1 « Étude d'Ablation en 4 Paliers ».
2. *Annexe portant le texte intégral du prompt.* Le plus solide : l'énoncé se vérifie sous les yeux du lecteur. Aucune annexe ne porte encore le prompt ; ce serait une annexe à créer, voisine de l'Annexe D « Bilan de la Calibration ».
3. *Discussion ou limites.* À réserver au cas où un relecteur soulève l'objection : la réponse y gagne en force d'être donnée en défense, mais elle arrive tard.
**Recommandation :** l'écrire une fois en méthodes (candidat 1), et laisser l'annexe du prompt (candidat 2) la porter en vérification.

**Ce que ça coûte.** Rien à mesurer, tout est vérifié. Le seul coût est de tenir l'énoncé à jour : il devient faux si une future version du prompt introduit un seuil ou un coefficient. À revérifier avant soumission par la même recherche (`[<>]=?\d`, « seuil », « supérieur », « inférieur », « au-delà », `\d+ *(km|min|€)`) sur la variante active.

**Pourquoi ce n'est pas dans l'introduction.** La section 3 dit déjà ce qui compte pour son argument, qu'aucun chiffre de l'enquête n'atteint le modèle. La version forte porte sur une autre question, la parenté avec les modèles de règles, qui n'a pas sa place dans le verrou.

**Décision du 10 septembre 2026.** Offert et retenu par l'auteur pour un chapitre à venir, emplacement non tranché (REMARQUES 3.6, point abandonné pour l'introduction).

---

## 5. Risque pour la reproductibilité AAMAS : données sous convention nominative et Supplementary Material (ZIP 25 Mo)

**Ce que c'est (remarque de relecture).** *« Risque pour la reproductibilité AAMAS : Si un relecteur ne peut pas rejouer les expériences parce que les données d'enquête sont sous embargo/convention nominative, le code et la cohorte synthétique scellée doivent être intégralement décrits et rendus reproductibles dans le Supplementary Material (ZIP anonyme de 25 Mo). »*

**Ce que le papier doit faire.** Les microdonnées brutes de l'enquête EMC² 2023 (`lil-1750`) ne peuvent pas être cédées ni redistribuées dans le ZIP de soumission ([`SOUMISSION_AAMAS_2027.md`](SOUMISSION_AAMAS_2027.md) § 3, [`../sources/ENGAGEMENT_DONNEES_EMC2.md`](../sources/ENGAGEMENT_DONNEES_EMC2.md)). Pour garantir une reproductibilité inattaquable lors de l'évaluation en double aveugle :
1. La cohorte synthétique scellée v6 (1 000 personas, 3 299 déplacements, anonymisée et générée par la chaîne eqasim/sélection par ménages) doit être fournie avec ses traits complets et son manifeste d'empreinte (`412efada…`).
2. Tout le code d'inférence, de calcul des métriques (`mobility_core`, `mobility_llm`), les configurations d'expériences (`experiments.yaml`), les graines de tirage et les scripts d'évaluation doivent être inclus dans l'archive ZIP anonyme (≤ 25 Mo).
3. L'article doit expliciter clairement la disjonction entre les microdonnées d'enquête protégées (qui servent d'étalon statistique externe de référence et d'entraînement pour les références tabulaires) et la cohorte synthétique entièrement réplicable par les tiers.

**Où le placer — trois points d'ancrage :**
1. *Chapitre 4, Section 4.5 & 4.7* ([`fr/04_metrics_and_substrate.md`](fr/04_metrics_and_substrate.md)) : expliciter la distinction données d'enquête protégées vs cohorte synthétique réplicable.
2. *Annexe G* ([`fr/99_annexes.md`](fr/99_annexes.md)) et [`SOUMISSION_AAMAS_2027.md`](SOUMISSION_AAMAS_2027.md) § 3 : cadrer la constitution du ZIP anonyme de 25 Mo.
3. *Rebuttal / Réponses aux relecteurs* : réponse formelle préparée en cas d'attaque sur la reproductibilité.

**Ce que ça coûte.** Aucun coût expérimental : la cohorte v6 et le code existent déjà. Le seul coût est de préparer l'archive anonymisée et de vérifier qu'aucun fichier du ZIP ne viole la convention `lil-1750`.

**Décision du 12 septembre 2026.** Consigné dans les actions pour l'écriture du papier.

---

## 6. Objection sur la portée de H0 : apport scientifique face au boosting tabulaire sur-spécialisé

**Ce que c'est (objection de relecture).** *« Prétendre que $H_0$ est une découverte majeure est exagéré : il est évident qu'un agent sous prompt factuel neutre et circonstancié ou légèrement prompté à la main ne peut pas battre un Gradient Boosted Tree (LightGBM) entraîné de façon supervisée sur 31 000 trajets locaux réels. Vous comparez un modèle non entraîné avec un modèle sur-spécialisé. Quel est l'apport scientifique réel au-delà de confirmer que le boosting tabulaire surpasse le zero-shot ? »*

**Ce que le papier doit faire (défense et positionnement).** L'article ne doit pas présenter $H_0$ comme la « surprise » d'une défaite du LLM face au boosting, mais comme une clarification méthodologique et une démonstration en deux volets :
1. **La réfutation formelle du discours ambiant (Tier 3 de SILICA) :** Une part importante de la littérature récente sur les agents génératifs (CitySim, AgentMove, travaux récents CHI/AAMAS) suggère ou laisse entendre que des agents LLM dotés de personas et de bon sens urbain capturent spontanément les comportements humains. $H_0$ à parité informationnelle (21 variables, offre physique OTP) apporte une mesure rigoureuse de la borne : le prompt engineering manuel ne franchit pas le plafond distributionnel sur l'impédance physique, et l'écart reste structurel.
2. **L'asymétrie d'exposition assumée et chiffrée :** L'article annonce dès le départ l'asymétrie (31 279 trajets vus par LightGBM contre zéro pour le LLM). La comparaison n'est pas un concours algorithmique asymétrique gratuit, c'est l'étalonnage de ce que coûte l'absence d'enquête locale (coût de transfert).
3. **L'apport scientifique au-delà du nominal (le véritable cœur du papier) :**
   - *Régimes non tabulés (Section 7) :* Là où LightGBM est totalement aveugle et amnésique (incapable d'intégrer une fermeture imprévue de station, une alerte canicule ou un article de presse locale sans ré-entraînement lourd), l'agent LLM démontre une adaptation qualitative et une inertie cognitive (hystérésis sur 5 jours).
   - *L'architecture hybride en cascade (Section 8) :* La conclusion logique n'est pas « jetons le LLM » mais « combinons-les » : 90 % des flux de routine traités instantanément par la référence tabulaire (0 token, fidélité parfaite), et 10 % de cas complexes, chocs ou forte incertitude délégués au LLM.

**Où le placer — trois points d'ancrage :**
1. *Chapitre 1 (§ 1.2 Le verrou, et § 1.3 C2/H0)* : désamorcer immédiatement en cadrant $H_0$ comme un plafond méthodologique et non une découverte de supériorité algorithmique naïve.
2. *Chapitre 6 (§ 6.2 et § 6.7)* : insister sur l'enseignement transférable (« bien classer l'enquête ne suffit pas à simuler la ville » et asymétrie d'exposition).
3. *Chapitre 8 (§ 8.1 Limites, § 8.2 & 8.3 Cascade hybride)* : réponse complète structurée en perspective hybride.
4. *Rebuttal AAMAS* : argumentaire prêt face à cette attaque prévisible.

**Décision du 12 septembre 2026.** Consigné dans les actions pour l'écriture du papier.

---

## 7. Formalisation compacte du dispositif agentique en remplacement de la description narrative

> ✅ **Appliqué le 15 septembre 2026** dans les trois arbres (`fr/`, `en/`, `overleaf/`), chapitre 3 en `brouillon v0.5` — quadruplet et tirage en notation, **espace d'action en clair** par décision de l'auteur du même jour.

**Ce que c'est (action de rédaction / standard AAMAS).** *« Remplacer la description narrative du dispositif par une formalisation propre en un bloc compact :*
$$\text{Agent}_i = \langle P_i, M_{i,t}, C_i, \pi_\theta \rangle$$
*où $P_i$ est le persona socio-démographique scellé, $M_{i,t}$ le registre de mémoire bi-composante (STM circulaire, LTM vectorielle), $C_i$ l'état de la chaîne de véhicules du ménage, et $\pi_\theta(a \mid o_t, M_{i,t})$ la distribution verbalisée sur l'espace d'action restreint $\mathcal{A}(o_t, C_i)$. »*

**Ce que le papier doit faire.** Le chapitre 3 actuel ([`fr/03_architecture.md`](fr/03_architecture.md)) est rédigé en style narratif issu de la v0.1. AAMAS exige une rigueur formelle (*Dual Core*) pour les architectures multi-agents :
1. Remplacer la prose narrative du § 3.1 par un bloc compact introduisant formellement le quadruplet $\text{Agent}_i = \langle P_i, M_{i,t}, C_i, \pi_\theta \rangle$.
2. Spécifier rigoureusement l'espace d'action contextuel $\mathcal{A}(o_t, C_i)$ : sous-ensemble des modes physiques offerts à l'instant $t$ par OpenTripPlanner et OSMnx sous la contrainte d'éligibilité et de localisation des véhicules $C_i$ (règles de chaîne).
3. Poser la décision comme un échantillonnage sur la distribution de probabilité verbalisée par le modèle : $a_t \sim \pi_\theta(\cdot \mid o_t, M_{i,t})$, garantissant la préservation de la diversité individuelle face aux modes déterministes.

**Où le placer.**
- *Chapitre 3, Section 3.1 & 3.3* ([`fr/03_architecture.md`](fr/03_architecture.md)) : remplacement direct de la narration en tête du chapitre.

**Décision du 12 septembre 2026.** Consigné dans les actions pour l'écriture du papier.

---

## Journal

- 8 septembre 2026 — création du fichier avec trois points, issus des décisions 4.3, 4.5 et 4.7 de la relecture de l'introduction.
- 10 septembre 2026 — point 4 ajouté : version forte sur l'absence de formule dans le prompt, vérifiée, à écrire dans un chapitre à venir (trois emplacements candidats, méthodes recommandé). Point 3 rafraîchi : il décrivait un état de l'introduction périmé depuis la v0.13.
- 15 septembre 2026 — point 7 appliqué : le quadruplet $\text{Agent}_i$ au § 3.1 du chapitre 3 et le tirage $a_t \sim \pi_\theta$ au § 3.3, dans les versions française, anglaise et LaTeX. L'espace d'action, en revanche, est **écrit en clair** : la notation $\mathcal{A}(o_t, C_i) \subseteq \mathcal{O}(o_t)$ a été posée puis retirée le jour même, décision de l'auteur, le fond étant conservé.
- 12 septembre 2026 — points 5, 6 et 7 ajoutés : point 5 sur le risque de reproductibilité AAMAS (embargo d'enquête / cohorte synthétique et code dans le ZIP de 25 Mo) ; point 6 sur l'objection de portée de H0 (prompt factuel neutre/calibré vs LightGBM supervisé sur 31k trajets) et la valorisation des apports hors nominal (régimes non tabulés et cascade hybride) ; point 7 sur la formalisation mathématique compacte du dispositif agentique ($\text{Agent}_i = \langle P_i, M_{i,t}, C_i, \pi_\theta \rangle$) en remplacement de la description narrative du chapitre 3.

---

## Benchmark multi-modèles — sorti du chapitre 5, puis revenu sous une autre forme

> **Mise à jour du 16 septembre 2026, même jour.** Le principe est **revenu au chapitre 5**, au
> § 5.2 : mesurer plusieurs modèles, et plusieurs générations d'un même fournisseur, parce qu'un
> écart obtenu sur un seul modèle ne dit pas s'il tient au modèle ou à la condition. Ce qui reste
> ici est l'**inventaire** ci-dessous, qui n'est pas publiable en l'état et dont la destination
> n'est pas tranchée. Le § 5.2 ne nomme que les bras réellement mesurés et porte la note
> « benchmark à compléter ».

### L'inventaire, tel qu'il occupait le chapitre

**Ce que c'était.** L'inventaire des voies d'inférence confrontées au prompt factuel neutre, qui
occupait le § 5.2 du chapitre 5 avant la restructuration du 15 septembre, puis son bas de fichier
comme texte conservé.
**Pourquoi il en sort.** À huit pages, un inventaire de fournisseurs est un catalogue et non un
argument ; et une liste de modèles décrit la fabrication de l'étude plutôt que sa mesure, ce que
la règle d'écriture du [README](README.md) exclut du corps d'un chapitre.
**Ce qu'il apporte encore.** Il répond à l'objection qu'un résultat tiendrait à un fournisseur ou
à une famille d'architectures. Les scores par modèle, eux, vivent au chapitre 6.
**Destination à trancher.** Annexe, ou tableau résumé au § 6.1 — question 3 du
[ticket 080](../../tickets/ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md).
Le texte n'est pas publiable en l'état.

**Aussi retiré du chapitre 5, et sans destination à trancher :** la note qui disait où était
passée la matière du chapitre lors de la restructuration — le protocole de variabilité à
$\tau = 0{,}0$ au chapitre 6 § 6.3, la calibration du prompt absorbée au § 5.2 et son fichier
`4.5` archivé. C'est de l'histoire de fabrication : elle vit dans `fr/README.md` et dans le dépôt.

<details>
<summary>Texte conservé</summary>

Afin de garantir que les résultats observés ne constituent pas un artefact propre à un fournisseur ou à une famille d'architectures, le benchmark confronté au prompt factuel neutre et circonstancié couvre l'ensemble des voies d'inférence orchestrées par la plateforme *Pilotage llm-agents-gama* :

1. Modèles propriétaires distants (API cloud) :
   * Google Gemini : `gemini-3.1-flash-lite` (juge de référence stabilisé de l'évaluation, seuil de quota journalier appliqué), `gemini-3.5-flash-lite` (variante de génération suivante), et `gemini-3.8-flash`.
   * Mistral AI : `mistral-small-latest` (inférence souveraine européenne, 60 req/min) et `mistral-large-2512` (modèle frontière à grand contexte, 30 req/min).
2. Modèles ouverts managés à haut débit (inférence LPU cloud) :
   * Qwen : `qwen/qwen3.6-27b` et `qwen/qwen3.8-27b` (servis via l'infrastructure Groq).
   * Grands modèles ouverts : `gpt-oss-120b` (servi via Cerebras et Groq) et famille Google Gemma (`gemma-4-31b` via Cerebras, `gemma-4-26b-a4b-it` et `gemma-4-31b-it` via Google).
3. Inférence locale déterministe sur poids ouverts (LM Studio sur machine hôte) :
   * Exécutés localement via un adaptateur standardisé OpenAI-compatible (`http://host.docker.internal:1234/v1`), garantissant l'indépendance intégrale vis-à-vis des quotas externes et la souveraineté absolue des données de mobilité :
     * Famille Qwen : `qwen/qwen3.8-27b` (quantifié MLX 4-bit, 27B, contexte 262k), `qwen3-vl-8b-instruct-mlx`, `qwen3-vl-32b-instruct-mlx`.
     * Famille Mistral : `mistralai/mistral-small-3.2` (24B, 4-bit), `mistralai/mistral-nemo-instruct-2407` (12B), `mistralai/mistral-7b-instruct-v0.3` (7B).
     * Modèles compacts et exploratoires : `google/gemma-4-e4b` (4B effectifs), `meta/muse-glimmer` (28B).
4. Décideur autonome Antigravity (sous-agents sans quota d'API) :
   * Exécution par délégation directe à des sous-agents autonomes via un protocole IPC local (`gemini-3.8-flash`, `claude-opus-4.6`), permettant de dérouler des expériences complètes sur la cohorte scellée sans dépendance aux quotas de requêtes externes.

Tous ces modèles sont soumis au même contrat unifié d'évaluation (mêmes 21 variables, même ordre randomisé des options OTP/OSM, même schéma de sortie JSON probabiliste).

</details>
