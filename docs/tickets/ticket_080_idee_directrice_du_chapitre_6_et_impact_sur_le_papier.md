# Ticket 080 — L'idée directrice du chapitre 6 au vu des résultats, et son impact sur l'ensemble du papier

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-15. **Réécrit le même jour** après le rapport de
> `docs/traces/2026-09-15_09-20_ticket080_idee_directrice_chapitre6/rapport.md`, qui a établi que
> le chiffre ayant déclenché le ticket était calculé sur 8 % des décisions (§ 0.1).
>
> **Catégorie** : Rédaction & Publication (📄) / Modélisation Statistique (📊)
>
> **Objet principal — c'est une décision, pas une mesure.** Trancher ce que le chapitre 6
> démontre, puis en déduire ce qui change dans le reste du papier.
>
> **Touche l'article** : [`fr/06_results.md`](../paper/article/fr/06_results.md) en premier
> lieu, et par ricochet [`fr/00_abstract.md`](../paper/article/fr/00_abstract.md) (§ résultats),
> [`fr/01_introduction.md`](../paper/article/fr/01_introduction.md) (§ 1.3, hypothèse H0),
> [`fr/04_metrics_and_substrate.md`](../paper/article/fr/04_metrics_and_substrate.md) (§ 4.1),
> [`fr/04.5_prompt_calibration.md`](../paper/article/fr/04.5_prompt_calibration.md) (règle 2),
> [`fr/05_factual_neutral_prompt.md`](../paper/article/fr/05_factual_neutral_prompt.md),
> [`fr/08_limits_and_hybrid.md`](../paper/article/fr/08_limits_and_hybrid.md) et
> [`fr/09_conclusion.md`](../paper/article/fr/09_conclusion.md).
>
> **Ne mesure rien lui-même**, sauf ce qui se recalcule sans appel LLM depuis les fichiers du
> dépôt (c'est ce que fait le rapport du 15/09). Les campagnes appartiennent aux tickets 073,
> 074, 055, 046, 058. Ce ticket les ordonne et dit ce qu'on en attend pour décider.

---

## 0. Point de départ — ce qui est établi au 2026-09-15, 09:30 UTC

### 0.1 Le chiffre invalide

Le composite **5,35** du bras `gemini-3.5-fl + expert_gem_3.8_v2` (exécution
`2026-09-12_11_24_28`, campagne v5) a été calculé sur **274 lignes de `moves.csv`** — 198
décisions du premier jour, 85 personas — au lieu des 3 161 lignes (2 347 décisions, 867
personas) de tous les autres bras. Cause : arrêt forcé le 13/09 à 07:04:47 puis reprise à froid
qui a resservi les 3 299 décisions depuis le cache sans réécrire le journal des mouvements ; le
scoreur a scoré le journal tronqué sans alarme. `decisions.jsonl` est, lui, complet.

Rescoré sur le journal reconstitué (scoreur officiel, même formule, même périmètre que les
autres bras) : **6,17** de composite, **20,70** de L1 global, **12,53** hors choix unique.
Le prétendu « meilleur bras » était en réalité le moins bon des deux prompts experts.

### 0.2 Le tableau corrigé

Formule `v1_reference` (sha256 `0aeee565…`). Campagne v5, cohorte `population_1000_AAMAS_v5` :

| Bras | Composite EMD-JSD | L1 global | Hors choix unique |
|---|---|---|---|
| `lgbm` hors chaîne | 4,19 | 2,48 | 4,01 |
| `klr` hors chaîne | 4,22 | 4,32 | 3,99 |
| `mnl` hors chaîne | 4,32 | 6,42 | 4,18 |
| `rf` hors chaîne | 4,45 | 6,89 | 4,14 |
| `lgbm` **en chaîne** | **4,50** | 12,52 | 10,46 |
| `klr` en chaîne | 4,55 | 9,25 | 9,95 |
| `mnl` en chaîne | 4,96 | 11,37 | 11,15 |
| `rf` en chaîne | 5,10 | 8,42 | 10,45 |
| `gemini-3.5-fl` + `expert_gem_3.8_v2_neutre_justif` | **5,79** | 17,34 | 11,37 |
| `gemini-3.5-fl` + `expert_gem_3.8_v2` (reconstitué) | **6,17** | 20,70 | 12,53 |
| `gemini-3.5-fl` + `prooptv4` | 7,44 | 23,15 | 13,87 |
| `gemini-3.5-fl` + prompt minimal (palier 1) | 8,95 | 28,11 | 16,70 |
| `gemini-3.1-fl` + `expert_gem_3.8_v2` | 9,34 | 28,86 | 16,42 |
| `durmin` / `majvoiture` / `alea` | 26,93 / 32,68 / 55,95 | | |

Campagne v6 (`bascule_anglaise_v6_sans_gemini31`, ticket 074), cohorte
`population_1000_AAMAS_v6`, sceau `412efada…`, état au 15/09 07:00 UTC :

| Bras | Composite | L1 global | Hors choix unique |
|---|---|---|---|
| `lgbm` hors chaîne | 4,20 | 2,48 | 4,03 |
| `lgbm` en chaîne | **4,40** | 12,21 | 10,04 |
| `klr` en chaîne | 4,44 | 9,54 | 9,51 |
| `mnl` en chaîne | 4,82 | 10,68 | 10,57 |
| `rf` en chaîne | 5,05 | 8,99 | 10,14 |
| **`gemini-3.5-fl` + `prompt_expert_04`** (= `expert_gem_3.8_v2` en anglais) | **5,30** | 14,24 | 10,39 |
| **`gemini-3.5-fl` + `prompt_expert_05`** (= `pe04` sans la clause anti-marche) | **5,00** | 13,21 | **9,41** |
| `durmin` / `majvoiture` / `alea` | 27,37 / 33,03 / 55,85 | | |
| `prompt_expert_06` / `08`, `prompt_minimal_02`, `agy-gemini-38-f` | en cours au 15/09 12:00 | | |

**`pe05` rouvre la question de la lecture, et cette fois proprement.** Sur la lecture **hors
choix unique**, 9,41 place le prompt calibré **devant les quatre familles tabulaires**
(`klr` 9,51, `lgbm` 10,04, `rf` 10,14, `mnl` 10,57) ; sur le composite et sur le L1 global, il
reste derrière. Le choix de la lecture décide donc à nouveau du signe — d'où l'urgence du § 3.2,
et l'obligation de l'arrêter par le contrat avant de remplir le moindre emplacement.

**Le décalage v5 → v6 est systématique, non aléatoire.** Deux paires indépendantes de prompts
identiques au caractère près, traduits : `pe04` 6,16 → 5,30 (−0,86) et `neutre_justif`/`pe05`
5,79 → 5,00 (−0,79). Même sens, même amplitude. Ce n'est donc pas le non-déterminisme du modèle :
c'est la langue du prompt, la cohorte, ou les deux — et le rejeu à l'identique (§ 3.1) est le seul
moyen de les séparer.

**Trois lectures, un seul verdict.** Le prompt calibré est derrière les quatre familles
tabulaires en chaîne sur le composite et sur le L1 global, et entre `rf` et `mnl` hors choix
unique. La lecture de référence reste à écrire (§ 3.2), mais elle ne décide plus du signe.

**Le palier 2 porte toujours l'essentiel du gain** : 8,95 → 5,79 / 6,17 sur v5, soit 2,8 à 3,2
points ; le palier 1 sur v6 (`prompt_minimal_02`) tombe dans la journée.

**Le bras LLM bouge de 0,87 point entre v5 et v6** (6,17 → 5,30) pour le même prompt traduit,
le même modèle, la même graine ; les témoins bougent de moins de 0,15.

### 0.3 Ce que l'instrument sait distinguer (rééchantillonnage par grappe de personnes)

- **Résolution par bras** : IC95 ≈ ±1,3 point de composite (écart-type 0,65–0,9), pour tous les
  bras. Le bruit vient surtout de `distance` (σ 1,31 — strate `plus_50km`, n = 17) et de `age`
  (σ 0,64 — strates quinquennales de 32 à 77 décisions).
- **Différences appariées** (mêmes personas des deux côtés, 200 réplicats) :

| Comparaison | Δ composite [IC95] | P(Δ>0) |
|---|---|---|
| v6 `pe04` − `lgbm` | **+0,98 [−0,26 ; +2,39]** | 0,94 |
| v6 `pe04` − `klr` | +0,98 [−0,12 ; +2,51] | 0,95 |
| v6 `pe04` − `rf` | +0,41 [−0,64 ; +1,79] | 0,70 |
| v6 `pe04` − `mnl` | +0,61 [−0,62 ; +2,05] | 0,85 |
| v6 `pe05` − `lgbm` | +0,76 [−0,42 ; +1,93] | 0,88 |
| v6 `pe05` − `rf` | +0,18 [−0,87 ; +1,36] | 0,58 |
| v6 `pe05` − `pe04` | −0,23 [−0,99 ; +0,58] | 0,27 |

Sur la lecture **hors choix unique**, le signe s'inverse pour `pe05` : −0,48 [−2,38 ; +1,02]
face à `lgbm` (P(pire) = 0,30), −0,95 [−2,88 ; +0,65] face à `mnl` (P = 0,15). Devant, mais pas
démontrablement. **Aucune des deux lectures ne produit un écart séparable de zéro** : c'est le
fait central du chapitre, et il tient quelle que soit la lecture retenue.

L'ablation de la clause anti-marche (`pe04` → `pe05`) vaut −0,23 [−0,99 ; +0,58] sur v6, et
valait −0,47 [−1,34 ; +0,37] sur v5 (`v2` → `neutre_justif`). Ni l'une ni l'autre n'est
significative seule ; **les deux vont dans le même sens sur deux substrats indépendants**, ce qui
est l'argument le plus solide disponible pour cette mutation — et se dit comme tel, pas comme une
mesure significative.
| v5 `v2` − `lgbm` | +1,86 [+0,57 ; +3,29] | 1,00 |
| **v5 minimal − `v2`** | **+2,65 [+1,24 ; +3,75]** | 1,00 |
| **v5 minimal − `neutre_justif`** | **+3,12 [+1,83 ; +4,29]** | 1,00 |
| v5 `v2` − `neutre_justif` | +0,47 [−0,37 ; +1,34] | 0,91 |

  L'écart-type apparié vaut ≈ 0,7 à N = 1 000 : **aucune marge d'équivalence inférieure à
  1,4 point ne se conclut d'un run sur cette cohorte**, et les graines n'y changent rien — seule
  une cohorte plus grande ou plusieurs cohortes réduisent ce terme.

### 0.4 Décision par décision

Même prompt rejoué (v5 FR → v6 EN) : 86 % de modes les plus probables identiques, 44 % des
distributions déplacées de plus de 20 points — autant qu'entre le prompt minimal et le prompt
calibré (86 % / 43 %). `lgbm` v5 → v6 : 100 % / 0 %. `lgbm` face au LLM : 74 % d'argmax communs.
**La calibration déplace des parts agrégées sur un fond de décisions individuelles instables.**

### 0.5 Sous-classes (v6 `pe04` face à v6 `lgbm`, L1 en points)

Mieux : motif travail 12,6 vs 26,9 ; 2–5 km 15,1 vs 27,7 ; 1–2 km 14,8 vs 24,7 ; 45–49 ans
6,6 vs 18,8 ; 5–9 ans 17,0 vs 30,5 ; scolaires 13,2 vs 19,5. Moins bien : personnes au foyer
43,4 vs 20,8 (marche −22) ; chômeurs 32,3 vs 21,4 (voiture −16) ; achats 24,1 vs 13,2 (TC +10) ;
études 31,9 vs 20,8 (TC −14) ; 20–50 km 14,1 vs 2,6 ; 0–1 km 18,9 vs 7,4. Tous échouent : 15–19
ans (47–57), > 50 km (57–78), temps partiel, étudiants. Signature résiduelle du LLM : TC +4,
vélo ×2 (7,5 contre 4,1), voiture −5.

**Lecture principe par principe — deux des quatre portent, deux échouent.** Le prompt calibré
énonce quatre principes ; confrontés aux strates qu'ils visent explicitement :

| Principe du prompt | Strate visée | LLM vs `lgbm` (L1) | Verdict |
|---|---|---|---|
| Temps de vie des actifs | motif travail, actifs temps plein | 12,6 vs 26,9 ; 13,6 vs 15,4 | **porte** |
| Friction de chaîne | trajets 1–2 km et 2–5 km | 14,8 vs 24,7 ; 15,1 vs 27,7 | **porte** |
| Autonomie des aînés | retraités, 60–74 ans | 18,6 vs 13,3 ; 15,8 vs 8,2 ; 26,7 vs 19,3 | **échoue** |
| Logistique d'emport | motif achats | 24,1 vs 13,2 | **échoue** |

C'est un résultat d'ablation à part entière, et il est plus intéressant que le score global : la
calibration ne marche pas parce qu'elle « ajoute du raisonnement », elle marche sur deux
mécanismes précis et se trompe sur deux autres. À publier au § 6.2, et à confirmer sur les bras
v6 restants. Sur les deux dimensions **hors calibration** (couronne,
logement), le retard du LLM sur les tabulaires passe de +2 à +5 points à **+8**.

### 0.6 Ce que le prompt calibré est

Sa perte de calibration porte sur les mêmes cinq dimensions et le même fichier de cibles que le
score final (`cerema_values.yaml`). C'est un modèle ajusté à ~50 cellules agrégées de l'enquête,
par un médium qualitatif, comparé à des modèles ajustés à 13 045 trajets désagrégés. De plus,
d'après la provenance de `prompts.yaml`, **`prompt_expert_06`, `07` et `08` ont été édités au vu
des scores de la cohorte scellée v5** (« correction des dérives mesurées sur
`exp_gemini-35-fl_expgem38v2_…_v5` », « L1 global 17,34 »). Ils ne peuvent pas porter H0. Seul
`prompt_expert_04` (10/09, antérieur au premier run sur la cohorte) et son ablation `05` le
peuvent — sous réserve de confirmer sur quels personas les « 20 cas empiriques » de `pe03` ont
été mesurés.

---

## 1. Le basculement, énoncé sans détour — version corrigée

Le plan et le chapitre 1 annoncent une hypothèse **H0 de non-atteinte** sans marge chiffrée. Les
chiffres du 14/09 semblaient la renverser ; ils reposaient sur 8 % des décisions. Les chiffres
corrigés la remettent dans le bon sens — le prompt calibré est derrière — **mais à une distance
que le dispositif ne sait pas mesurer** : +0,98 [−0,26 ; +2,39] apparié. Publier « n'atteint
pas » serait aussi indéfendable que publier « atteint ».

Ce qui est établi : le palier 1 échoue nettement ; la calibration rattrape 2,8 à 3,2 points sur
les 4,5 qui séparaient le palier 1 du meilleur tabulaire ; les décisions individuelles du LLM
sont instables d'une exécution à l'autre là où le tabulaire est déterministe.

---

## 1 bis. Décisions de l'auteur, 2026-09-15 après-midi

Six décisions, prises en séance. Elles ferment des questions ouvertes du § 9 et en ouvrent une.

**D1 — Les quatre lectures sont toutes publiées, et le choix de celle qui porte le test est
reporté à la fin.** Les quatre sont : composite EMD-JSD toutes décisions ; composite hors choix
unique ; L1 global des parts ; lecture hors chaîne des bras tabulaires. Aucune n'est retirée du
chapitre 6.
*Réserve consignée, non bloquante :* arrêter la lecture après avoir vu tous les résultats est le
reproche que la § 3.2 anticipait. Ce que la décision impose en contrepartie, et qui la rend
tenable : les quatre lectures sont **publiées ensemble, pour tous les bras**, et le texte dit
**pourquoi** la lecture retenue l'est — par le contrat d'évaluation, jamais par le résultat
qu'elle donne. Un tableau à quatre colonnes où le signe change d'une colonne à l'autre est un
résultat honnête ; le même tableau amputé de trois colonnes ne l'est pas.

**D2 — Le bruit de mesure et les intervalles appariés sont acquis** (§ 0.3), ils entrent au
chapitre tels quels.

**D3 — Le rejeu à l'identique est préparé et entre dans la campagne.** Tous paramètres
identiques, graines comprises : `graine_ordre`, `graine_tirage`, `graine_calendrier` à 42, même
cohorte, même jeu gelé, même prompt, même modèle, τ = 0. Rien ne change que l'instant
d'exécution : ce qui bouge vient donc du modèle lui-même. Voir § 3.1 bis pour l'état de
préparation.

**D4 — Trois cohortes supplémentaires de 1 000 personas sont à générer**, et le meilleur prompt
expert est rejoué sur chacune. C'est l'axe 2 du ticket 073, et c'est le seul levier qui réduise
l'écart-type d'échantillonnage. Voir § 3.1 ter.

**D5 — L'audit unitaire contre les microdonnées de l'enquête est acté** comme livrable
d'avant-soumission (ticket 058). C'est le test qui répond à la question d'origine : l'agent
retrouve-t-il les choix réellement déclarés, déplacement par déplacement.

**D6 — Benchmark multi-modèles : abandonné puis rétabli le même jour.** La décision de s'en
passer est revenue ; le ticket 055 repasse **à faire**. Ce que ce retour change, et ce qu'il ne
change pas :

- **Ce qu'il apporte, et c'est considérable.** Le résultat le plus solide du chapitre 6 est
  intra-modèle : la calibration vaut +2,65 à +3,12 points de composite. Reproduire ce **signe**
  sur deux ou trois familles de modèles le fait passer d'une observation sur un modèle à une
  **propriété du prompt**. C'est le seul renfort disponible qui ne dépende pas d'une mesure de
  dispersion, et il répond d'avance à l'objection « vous avez trouvé une bizarrerie de Gemini ».
- **Ce qu'il coûte.** Du quota, en concurrence directe avec les rejeux (§ 3.1 bis) et les trois
  cohortes (§ 3.1 ter). L'ordre recommandé ne bouge pas : d'abord le palier 1 sur v6, puis le
  rejeu à l'identique, puis les cohortes, puis le benchmark. Compter **deux** bras par modèle,
  palier 1 et palier 2, pour que la comparaison porte sur l'écart et non sur le niveau, soit
  ≈ 3 h 30 et ≈ 4 200 sollicitations par modèle ajouté.
- **Ce qu'il ne faut pas en attendre.** Ni un classement de modèles, ni la variabilité
  inter-graines, que le ticket 073 mesure mieux et moins cher. Le chapitre 5 accueille un tableau,
  pas un catalogue : à huit pages, huit modèles alignés sont du remplissage.
- **Sur l'article.** La limite « nos résultats portent sur un seul modèle de fondation » reste
  écrite tant que la mesure n'existe pas ; elle se retire le jour où deux modèles montrent le
  même signe. La question 4 du § 9 se rouvre sous une autre forme : non plus « le benchmark
  existe-t-il », mais « combien de modèles, et dans le corps ou en annexe ». Recommandation :
  deux modèles en plus de Gemini, deux paliers chacun, un tableau dans le corps.

---

## 2. La décision — trois idées directrices candidates, réévaluées

### Option A — L'équivalence
Tombe telle quelle : ni la dispersion, ni la puissance ne la permettent. Survit sous sa forme
défendable : « **non séparable à cette puissance** », avec l'intervalle apparié imprimé.

### Option B — Le palier 2 fait le travail
Tient : 2,65 à 3,12 points appariés, IC loin de zéro, intra-modèle. À compléter d'un
avertissement que la mesure de § 0.4 impose : ce gain est un déplacement de parts, pas une
stabilisation des décisions.

### Option C — Le critère a changé de nature
Renforcée par les mesures : coût (`pe04` v6 : 6 197 s pour 2 468 requêtes ; `lgbm` : 33 s),
reproductibilité (14 % de bascules contre 0 %), et régime non tabulé (chapitre 7).

**Recommandation portée au ticket (à valider ou rejeter par l'auteur) :** B comme colonne
vertébrale, C comme clôture ouvrant sur le chapitre 7, A remplacée par l'estimation appariée.
Phrase proposée :

> À information égale, quatre principes qualitatifs ramènent un agent LLM à un point de
> composite des modèles ajustés sur l'enquête — un écart que ce dispositif ne sait ni confirmer
> ni exclure — mais la calibration déplace des parts, pas des décisions : d'une exécution à
> l'autre, un déplacement sur sept change de mode quand le modèle tabulaire n'en change aucun.

Titres candidats : « Ce que la calibration déplace, et ce qu'elle ne déplace pas » ; « Le prompt
rattrape presque le tableau » ; « À un point de l'oracle, et à quatorze bascules sur cent ».

**H0.** Sans marge écrite avant la mesure, elle n'est pas testable, et toute marge choisie
maintenant l'est après avoir vu 5,30. Deux issues propres : (a) retirer « pré-enregistrée » et
présenter une **estimation** appariée (signe, amplitude, intervalle) ; (b) pré-enregistrer
maintenant, avant les graines et le palier 1 v6, une marge ≥ 1,5 point justifiée par la
résolution de l'instrument, en acceptant « non concluant ». **Recommandation : (a).**

---

## 3. Ce qui manque pour trancher

### 3.1 La dispersion propre au LLM — bloquant pour toute phrase sur l'écart
Une seule mesure indirecte existe : 0,87 de composite et 14 % de bascules entre v5 (FR) et v6
(EN), langue et non-déterminisme confondus. **Il faut** : rejouer `pe04` sur v6 à l'identique
(même graine) — la mesure la moins chère et la plus informative —, puis trois graines de plus
(073 axe 1 ; cinq runs ≈ 12 300 requêtes ≈ 8 h 30 au débit actuel).

### 3.1 bis Rejeu à l'identique — prêt, sans code (D3)

La plateforme est déjà faite pour cela : une relance sur une expérience existante **ajoute une
exécution** dans le même dossier et n'écrase rien (règle E18), et le nommage refuse de dupliquer
une expérience dont aucun paramètre ne change — il renvoie explicitement vers la relance. Les
deux commandes, à passer quand la campagne courante aura rendu la main :

```
make experience-lancer NOM=exp_gemini-35-fl_proexp04_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_t0_nosim
make experience-lancer NOM=exp_gemini-35-fl_proexp05_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_t0_nosim
```

Chacune coûte ≈ 1 h 45 et ≈ 2 450 sollicitations. La comparaison se lit ensuite par
`experiences comparer EXEC_A EXEC_B`, plus le taux de bascule du § 0.4.

**Point d'arrêt.** Les faire porter par le moteur de campagne demande une **modification de
code** : `campagne.py` compte faite toute expérience dont l'état est `terminee` (l. 675), donc
une campagne de rejeux sauterait les deux. Plan proposé, à valider avant écriture — une clé
`rejeux:` dans le YAML de campagne, listant des expériences à relancer quel que soit leur état,
et un compteur d'exécutions attendues par expérience dans `etat.json` en remplacement du test
binaire « faite ». Tant que ce n'est pas validé, les deux commandes ci-dessus font le travail.

### 3.1 ter Trois cohortes supplémentaires — point d'arrêt sur le code (D4)

Le vivier est disponible et **déjà en anglais** (`data/population/toulouse_population_10000.json`,
11 329 personnes, 5 658 ménages, régénéré le 14/09) : une cohorte tirée aujourd'hui est
directement comparable à la v6. Le tirage est stratifié par ménage, et l'ordre d'entrée dans
chaque sous-cellule est celui de `sha256("aamas_seal_v4:" + household_id)`.

**Le sel est écrit en dur dans `scripts/AAMAS/seal_population.py`.** Tirer trois cohortes
distinctes des mêmes marges demande donc d'en faire un paramètre. Plan proposé, à valider avant
écriture :

1. Option `--sel` sur la sous-commande `select`, **valeur par défaut `aamas_seal_v4:`** — sans
   elle, rien ne change, et la non-régression se vérifie en rejouant la sélection v6 et en
   comparant les 1 000 `person_id` obtenus.
2. Le sel employé est journalisé dans `selection.json` et dans le `MANIFEST.yaml` du sceau, à
   côté de la version de règle : une cohorte dont on ne sait pas de quel sel elle sort n'est pas
   reproductible.
3. Trois sels, `aamas_cohorte_B:`, `C:`, `D:`, puis `seal` et le contrôle des treize marges pour
   chacune. Le **recouvrement de ménages** avec la v6 est mesuré et publié : ≈ 499 ménages tirés
   sur 5 658, le recouvrement attendu est faible mais non nul, et les sous-cellules étroites
   reprendront les mêmes ménages par construction.

**Coût aval, indépendant du code, et c'est lui qui domine.** Chaque cohorte exige son jeu gelé
d'itinéraires : celui de la v6 a demandé **1 h 52** de calcul d'itinéraires
(`data/jeux/population_1000_AAMAS_v6_20260316_EN/MANIFEST.yaml`, 20:43 → 22:35 le 14/09) et
38 Mo. Puis un bras LLM par cohorte, ≈ 1 h 45. Soit pour trois cohortes ≈ **6 h de préparation
et ≈ 5 h 15 d'exécution**, en supposant le quota disponible. La pile Docker est à l'arrêt au
moment où ces lignes sont écrites : la préparation des jeux ne peut pas démarrer avant
`docker compose up`.

### 3.2 La lecture de référence — à écrire au chapitre 4, par le contrat
Les trois lectures concordent désormais en signe ; le choix n'a plus l'air fait après coup, mais
il doit être écrit. Recommandation : la lecture **en chaîne, en masse** porte le test — seule
lecture où tous les décideurs affrontent les mêmes jeux de choix que l'agent ; hors chaîne =
référence face à l'enquête ; hors choix unique = diagnostic. Le fond reste le ticket 046.

### 3.3 Le palier 1 sur v6 — tombe aujourd'hui
`prompt_minimal_02` est le dernier bras LLM de la campagne. Il fixe l'ablation sur v6.

### 3.4 Les prompts admissibles — décision de protocole, gratuite
Déclarer `prompt_expert_04` comme unique palier 2 pour H0 ; `05` comme ablation ; `06`, `07`,
`08` comme « ajustés au vu de la cohorte », publiables en borne haute d'ajustement en
échantillon. Confirmer la population des « 20 cas empiriques » de `pe03`.
**Nuance sur `pe05`** : c'est `pe04` privé de la clause anti-marche, et cette suppression (M5) a
été mesurée sur la cohorte v5 le 13/09 (`neutre_justif`, 5,79 contre 6,16) avant d'être retenue.
`pe05` est donc une ablation **informée par la cohorte** : recevable comme ablation d'hygiène
(la clause était un a priori modal, motif indépendant du score), pas comme prompt pré-enregistré.
Si le palier 2 doit porter un seul prompt hors échantillon, c'est `pe04`.

### 3.5 Ce qui manquerait encore, par ordre de valeur ajoutée

| Manque | Pourquoi ça compte | Ticket |
|---|---|---|
| Garde-fou du scoreur sur journal tronqué + régénération du journal après reprise | le 5,35 n'aurait jamais dû exister | à ouvrir (ingénierie) |
| Intervalles par grappe et différences appariées dans `scores.json` | 6 s par bras ; sans eux tout écart < 1,4 est du bruit lu comme un signal | à ouvrir |
| Couronnes de résidence v6 non reconnues (`1st ring`…) | dimension d'affichage perdue, analyse hors calibration impossible sur v6 | 074 |
| Strates minuscules dans le composite (`plus_50km` n = 17) | première source du bruit du composite | 058 / formule |
| Rejeu à l'identique puis inter-graines | condition de toute phrase sur l'écart | 073 axe 1 |
| Audit unitaire contre les microdonnées de l'enquête | le seul test qui tranche « même cour » | 058 |
| Sensibilité à la cohorte | sur-apprentissage de cohorte ; seul terme qui réduit l'écart-type apparié | 073 axe 2 |
| Coût par bras (tokens, durée, €) | matière de l'option C | 004 / 054 |
| Autre site | **n'est pas un test, c'est un projet** ; à annoncer comme limite | — |

---

## 4. Impact sur l'ensemble du papier

| Section | Ce qui devient faux ou daté | Action |
|---|---|---|
| `fr/06_results.md`, « Pourquoi ce chapitre est à l'arrêt » | « à 0,85 point du LightGBM, le devance sur le L1 global, et devance les quatre familles hors choix unique » | **faux** — derrière sur les trois lectures ; réécrire avec l'apparié |
| `fr/06_results.md` § 6.2 | « plus du double de cette borne » | vrai (2,65 à 3,12) ; ajouter l'avertissement de § 0.4 |
| `fr/06_results.md` § 6.3 | « deux variantes distinctes » | l'une était tronquée ; sensibilité au prompt = 0,47 [−0,37 ; +1,34] |
| Résumé, § résultats | « aucune des deux conditions LLM n'atteint la référence dans la marge d'équivalence » | palier 1 : vrai ; palier 2 : indécidable — passer en estimation |
| § 1.3, C2 et H0 | « une hypothèse est préenregistrée… réfutée si… » | reformuler (§ 2 H0) |
| § 4.1 | « la lecture qui décide de tout » | ne décide plus du signe ; écrire la règle |
| `fr/04.5_prompt_calibration.md`, règle 2 | « aucun persona du jeu de test n'est vu au cours de la calibration » | **faux pour `pe06`–`pe08`** ; vrai pour `pe04` sous réserve |
| Chapitre 5 | inchangé : le palier 1 échoue bien | figer le chapitrage (§ 5) |
| Chapitre 7 | renforcé | inchangé, sa place monte |
| Chapitre 8 | cascade motivée par « le LLM ne sait pas faire » | motiver par coût (×190), reproductibilité (0 % vs 14 %), régime non tabulé |
| Chapitre 9, point 1 | « quatre fois plus fidèles en argmax (7,30 vs 29,81) » | chiffres périmés ; remplacer par les appariés |
| `relecture/01_introduction.md` 4.13 | « two hypotheses » | se règle par la décision H0 |
| Ticket 073 § 1 et note de statut | 5,3452 / 8,0910 « devant les oracles » | corrigés le 15/09 |

**Effet de bord à ne pas manquer :** « le prompt calibré arrive à un point de l'oracle » est une
mesure ; « le LLM comprend la mobilité » n'en est pas une — et « l'agent génératif rivalise sans
apprentissage » non plus, puisque le prompt est ajusté sur les mêmes cibles.

### 4 bis. Signalement du 2026-09-16, après la réécriture du chapitre 6 en `brouillon v0.2`

**Rien à corriger tout de suite.** Décision de l'auteur du 2026-09-16 : on reprendra ces
passages **à la fin**, quand toutes les mesures seront là — le rejeu des neuf bras LLM sur le jeu
corrigé (ticket 088 § 3.4), le prompt neutre sur `gemini-3.5-flash-lite`, le rejeu à l'identique
(073 axe 1) et les trois cohortes (073 axe 2). Ce qui suit est le constat, pas une action.

Ce qui a changé dans le chapitre 6 et qui déborde sur le reste du papier : l'ablation
neutre → réglé est désormais mesurée sur la cohorte **v6** et **sur deux fournisseurs**, en
différence appariée (2 000 réplicats, trace
`docs/traces/2026-09-16_19-00_ch6_apparies_neutre_regle/`), là où la version `v0.1` citait la v5
sous ⚠ et un seul modèle. Les trois exceptions de substrat disparaissent du chapitre.

| Section | Ce qui devient faux ou daté | Gravité |
|---|---|---|
| `fr/00_abstract.md` et `en/00_abstract.md`, corps § 3 | « il les égale […] En rééchantillonnant la cohorte, il passe devant l'oracle une fois sur huit. » L'écart au plafond est mesuré sur **trois** modèles portant la même consigne réglée : `gemini-3.5` +1,21 [+0,15 ; +2,34], `gemini-3.1` +4,91 [+3,68 ; +6,22], `mistral-large` +3,61 [+1,89 ; +5,50]. L'égalité vaut pour un modèle sur trois ; sur les deux autres l'intervalle exclut zéro sur les trois lectures. | **majeur** |
| `fr/00_abstract.md`, corps § 3 | « L'écart dépend du modèle de fondation, mesuré sur six familles [TBC] » — ce n'est plus un projet mais un résultat, sur trois modèles : le même texte donne 4,49 / 7,20 / 8,41 de composite selon le porteur, et l'écart entre le meilleur et le pire porteur (3,87 points) dépasse le gain que ce texte apporte au moins bon (2,89). | **majeur** |
| `fr/01_introduction.md` § 1.3 | « Une hypothèse est préenregistrée. » et « H0 est réfutée si la condition calibrée entre dans la marge d'équivalence » — le § 6.4 énonce qu'aucun test d'équivalence n'est rapporté. Déjà signalé le 15/09 au § 2 de ce ticket, toujours pas porté. | **majeur** |
| `fr/01_introduction.md` § 1.4 | « La section 6 présente l'ablation en quatre paliers […] et teste H0 » — le chapitre 6 n'emploie plus le vocabulaire des paliers (abandonné par le chapitre 5 en `v0.8`) et ne teste plus H0. | mineur |
| `fr/00_abstract.md`, en-tête de version | « transports collectifs à 15,9 % » ne se reproduit plus ; le prompt réglé publié au § 6.6 est à 16,0 %. | mineur |
| `article/README.md`, `fr/README.md`, `plan/PLAN.md` | le chapitre 6 y est « trame `v0.1` » et son titre « non arrêté » ; il est en `brouillon v0.2` et s'intitule **Résultats** (décision de l'auteur du 2026-09-16, contre les trois candidats du § 2 : le titre ne doit pas annoncer une conclusion). | mineur |

**Vérifiés et indemnes :** `fr/04_metrics_and_substrate.md` § 4.4 — tableau sur le jeu corrigé,
cohérent avec le § 6.1, et l'ordre `lgbm`/`klr` y est déjà donné pour non significatif ;
`fr/05_factual_neutral_prompt.md` § 5.2, dont l'emplacement `[xx]` du prompt neutre sur
`gemini-3.5` correspond, et § 5.4, dont « les planchers valant sept à quatorze fois le composite
du plafond » se vérifie (26,97/3,60 = 7,5 ; 50,16/3,60 = 13,9) ; `fr/03_architecture.md` ;
`fr/02_related_work.md` ; `fr/07`, `08`, `09`, brouillons dont aucun chiffre n'est repris.

**Non recalculable en l'état :** le taux d'instabilité de 86,1 % du § 6.7. Les expériences v5 ne
sont plus sous `data/experiences/`. Conservé, marqué **TBD**, sa limite écrite en commentaire —
il confond non-déterminisme du modèle et effet de la traduction du prompt (073 axe 1).

---

### 4 ter. Signalement du 2026-09-17, après la réorganisation du chapitre 6 en `brouillon v0.3`

**Ce ticket ne se clôt pas tant que les trois entrées majeures ci-dessous ne sont pas statuées.**
Statuer veut dire : soit le passage est corrigé dans le chapitre concerné, soit l'auteur décide
par écrit de le laisser tel quel, et la ligne porte alors la mention « laissé en l'état, décision
du <date> ». Une entrée majeure sans l'une ou l'autre de ces marques interdit le passage du
ticket à `terminé`.

Ce qui a changé dans le chapitre 6 : réorganisation en cinq sections autour du couple
modèle-consigne ; quatre figures en anglais régénérables (`scripts/analysis/plot_chapitre6.py`) ;
vocabulaire aligné sur le dépôt (décideur, prompt minimal, prompt expert), au chapitre 5 comme
au 6 ; le coût d'exécution déplacé au chapitre 9 ; l'exactitude sur les choix observés accueillie
au § 6.4 ; l'écart entre deux modèles d'un même fournisseur mesuré en différence appariée (trace
`docs/traces/2026-09-17_08-00_ch6_meme_fournisseur/`).

| Section | Ce qui devient faux ou daté | Gravité | Statut |
|---|---|---|---|
| `fr/00_abstract.md` § 3 et `en/00_abstract.md` § 3 | « ramène le meilleur modèle, en distribution, à 1,2 point du gradient boosté ». Recalculé une fois la campagne finie, sur le jeu corrigé et avec `prompt_expert_05` des deux côtés, l'écart vaut **+1,35 [+0,28 ; +2,47]** face au gradient boosté et **+1,38 [+0,32 ; +2,45]** face à la régression à noyau — il exclut zéro face à ces deux méthodes — mais **+0,94 [−0,06 ; +1,98]** face à la forêt aléatoire et **+0,96 [−0,18 ; +2,17]** face au logit, où il ne l'exclut pas. | **majeur** | **corrigé le 2026-09-17** : les deux résumés portent 1,4 point, et leurs métadonnées disent que l'écart exclut zéro face à deux des quatre méthodes |
| `fr/00_abstract.md` et `en/00_abstract.md`, métadonnées (l. 12-13) | Renvois « § 6.5 » (désaccord décision par décision) et « § 6.6 » (vélo, transports collectifs) : ces sections n'existent plus. Le désaccord est au § 6.4, le vélo au § 6.3. Le mot « bras » y désigne encore les décideurs. | **majeur** | **corrigé le 2026-09-17** |
| `fr/01_introduction.md` § 1.2 et § 1.3 | « prompt factuel neutre et circonstancié » et « prompt calibré à la main » nomment des conditions que les chapitres 5 et 6 appellent désormais **prompt minimal** et **prompt expert** (environ six occurrences). | **majeur** | **corrigé le 2026-09-17** |
| `fr/04_metrics_and_substrate.md` § 4.1 | « la résolution atteinte est de ±1,3 point de composite par bras » — même formulation que celle corrigée au chapitre 5 (elle ne dit pas de quel instrument il s'agit), et le mot « bras ». | mineur | **corrigé le 2026-09-17** |
| `fr/07_untabulated_regimes.md` (tableau des conditions, § 52), `fr/08_limits_and_hybrid.md` (l. 22), `fr/99_annexes.md` | « bras » employé pour désigner une condition expérimentale. | mineur | **corrigé le 2026-09-17** |
| `fr/08_limits_and_hybrid.md` | ses sous-sections sont numérotées 6.2 et 6.3, ce qui entre en collision visuelle avec les renvois au chapitre 6. | mineur | laissé en l'état : la renumérotation du chapitre 8 est un chantier à part |
| `fr/README.md` (l. 198-199), `plan/PLAN.md` (l. 71-72) | décrivent un chapitre 6 en sept sections, avec un § 6.5 SHAP qui n'existe dans aucune version mesurée. | mineur | **corrigé le 2026-09-17** |


**Avancement du 2026-09-17, après la fin de la campagne de rejeu.** La campagne
`rejeu_jeu_corrige_v6` s'est terminée à 09:25 : les neuf décideurs à modèle de langue existent
sur le jeu corrigé, et le chapitre comme l'annexe H sont passés sur ce seul substrat
(`gemini-3.5` expert 4,86 au lieu de 4,49, `gemini-3.1` expert 8,98 au lieu de 8,41, variantes 06
et 08 à 5,33 et 6,58). Les six entrées ci-dessus marquées **corrigé** l'ont été le même jour. Il
les sept entrées ci-dessus sont statuées le même jour, six corrigées et une laissée en l'état.

**Le recalcul complet a rendu** (`docs/traces/2026-09-17_09-40_ch6_jeu_corrige_complet/`) :
quatorze différences appariées, 2 000 réplicats, tous les décideurs sur le jeu corrigé. Il
déplace deux conclusions du chapitre. L'écart au plafond exclut désormais zéro face au gradient
boosté (+1,35 [+0,28 ; +2,47]) et à la régression à noyau, et ne l'exclut pas face à la forêt
aléatoire ni au logit : la proximité se lit méthode par méthode, non contre un plafond unique. Et
le gain d'ingénierie de prompt ne va plus au modèle contre lequel la consigne a été réglée —
`gemini-3.1` gagne 3,37 points là où `gemini-3.5` en gagne 2,27, ce qui ne change pas l'énoncé du
chapitre, l'écart entre les deux modèles (4,15) restant supérieur au gain du moins bon (3,37).

**Ce qui interdit encore la clôture** : les deux **TBC** du § 6.5 (dispersion inter-graines,
ticket 073 axe 1) et les deux `[xx]` du § 6.4 (exactitude unitaire de l'agent, ticket 058). Ce
ne sont pas des impacts non statués mais des mesures manquantes ; le verrou de clôture posé plus
haut est levé pour les entrées d'impact.

**Vérifiés et indemnes :** `fr/02_related_work.md` (le mot « bras » n'y désigne pas une condition
expérimentale) ; `fr/03_architecture.md` ; `en/01` à `en/04`, dont les chiffres tabulaires (3,60
à 4,09, parts cibles) sont ceux du jeu corrigé ; les `.tex` d'`overleaf/`, qui s'arrêtent au
chapitre 4 ; `relecture/00_abstract.md` et `relecture/01_introduction.md`, grilles sans chiffre
du chapitre 6.

**Deux emplacements ouverts dans le chapitre lui-même**, qui ne sont pas des impacts mais des
mesures manquantes : les deux `[xx]` d'exactitude de l'agent au § 6.4 (ticket 058, la jointure
aux modes déclarés de l'enquête n'est pas outillée) et les deux **TBC** du § 6.5, qui anticipent
la dispersion inter-graines du ticket 073 axe 1 sur décision de l'auteur.

---

## 5. Chapitrage figé le 2026-09-15 (décision de l'auteur)

Le numéro intercalaire `4.5` disparaît : aucun article publié ne porte une section 4.5, et sa
présence signale une insertion tardive. Son contenu rejoint le chapitre 5, qui devient le
chapitre de **protocole**, le 6 restant celui des **résultats**.

### Chapitre 5 — protocole

> **5. Quatre façons de choisir, une seule information**

- **5.1 Le prompt factuel neutre : tout dire de la personne et du trajet, rien de la décision**
  (actuel `05` § 5.1)
- **5.2 Le prompt calibré : optimiser sans apprendre l'enquête par cœur**
  (actuel `04.5` § 4.5.1, 4.5.3, 4.5.4) → **un seul paragraphe** note que la calibration
  génétique a été écartée sur son coût en tokens ; **un autre dit quel prompt porte le palier 2
  et pourquoi les autres n'en sont pas** (§ 3.4).
- **5.3 Les deux bouts de l'échelle : planchers et références tabulaires** (actuel `06` § 6.1)

*Supprimé :* la section sur le goulet computationnel du génétique (actuel `04.5` § 4.5.2) ; sa
perspective part au chapitre 8.

### Chapitre 6 — résultats

> **6. \<titre à arrêter avec l'idée directrice — candidats en § 2\>**

- **6.1 Un tableau, trois lectures, un signe** — les bras, la lecture qui porte le test, les
  intervalles appariés
- **6.2 Ce que la calibration déplace** — palier 1 → 2, l'ablation proprement dite
- **6.3 Ce qu'elle ne déplace pas** — bascules individuelles, rejeu à l'identique (actuel `05` § 5.3)
- **6.4 Trajet par trajet, à information égale** — audit unitaire sur les 21 variables
- **6.5 Ce que le modèle dit faire et ce qu'il fait** — SHAP contre justifications
- **6.6 L'angle mort sur les modes minoritaires** — vélo ×2, TC +4, et les strates que tout le
  monde rate
- **6.7 Bien classer l'enquête ne suffit pas à simuler la ville**

*Abandonnés :* « le prompt ne rattrape pas le tableau » (démenti le 15/09 au matin) et « trois
lectures, trois verdicts » (démenti le 15/09 à midi).

*Déplacé :* le benchmark multi-modèles (actuel `05` § 5.2) va en annexe ou se réduit à un tableau
dans 6.1.

---

## 6. Livrables attendus

1. **Une décision écrite** : laquelle des options porte le chapitre 6, et son titre.
2. **La règle de lecture de référence**, écrite au chapitre 4 et justifiée par le contrat.
3. **La reformulation de H0** au § 1.3 et dans le résumé — estimation appariée, ou marge
   pré-enregistrée avec sa justification.
4. **La liste des prompts admissibles** au palier 2, écrite au chapitre 5.
5. **Le chapitre 6 réécrit** selon le chapitrage du § 5, une fois 073 (rejeu à l'identique au
   minimum) et 074 (`prompt_minimal_02`) livrés.
6. **La répercussion** sur les chapitres 4.5, 8 et 9 et sur le point 4.13 de la relecture.
7. **Deux tickets d'ingénierie ouverts** le 15/09 : [081](ticket_081_garde_fou_du_scoreur_sur_journal_tronque.md) (garde-fou du scoreur + régénération du journal) et [082](ticket_082_couronnes_de_residence_v6_non_reconnues_par_le_scoreur.md) (couronnes v6). Les intervalles dans `scores.json` restent à ouvrir.

## 7. Critères d'acceptation

- [ ] L'idée directrice du chapitre 6 est écrite en une phrase, datée, dans ce ticket.
- [ ] Aucune phrase du papier n'affirme une équivalence ou une infériorité sans intervalle apparié.
- [ ] La lecture de référence est fixée au chapitre 4 **avant** que le moindre emplacement chiffré
      du chapitre 6 ne soit rempli.
- [ ] Tous les chiffres publiés viennent de la campagne v6, aucun de v5, et aucun d'une exécution
      dont `lecture.total` s'écarte de 3 161.
- [ ] Le prompt qui porte le palier 2 est nommé, et les prompts édités au vu de la cohorte sont
      étiquetés comme tels.
- [ ] Le résumé, le § 1.3, la règle 2 du chapitre 4.5 et le chapitre 9 ne contredisent plus le
      chapitre 6.
- [ ] Le numéro de section `4.5` n'existe plus ni dans `fr/`, ni dans `plan/PLAN.md`.

## 8. Liens

- Rapport du 15/09 : `docs/traces/2026-09-15_09-20_ticket080_idee_directrice_chapitre6/rapport.md`
  (hors git ; scripts, journaux reconstitués, intervalles).
- [Ticket 081](ticket_081_garde_fou_du_scoreur_sur_journal_tronque.md) — garde-fou du scoreur et régénération du journal après reprise (ouvert le 15/09).
- [Ticket 082](ticket_082_couronnes_de_residence_v6_non_reconnues_par_le_scoreur.md) — couronnes de résidence v6 (ouvert le 15/09).
- [Ticket 073](ticket_073_reproductibilite_prompt_calibre_multi_graines_multi_populations.md) — rejeu à l'identique, inter-graines, cohortes. **Dépendance dure.**
- [Ticket 074](ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md) — campagne v6 ; couronnes v6 à corriger.
- [Ticket 058](ticket_058_perimetre_et_methode_audit_unitaire.md) — audit unitaire ; strates minuscules du composite.
- [Ticket 046](ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md) — l'asymétrie derrière la lecture de référence.
- [Ticket 057](ticket_057_audit_et_reflexion_double_lecture_tabulaire.md) — double lecture en chaîne / hors chaîne.
- [Ticket 055](ticket_055_benchmark_multimodeles_et_variabilite.md) — benchmark multi-modèles.
- [Ticket 054](ticket_054_sobriete_computationnelle_prompt_calibration.md) — coût de la calibration, option C.
- [Ticket 061](ticket_061_finalisation_chapitre_9_conclusion.md) — la conclusion, après celui-ci.

## 9. Questions ouvertes

1. H0 : estimation (a) ou marge pré-enregistrée (b) ? Si (b), quelle marge, et acceptée comme
   possiblement « non concluante » ?
2. Sur quels personas les « 20 cas empiriques » de `prompt_expert_03` ont-ils été mesurés ?
   Si sur la cohorte v1 ou v5, `pe04` n'est pas non plus hors échantillon.
3. Combien de graines pour le 073 axe 1, sachant qu'elles ne réduisent pas le terme
   d'échantillonnage de cohorte (±1,4 apparié) ? Recommandation : un rejeu à l'identique d'abord,
   puis trois graines ; les cohortes supplémentaires comptent plus que la cinquième graine.
4. Le benchmark multi-modèles : combien de modèles, et dans le corps ou en annexe ? (La question
   « existe-t-il » est close le 15/09 : oui, D6 rectifiée le jour même.) Recommandation : deux
   modèles en plus de Gemini, palier 1 et palier 2 chacun, un tableau dans le corps du chapitre 5.
5. Le bras `agy-gemini-38-f` reste-t-il dans le papier ?
6. Faut-il retravailler la formule du composite (strates minimales) **avant** de publier le
   moindre intervalle, au risque de rescorer toute la campagne ?
7. Les deux modifications de code des § 3.1 bis et 3.1 ter sont-elles validées ? Sans la
   première, les rejeux se lancent à la main ; sans la seconde, il n'y a pas de cohorte
   supplémentaire, donc pas d'axe 2.
8. Les trois cohortes supplémentaires doivent-elles être **disjointes** de la v6 en ménages, ou
   simplement tirées d'un autre sel ? Disjointes, elles mesurent mieux la variance
   d'échantillonnage ; tirées d'un autre sel, elles reflètent ce qu'un autre chercheur obtiendrait
   en refaisant le tirage. Recommandation : autre sel, recouvrement mesuré et publié.

## 10. Journal

- **2026-09-15 matin** — ticket ouvert sur le constat « trois lectures, trois verdicts ».
- **2026-09-15, 07:00–09:30 UTC** — le 5,35 est établi comme calculé sur 274 lignes ; rescoré à
  6,17 ; v6 `pe04` tombe à 5,30 ; intervalles par grappe et différences appariées ; churn
  décisionnel ; dimensions hors calibration ; contamination de `pe06`–`pe08` établie par la
  provenance des prompts ; rapport écrit ; ticket réécrit ; ticket 073 corrigé.
- **2026-09-15, 10:00–12:00 UTC** — tickets [081](ticket_081_garde_fou_du_scoreur_sur_journal_tronque.md)
  et [082](ticket_082_couronnes_de_residence_v6_non_reconnues_par_le_scoreur.md) **livrés** : le
  scoreur refuse un journal incomplet et écrit `perimetre_verifie`, la reprise régénère le
  journal, les quatre couronnes sont de retour sur v6. L'exécution du 12/09, régénérée et
  rescorée par la plateforme, donne **6,157** — la reconstitution manuelle annonçait 6,17.
  `prompt_expert_05` tombe à **5,00 / 13,21 / 9,41** : devant les quatre tabulaires sur la lecture
  hors choix unique, derrière sur les deux autres. Le décalage v5 → v6 est établi systématique
  (−0,86 et −0,79 sur deux paires). Restent `pe06`, `pe08`, `prompt_minimal_02`, et le bras
  Antigravity repoussé en fin de file après un démarrage sans décision.
- **2026-09-15, fin d'après-midi** — D6 **rectifiée** : le benchmark multi-modèles est rétabli,
  ticket 055 à faire, et ce qu'il apporte est écrit au § 1 bis. Le chapitre 6 est **installé**
  dans l'arbre de l'article après accord du verrou, sous le nom `fr/06_results.md` (renommé de
  `06_ablation.md`), avec une règle de substrat visible : trois exceptions ⚠ citant la cohorte
  archivée, chacune portant sa raison et la mesure qui la remplacera.
- **2026-09-16 soir** — chapitre 6 réécrit en entier, `brouillon v0.2`, titre arrêté à
  **Résultats**. L'ablation neutre → réglé passe sur la v6 et sur deux fournisseurs : −2,89
  [−3,68 ; −2,12] sur `gemini-3.1-flash-lite`, −7,17 [−8,70 ; −5,69] sur `mistral-large-2512`,
  2 000 réplicats (trace `2026-09-16_19-00_ch6_apparies_neutre_regle`). Les trois exceptions ⚠ de
  substrat disparaissent. Trois résultats neufs, sans un appel de modèle : le transfert du même
  prompt d'un modèle à l'autre (l'écart entre porteurs dépasse le gain du texte), la pente de
  distance que le levier de calibration installe et sur laquelle l'agent devance les quatre
  méthodes ajustées, et le bloc des méthodes tabulaires (89–92 % d'accord entre elles) que ni un
  agent ni deux agents entre eux ne rejoignent (70 % et 73 %). Substrat : bras déterministes sur
  le jeu corrigé, bras LLM marqués **TBD** en attendant le rejeu du 088 § 3.4. Signalement
  d'impact sur les autres chapitres consigné au § 4 bis — **à traiter à la fin**, pas maintenant.
- **2026-09-15 après-midi** — six décisions de l'auteur, consignées au § 1 bis : quatre lectures
  publiées et choix reporté à la fin, rejeu à l'identique préparé, trois cohortes à générer,
  audit unitaire acté, benchmark multi-modèles abandonné. Deux points d'arrêt code ouverts
  (§ 3.1 bis et ter). Première version du chapitre 6 rédigée hors de l'arbre de l'article, en
  attente de l'accord du verrou.
