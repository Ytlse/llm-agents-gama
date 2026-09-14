# Annexes techniques (brouillon)

<!-- Dernière mise à jour : 2026-09-11 -->

**Document :** brouillon français du chapitre, extrait de `MANUSCRIT_DETAILLE_2026.md` `v1.6` (3 septembre 2026), Annexes Techniques — « Annexes Techniques ». Le manuscrit entier est figé dans [`../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md`](../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md).
**Statut :** `brouillon v0` — texte **antérieur** à la réécriture de l'introduction (dont la v0.1 date du 8 septembre 2026). Trois choses à reprendre avant d'en faire un chapitre : le vocabulaire « Tier 1 / 2 / 3 », que les chapitres rédigés remplacent par *exploratory / robust / transferable* (étapes de certification de SILICA) ; les chiffres, à recouper depuis leur source dans le dépôt et non recopiés d'ici ; les renvois de section, qui suivent l'ancienne numérotation du manuscrit. Ni maître anglais ni rendu LaTeX à ce stade. **Ajout du 11 septembre 2026 :** l'annexe G, écrite hors manuscrit, porte la source des données d'enquête, sa citation et les engagements de la convention `lil-1750`.
**Place dans l'article :** section du même numéro dans le plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). État d'avancement : [`../README.md`](../README.md).

---

### Annexe A : Synthèse des Quotas API & Plateforme Antigravity
L'inférence s'appuie sur le gateway API SWRR (`llm_module`, 11 instances, 206 RPM / 37 700+ RPD) et l'environnement agentique Google Antigravity (Gemini 3.6 Flash / 3.5 Flash Lite, contexte 1M tokens, sous-agents isolés).

### Annexe B : Script d'Évaluation sur Enquête (`eval_llm_on_survey.py`)
Script d'inférence en aveugle sur $13\,045$ trajets scellés de l'enquête EMC² 2023.

### Annexe C : Configuration Inférence Locale Qwen-32B
Serveur vLLM `Qwen/Qwen2.5-32B-Instruct-AWQ` à $\tau=0.0$ et seed fixée.

### Annexe D : Bilan de la Calibration & Justification du Pivot
Paysage de perte non convexe justifiant le pivot vers l'architecture hybride.

### Annexe E : Dictionnaire des 21 variables du contrat d'évaluation

Le contrat de parité de la section 4.2 désigne ces 21 variables, et elles seules. La liste est figée
dans le dépôt (`spec_version 2`) et c'est ce même fichier qui construit la matrice de dessin des
quatre familles tabulaires : ni le logit, ni l'oracle, ni le témoin, ni la régression à noyau ne
voient autre chose. <!-- source: scripts/progedo_logit/feature_spec.json -->

**Personne et ménage — 12 variables**

| Variable | Type | Ce qu'elle dit |
|---|---|---|
| `age` | numérique | âge en années révolues |
| `gender` | catégorielle | femme / homme |
| `household_size` | numérique | nombre de personnes du ménage |
| `has_driving_license` | booléen | la personne détient le permis |
| `has_pt_subscription` | booléen | la personne a un abonnement aux transports collectifs |
| `number_of_cars` | numérique | voitures du ménage |
| `car_availability` | catégorielle | voiture disponible pour tous les adultes, pour certains, pour aucun |
| `has_bike` | booléen | la personne dispose d'un vélo |
| `socioprofessional_class` | catégorielle | catégorie socioprofessionnelle, 8 modalités |
| `main_occupation` | catégorielle | occupation principale, 8 modalités |
| `employed` | booléen | la personne occupe un emploi |
| `studies` | booléen | la personne suit des études |

**Contexte du déplacement — 3 variables**

| Variable | Type | Ce qu'elle dit |
|---|---|---|
| `purpose` | catégorielle | motif de l'activité de destination — domicile, travail, études, achats, loisirs, autre |
| `purpose_origin` | catégorielle | motif de l'activité d'origine, mêmes modalités |
| `departure_hour` | numérique | heure de départ, en heures décimales |

**Géographie — 6 variables**

| Variable | Type | Ce qu'elle dit |
|---|---|---|
| `od_km` | numérique | distance origine-destination à vol d'oiseau |
| `same_zone` | booléen | origine et destination dans la même zone fine de l'enquête |
| `dist_center_orig_km` | numérique | distance de l'origine à l'hypercentre |
| `dist_center_dest_km` | numérique | distance de la destination à l'hypercentre |
| `density_orig` | numérique | densité de population de la zone d'origine |
| `density_dest` | numérique | densité de population de la zone de destination |

L'hypercentre est le centroïde des zones fines du secteur du Capitole, et les distances sont
calculées en projection légale. Une variante à 19 variables, sans les deux distances à
l'hypercentre, a été mesurée — exactitude **[xx]**, composite **[xx]** — et deux définitions
alternatives de la distance ont été écartées ; le contrat servi est celui à 21 variables.

Ce que l'agent reçoit **en plus** de ces 21 variables — l'agenda de ses trajets restants, la météo
des tranches horaires à venir, sa mémoire — est décrit en section 4.2, et la formulation de cette
asymétrie n'est pas arrêtée.

---

### Annexe F : Journal des Corrections Méthodologiques (v1.4 → v1.6)

Chaque chiffre du manuscrit a été recoupé avec les mesures produites par le dépôt. Onze écarts ont été corrigés dans cette version :

| # | Écart relevé en `v1.3` | Correction appliquée en `v1.4` |
|---|---|---|
| 1 | « 15 variables » à parité informationnelle | Contrat de production à **21 variables** (`spec_version 2`) |
| 2 | L1 de l'oracle ($2,68$) opposée à celle du LLM ($29,81$) | Masse de probabilité vs argmax : comparaison ramenée à **$7,30$ contre $29,81$** |
| 3 | « $\chi^2$, $p = 0,98$ confirme la parfaite fidélité » | Non-rejet ≠ preuve ; remplacé par un **test d'équivalence** et des tailles d'effet |
| 4 | Jalon 0 présenté comme une validation | Requalifié en **contrôle de cohérence** ; croisements à tester |
| 5 | Composites comparés sans effectif | Effectif désormais obligatoire : **$+5,02$ pt** mesurés à décisions constantes en passant de 881 à 81 personnes |
| 6 | Parité présentée comme symétrique | **Dissymétrie d'exposition déclarée** ($31\,279$ trajets vus contre zéro) et bras few-shot ajouté |
| 7 | « Modèle tabulaire aveugle à l'événement » | Il n'est pas aveugle, il n'est pas informé → **condition 5** (oracle recevant l'événement encodé) |
| 8 | Effet presse mesuré contre une condition sans article | Ajout des bras **paraphrase sans indice modal** et **article placebo** |
| 9 | « $10\,000\times$ plus rapide » | **$\approx 2\,700\times$**, d'après le tableau comparatif du manuscrit lui-même |
| 10 | Périmètre de l'audit unitaire ($1\,000$ vs $13\,045$ trajets) | Périmètres explicités : oracle sur $13\,045$, LLM sur un sous-échantillon de $1\,000$ tiré du même jeu |
| 11 | Poids du composite annoncés à $0,40 / 0,20 / 0,20 / 0,20$ avec $\sum w = 1$ | Poids réellement servis : global $1,0$ · absence $1,0$ · âge $0,5$ · occupation $0,5$ · motif $0,5$ · genre $0,3$ · distance $0,3$ — **somme pondérée non renormalisée** |
| 12 *(v1.6)* | Tableau de conformité démographique (§ 2.2) : cibles $51,8 / 19,4 / 62,1 / 18,5 / 22,3 / 46,1 / 31,6 / 84,2$ et cohorte $51,9 / 19,2 / 62,4 / 18,4 / 22,1 / 46,5 / 31,4 / 84,0$ **sans source** — elles ne correspondent ni au rapport AUAT (5-17 ans : 16 % ; motorisation des ménages : 19 / 45 / 35 %, p. 21), ni à la population de référence mesurée (16,2 % de 5-17 ans, 13,0 % de personas sans voiture) | Cibles remplacées par celles du rapport (p. 10, 11, 21) et, pour les marges non publiées (sexe, permis, immobiles), par des recalculs sur microdonnées gelés ; cohorte = population scellée v3 mesurée par `scripts/AAMAS/control_population.py` (13 marges, TOST $\pm 1$ pt) ; la conformité est déclarée **par construction** pour les marges allouées |

*Sources de recoupement :* `scripts/progedo_logit/mode_choice_policy_metrics.json` (accuracy, LogLoss, matrice de confusion, importances de gain), `scripts/progedo_logit/feature_spec.json` (contrat de variables), `docs/arch/score-synthesis.md` (renormalisation sur l'offre, témoin d'effectif, gardes de substrat), `docs/changelog.md` (temps terminaux par mode, variantes de distance mesurées).

---

### Annexe G : Source des données d'enquête, citation et engagements d'utilisation

Les références tabulaires de cet article — logit multinomial et oracle LightGBM — sont ajustées
sur les microdonnées de l'enquête ménages-déplacements certifiée Cerema de la grande
agglomération toulousaine (**EMC² 2023**), obtenues auprès de **Quetelet-Progedo-Diffusion**
sous la convention **`lil-1750`**.

**Citation de la source.** **[modèle de citation | à recopier depuis l'annexe de la convention
`lil-1750`]**. Formulation provisoire, en attendant ce libellé : « Tisséo Collectivités
(producteur), *Enquête Ménages Déplacements — Enquête Mobilité Certifiée Cerema (EMC²) de la
Grande Agglomération Toulousaine, 2023* [fichier électronique], Quetelet-Progedo-Diffusion
(diffuseur). » Entrées bibliographiques : `tisseo2023emc2` pour le rapport publié,
`progedo2023emc2microdata` pour le fichier diffusé.

**Ce que la convention engage.** Usage exclusivement de recherche ; aucune cession des données à
un tiers, sous quelque forme que ce soit ; traitement conforme aux règles de l'art et au secret
statistique ; inscription de la recherche au registre de déclaration de traitement de
l'établissement ; respect de la réglementation sur les données personnelles ; mention de la
source dans les communications et publications ; information du diffuseur des communications,
des constats de qualité et de toute réutilisation ; stockage en espace chiffré pendant la
recherche ; destruction des fichiers à son terme. Le texte complet des engagements est recopié
dans [`../../sources/ENGAGEMENT_DONNEES_EMC2.md`](../../sources/ENGAGEMENT_DONNEES_EMC2.md), qui
tient aussi le journal des informations envoyées au diffuseur.

**Conséquence sur le matériel supplémentaire.** Ni les microdonnées, ni le jeu de test scellé de
13 045 trajets, ni aucun fichier qui en reproduirait le contenu n'accompagnent l'article
(section 4.7). Le statut des ressources dérivées de l'enquête — lois agrégées par couronne,
découpages de zones fines — est examiné à part et n'est pas tranché à ce jour.

**À la version finale.** La mention du registre de déclaration de traitement, qui nomme
l'établissement, ne figure pas dans la version soumise en double insu : elle est à ajouter ici
au moment de la version non anonyme, avec les remerciements au diffuseur.

---

### Tickets associés à ce chapitre
- [Ticket 053](../../../tickets/ticket_053_acces_donnees_recherche_et_reproductibilite.md) — Sanctuarisation de la frontière de reproductibilité et accès aux données de recherche (Quetelet-Progedo)
- [Ticket 062](../../../tickets/ticket_062_revue_et_alignement_des_annexes_techniques.md) — Revue, complétion et alignement des Annexes techniques A à G (Chapitre 99)

