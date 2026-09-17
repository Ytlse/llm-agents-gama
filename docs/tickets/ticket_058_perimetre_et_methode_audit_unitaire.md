# Ticket 058 — Clarification du périmètre et méthodologie de l'audit unitaire à parité des 21 variables (Chapitre 6 § 6.3)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 suite à l'arbitrage de la tâche 15 de [`docs/paper/suivi_actions_publication.md`](../paper/suivi_actions_publication.md).
>
> **Touche l'article** : mise à jour et clarification méthodologique de la section 6.3 de [`docs/paper/article/fr/06_results.md`](../paper/article/fr/06_results.md).

## Contexte & Enjeux

Le brouillon actuel du chapitre 6 (§ 4.3 du fichier hérité de la v1.6) mentionne un audit unitaire sur un échantillon de $1\,000$ trajets extraits des microdonnées de l'enquête EMC² (`mode_choice_test.csv` issu de `eval_llm_on_survey.py`). 

Or, le reste de l'article a été réaligné sur un substrat unique en simulation : la **cohorte scellée v5** ($1\,000$ personas, $3\,299$ trajets cycliques). 

Il est nécessaire de clarifier et d'auditer méthodologiquement ce que mesure l'audit unitaire désagrégé :
1. **Mesure sur la cohorte scellée v5** : comparer les choix trajet par trajet entre le LLM et les modèles tabulaires sur les $3\,299$ déplacements contraints par les chaînes de la journée.
2. **Mesure sur l'enquête réelle (1 000 trajets)** : évaluer l'accord unitaire direct du LLM face aux choix réels déclarés par les Toulousains dans l'enquête.

## Ce que le ticket livre

1. **Arbitrage méthodologique du périmètre unitaire :**
   - Décider si l'audit unitaire du Chapitre 6 porte sur la cohorte scellée v5 (cohérence globale avec le reste de l'ablation), sur le sous-échantillon d'enquête (confrontation au sol réel), ou sur une présentation articulée des deux.
2. **Harmonisation des métriques micro-décisionnelles :**
   - Définir les indicateurs à publier à ce niveau de granularité : matrice de confusion 4x4, exactitude globale, entropie croisée et rappel par mode.
3. **Mise à jour rédactionnelle du § 6.3 de `fr/06_results.md` :**
   - Réécrire la section pour éliminer les anachronismes de la v1.6 et aligner rigoureusement la description sur le substrat et le protocole retenus.
4. **Ajout du footer des tickets associés** au bas de `06_results.md`.

## Arbitrage du 15 septembre 2026 — le périmètre est tranché

**Décision de l'auteur :** l'audit unitaire porte sur **les déplacements de l'enquête**, pas sur
la cohorte scellée. La raison est qu'il n'y a pas de choix : la cohorte est synthétique et
**aucune de ses personnes n'a déclaré le mode qu'elle a pris**. Il n'existe aucune vérité terrain
individuelle à confronter — l'exactitude n'y est pas « difficile à mesurer », elle n'y est pas
définie. Le `scores.json` d'une exécution ne porte d'ailleurs aucune exactitude, et c'est
cohérent.

Les deux échelles restent donc séparées et **ne se comparent jamais terme à terme** : le
composite agrégé se lit sur la cohorte scellée, l'exactitude désagrégée sur l'enquête. Le
chapitre 5 le dit au § 5.3 (réserve de lecture) et décrit le dispositif au **§ 5.4**.

### Le protocole retenu

1. **Échantillon.** Tirage dans la partition de test scellée de l'enquête
   (`scripts/progedo_logit/mode_choice_test.csv`, 13 045 déplacements, découpage par ménage,
   `split = test`), avec les poids de redressement. Ordre de grandeur visé : ~1 000 déplacements,
   soit environ un tiers d'un bras de campagne en appels LLM.
2. **Reconstruction de l'offre.** Pour chaque déplacement tiré, les itinéraires sont calculés par
   **les mêmes moteurs que la cohorte** — plus court chemin sur le graphe routier pour les modes
   directs, OpenTripPlanner sur les grilles horaires pour les transports collectifs — depuis les
   centroïdes des zones fines d'origine et de destination, à l'heure de départ déclarée. Sans
   cette étape, l'agent n'a rien à choisir : c'est elle qui conditionne tout l'audit.
3. **Parité stricte.** Tous les décideurs sont joués sur **la même offre** : agent au palier 1 et
   au palier 2, les quatre familles tabulaires renormalisées selon la règle 3 du chapitre 4, et
   l'*a priori* empirique. Les 21 variables sont celles de `feature_spec.json`.
4. **Métriques publiées.** Exactitude (pondérée et non pondérée), entropie croisée, matrice de
   confusion 4 × 4, rappel et précision par mode — la liste annoncée au § 4.1.
5. **Repères déjà établis**, sur les 13 045 déplacements et à titre de plafond tabulaire :
   LightGBM 0,785 · régression logistique à noyau 0,784 · forêt aléatoire 0,776 · logit
   multinomial 0,766 ; l'*a priori* « toujours la voiture » vaut 0,571, qui est la part observée
   de la voiture.

### Les deux écarts au terrain, déclarés et non corrigés

- **Origine et destination sont des centroïdes de zone fine**, pas des adresses : l'offre
  reconstruite est celle d'un déplacement représentatif de la zone. Les microdonnées ne portent
  pas de coordonnées, et la convention `lil-1750` interdit d'en redistribuer.
- **La journée réellement vécue par l'enquêté n'est pas reconstituable.** Les conditions du jour
  sont donc tirées dans la **fenêtre de recueil** (20 septembre → 18 février, jours ouvrés), et
  non dans l'année — ce qui rejoint le [ticket 023](ticket_023_fenetre_meteo_jeux_geles.md).

### Ce que l'audit ne fera pas

Il ne remplace pas le composite agrégé et ne le corrige pas. Un modèle peut mener sur l'exactitude
désagrégée et perdre sur les parts agrégées — c'est le résultat de Martín-Baos et al. (2023), cité
au § 4.1, et c'est exactement pourquoi les deux se publient côte à côte sans être résumés en un
classement.

---

## Critères d'acceptation
- [x] Le périmètre de données de l'audit unitaire est explicitement tranché et documenté (arbitrage du 15/09/2026 ci-dessus).
- [ ] L'échantillon est tiré et son offre d'itinéraires reconstruite.
- [ ] Les décideurs sont joués à parité sur cette offre, et les métriques publiées.
- [ ] La règle de parité des 21 variables est vérifiée sur les jeux de données évalués.
- [ ] La section 6.3 est réécrite en totale cohérence avec les chapitres 4 et 5.
- [ ] Le footer de `06_results.md` référence le ticket 058.

---

## Arbitrages du 16 septembre 2026 — le substrat est construit

### Les paliers changent de nom

« Palier 1 » et « palier 2 » deviennent **palier A (minimal)** et **palier B (expert)**. Le
renommage de l'article est différé et porté par un TODO en tête du chapitre 5 : il se fera en
une passe sur les 24 occurrences des cinq fichiers concernés.

### Les déplacements intra-zone sont écartés, et la lecture se fait par bande de distance

3 413 déplacements sur 13 045 (26,2 %) ont la même zone fine à l'origine et à la destination :
entre deux centroïdes confondus il n'y a pas d'itinéraire à calculer. Ils sont écartés, comme
le fait déjà le constructeur de jeu pour la cohorte (motif `origine_egale_destination`, 138
déplacements sur 3 299). L'audit porte donc sur **9 632 déplacements**, pour 2 930 enquêtés.

Le mode dépend d'abord de la distance, et c'est ce qui rend l'exclusion lisible. Mesuré :

| Bande | Gardés | Marche, tous | Marche, gardés |
|---|---|---|---|
| 0-1km | 1 684 / 4 338 (39 %) | 65,5 % | 64,6 % |
| 1-2km | 1 550 / 2 209 (70 %) | 24,2 % | 25,0 % |
| 2-5km | 2 708 / 2 807 (96 %) | 7,1 % | 5,5 % |
| 5-10km | 2 080 / 2 081 (100 %) | 1,3 % | 1,3 % |
| 10-20km | 1 121 / 1 121 (100 %) | 0,1 % | 0,1 % |
| 20-50km | 472 / 472 (100 %) | 0,2 % | 0,2 % |
| plus_50km | 17 / 17 (100 %) | 0,0 % | 0,0 % |
| **Total** | **9 632 / 13 045 (74 %)** | **27,6 %** | **17,2 %** |

La perte se concentre sur les deux premières bandes, et **la part de marche ne bouge pas à
l'intérieur d'une bande**. Les 10,5 points d'écart global sont un effet de composition, pas une
déformation du comportement observé. L'exactitude se publie donc **par bande de distance**, sur
les bornes du composite agrégé (`_DIST_BUCKETS`, axe pondéré 0,3), le chiffre global se lisant
à côté et non à la place.

### Les conditions du jour sont celles du jour réellement décrit

L'enquête porte sur la veille de l'entretien, et le fichier personnes date cette journée-là :
le jour de semaine calculé depuis `AN/MOIS/DATE` vaut `JOUR` (« jour des déplacements ») pour
20 462 personnes sur 20 463, et ne tombe jamais un samedi. La date est connue pour **les 9 632
déplacements**, du 19 septembre 2022 au 15 février 2023, sur 82 dates distinctes.

Le tirage dans la fenêtre de recueil prévu plus haut est donc remplacé par la date réelle de
chaque enquêté. Ce que cela ne donne pas : la météo historique de ces journées. Le fichier
météo couvre une année et s'indexe par (mois, jour) ; le bulletin est donc celui du bon jour
calendaire, pris dans notre année — un appariement saisonnier ancré sur le jour réel.

### Ce qui est servi au modèle

Le narratif lit sept champs, dont quatre sortent des 21 variables. L'arbitrage est de servir ce
que l'enquête permet de reconstruire, sans rien fabriquer : `residence_zone` (couronne de la
zone fine de résidence) et `travel_purposes` (motifs de la journée déclarée) sont servis ;
`income` est omis, EMC² Toulouse 2023 ne portant aucune variable de revenu ; `professional_activity`
est omis, sa nomenclature venant d'eqasim, et le narratif retombe sur `main_occupation`.

Le prénom, en revanche, ne peut pas être omis : `eqasim_loader` remplace un `name` vide par un
tirage Faker **sans graine**, ce qui ferait changer le prompt — et la clé du cache de décisions
— d'une exécution à l'autre. Il est donc tiré par graine dérivée du `person_id`, comme la
cohorte v6 depuis le ticket 074.

### Le libellé de zone n'atteint pas le modèle, et cela vaut aussi pour la cohorte

`eqasim_loader._parse_activity` construit ses `Location` sans le champ `zone` : sur le bras de
référence v6, le prompt part avec `destination_zone: None` pour 3 154 décisions sur 3 161. La
parité de l'audit est tenue parce que les deux côtés perdent ce champ. Le constat n'est pas
corrigé ici : rendre la phrase au modèle changerait le prompt de tous les bras déjà joués.

Effet de bord repéré au passage : trois personas de la cohorte portent un libellé dégradé
(« an unknown area in an unknown municipality ») alors que leur code INSEE désigne Toulouse ou
Bazus, le géocodage inverse étant resté muet à la génération. Sans conséquence tant que le
champ est jeté.

### Essai à blanc concluant

Sur 20 enquêtés (69 déplacements déclarés), le constructeur de jeu rend 89 paires — la
fermeture de journée est comptée, et elle tombe sur place pour 2 862 des 2 930 enquêtés, donc
sans coût. Résultat : 69 déplacements couverts, 20 `origine_egale_destination`, **0 erreur**,
94 s à concurrence 4. Les journées d'enquête passent les moteurs sans traitement particulier.

### Ce que l'audit coûtera

| Poste | Volume | Coût |
|---|---|---|
| Jeu (routage OTP/OSMnx) | ~9 700 itinéraires à calculer | ~1 h 50 à concurrence 8 |
| Palier A + palier B | ~6 400 sollicitations, ~990 requêtes par palier | 4 jours de quota (500 req/jour) |
| Quatre familles tabulaires, *a priori*, planchers | 9 632 décisions chacun | quelques secondes |


### La lecture est chaînée, et seulement chaînée (arbitrage du 16 septembre 2026)

L'audit ne publie que la lecture sous contrainte de chaîne, comme l'évaluation agrégée. La
lecture hors chaîne n'est pas produite.

**Conséquence à assumer dans la rédaction : la phrase « tous les décideurs sont joués sur la
même offre » devient fausse et doit disparaître.** Sous chaîne, l'offre dépend des choix déjà
faits — qui prend la voiture le matin la déplace, et l'option n'est plus là l'après-midi. Mesuré
sur les mêmes déplacements : les jeux d'options diffèrent entre décideurs sur 1 042 à 2 718
déplacements, et le mode déclaré manque des options présentées 947 fois pour `majvoiture`,
1 226 pour `lgbm`, 3 226 pour `alea`. C'est le gradient déjà mesuré au ticket 057 sur les
blocages de sortie.

Ce qui reste commun à tous, et constitue le seul plafond partagé : **85 déplacements** dont
aucun moteur ne sait produire le mode déclaré. L'exactitude maximale de l'audit est 99,1 %.

### La météo est celle du jour décrit

`dates_meteo.json` accompagne la population et donne, par personne, la date de sa journée
d'enquête. Le runner la ramasse par convention et le bulletin servi est celui de ce jour
calendaire, sans tirage. Le fichier vit **à côté** de la population : la date n'est pas un
trait de la personne et n'a à entrer ni dans le narratif ni dans la clé du cache. Absent — cas
de la cohorte —, le tirage par graine reste le dispositif, inchangé.

### Résultats des bras gratuits (16 septembre 2026)

| Décideur | Exactitude pondérée | Arbitrées | Forcées | Entropie croisée | Rappel vélo |
|---|---|---|---|---|---|
| `lgbm` | 71,5 % | 67,4 % | 82,7 % | 0,419 | 20,4 % |
| `klr` | 70,6 % | 66,2 % | 82,5 % | 0,438 | 19,3 % |
| `mnl` | 68,6 % | 64,2 % | 82,0 % | 0,478 | 18,3 % |
| `durmin` | 68,1 % | 65,3 % | 76,0 % | — | 25,8 % |
| `majvoiture` | 66,7 % | 61,7 % | 79,7 % | — | 2,3 % |
| `alea` | 23,5 % | 21,5 % | 41,7 % | 1,260 | 11,4 % |

L'heuristique de durée minimale égale le logit multinomial (68,1 % contre 68,6 %) et rattrape
plus de vélos que le gradient boosté. La forêt aléatoire manque : elle refuse de tourner sous
scikit-learn 1.9.1 alors que son artefact a été estimé sous 1.8.0.


### Le lancement du palier A butte sur deux garde-fous, dont un se trompe (17 septembre 2026)

**Premier garde-fou, faux : l'estimateur ignore le groupement d'agents.** `aptitude.verifier`
compare `sollicitations × marge` au cumul des `rpd_limit` — une requête par sollicitation. La
passerelle, elle, groupe : mesuré trois fois sur des runs en vol ou archivés, **6,5 à 8,0
sollicitations par requête API** (`proexp05` archivé 2 108/325 ; `proexp04` en vol 648/82 puis
976/122). Le palier A coûte donc environ 1 230 requêtes, soit 1,2 jour de quota cumulé, quand
l'estimateur annonce « ~10 jours » et refuse. Le refus est levé par `lancer --ignorer-aptitude`,
qui est l'échappement prévu ; corriger l'estimateur pour qu'il tienne compte du groupement reste
à décider, parce qu'il gate tous les lancements de campagne.

**Second garde-fou, juste : les deux clés Gemini étaient épuisées.** 500/500 chacune le
17 septembre à 06 h 15. Ce refus-là se produit au lancement et **aucun drapeau ne le lève** —
ni `--ignorer-aptitude`, ni `--attendre-fenetre`, que le message d'erreur suggère pourtant. Seul
le renouvellement du quota le lève (minuit heure du Pacifique, soit 9 h à Paris). Le message
gagnerait à ne pas conseiller un drapeau sans effet à cet endroit.

