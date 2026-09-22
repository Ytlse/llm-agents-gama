# Annexes techniques (brouillon)

<!-- Dernière mise à jour : 2026-09-21 -->

**Document :** brouillon français du chapitre, extrait de `MANUSCRIT_DETAILLE_2026.md` `v1.6` (3 septembre 2026), Annexes Techniques — « Annexes Techniques ». Le manuscrit entier est figé dans [`../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md`](../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md).
**Statut :** `brouillon v0` — texte **antérieur** à la réécriture de l'introduction (dont la v0.1 date du 8 septembre 2026). Deux choses à reprendre avant d'en faire un chapitre : les chiffres, à recouper depuis leur source dans le dépôt et non recopiés d'ici ; les renvois de section, qui suivent l'ancienne numérotation du manuscrit. Le vocabulaire « Tier 1 / 2 / 3 » a quitté ces annexes — vérifié le 21 septembre 2026, aucune occurrence n'y subsiste ; il était retiré sans que cet en-tête le dise. Ni maître anglais ni rendu LaTeX à ce stade. **Ajout du 11 septembre 2026 :** l'annexe G, écrite hors manuscrit, porte la source des données d'enquête, sa citation et les engagements de la convention `lil-1750`. **Ajout du 15 septembre 2026 ([ticket 053](../../../tickets/ticket_053_acces_donnees_recherche_et_reproductibilite.md)) :** l'annexe G porte aussi la démarche d'accès au portail de diffusion, le dépôt des fichiers reçus dans l'arborescence locale, les commandes de rejeu de l'ajustement, et la frontière de l'archive de soumission.
**Place dans l'article :** section du même numéro dans le plan annoncé en 1.4 de [`../en/01_Introduction.md`](../en/01_Introduction.md). État d'avancement : [`../README.md`](../README.md).

---

### Annexe A : Synthèse des Quotas API & Plateforme Antigravity
L'inférence s'appuie sur le gateway API SWRR (`llm_module`, 11 instances, 206 RPM / 37 700+ RPD) et l'environnement agentique Google Antigravity (Gemini 3.6 Flash / 3.5 Flash Lite, contexte 1M tokens, sous-agents isolés).

### Annexe B : Script d'Évaluation sur Enquête (`eval_llm_on_survey.py`)
Script d'inférence en aveugle sur $13\,045$ trajets scellés de l'enquête EMC² 2023.

### Annexe C : Configuration Inférence Locale Qwen-32B
Serveur vLLM `Qwen/Qwen2.5-32B-Instruct-AWQ` à $\tau=0.0$ et seed fixée.

### Annexe D : Bilan de la Calibration & Justification du Pivot
Paysage de perte non convexe justifiant le pivot vers l'architecture hybride.

### Annexe E : Dictionnaire des 21 variables du protocole de comparaison

Le protocole de comparaison de la section 4.3 désigne ces 21 variables, et elles seules. La liste est figée
dans le dépôt (`spec_version 2`) et c'est ce même fichier qui construit la matrice de dessin des
quatre méthodes tabulaires : ni le logit, ni le gradient boosté, ni la forêt aléatoire, ni la régression à noyau ne
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
alternatives de la distance ont été écartées ; le protocole servi est celui à 21 variables.

Ce que l'agent reçoit **en plus** de ces 21 variables — l'agenda de ses trajets restants, la météo
des tranches horaires à venir, les itinéraires eux-mêmes — est décrit en section 4.3, et la formulation de cette
asymétrie n'est pas arrêtée.

---

### Annexe F : Journal des Corrections Méthodologiques (v1.4 → v1.6)

Chaque chiffre du manuscrit a été recoupé avec les mesures produites par le dépôt. Onze écarts ont été corrigés dans cette version :

| # | Écart relevé en `v1.3` | Correction appliquée en `v1.4` |
|---|---|---|
| 1 | « 15 variables » à parité informationnelle | Contrat de production à **21 variables** (`spec_version 2`) |
| 2 | L1 de la référence tabulaire ($2,68$) opposée à celle du LLM ($29,81$) | Masse de probabilité vs argmax : comparaison ramenée à **$7,30$ contre $29,81$** |
| 3 | « $\chi^2$, $p = 0,98$ confirme la parfaite fidélité » | Non-rejet ≠ preuve ; remplacé par un **test d'équivalence** et des tailles d'effet |
| 4 | Jalon 0 présenté comme une validation | Requalifié en **contrôle de cohérence** ; croisements à tester |
| 5 | Composites comparés sans effectif | Effectif désormais obligatoire : **$+5,02$ pt** mesurés à décisions constantes en passant de 881 à 81 personnes |
| 6 | Parité présentée comme symétrique | **Dissymétrie d'exposition déclarée** ($31\,279$ trajets vus contre zéro) et condition few-shot ajoutée |
| 7 | « Modèle tabulaire aveugle à l'événement » | Il n'est pas aveugle, il n'est pas informé → **condition 5** (référence tabulaire recevant l'événement encodé) |
| 8 | Effet presse mesuré contre une condition sans article | Ajout des conditions **paraphrase sans indice modal** et **article placebo** |
| 9 | « $10\,000\times$ plus rapide » | **Retiré.** Le rapport annoncé en `v1.4` ($\approx 2\,700\times$) venait du tableau comparatif du manuscrit, non d'une mesure du dépôt : le recoupement du 15 septembre 2026 n'a trouvé aucune source. Le chiffre est écarté jusqu'à mesure (chapitre 9, point 1) |
| 10 | Périmètre de l'audit unitaire ($1\,000$ vs $13\,045$ trajets) | Périmètre unifié : les neuf décideurs sont mesurés sur le même terrain, $9\,621$ déplacements déclarés par $2\,930$ enquêtés, chacun sur sa journée et sa date d'enquête. Les repères tabulaires sur $13\,045$ restent publiés au § 5.3 ; ils valent hors contrainte de chaîne et ne sont pas commensurables |
| 11 | Poids du composite annoncés à $0,40 / 0,20 / 0,20 / 0,20$ avec $\sum w = 1$ | Poids réellement servis : global $1,0$ · absence $1,0$ · âge $0,5$ · occupation $0,5$ · motif $0,5$ · genre $0,3$ · distance $0,3$ — **somme pondérée non renormalisée** |
| 12 *(v1.6)* | Tableau de conformité démographique (§ 2.2) : cibles $51,8 / 19,4 / 62,1 / 18,5 / 22,3 / 46,1 / 31,6 / 84,2$ et cohorte $51,9 / 19,2 / 62,4 / 18,4 / 22,1 / 46,5 / 31,4 / 84,0$ **sans source** — elles ne correspondent ni au rapport AUAT (5-17 ans : 16 % ; motorisation des ménages : 19 / 45 / 35 %, p. 21), ni à la population de référence mesurée (16,2 % de 5-17 ans, 13,0 % de personas sans voiture) | Cibles remplacées par celles du rapport (p. 10, 11, 21) et, pour les marges non publiées (sexe, permis, immobiles), par des recalculs sur microdonnées gelés ; cohorte = population scellée v3 mesurée par `scripts/AAMAS/control_population.py` (13 marges, TOST $\pm 1$ pt) ; la conformité est déclarée **par construction** pour les marges allouées |

*Sources de recoupement :* `scripts/progedo_logit/mode_choice_policy_metrics.json` (accuracy, LogLoss, matrice de confusion, importances de gain), `scripts/progedo_logit/feature_spec.json` (variables du protocole), `docs/arch/score-synthesis.md` (renormalisation sur l'offre, témoin d'effectif, gardes de substrat), `docs/changelog.md` (temps terminaux par mode, variantes de distance mesurées).

---

### Annexe G : Source des données d'enquête, citation et engagements d'utilisation

Les références tabulaires de cet article — logit multinomial, gradient boosté LightGBM,
régression logistique à noyau et forêt aléatoire — sont ajustées
sur les microdonnées de l'enquête ménages-déplacements certifiée Cerema de la grande
agglomération toulousaine (**EMC² 2023**), obtenues auprès de **Quetelet-Progedo-Diffusion**
sous la convention **`lil-1750`**.

**Citation de la source.** Le modèle annexé à la convention impose ce libellé, à un millésime près :

> doi:10.13144/lil-0933
> Enquête Ménages Déplacements (EMD), Toulouse / Grande agglomération toulousaine
> (EMD, Toulouse / Grande agglomération toulousaine) - 2023, CEREMA, Syndicat mixte
> des transports en commun de l'agglomération toulousaine (producteurs), PROGEDO-ADISP
> (diffuseur)

Le modèle tel que délivré porte « 2013 ». L'enquête utilisée dans ce travail est celle de **2023**,
et c'est elle que la citation nomme : le millésime est corrigé ici, le reste du libellé est recopié
sans changement. Le DOI reste celui que le diffuseur a attribué à la commande.

Entrées bibliographiques : `tisseo2023emc2` pour le rapport publié,
`progedo2023emc2microdata` pour le fichier diffusé.

**Obtenir les données.** Les microdonnées sont diffusées à la recherche par le portail
Quetelet-Progedo-Diffusion (ADISP), `https://commande.progedo.fr/`. La fiche à demander est
l'*Enquête Mobilité Certifiée Cerema (EMC²) de la Grande Agglomération Toulousaine, 2023*
(Tisséo Collectivités, producteur ; Cerema, certification). La demande se fait en ligne :
création d'un compte, sélection de l'enquête au catalogue, déclaration du projet de recherche,
signature de l'engagement rappelé ci-dessous. La convention de ce travail porte le numéro
`lil-1750` ; un tiers obtient la sienne, sous son propre numéro. Aucune démarche auprès des
auteurs n'est nécessaire, et aucune ne remplace celle-là : les engagements interdisent la
cession.

**Ce que la convention engage.** Usage exclusivement de recherche ; aucune cession des données à
un tiers, sous quelque forme que ce soit ; traitement conforme aux règles de l'art et au secret
statistique ; inscription de la recherche au registre de déclaration de traitement de
l'établissement ; respect de la réglementation sur les données personnelles ; mention de la
source dans les communications et publications ; information du diffuseur des communications,
des constats de qualité et de toute réutilisation ; stockage en espace chiffré pendant la
recherche ; destruction des fichiers à son terme. Le texte complet des engagements est recopié
dans [`../../sources/ENGAGEMENT_DONNEES_EMC2.md`](../../sources/ENGAGEMENT_DONNEES_EMC2.md), qui
tient aussi le journal des informations envoyées au diffuseur.

**Rejouer l'ajustement.** Les fichiers reçus se déposent tels quels sous `data/PROGEDO 2023/` :
les trois fichiers standards en
`lil-1750-Donnees_CSV/fichiers_standards/Toulouse_2023_std_{pers,men,depl}.csv`, la couche de
zones fines en `lil-1750-Documentation/SIG/EMC2_Toulouse_2023_ZF_26052023.shp`.
`scripts/progedo_logit/build_mode_choice_dataset.py` reconstruit alors le jeu d'entraînement et
son découpage : le partage est fait par ménage (`GroupShuffleSplit` sur l'identifiant de
ménage, 25 %, graine 0), si bien que les 13 045 trajets de test se retrouvent à l'identique,
sans qu'aucun ménage ne soit à cheval sur les deux côtés. Les quatre méthodes se réajustent
ensuite par `fit_mode_choice_{policy,logit,klr,forest}.py`, et les chiffres publiés en 4.4 se
recalculent depuis les `*_metrics.json` produits.

**Conséquence sur le matériel supplémentaire.** La frontière passe là : l'archive porte le code,
les configurations d'expérience, les graines et la cohorte synthétique scellée v6 avec son
manifeste de contrôle démographique, tout ce qui s'audite sans démarche. Elle ne porte ni les
microdonnées, ni le jeu de test scellé de 13 045 trajets, ni aucun fichier qui en reproduirait
le contenu (§ 4.4).

**La même lecture sur les modes tirés.** Les exécutions du § 4.4, lues sur le mode tiré dans la
masse plutôt que sur la masse elle-même, donnent le composite EMD–JSD suivant. L'écart à la
lecture par masse mesure le bruit du tirage, et il ne va pas dans le même sens pour toutes :
vingt-huit centièmes pour le gradient boosté, un demi-point pour le logit, huit centièmes en
moins pour la régression à noyau. L'ordre des quatre méthodes change deux fois par rapport à la
masse : la forêt aléatoire passe devant le logit qu'elle suivait, et la régression à noyau devant
le gradient boosté.

| Méthode de référence | composite EMD–JSD, modes tirés |
|---|---:|
| Gradient boosté (LightGBM) | 3,88 (+0,28) |
| Logit multinomial | 4,54 (+0,52) |
| Régression logistique à noyau | 3,52 (−0,08) |
| Forêt aléatoire | 4,40 (+0,31) |

<!-- source: scores.json des mêmes exécutions que le § 4.4, composite.emd_jsd_tire ; l'écart est
     donné face à composite.emd_jsd ; jeu corrigé du ticket 088, exécutions du 2026-09-16 --> L'offre d'itinéraires soumise aux agents n'en fait pas partie non plus, pour
sa taille et non pour son statut : elle se régénère depuis la cohorte par les calculateurs, et le
manifeste du jeu scelle les empreintes qui permettent de vérifier que le jeu reconstruit est le
même (population, flux GTFS, graphes OTP et OSMnx, fichiers de configuration). Un relecteur
vérifie donc la cohorte, le protocole et les scores immédiatement, et le volet d'entraînement des
références tabulaires après une demande au diffuseur. Le statut des ressources dérivées de
l'enquête — lois agrégées par couronne, découpages de zones fines — est examiné à part et n'est
pas tranché à ce jour.

**À la version finale.** La mention du registre de déclaration de traitement, qui nomme
l'établissement, ne figure pas dans la version soumise en double insu : elle est à ajouter ici
au moment de la version non anonyme, avec les remerciements au diffuseur.

---

### Annexe H : résultats détaillés du chapitre 6

Le chapitre 6 ne publie que les enseignements ; cette annexe porte les tableaux complets sur
lesquels ils reposent. Substrat : cohorte `population_1000_AAMAS_v6`, jeu
`population_1000_AAMAS_v6_20260316_EN_c`, <!-- jeu corrigé du ticket 088 -->
3 154 décisions scorées, 868 personnes mobiles. Tous les décideurs y sont mesurés : la campagne
de rejeu s'est terminée le 2026-09-17 à 09:25, et aucun chiffre de cette annexe n'est lu sur le
substrat antérieur.

#### H.1 Les différences appariées, sur les trois lectures

Rééchantillonnage par grappe au niveau de la personne, 2 000 réplicats, graine 2026, 868
personnes communes de part et d'autre. Un écart positif est une erreur plus forte pour le
premier terme ; en gras, les intervalles qui ne contiennent pas zéro.

| Différence appariée | Composite | Hors choix unique | L1 parts globales |
|---|---|---|---|
| `gemini-3.5` expert − minimal | **−2,27 [−3,22 ; −1,40]** | **−3,59 [−4,83 ; −2,45]** | **−10,2 [−12,5 ; −8,0]** |
| `gemini-3.1` expert − minimal | **−3,37 [−4,25 ; −2,45]** | **−4,15 [−5,22 ; −3,09]** | **−8,6 [−10,6 ; −6,8]** |
| `mistral-large` expert − minimal | **−7,25 [−8,67 ; −5,90]** | **−8,63 [−10,28 ; −7,15]** | **−18,0 [−22,4 ; −13,5]** |
| `gemini-3.5` expert − gradient boosté | **+1,35 [+0,28 ; +2,47]** | +1,09 [−0,27 ; +2,45] | +4,3 [−1,2 ; +9,7] |
| `gemini-3.5` expert − régression à noyau | **+1,38 [+0,32 ; +2,45]** | **+1,35 [+0,10 ; +2,69]** | **+7,1 [+1,8 ; +12,1]** |
| `gemini-3.5` expert − forêt aléatoire | +0,94 [−0,06 ; +1,98] | +1,17 [−0,02 ; +2,39] | **+7,7 [+3,3 ; +11,7]** |
| `gemini-3.5` expert − logit multinomial | +0,96 [−0,18 ; +2,17] | +0,39 [−1,10 ; +1,80] | +4,4 [−0,4 ; +8,5] |
| `gemini-3.1` expert − gradient boosté | **+5,50 [+4,19 ; +6,93]** | **+6,65 [+5,21 ; +8,29]** | **+21,7 [+16,6 ; +27,0]** |
| `mistral-large` expert − gradient boosté | **+4,07 [+2,47 ; +5,75]** | **+6,33 [+4,54 ; +8,09]** | **+17,2 [+12,7 ; +21,6]** |
| `gemini-3.1` − `gemini-3.5`, prompt expert | **+4,15 [+2,99 ; +5,43]** | **+5,56 [+4,12 ; +7,02]** | **+17,4 [+14,6 ; +20,3]** |
| `gemini-3.1` − `gemini-3.5`, prompt minimal | **+5,25 [+4,11 ; +6,40]** | **+6,13 [+4,75 ; +7,53]** | **+15,8 [+13,2 ; +18,3]** |
| `mistral-large` − `gemini-3.5`, prompt expert | **+2,71 [+1,17 ; +4,25]** | **+5,24 [+3,76 ; +6,66]** | **+12,8 [+8,3 ; +17,4]** |
| `gemini-3.1` − `mistral-large`, prompt expert | +1,44 [−0,10 ; +2,98] | +0,32 [−1,14 ; +1,82] | +4,6 [−0,1 ; +9,0] |
| `gemini-3.1` − `mistral-large`, prompt minimal | **−2,45 [−4,08 ; −0,85]** | **−4,16 [−5,89 ; −2,45]** | **−4,8 [−7,4 ; −2,2]** |
| Jev sous consigne `gemini-3.5` − prompt minimal | **−9,71 [−11,66 ; −7,80]** | **−12,78 [−14,86 ; −10,68]** | **−30,2 [−36,0 ; −24,6]** |
| Jev sous consigne `gemini-3.5` − gradient boosté | +0,66 [−0,63 ; +2,07] | +1,32 [−0,19 ; +2,86] | +3,1 [−1,4 ; +7,3] |
| Jev sous consigne `gemini-3.5` − régression à noyau | +0,69 [−0,57 ; +2,06] | **+1,58 [+0,22 ; +3,00]** | **+5,9 [+1,6 ; +9,8]** |
| Jev sous consigne `gemini-3.5` − forêt aléatoire | +0,25 [−1,03 ; +1,61] | **+1,40 [+0,08 ; +2,80]** | **+6,5 [+1,8 ; +10,6]** |
| Jev sous consigne `gemini-3.5` − logit multinomial | +0,27 [−1,11 ; +1,70] | +0,62 [−0,97 ; +2,24] | +3,1 [−1,7 ; +7,8] |
| Jev sous consigne `gemini-3.5` − `gemini-3.5` expert | −0,69 [−2,04 ; +0,65] | +0,23 [−1,14 ; +1,56] | −1,2 [−7,0 ; +4,3] |

<!-- ⚠ NOMMAGE DES BRAS JEV, aligné le 22 septembre 2026 sur la décision de l'auteur : prompt_expert_32 EST le prompt expert de Jev, et c'est lui que publie le § 6.1. Les lignes « Jev sous consigne `gemini-3.5` » de cette annexe sont prompt_expert_05, la consigne réglée contre gemini-3.5-flash-lite et servie telle quelle ; les lignes « Jev, prompt expert » sont prompt_expert_32. Les différences appariées de H.1 n'ont été calculées que sur prompt_expert_05 ; l'équivalent sous prompt_expert_32 n'existe pas. -->

Le classement des modèles change avec la consigne. Sous prompt minimal, `gemini-3.1` devance
`mistral-large` de 2,45 points, intervalle excluant zéro ; sous prompt expert, `mistral-large`
repasse devant de 1,44, intervalle contenant zéro. Un banc d'essai conduit sous une seule
consigne mesure donc le couple modèle-consigne, non le modèle.

Le composite ne sépare Jev sous la consigne de `gemini-3.5` d'aucune des quatre méthodes tabulaires, alors que
`gemini-3.5` sous la même consigne est séparable des deux meilleures. Les deux autres lectures le
départagent davantage : hors choix unique, il reste derrière la régression à noyau et la forêt
aléatoire, et sur les parts globales derrière les deux mêmes. Aucune des trois lectures ne le
sépare du prompt expert à modèle de langue.

L'ablation de la clause de justification, qui demandait à l'agent d'expliquer pourquoi la marche
n'obtient pas la plus forte probabilité, vaut **+0,17 [−0,45 ; +0,79]** point à sa suppression :
son retrait améliore le composite, sans que l'intervalle exclue zéro. Elle est mesurée sur
l'ancien substrat, la variante qui la portait ayant été retirée du dépôt le 2026-09-17.

<!-- source: docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/ — quatorze paires, 2 000 réplicats, graine 2026, 868 personnes communes, tous les décideurs sur le jeu corrigé. La clause de justification vient de docs/traces/2026-09-16_15-05_pe04_intervalles_apparies_manquants/ (pe05 − pe04). Les six paires Jev viennent de docs/traces/2026-09-21_ticket096_lot2/paired_complet_B2000.json, même méthode et mêmes 868 personnes ; le même passage a recalculé les quatorze paires d'origine, qui ressortent au centième près — c'est le contrôle que l'ajout des deux bras n'a rien déplacé. Le bras prompt_expert_32, réglé pour Jev sur cette cohorte même, n'entre pas dans ce tableau : son score est en échantillon et ne se compare pas aux autres. -->

#### H.2 L'erreur par dimension et par décideur

Moyenne des erreurs L1 de strate, pondérée par l'effectif des strates couvertes. Les dimensions
entrant dans le composite sont l'âge, le genre, l'occupation, le motif et la distance ; la
couronne de résidence et le type de logement n'entrent ni dans le composite ni dans le cycle de
calibration.

| Erreur L1 pondérée (%) | distance | motif | âge | occupation | genre | couronne | logement |
|---|---:|---:|---:|---:|---:|---:|---:|
| `gemini-3.5`, prompt minimal | 24,1 | 27,9 | 30,6 | 25,3 | 23,9 | 25,7 | 30,5 |
| `gemini-3.5`, prompt expert | **14,2** | 21,4 | 22,1 | 18,5 | 13,6 | 19,6 | 23,6 |
| `gemini-3.1`, prompt minimal | 38,0 | 37,8 | 43,9 | 39,2 | 39,4 | 40,5 | 43,1 |
| `gemini-3.1`, prompt expert | 30,2 | 30,8 | 35,8 | 31,2 | 30,7 | 33,0 | 37,4 |
| `mistral-large`, prompt minimal | 51,9 | 39,3 | 46,8 | 43,8 | 44,5 | 47,6 | 51,0 |
| `mistral-large`, prompt expert | 33,7 | 27,9 | 30,4 | 28,6 | 25,3 | 29,6 | 33,0 |
| Jev, prompt minimal | 47,0 | 40,2 | 45,9 | 43,0 | 42,5 | 44,5 | 47,5 |
| Jev, consigne `gemini-3.5` | 20,4 | 22,1 | 20,5 | 16,3 | 11,8 | 20,2 | 19,7 |
| Jev, prompt expert *(en échantillon)* | 17,9 | 17,2 | 19,8 | 14,1 | 9,5 | 19,2 | 21,1 |
| Gradient boosté (LightGBM) | 17,8 | **13,6** | 18,2 | 15,7 | 8,5 | 11,5 | 16,6 |
| Forêt aléatoire | 16,8 | 18,1 | **16,8** | **12,9** | **5,3** | **9,5** | **15,9** |

Deux dimensions n'entrent ni dans le composite ni dans le cycle de calibration, la couronne de
résidence et le type de logement, et ce sont celles où les décideurs à consigne restent le plus
loin des méthodes ajustées. Le classifieur à sortie typée s'y tient à 19,2 et 21,1 points quand
la forêt aléatoire fait 9,5 et 15,9, alors qu'il la rejoint sur le genre et la distance. Ce qui
n'est pas noté n'est pas réglé.

<!-- source: scores.json, detail.<dimension>.strates, moyenne des l1 de strate pondérée par n sur les strates couvertes ; tous les décideurs sur le jeu corrigé. En gras, la plus faible erreur de chaque colonne : la distance est la seule où un agent la détient, et le bras en échantillon ne concourt pas. Les trois lignes Jev ont été calculées par le même passage que les autres, et ce passage reproduit au dixième près les deux lignes gemini-3.5 déjà publiées — c'est le contrôle que la règle d'agrégation n'a pas changé. Figures régénérées par scripts/analysis/plot_chapitre6.py. -->

![Part de la voiture par strate, six dimensions](../images/ch99_dimensions_voiture.png)

*Figure H.1 — La part de la voiture par strate sur six dimensions, avant et après ingénierie de
prompt, contre la cible d'enquête et la méthode tabulaire la plus proche de cette cible sur
chaque dimension. Les deux dernières, couronne de résidence et type de logement, n'entrent ni
dans le composite ni dans le cycle de calibration, et l'écart y reste large après réglage.*

![Les quatre modes par tranche de distance](../images/ch99_modes_distance.png)

*Figure H.2 — Les quatre modes par tranche de distance, un panneau par mode. La voiture et la
marche se placent sur la cible dès un kilomètre ; les transports collectifs sont surestimés de
deux à cinq points entre deux et vingt kilomètres, et le vélo l'est d'un facteur deux sur toutes
les tranches où il pèse. La méthode tabulaire se trompe en sens inverse sur le vélo, qu'elle
place sous la cible partout.*

![Les quatre modes par occupation](../images/ch99_modes_occupation.png)

*Figure H.3 — Les quatre modes lus par occupation, mêmes courbes que la figure H.2.
Les deux strates scolarisées, élèves et étudiants, sont celles où l'agent place le vélo le plus
haut : 8,2 et 13,3 % sous prompt expert, contre 4,2 et 4,0 % dans l'enquête. Les transports
collectifs des étudiants, eux, passent de 37,9 à 35,5 % après réglage quand la cible est à
41,4 % : le réglage les éloigne de la cible sur cette strate.*

![Les quatre modes par motif de déplacement](../images/ch99_modes_motif.png)

*Figure H.4 — Les quatre modes par motif de déplacement. Le motif études est celui où l'agent
s'éloigne le plus de la cible après réglage, et il s'en éloigne dans le sens de la voiture, sur
une population qu'aucun des quatre principes ne vise.*

#### H.3 Les parts modales de chaque décideur

| Part (%) | Voiture | Marche | Transports collectifs | Vélo |
|---|---:|---:|---:|---:|
| Enquête EMC² 2023 | 56,7 | 26,8 | 12,4 | 4,1 |
| Prompt minimal, `gemini-3.5` | 47,4 | 24,0 | 20,9 | 7,6 |
| Prompt expert, `gemini-3.5` | 52,3 | 24,2 | 16,6 | 6,8 |
| Prompt minimal, `gemini-3.1` | 44,1 | 19,5 | 28,8 | 7,7 |
| Prompt expert, `gemini-3.1` | 46,2 | 21,7 | 24,8 | 7,4 |
| Prompt minimal, `mistral-large` | 36,7 | 24,4 | 30,6 | 8,2 |
| Prompt expert, `mistral-large` | 43,4 | 29,3 | 19,2 | 8,1 |
| Prompt minimal, Jev | 38,7 | 23,4 | 31,0 | 6,9 |
| Consigne `gemini-3.5`, Jev | 51,9 | 32,3 | 10,9 | 4,9 |
| Prompt expert, Jev | 51,5 | 28,0 | 15,2 | 5,4 |
| Gradient boosté | 52,8 | 29,1 | 14,8 | 3,3 |
| Forêt aléatoire | 56,2 | 27,6 | 14,2 | 2,0 |
| Régression logistique à noyau | 54,4 | 28,9 | 13,6 | 3,0 |
| Logit multinomial | 53,3 | 27,2 | 16,4 | 3,0 |

Tous les décideurs sous-estiment la voiture, effet de la contrainte de chaîne qui pèse sur tous
en lecture chaînée. Les deux familles se trompent en sens opposés sur le vélo : les trois modèles
de langue le placent entre 6,8 et 8,1 %, les quatre méthodes tabulaires entre 2,0 et 3,3 %.

Le classifieur à sortie typée se range du côté des méthodes tabulaires sur le vélo, 4,9 % sous la
consigne experte pour une cible de 4,1 %, et il est le seul décideur à consigne à y parvenir. Sa
marge d'erreur part ailleurs : il sur-produit la marche de cinq points et sous-produit les
transports collectifs d'un point et demi, et c'est ce partage-là que la consigne réglée pour lui
refait, sans jamais nommer l'un ni l'autre.

<!-- source: scores.json, global.actual et global.target ; les trois lignes Jev viennent des exécutions du 2026-09-21 sur le jeu corrigé. -->

#### H.4 Les strates que le réglage dégrade, sur les trois modèles

| Erreur L1 de strate (%) | prompt minimal | prompt expert |
|---|---:|---:|
| Motif études, `gemini-3.5` (n = 218) | 28,0 | 33,5 |
| Motif études, `gemini-3.1` (n = 218) | 20,0 | 21,2 |
| Motif études, `mistral-large` (n = 218) | 8,7 | 22,3 |
| 15–19 ans, `gemini-3.5` (n = 61) | 53,4 | 58,3 |
| 15–19 ans, `gemini-3.1` (n = 61) | 49,2 | 47,9 |
| 15–19 ans, `mistral-large` (n = 61) | 34,1 | 44,9 |

La dégradation du motif études se retrouve sur les trois modèles, celle des 15–19 ans sur
`gemini-3.5` et `mistral-large`. Deux strates résistent par ailleurs à tous les décideurs,
méthodes tabulaires comprises : les 15–19 ans, de 38 à 58 points d'erreur, et les déplacements de
plus de 50 kilomètres, de 42 à 72 points sur seize à dix-neuf décisions selon le décideur.

<!-- source: scores.json, detail.motif.strates et detail.age.strates -->

#### H.5 L'accord décision par décision, six paires

Déplacements portant au moins deux options offertes aux deux décideurs, 2 374 à 2 479 selon la
paire ; tous les décideurs sur le jeu corrigé.

| Paire | Accord, mode le plus probable | Accord, mode tiré | L1 médiane entre distributions |
|---|---:|---:|---:|
| Gradient boosté / régression à noyau | 91,6 % | 90,5 % | 8,3 |
| Gradient boosté / forêt aléatoire | 89,0 % | 88,3 % | 11,3 |
| Prompt expert `gemini-3.5` / gradient boosté | 69,7 % | 61,4 % | 39,0 |
| Prompt expert `gemini-3.5` / forêt aléatoire | 71,4 % | 60,4 % | 42,6 |
| Prompt expert `gemini-3.5` / prompt expert `gemini-3.1` | 79,6 % | 72,8 % | 40,0 |
| Prompt expert `gemini-3.1` / prompt expert `mistral-large` | 72,6 % | 70,6 % | 40,0 |
| Consigne `gemini-3.5` Jev / gradient boosté | 71,9 % | 71,1 % | 35,2 |
| Consigne `gemini-3.5` Jev / forêt aléatoire | 73,3 % | 71,2 % | 35,6 |
| Consigne `gemini-3.5` Jev / prompt expert `gemini-3.5` | 78,7 % | 65,7 % | 34,0 |
| Consigne `gemini-3.5` Jev / prompt minimal Jev | 68,1 % | 70,3 % | 44,0 |
| Prompt expert Jev / gradient boosté | 71,4 % | 70,4 % | 35,7 |
| Prompt expert Jev / consigne `gemini-3.5` Jev | 92,1 % | 89,8 % | 10,0 |

L'écart médian entre les distributions de deux agents vaut quatre fois celui qui sépare deux
méthodes tabulaires.

Le classifieur à sortie typée se tient entre les deux familles, et sa colonne du mode tiré le
montre mieux que celle du mode le plus probable. Il s'accorde avec le gradient boosté sur 71,9 %
des modes les plus probables, à peine plus que le prompt expert à modèle de langue, mais son
accord ne se défait pas au tirage, 71,1 % contre 61,4 % : ses distributions sont assez proches de
celles d'une méthode tabulaire pour que le tirage les sépare peu, et son écart médian de 35,2 est
le plus faible qu'un décideur à consigne obtienne face à une méthode ajustée. Les deux variantes
expertes réglées sur lui, enfin, s'accordent à 92,1 % et ne s'écartent que de 10,0 points, au
niveau de deux méthodes tabulaires entre elles.

<!-- source: moves.csv des exécutions du jeu corrigé, colonnes P(Marche/Vélo/Voiture Privée/Transports_collectifs) % et Mode de transport Choisi ; les six premières lignes recalculées le 2026-09-17 après la fin de la campagne de rejeu, les six suivantes le 2026-09-22 par docs/traces/2026-09-22_lot1_apparies_audit/scripts/accord_paires_h5.py. Ce script reproduit les six lignes d'origine au dixième près et retrouve leur fourchette d'effectifs, ce qui a demandé de retrouver trois règles que le tableau ne disait pas : la distribution se lit sur les quatre colonnes primaires sans replier le train ni les deux-roues motorisés, le filtre des options offertes replie, et le mode tiré se compare sur son libellé brut. Les deux lignes Jev que le § 6.4 portait avant ce recalcul, 72,2 % et 71,7 % face au gradient boosté, venaient d'une recomputation qui déplaçait aussi les lignes publiées ; elles sont remplacées par les valeurs de ce passage. -->

#### H.6 Les variantes de prompt et leurs scores

| Variante | Statut | Composite | Hors choix unique | L1 parts globales |
|---|---|---:|---:|---:|
| `prompt_minimal_02` | aucune ingénierie | 7,02 | 10,39 | 24,08 |
| `prompt_expert_05` | ablation retenue au vu de la cohorte | 4,86 | 6,86 | 13,85 |
| `prompt_expert_06` | ajustée au vu de la cohorte évaluée | 5,33 | 7,24 | 15,39 |
| `prompt_expert_08` | ajustée au vu de la cohorte évaluée | 6,58 | 10,32 | 21,74 |

Les quatre premières sur `gemini-3.5-flash-lite`. Les trois variantes expertes ont vu la cohorte,
à des degrés différents : `prompt_expert_06` et `prompt_expert_08` ont été réécrites sur ses
résidus, `prompt_expert_05` n'y a touché que par la rétention d'une ablation. Les deux premières
devaient donner une borne haute d'ajustement en échantillon ; elles font moins bien que la
troisième. Le plafond que le protocole attendait n'est pas atteint par les prompts qui avaient le
plus accès aux résidus.

Six mutations ont été mesurées sur le classifieur à sortie typée, seul porteur dont la consigne
ait été réécrite au vu de ses propres écarts par strate. Toutes partent de `prompt_expert_05`,
que ce porteur jouait à 4,19.

| Variante | Mécanisme visé | Composite | Hors choix unique | L1 parts globales |
|---|---|---:|---:|---:|
| `prompt_expert_31` | la marche continue porte son propre coût, en cinquième principe | 3,63 | 6,32 | 11,28 |
| `prompt_expert_32` | friction de chaîne réécrite à deux versants, **retenue** | 3,65 | 6,58 | 10,48 |
| `prompt_expert_33` | coût récurrent du véhicule face aux ressources du foyer | 9,16 | 14,74 | 33,90 |
| `prompt_expert_34` | régularité d'un trajet servant un motif habituel | 4,14 | 7,95 | 16,22 |
| `prompt_expert_35` | la retenue, plus la protection de la marche courte et « only when » | 4,16 | 7,58 | 15,32 |
| `prompt_expert_36` | la retenue, plus la protection de la marche courte seule | 3,91 | 7,08 | 13,27 |

La variante retenue n'est pas celle qui obtient le meilleur composite. `prompt_expert_31` fait
3,63 contre 3,65, écart indistinguable, mais dégrade deux fois plus de strates ; le choix s'est
porté sur celle qui déplaçait le moins de choses par ailleurs. Deux mutations montrent où la
marge se referme. Celle qui opposait le coût récurrent d'un véhicule aux ressources du foyer fait
chuter la part voiture de dix-sept points et dégrade 32 strates sur 37. Et trois mots ajoutés
devant la clause retenue, « It is only when », lui coûtent un demi-point de composite et cinq
points de L1, de 3,65 à 4,16 et de 10,5 à 15,3. Une consigne qui nomme un critère déplace ce
porteur ; la même consigne rendue conditionnelle ne le déplace plus.

<!-- source: data/experiences/exp_gemini-35-fl_{promin02,proexp05,proexp06,proexp08}_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_*t0_nosim ; prompt_expert_07 déclaré, non joué ; prompt_expert_04 supprimé du dépôt le 2026-09-17. Les six mutations Jev : exp_jev-1130_proexp{31..36}_…_c_nosim, jouées le 2026-09-21, scores lus dans leurs scores.json ; textes, mécanismes et motifs de rejet dans docs/traces/2026-09-21_jev_mutations/README.md § 4, chacun audité conforme avant lancement par l'agent prompt-auditor. Les scores de ces six variantes sont en échantillon : les écarts qui ont guidé les mutations ont été lus sur la cohorte qui les note. La procédure d'optimisation est décrite au § 5.2, ses garde-fous au § 5.2.3. Ordre de grandeur de la recherche, déclaré par l'auteur : une douzaine d'itérations sur gemini-3.5-flash-lite, deux ou trois sur chacun des deux autres modèles. -->

---

### Annexe I : l'audit unitaire, décideur par décideur

Le substrat diffère de celui de l'annexe H : les journées réellement décrites par les enquêtés,
9 621 déplacements de 2 930 personnes, chacun portant le mode déclaré (protocole du § 5.4). Ces
chiffres ne se comparent pas à ceux de l'annexe H, qui portent sur la cohorte synthétique.

#### I.1 L'accord global

| Décideur | Exactitude pondérée | Sur décisions arbitrées | Entropie croisée | GMPCA |
|---|---:|---:|---:|---:|
| Gradient boosté | 71,5 | 67,4 | **0,299** | **0,741** |
| Régression logistique à noyau | 70,6 | 66,2 | 0,325 | 0,723 |
| Forêt aléatoire | 69,9 | 65,5 | 0,321 | 0,726 |
| Logit multinomial | 68,6 | 64,2 | 0,358 | 0,699 |
| Durée minimale | 68,1 | 65,3 | — | — |
| Prompt expert | 67,6 | 65,2 | 0,341 | 0,711 |
| Tout-voiture | 66,7 | 61,7 | — | — |
| Prompt minimal | 64,8 | 61,6 | 0,384 | 0,682 |
| Jev, prompt expert *(en échantillon)* | 64,7 | 60,8 | 0,464 | 0,629 |
| Jev, consigne `gemini-3.5` | 64,3 | 60,2 | 0,509 | 0,601 |
| Jev, prompt minimal | 56,6 | 52,2 | 0,552 | 0,576 |
| Hasard uniforme | 23,5 | 21,5 | — | — |

Le prompt expert gagne une place d'une colonne à l'autre : il passe derrière le logit
multinomial sur l'exactitude et devant lui sur l'entropie croisée, les trois autres méthodes
tabulaires restant devant sur les deux. Les trois bras Jev occupent les trois dernières places
sur l'entropie croisée, et deux d'entre eux passent sous le plancher tout-voiture sur
l'exactitude. Les deux planchers durs ne reçoivent pas d'entropie croisée, infinie dès la
première erreur, et le hasard uniforme ne couvre pas le support commun.

L'entropie croisée et le GMPCA sont mesurés sur le support commun : les 5 229 décisions
arbitrées que notent tous les décideurs à distribution joués sur ce jeu.

<!-- source: docs/traces/2026-09-22_lot0_entropie_support_unique/, ticket 101 lot 0 — rejeu du
2026-09-22 par scripts/progedo_logit/audit_unitaire_058.py sur les douze expériences du jeu
enquete_058_test_20260316. Le support est défini par les neuf décideurs à distribution, les
trois bras Jev du ticket 096 compris : ils le raboteraient pour tout le monde s'ils en étaient
exclus, et l'y faire entrer coûte 222 décisions sur les 5 451 de la mesure du 2026-09-21. Les
valeurs déplacées sont la régression à noyau (0,324 → 0,325 et 0,724 → 0,723), le prompt expert
(0,342 → 0,341) et le prompt minimal (0,383 → 0,384) ; le gradient boosté, la forêt aléatoire et
le logit multinomial sont inchangés, et aucun classement ne bouge. Les trois lignes Jev viennent
du même rejeu ; leurs bras sont exp_jev-1130_{promin02,proexp05,proexp32}_jtir_pop-enquete_058_test_…,
joués le 2026-09-21, 12 562 décisions chacun, 9 612 à 9 614 déplacements notés. -->

#### I.1 bis Les différences appariées sur l'audit unitaire

Même méthode qu'à l'annexe H.1 : 2 000 réplicats, graine 2026, rééchantillonnage par grappe au
niveau de la personne, 2 929 personnes. L'exactitude est rééchantillonnée sur tous les
déplacements notés par le décideur, l'entropie croisée sur le support commun ; les deux supports
sont tirés du même tirage de personnes. Un écart négatif sur l'exactitude et positif sur
l'entropie croisée se lisent tous deux « le premier est derrière le second ». En gras, les
intervalles qui ne contiennent pas zéro.

| Différence appariée | Exactitude (pt) | Entropie croisée |
|---|---|---|
| Jev sous consigne `gemini-3.5` − gradient boosté | **−7,20 [−8,51 ; −5,78]** | **+0,210 [+0,181 ; +0,241]** |
| Jev sous consigne `gemini-3.5` − régression à noyau | **−6,31 [−7,64 ; −4,89]** | **+0,184 [+0,156 ; +0,215]** |
| Jev sous consigne `gemini-3.5` − forêt aléatoire | **−5,67 [−7,02 ; −4,27]** | **+0,189 [+0,162 ; +0,216]** |
| Jev sous consigne `gemini-3.5` − logit multinomial | **−4,31 [−5,69 ; −2,87]** | **+0,151 [+0,122 ; +0,181]** |
| Jev sous consigne `gemini-3.5` − prompt expert `gemini-3.5` | **−3,33 [−4,92 ; −1,55]** | **+0,169 [+0,141 ; +0,196]** |
| Jev sous consigne `gemini-3.5` − tout-voiture | **−2,42 [−4,26 ; −0,62]** | — |
| Jev prompt expert − Jev sous consigne `gemini-3.5` | +0,38 [−0,24 ; +1,03] | **−0,045 [−0,054 ; −0,037]** |
| Jev prompt expert − tout-voiture | **−2,04 [−3,78 ; −0,29]** | — |
| Prompt expert − gradient boosté | **−3,87 [−5,47 ; −2,28]** | **+0,041 [+0,021 ; +0,060]** |
| Prompt expert − régression à noyau | **−2,98 [−4,61 ; −1,42]** | +0,016 [−0,005 ; +0,036] |
| Prompt expert − forêt aléatoire | **−2,35 [−3,93 ; −0,76]** | **+0,020 [+0,001 ; +0,038]** |
| Prompt expert − logit multinomial | −0,98 [−2,61 ; +0,58] | −0,018 [−0,039 ; +0,003] |
| Prompt minimal − prompt expert | **−2,81 [−4,01 ; −1,54]** | **+0,043 [+0,031 ; +0,055]** |

Deux lectures que ces intervalles autorisent et que les niveaux du tableau précédent ne
donnaient pas. Jev sous la consigne de `gemini-3.5`, qu'aucune comparaison appariée ne sépare des quatre
méthodes tabulaires sur la répartition agrégée (annexe H.1), est ici séparable de chacune
d'elles, du prompt expert à modèle de langue et du plancher tout-voiture. Et l'avance du prompt
expert sur le logit multinomial en entropie croisée, que le § 6.4 mentionne, ne se sépare pas de
zéro : ce qui est établi est qu'il est derrière le gradient boosté et la forêt aléatoire.

Le prompt expert de Jev déplace l'entropie croisée sans déplacer l'exactitude de façon
séparable : elle ne lui fait pas désigner le mode déclaré plus souvent, elle lui laisse
davantage de masse quand il se trompe.

<!-- source: docs/traces/2026-09-22_lot1_apparies_audit/, ticket 101 lot 1 — script paired_audit_unitaire.py,
sortie paired_audit_B2000.json. Les estimations ponctuelles recalculées par ce script reproduisent
celles d'audit_unitaire_058.py à 1e-9 près sur les douze bras ; le script refuse de publier au-delà.
Le bras « réglé pour lui » est prompt_expert_32 et son score est en échantillon : son intervalle
borne une variation d'échantillonnage, pas une performance de généralisation. -->


#### I.2 Précision et rappel par mode

| Décideur | vélo | voiture | TC | marche |
|---|---|---|---|---|
| Gradient boosté | 27,3 / 20,4 | 85,3 / 79,0 | 53,8 / 61,7 | 53,2 / 63,4 |
| Régression logistique à noyau | 25,2 / 19,3 | 85,2 / 78,1 | 52,6 / 60,4 | 51,1 / 62,7 |
| Forêt aléatoire | 25,5 / 13,9 | 84,5 / 77,2 | 51,2 / 60,6 | 50,8 / 64,0 |
| Logit multinomial | 24,2 / 18,3 | 84,3 / 76,8 | 49,1 / 57,5 | 49,1 / 60,0 |
| Durée minimale | 16,9 / 25,8 | 74,4 / 92,3 | 53,5 / 39,7 | 81,3 / 19,2 |
| Prompt expert | 15,0 / 22,5 | 80,1 / 80,4 | 49,7 / 55,2 | 62,9 / 47,2 |
| Tout-voiture | 16,1 / 2,3 | 72,6 / 95,8 | 42,3 / 25,3 | 35,9 / 16,2 |
| Prompt minimal | 14,7 / 24,1 | 81,2 / 75,1 | 42,8 / 60,0 | 61,2 / 44,2 |
| Jev, prompt expert | 14,0 / 18,1 | 80,3 / 75,6 | 44,7 / 43,8 | 48,6 / 56,3 |
| Jev, consigne `gemini-3.5` | 13,5 / 16,9 | 80,3 / 75,4 | 48,9 / 35,0 | 44,2 / 63,1 |
| Jev, prompt minimal | 11,1 / 19,0 | 82,3 / 60,9 | 33,2 / 64,1 | 49,9 / 43,3 |

Précision / rappel, en %. Effectifs déclarés : 431 vélo, 5 971 voiture, 1 562 TC, 1 652 marche.

Les deux paliers rappellent le vélo mieux que toute méthode ajustée, 22,5 et 24,1 % contre 20,4
au gradient boosté, et le paient en précision, 15,0 et 14,7 % contre 27,3. Ils perdent la marche,
rappel 47,2 et 44,2 % contre 63,4. Leur précision sur la marche est pourtant la meilleure du
tableau, 62,9 % : quand ils annoncent la marche ils ont raison, ils ne l'annoncent pas assez
souvent.

Les bras Jev répartissent leur erreur autrement. Sous la consigne écrite pour `gemini-3.5`, la
marche est rappelée à 63,1 %, au niveau du gradient boosté, et les transports collectifs tombent
à 35,0 % contre 55,2 % au prompt expert à modèle de langue : c'est là que part la masse que
l'exactitude ne retrouve pas. Sous prompt minimal, le rapport s'inverse sur les deux mêmes modes,
64,1 % de rappel en transports collectifs et 43,3 % sur la marche, et la voiture perd quinze
points de rappel. Son propre prompt expert refait le partage entre marche et transports
collectifs sans nommer ni l'un ni l'autre.

#### I.3 La matrice de confusion du prompt expert

| déclaré \ prédit | vélo | voiture | TC | marche |
|---|---:|---:|---:|---:|
| vélo | 97 | 227 | 62 | 45 |
| voiture | 345 | 4 799 | 540 | 283 |
| TC | 88 | 481 | 862 | 132 |
| marche | 116 | 488 | 269 | 779 |

L'audit porte un plafond : 1 295 déplacements, 13,5 %, ont leur mode déclaré absent des options
présentées, retiré par le verrou de chaîne ou par le plafond d'options. Aucun décideur ne pouvait
le trouver. Le compte va de 1 226 à 1 838 selon le décideur, les trois bras Jev portant les trois
valeurs les plus élevées.

La figure de cet audit est au § 6.4, figure 6.5.

<!-- source: scripts/progedo_logit/audit_unitaire_058.py sur le jeu enquete_058_test_20260316, douze décideurs, exécutions du 2026-09-16 au 2026-09-21 ; les deux bras LLM sont exp_gemini-35-fl_{promin02,proexp05}_jtir_pop-enquete_058_test_… et les trois bras Jev exp_jev-1130_{promin02,proexp05,proexp32}_jtir_pop-enquete_058_test_…, 12 562 décisions chacun. Rejeu du 2026-09-22, docs/traces/2026-09-22_lot0_entropie_support_unique/. Figures régénérées par scripts/analysis/plot_audit_unitaire.py. Les déplacements dont l'enchaînement est rompu (11) sont écartés, et 9 612 à 9 618 sont notés selon le décideur. -->

---

### Tickets associés à ce chapitre
- [Ticket 053](../../../tickets/ticket_053_acces_donnees_recherche_et_reproductibilite.md) — Sanctuarisation de la frontière de reproductibilité et accès aux données de recherche (Quetelet-Progedo)
- [Ticket 062](../../../tickets/ticket_062_revue_et_alignement_des_annexes_techniques.md) — Revue, complétion et alignement des Annexes techniques A à G (Chapitre 99)

