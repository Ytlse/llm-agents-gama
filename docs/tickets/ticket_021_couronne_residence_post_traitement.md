# Ticket 021 — La couronne de résidence, posée à la génération et non devinée à la distance

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité.
>
> **Nature du ticket** : *correction*. Il traite les **deux écarts « à corriger »** rendus
> par le [ticket 020](ticket_020_perimetre_population_cerema.md) — l'axe **A2** (couronnes
> définies par distance et non par commune) et l'axe **A4** (domiciles hors du périmètre
> d'enquête classés en 3ᵉ couronne). Un seul trait les résout tous les deux, parce qu'ils
> sont la même question posée deux fois : *dans quelle zone de l'enquête ce domicile
> se trouve-t-il, et s'y trouve-t-il ?*
>
> **La voie retenue est un post-traitement de la population générée**, pas une modification
> du classement au runtime. La raison est chiffrée au § « Pourquoi un post-traitement » :
> la voie runtime invalide trois caches et exige un run complet, pour corriger une chose
> que la population sait déjà.
>
> **La mesure se fait sur le jeu gelé `v7`**, dernière base de référence du registre
> `scripts/synthesis/avancement.yaml`. Le § « La mesure » dit pourquoi, et surtout ce que
> `v7` ne peut pas mesurer.

## Ce que le ticket 020 a établi, et qu'on ne remesure pas

Mesures du 2026-08-24, archivées dans
[`docs/traces/2026-08-24_perimetre_population/`](../traces/2026-08-24_perimetre_population/README.md) :

| | |
|---|---|
| Personas changeant de couronne (population de référence, 1 021) | **249 · 24,4 %** |
| Personas changeant de couronne (population du run, 930) | **178 · 19,1 %** |
| Faux Toulousains | **66** — Blagnac 21, Balma 19, Tournefeuille 6, Colomiers 5, Ramonville 5, L'Union 4, Aucamville 3, Launaguet 2, Auzeville-Tolosane 1 |
| Domiciles hors des 453 communes | **45 · 4,4 %**, de 48 à 114 km du Capitole |
| Part du stratum « 3ᵉ couronne » publié qui n'est pas dans le périmètre | **76 %** (45 sur 59) |
| Effet sur la note : L1 moyen pondéré par zone | **47,8 pt publié contre 50,7 pt correct** |

L'erreur est **unidirectionnelle** : les 179 zones fines de la commune de Toulouse sont
toutes à moins de 7,0 km de l'hypercentre, donc le disque de 8 km ne perd aucun Toulousain
— il en capte. Il **gonfle Toulouse et vide la 1ʳᵉ couronne**, où la cible `voiture` passe
de 31 % à 64 %.

Ce ticket ne rejoue pas ces mesures. Il les prend pour acquises et corrige. En revanche il
**ne réutilise pas non plus le 47,8 → 50,7 tel quel** : ces deux nombres viennent du
move-log du run du 2026-08-24, dont le périmètre de records n'est pas celui de `v7`. Ils
donnent l'ordre de grandeur attendu, pas le résultat à publier.

---

## Pourquoi un post-traitement, et pas une correction du classement au runtime

`geo_reference.residence_zone` a **trois appelants de production**, et c'est la clé de tout
ce ticket :

| Appelant | Ce qu'il classe | Entre-t-il dans un cache ? |
|---|---|---|
| [`move_logger._residence_zone`](../../llm-agents/urban_mobility_agents/utils/move_logger.py) | le **domicile** de l'agent → colonne « Lieu de résidence » du journal, donc tout le scoring par zone | **non** — le journal est un CSV de sortie |
| [`osmnx_direct._make_travel_plan:192`](../../llm-agents/trip_helper/osmnx_direct.py) | l'**origine** et la **destination** d'un trajet → temps terminal facturé (ticket 013) | **oui** — durées des plans, donc cache OTP *et* cache de décisions LLM |
| [`export_terminal_time.py:98`](../../scripts/progedo_logit/export_terminal_time.py) | les **785 centroïdes de zones fines** → les **strates des lois** de temps terminal | **oui, en amont** : la ressource `terminal_time_emc2.json`, dont le `meta.crown_definition` inscrit ce classement |

(`scripts/data/population/audit_perimetre.py` l'appelle aussi, mais c'est l'outil de mesure
du ticket 020 : il compare les deux classements, il n'en sert aucun.)

Les deux écarts du ticket 020 vivent **entièrement dans la première ligne**. Ce sont des
écarts de *lecture* : ils faussent la façon dont on note un run, pas la façon dont les
agents décident. Poser la couronne sur le persona à la génération corrige donc les deux
sans toucher aux chemins qui portent les caches — **aucun bump de `version` dans
`terminal_time.yaml`, aucun run à rejouer.**

La troisième ligne est aussi la raison pour laquelle aligner le temps terminal est un
ticket distinct et non un lot de plus : les lois elles-mêmes sont **stratifiées par le
classement métrique**. Les basculer ne demande pas de changer un `if` au runtime, mais de
**ré-exporter la ressource** (version 2 → 3) et de rejouer ce qui en dépend.

### La divergence que ça crée, et pourquoi elle est acceptable — mais pas invisible

Le docstring de `geo_reference.residence_zone` avertit qu'un double classement
« ferait facturer un stationnement de centre-ville à un agent que le move-log dit en 2ᵉ
couronne ». C'est exact, et ce ticket **crée délibérément cette divergence**. Trois raisons
la rendent tenable, la troisième étant une condition à tenir :

1. **Les deux ne classent pas le même objet.** Le journal classe une *personne* par sa
   résidence ; le temps terminal classe un *point* d'origine ou de destination, qui n'est le
   domicile que pour une fraction des trajets. L'invariant qui compte est que les deux
   utilisent la même *définition de zone pour un point donné* — pas qu'ils rendent la même
   valeur pour deux objets différents.
2. **L'amplitude est bornée et mesurée.** Depuis l'alignement `tt3`, les lois de temps
   terminal sont massées à zéro et leurs moyennes valent :

   | couronne | accès | stationnement | total |
   |---|---:|---:|---:|
   | Toulouse | 0,36 min | 0,52 min | **0,87 min** |
   | 1ʳᵉ couronne | 0,14 | 0,17 | **0,30** |
   | 2ᵉ couronne | 0,16 | 0,19 | 0,34 |
   | 3ᵉ couronne | 0,09 | 0,06 | 0,15 |

   Le pire couple **observé** dans la matrice de confusion du ticket 020 est Toulouse
   contre 1ʳᵉ couronne (66 cas) : **34 secondes par bout de trajet**. Les deux autres
   couples observés valent 2 s (1ʳᵉ ↔ 2ᵉ, 57 cas) et 11 s (2ᵉ ↔ 3ᵉ, 79 cas). Le pire
   couple **possible**, Toulouse contre 3ᵉ couronne, vaudrait 43 s — il ne se produit pas.
   Sous `tt2` l'écart valait 4 minutes ; c'est le ticket 013 qui a absorbé le risque.
3. **La divergence doit être écrite dans le code, pas subie.** Une divergence documentée et
   bornée est une décision ; la même divergence non écrite est le bug de demain. Le lot 3
   l'inscrit dans le docstring de `residence_zone`, avec son amplitude et le ticket qui la
   fermera.

---

## La donnée : presque toute dans le conteneur

C'est le résultat qui rend ce ticket court. **La couronne se déduit du code de zone fine**,
sans nouvelle géométrie et sans nouvelle dépendance au runtime.

Le code `ZF` de l'enquête est un entier à 9 chiffres dont les **trois premiers sont le
numéro du secteur de tirage** (`NUM_DTIR`), et le secteur porte la couronne dans son champ
`NOM_D2`. [`export_commune_couronne.py`](../../scripts/progedo_logit/export_commune_couronne.py)
exploite déjà ce rattachement et **échoue si un seul code `ZF` ne s'y rattache pas** (0
orpheline sur 785) ou si une commune se retrouve à cheval sur deux couronnes.

Or `llm_module.core.zone_resolver` **résout déjà** un domicile en zone fine — c'est ainsi
que `housing_type` (ticket 019) et `bike_ownership` (ticket 015) travaillent — et sa
ressource `zf_zones.gpkg` est versionnée et montée dans le conteneur.

**Ce qui manque, et c'est ce qui fixe le grain de la table.** `zf_zones.gpkg` ne porte que
`ZF, XL93, YL93, SURF_M2, density_hh_km2, dist_center_km` : **ni `INSEE`, ni `COM`**. Une
table `secteur → couronne` de 88 lignes donnerait donc la couronne mais **jamais la
commune**, que l'axe B1 exige pour rendre l'imputation auditable. La table se publie donc
au grain **zone fine** : 785 lignes `zf → secteur, couronne, insee, commune`, depuis la
jointure que l'export calcule déjà en mémoire. Une sortie de plus, pas un travail de plus.

### Deux équivalences, mesurées le 2026-08-24 — c'était le lot 0

La première rédaction annonçait un « contrôle décisif, déjà passé ». Il ne l'était pas : ce
qui était établi était l'intégrité de la jointure `ZF → NUM_DTIR`, pas l'accord de deux
classements sur des domiciles. Les deux équivalences ont donc été mesurées avant tout code,
par `make audit-couronnes` — trace :
[`docs/traces/2026-08-24_couronne_equivalences/`](../traces/2026-08-24_couronne_equivalences/README.md).

| Porte | Ce qui n'allait pas de soi | Résultat |
|---|---|---|
| A | L'export vérifiait l'absence d'orpheline, pas la surjectivité sur les 88 secteurs | 88 secteurs, 88 préfixes, **0 orpheline, 0 secteur sans zone** |
| B | Rattachement par code contre jointure spatiale, au grain zone fine | **785 / 785 = 100,00 %**, au centroïde comme au point représentatif |
| C | Un domicile n'est pas un centroïde : il peut tomber près d'une frontière | **1 021 / 1 021 = 100,00 %** |
| D | Deux emprises construites séparément : union des 785 zones fines contre dissolution des 88 secteurs | 45 contre 45, **différence symétrique vide** |
| E | Recoupement **indépendant** contre la colonne `zone_communale` du ticket 020 | **1 021 / 1 021** |
| F | `zf_zones.gpkg` ne porte ni `INSEE` ni `COM` : la commune est-elle reproductible ? | **0** zone sans `INSEE`, **0** écart de commune sur les 976 |

Les sept portes passent : les lots 1 à 5 gardent la forme prévue. Le classement par préfixe
peut servir de chemin de production, `resolve() is None` peut servir de détecteur de
hors-périmètre — l'emprise normative restant le géojson des couronnes —, et la porte F
établit que la table doit bien se publier au grain **zone fine** : une table
`secteur → couronne` de 88 lignes n'aurait pas rendu la commune.

**Le garde-fou de couverture ne protège toujours pas ce cas** : l'alarme de `zone_resolver`
se déclenche à **15 %** de points hors couche (retombée 8 %, échantillon minimal 200). À
4,41 %, elle ne se déclenchera jamais. Ce n'est pas un seuil à vérifier, c'est un seuil qui
ne convient pas à cet usage.

---

## La mesure : sur le jeu gelé `v7`

`v7` est la dernière base de référence du registre `scripts/synthesis/avancement.yaml`
(production `tt3`). Trois propriétés vérifiées la rendent meilleure que le run courant :

- **2 710 records, 930 agents**, population
  `experiments/archive/2026-08-19_14_36/population_1000.json`, sha256 `cab69d4b…` conforme
  au manifeste, `home` renseigné sur les 930 — et ce fichier **porte déjà `housing_type` et
  `personal_bike`**. `residence_zone` rejoint la même famille, dans le même fichier.
- **« À décisions constantes » devient structurel.** Les records ne portent ni
  `lieu_residence` ni coordonnées, et la loss des jeux gelés ne connaît que
  `age, age_cat, occupation, genre, motif, dist_cat`
  ([`evaluation.py:297`](../../prompt_calibration/calibration/evaluation.py)). La couronne
  n'entre ni dans le prompt ni dans la note : elle se joint par `agent_id` au moment
  d'agréger. Zéro appel LLM.
- **L'axe sert l'article.** [`PROTOCOLE.md:108`](../../prompt_calibration/PROTOCOLE.md) fait
  du « lieu de résidence — Toulouse / 1ʳᵉ / 2ᵉ / 3ᵉ couronne » un des axes de la
  contribution T3. Corriger la couronne en est un prérequis, et la mesurer sur les jeux
  gelés, c'est la mesurer là où T3 sera publié.

### Pas de jeu `vN+1`, et pas de composite

**Pas de nouveau jeu.** Les lignes du registre opposent deux jeux (`v5`→`v6`, `v7`→`v8`)
parce que le **contenu du prompt** change. Ici rien du prompt ne bouge : mêmes records,
mêmes décisions, deux lectures. Un `v9` identique à `v7` sauf un descripteur que personne ne
lit serait un faux jumeau. La mesure passe par une **table de jointure**
`agent_id → couronne, commune`, archivée dans `docs/traces/`.

**Pas de composite.** `lieu_residence` n'est pas une dimension de l'évaluateur (ci-dessus) et
[`frames.py:114`](../../scripts/synthesis/frames.py) le marque `scored: False` : le composite
comparable ne bougerait **pas d'un millième**. Publier ce zéro serait le motif « vacuité ≠
perfection » en pleine page. Le score porté au registre est le **L1 de la dimension zone**,
avec un `score_caveat` qui dit pourquoi ce n'est pas un composite — champ prévu pour ça, déjà
utilisé par la ligne `car_availability`.

### Ce que `v7` ne peut pas mesurer

Ses 930 personas sont **bbox-filtrés** : aucun domicile hors couche. `v7` chiffre donc
**A2 seul**. A4 se chiffre sur la population de référence (1 021 personas, dont 45 dehors),
dans la même trace. La ligne du registre porte en conséquence `verdict: mesure` (« périmètre
partiel »), jamais `adopte`, et dit qu'aucun jeu gelé n'expose A4 aujourd'hui.

---

## Les axes, et ce qu'on tranche

| # | Axe | Décision |
|---|---|---|
| B1 | **Nom et forme du trait** | `residence_zone` **et** `residence_commune` dans `traits_json` — clés anglaises `snake_case` comme `housing_type` / `personal_bike` / `car_availability`, valeurs aux libellés de l'enquête. La couronne est ce que le scoring compare ; la commune est ce qui rend le classement auditable et survit à un redécoupage |
| B2 | **Hors périmètre** | `population_reference.OUT_OF_PERIMETER` (`hors périmètre`). Ce n'est pas une couronne, et [`test_population_reference.py:63`](../../llm_module/tests/test_population_reference.py) l'interdit déjà dans `COURONNES` |
| B3 | **Trait absent** | Colonne **vide**, comme `_housing_type` le fait déjà — et `move_logger` **cesse d'importer** `geo_reference.residence_zone`, ce qui rend le repli à la distance impossible par construction plutôt que par discipline. Le cas n'est pas résiduel : `toulouse_population_1000.json` ne porte aujourd'hui ni `housing_type` ni `personal_bike` |
| B4 | **Scoring du hors-périmètre** | Exclu des cibles par zone (il n'en a aucune) **et** sa masse comptée, sur le patron du drapeau `referenced` de `normalize_housing` et du `excluded_mass` de `global_view` |
| B5 | **Effet publié** | L1 de la dimension zone sur `v7`, à recalculer ; **le composite ne bouge pas** et `lieu_residence` reste `scored: False`. Le passer à `scored: True` rendrait incomparables les quatre lignes du registre et les scores stockés du DAG de calibration : hors périmètre |
| B6 | **Quel étage** | Étage **D** pour l'existant, étage **B** pour les générations neuves. **Pas l'étage A** : `enriched.py` travaille sur `spatial.home.locations`, coordonnées *avant* snap, alors que `llm_agents.py:439-446` snappe les localisations hors polygone OTP et que `identity.home` — que lit le journal — porte les coordonnées *après* snap. Poser la couronne en amont du snap la ferait diverger pour tout persona snappé |
| B7 | **Sort du classement métrique** | `COURONNE_BOUNDS_KM` reste, pour le temps terminal, qui classe des points quelconques **et dont les lois sont stratifiées avec lui**. Son docstring doit dire qu'il n'est plus la définition de la résidence, et que l'aligner demande de ré-exporter la ressource |
| B8 | **Où écrire quand la population est épinglée** | Les étages D réécrivent **en place**. Or `experiments/archive/2026-08-19_14_36/population_1000.json` est épinglé par sha256 dans les manifestes de `v5`, `v6`, `v7` **et** `v8` : l'enrichir casserait quatre jeux gelés. D'où `--out` sur ce seul script, et une table de jointure pour la mesure |

---

## Lots

0. **Lot 0 — Les deux équivalences — FAIT le 2026-08-24.**
   `scripts/data/population/audit_couronne_equivalences.py`, cible `make audit-couronnes`,
   aucun code de production : sept portes, dont un recoupement indépendant contre la trace
   du ticket 020. Toutes passent (§ ci-dessus). Codes de sortie `0 / 2 / 3` — le `3` dit
   **NON MESURABLE**, parce qu'une porte non mesurée est une porte qui passe. Les portes A,
   B et F exigent aujourd'hui la couche SIG d'accès restreint ; le script préfère déjà la
   table `zf_couronne.json` du lot 1 quand elle existe, et tournera alors sans elle.

1. **Lot 1 — La ressource et le classement — FAIT le 2026-08-24.**
   `export_commune_couronne.py` publie une troisième ressource,
   `llm_module/data/zf_couronne.json` (`version: zc1`) : 785 lignes
   `zf → secteur, couronne, insee, commune`, plus les 88 secteurs à part. Il a gagné
   l'assertion qui manquait — **aucun secteur sans zone fine** : l'absence d'orpheline
   disait que chaque zone trouve un secteur, pas que les deux couches décrivent le même
   périmètre. `llm_module/core/residence_zone.py` porte le lecteur (`CouronneTable`, qui
   refuse une version inattendue, une modalité hors `COURONNES`, un secteur à deux
   couronnes) et la classification de référence (`CommunalZones`), **montée depuis
   `audit_perimetre.py`** pour qu'il n'en existe qu'une — l'audit et la production lisent
   désormais la même. 16 tests
   ([`test_residence_zone.py`](../../llm_module/tests/test_residence_zone.py)) dont **la
   porte B rejouée à chaque exécution** : les 785 zones classées par code contre leur
   centroïde classé par appartenance. Une mesure ponctuelle se périme, un test non. Tous
   tournent sur ressources committées, sans `data/PROGEDO 2023`.

   *Détail utile pour le lot 2* : `couronne_of_zf` se replie sur le **secteur** quand le
   code de zone est inconnu — le secteur est le vrai porteur de la couronne dans l'enquête
   — mais `commune_of_zf` ne se replie **pas** : un secteur couvre plusieurs communes, et
   rendre « une commune du secteur » serait une invention.

2. **Lot 2 — Le post-traitement (étage D) — FAIT le 2026-08-24.**
   `scripts/data/population/enrich_residence_zone.py`, cible `make residence-zone`, ajouté
   en tête des enrichissements de l'étape 8 du notebook (il ne dépend d'aucun autre trait).
   Il résout chaque domicile par `zone_resolver`, lit la couronne par le **code** de zone
   fine, et écrit `residence_zone`, `residence_commune`, `residence_insee`. Déterministe et
   sans tirage : ce trait est **observé**, pas imputé — deux passes donnent le même octet,
   vérifié.

   **Trois écritures, trois significations** : une couronne dans le périmètre ;
   `hors périmètre` pour un domicile connu et dehors ; **aucun trait** sans coordonnées,
   parce qu'écrire « dehors » de quelqu'un dont on ne sait rien serait une affirmation. La
   commune ne s'invente jamais — un domicile hors couche n'en reçoit pas, et une zone
   résolue mais absente de la table ne reçoit rien du tout.

   `--check` porte sur ce que l'enrichissement maîtrise : couverture, **accord entre le
   classement par CODE et le classement par APPARTENANCE géométrique** (la porte du ticket,
   rejouée sur chaque population), modalités, taux hors périmètre sous le seuil d'alarme.
   L'écart au cadrage sort en **code 4** — informatif et distinct, parce qu'il mesure le
   tirage (axe A9) et non ce trait ; il se déclenche aujourd'hui sur les deux populations,
   ce qui est le comportement attendu. `--out` protège les populations épinglées par un
   manifeste de jeu gelé (B8) : vérifié, le sha256 de l'archive `2026-08-19_14_36` est
   inchangé après une passe.

   **Ce que la passe mesure au passage**, et qui recoupe le ticket 020 par un chemin
   indépendant : **249 personas (24,4 %)** de la population de référence auraient une autre
   couronne par distance à l'hypercentre, **178 (19,1 %)** sur la population des jeux gelés
   — exactement les chiffres publiés. 16 tests
   ([`test_enrich_residence_zone.py`](../../scripts/tests/test_enrich_residence_zone.py)),
   hors ligne, table et résolveur doublés.

3. **Lot 3 — Les lecteurs — FAIT le 2026-08-24.** `move_logger._residence_zone` prend
   désormais les `traits` et recopie le trait ; **son import de
   `geo_reference.residence_zone` a disparu**, et un test l'exige
   (`assert not hasattr(move_logger, "residence_zone")`) : le repli à la distance est
   impossible, pas seulement déconseillé. La colonne accepte `hors périmètre` — déclaré
   dans `RESIDENCE_VALUES` — et ramène à vide toute valeur hors référentiel, parce que la
   page de synthèse joint cette colonne sur les libellés EMC² et qu'une valeur exotique y
   disparaîtrait sans être comptée.

   Le docstring de `geo_reference.residence_zone` est réécrit : il s'annonce comme le
   **classement métrique du temps terminal**, dit que sa prétention à porter « les
   modalités de `lieu_residence` d'EMC² » était fausse et ce qu'elle a coûté, porte la
   divergence (34 s observés, 43 s possibles, avec la table des moyennes `tt3`), et dit
   que l'aligner exige de **ré-exporter** `terminal_time_emc2.json` — pas de changer un
   `if`. Le commentaire de `COURONNE_BOUNDS_KM` suit.

   **Les deux tests qui encodaient l'ancienne décision sont inversés**, et leur inversion
   *est* la décision : `test_une_seule_definition_des_couronnes` devient
   `test_les_deux_classements_sont_desormais_distincts` (il exigeait l'accord des deux, il
   exige maintenant l'absence de l'import), et `test_move_logger_hypercenter` sépare deux
   classes — les seuils métriques, qui restent pour le temps terminal, et la colonne du
   journal, qui recopie. 253 tests verts côté `llm-agents`.

4. **Lot 4 — Le scoring, la mesure, la publication — FAIT le 2026-08-24.**
   `frames.normalize_place` rend désormais `(clé, référencée)` comme `normalize_housing`,
   avec la clé ASCII `hors_perimetre` — la sortie brute donnait `hors_périmètre`, qui ne
   joignait rien et disparaissait sans un mot. `dimension_detail` publie une ligne
   supplémentaire `— hors référentiel —` portant la **masse exclue** de la dimension : sans
   elle, « exclu des cibles » se confondrait avec « inexistant ». Le geste vaut aussi pour
   la modalité « Autres » du logement, qui était dans le même cas depuis le ticket 019 —
   son test est étendu en conséquence.

   Mesure : `make couronne-v7`
   ([`measure_couronne_v7.py`](../../scripts/synthesis/measure_couronne_v7.py)), **zéro
   appel LLM**, splits `train` + `val` (2 197 lignes de décision, 569 agents). Trace :
   [`docs/traces/2026-08-24_couronne_v7/`](../traces/2026-08-24_couronne_v7/README.md).
   Ligne `couronne_residence` ajoutée au registre `avancement.yaml`.

   **Résultat : +2,11 pt de L1 par zone** (41,26 → 43,38, pondéré par le cadrage). Les
   quatre strates se dégradent — Toulouse +0,90, 1ʳᵉ +4,27, 2ᵉ +1,68 — et une 3ᵉ couronne
   **apparaît** à 41,88 là où le classement métrique n'en peuplait aucune.

   ⚠ **Un piège de pondération a failli faire publier l'inverse.** Pondérer le L1 par la
   **masse observée** rend **−0,26 pt**, soit une amélioration, alors que chaque strate
   empire : le reclassement sort 47 agents de Toulouse — la strate la pire, L1 ≈ 59 — et les
   verse dans de meilleures, si bien que la moyenne baisse par changement de mélange. Une
   moyenne pondérée par la masse n'est pas une règle de score valide pour comparer deux
   *classements*, puisque les poids bougent avec les strates. La grandeur publiée est donc
   pondérée par les parts de population du **cadrage**, identiques des deux côtés. C'est le
   critère d'acceptation « un ticket de correction qui améliore le score est suspect » qui a
   servi à attraper ce cas.

5. **Lot 5 — L'étage B — ÉCRIT, NON REJOUÉ.** Le trait est posé dans
   `eqasim-toulouse/synthesis/population/llm_agents.py`, sur `home_location` **après le
   snap** sur le polygone OTP — donc sur les coordonnées que `identity.home` portera, celles
   que lit le journal. Mêmes trois écritures que l'étage D, mêmes refus de deviner. Les
   ressources sont chargées une fois par stage, et leur absence lève au lieu de laisser une
   population sans couronne.

   ⚠ **Non rejoué**, exactement comme le lot 4 du ticket 015 : il demande
   `docker compose build eqasim` puis une régénération. Tant que ce n'est pas fait, une
   génération neuve n'a **pas** le trait et il faut lui passer l'étage D (`make
   residence-zone`). Le stage étant l'export terminal du `run:`, un cache pipeline chaud
   devrait éviter de rejouer la synthèse amont — à confirmer au premier rejeu, pas à
   supposer.

---

## Critères d'acceptation

- [x] Les deux équivalences du lot 0 sont **mesurées et archivées**, pas supposées — sept
      portes, toutes passées le 2026-08-24, dont un recoupement indépendant.
- [x] La couronne d'un domicile est **lue sur le persona**, jamais recalculée depuis une
      distance, partout où un résultat est comparé à une cible EMC².
- [x] `move_logger` **n'importe plus** `geo_reference.residence_zone` : le repli à la
      distance est impossible, pas seulement déconseillé. Une population sans le trait
      produit une colonne vide.
- [x] `hors périmètre` est une modalité de première classe : elle apparaît dans le journal,
      elle est **exclue** des cibles par zone, et sa masse est publiée.
- [x] La table publiée porte **la commune** autant que la couronne, et un test l'exige sur
      ressources committées (il tourne sans `data/PROGEDO 2023`).
- [x] L'effet est mesuré **sur `v7`** à décisions constantes pour A2, **sur les 1 021** pour
      A4, archivé dans `docs/traces/`, et porté au registre avec son `score_caveat` : **+2,11
      pt**, les quatre strates dégradées. **Un ticket de correction qui améliore le score est
      suspect** — et ce critère a servi : la première pondération rendait −0,26 pt, un
      artefact de mélange.
- [x] Le score publié n'est **pas** un composite, et la ligne du registre le dit. Le
      composite comparable est inchangé et `lieu_residence` reste `scored: False`.
- [x] La population `experiments/archive/2026-08-19_14_36/population_1000.json` est
      **inchangée octet pour octet** : `cab69d4b…`, revérifié après la mesure et republié
      dans la trace.
- [x] `terminal_time.yaml` n'est **pas** modifié, sa `version` n'est pas bumpée, et
      `terminal_time_emc2.json` n'est pas ré-exporté.
- [x] Le docstring de `geo_reference.residence_zone` ne prétend plus être la définition
      EMC² de la résidence, porte la divergence avec son amplitude, et dit que l'aligner
      demande de ré-exporter les lois.

## Hors périmètre

- **Le classement du temps terminal.** Il continue de classer des points par distance, et
  ses **lois sont stratifiées avec ce classement** (`meta.crown_definition`). L'aligner
  demande de ré-exporter la ressource, invalide trois caches et exige un run complet ; c'est
  un ticket distinct, à coordonner avec la correction de calibre en attente du
  [ticket 013](ticket_013_temps_terminal_itineraires.md).
- **Faire entrer la zone dans le composite** (`lieu_residence` → `scored: True`). Rendrait
  incomparables les quatre lignes du registre et les scores stockés du DAG. Si on le veut un
  jour, c'est un ticket qui rebaseline, pas un effet de bord de celui-ci.
- **La surconcentration spatiale de la population** (axe A9 du ticket 020 : 76,0 % en cœur
  d'agglomération contre 70,5 %). Ce ticket la rend *mesurable en continu* ; la corriger
  demande de retoucher le tirage.
- **Les trois autres limites du ticket 020** (A5 saison, A7 hiérarchie de mode principal,
  A8 grappes incomplètes). Chacune ouvre son propre ticket.
- **Le bassin de population de référence.** 4,4 % de domiciles hors périmètre sur
  `toulouse_population_1000.json` contre **0** sur les populations bbox-filtrées : l'exposition
  dépend de la population employée. Ce ticket rend le cas détectable ; décider quelle
  population fait foi est hors sujet ici.

## Ce qu'il faut savoir avant de commencer

- **Ne jamais enrichir en place une population épinglée par un manifeste.** Les étages D
  écrivent en place par réécriture atomique. Quatre jeux gelés (`v5` à `v8`) épinglent le même
  fichier par le même sha256. C'est le piège le plus coûteux du ticket, et il est silencieux.
- **Les 45 hors-périmètre ne se trahissent pas par leurs distances.** Mesuré : 5,15 km de
  parcours moyen contre 4,92 km pour les résidents du périmètre, 5,3 % de trajets au-delà
  de 20 km contre 3,1 %. Ils habitent loin et se déplacent localement. Leur exclusion ne
  déplacera donc **presque pas l'agrégat** — tout le dommage est concentré dans le stratum
  « 3ᵉ couronne », dont ils forment 76 %. Ne pas conclure à un non-effet : ce serait relire
  l'erreur de l'axe A2, qui ne bouge la cible moyenne que de 1,7 point tout en déplaçant un
  quart de la population.
- **Le cache de décisions LLM est clé par nom de population, pas par contenu**
  (`llm_agent.py:207`). Corriger un fichier en place ne l'invalide donc pas — ce qui est
  voulu ici, puisque la couronne n'entre dans aucun prompt, mais ce qui serait un bug
  silencieux pour un trait qui y entrerait.
- **Deux tests existants s'opposent à ce ticket** (lot 3). Ils ne sont pas des dégâts
  collatéraux : ils encodent l'ancienne décision, et leur réécriture est le geste par lequel
  la nouvelle est prise.

## Sources

- [ticket 020](ticket_020_perimetre_population_cerema.md) — l'instruction des neuf axes, et
  les deux verdicts « à corriger » que ce ticket exécute.
- [`docs/arch/perimetre-population.md`](../arch/perimetre-population.md) — mesures détaillées,
  matrice de confusion, effet sur le L1.
- [`docs/traces/2026-08-24_perimetre_population/`](../traces/2026-08-24_perimetre_population/README.md)
  — `agents_reclassement.csv` porte, pour chaque persona, sa commune réelle et ses deux
  classements : le contrôle de non-régression du lot 2 est déjà écrit.
- [`docs/arch/population-post-traitements.md`](../arch/population-post-traitements.md) — les
  quatre étages, et où ce trait s'insère (D pour l'existant, **B** pour les générations
  neuves).
- [`docs/traces/2026-08-24_couronne_equivalences/`](../traces/2026-08-24_couronne_equivalences/README.md)
  — le lot 0 : les sept portes, leur mesure, et ce qu'elles autorisent.
- [`docs/arch/protocole-parametre-exogene.md`](../arch/protocole-parametre-exogene.md) — le
  protocole de mesure sur jeux gelés, et la règle du registre d'avancement.
- [`llm_module/core/zone_resolver.py`](../../llm_module/core/zone_resolver.py) — la
  résolution point → zone fine, déjà en production, et son alarme de couverture à 15 %.
- [`llm_module/core/population_reference.py`](../../llm_module/core/population_reference.py)
  — `COURONNES`, `OUT_OF_PERIMETER`, et le cadrage validé.
- Modèles à suivre pour le lot 2 :
  [`enrich_housing_type.py`](../../scripts/data/population/enrich_housing_type.py) (ticket
  019) et [`enrich_personal_bike.py`](../../scripts/data/population/enrich_personal_bike.py)
  (ticket 015) — mêmes conventions de `--check` et de codes de sortie.
