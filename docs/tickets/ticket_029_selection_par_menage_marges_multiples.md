# Ticket 029 — Sélection par ménage à marges multiples, et les immobiles rendus à la population

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ce qui suit est une **spécification**. Suite directe du scellement du 2026-09-02
> ([controle-population-jeu-de-test.md](../arch/controle-population-jeu-de-test.md)) : la
> règle `aamas_seal_v2` alignait la couronne, la motorisation et l'occupation ; ce ticket
> aligne ce qu'elle laissait — âge fin, genre, ménages, équipements, logement — et rend à la
> population les personnes sans déplacement.

## Le problème, en trois mesures

1. **Les marges non allouées restent au biais du générateur.** Sur la population scellée v2
   (1 000 personas), le pas de 5 ans montre 9,8 % de 75 ans et + contre 7,1 % dans l'enquête,
   5,5 % de 45-49 ans contre 7,0 ; genre 50,7 / 49,3 contre 51,3 / 48,7 recalculés ; deux
   strates d'équipement hors tolérance (abonnement TC des demandeurs d'emploi 15,7 % contre
   28,8 ; permis des personnes au foyer 46,9 % contre 63,9).
2. **La sélection par personne fragmente les ménages** : 1 000 retenus dans 865 ménages dont
   308 complets, 51 % des membres déclarés présents (mesuré avec `household.id`).
3. **Il n'y a aucun immobile.** L'export eqasim écartait toute personne sans activité hors
   domicile ; l'EMC² 2023 compte **10,6 %** de personnes sans déplacement la veille (poids
   COEP, PENQ = 1). La population publiait 2,69 déplacements par agent contre 3,53.

## Ce que le ticket fait

### A — Cibles gelées `cm1` (`scripts/AAMAS/cibles_marges_personne.yaml`)
Sept marges personne recalculées sur les microdonnées (personnes interrogées, COEP), que le
rapport ne publie pas ou pas à ce pas : âge quinquennal (15), genre, taille de ménage portée
par la personne (5), permis des 18 ans et +, abonnement TC (P12, recodage de la loi
d'équipement), type de logement (M1 du ménage), immobile. Version, sommes et provenance
vérifiées à la lecture. Genre et permis passent de « non mesurable » à mesurable — la source
dit « recalcul gelé, non publié ».

### B — Sélection v3 (`seal_population.py`, `aamas_seal_v3`)
- **Unité = ménage** (`household.id`). Un ménage a une cellule couronne × motorisation ; ses
  membres de 5 ans et + sont tous dans le vivier dès que l'export garde les immobiles.
- **Allocation** par cellule en ménages (ordre `sha256` des identifiants de ménage, un ménage
  n'entre que s'il tient) ; déficits journalisés et reportés comme en v2.
- **Descente sur marges multiples** : échanges de ménages de même taille et même cellule qui
  réduisent la somme des écarts absolus en points aux huit marges (occupation p. 11 + `cm1`).
  Déterministe, journalisée (`descente` : avant / après par marge, échanges, perte).
- **Pré-imputation du vivier** (étape 3ter-a du notebook) : `fix_minor_traits`,
  `enrich_housing_type`, `enrich_personal_bike`, `enrich_equipment` tournent sur le checkpoint
  avant la sélection, pour que logement, permis et abonnement soient des marges.

### C — Immobiles (fork `eqasim-toulouse`, stage `llm_agents`)
Une personne sans activité hors domicile n'est plus écartée : journée « domicile 0 → 86 400 s »,
drapeau racine `immobile: true`, compteur en fin de stage. Côté chaîne, `ajuster_planning`
plantait (`KeyError: 1`) sur une journée à une activité : garde `n < 2`. Côté runtime, le
chemin « Pas de déplacement (même localisation) » existe et n'appelle pas le LLM ; aucune
hypothèse GAML sur le nombre d'activités trouvée — **à vérifier au premier run**.

### D — Contrôle (`control_population.py`)
Treize marges. Section **ménages et mobilité** : ménages, complets, membres présents ;
déplacements par persona et part d'immobiles face à l'enquête (3,53 ; 10,6 %). La synthèse
des écarts porte la fragmentation et la mobilité quand elles s'écartent.

## Ce que ce ticket ne fait pas
- Il ne change pas les chaînes d'activités (ENTD 2008) : les agents mobiles gardent ≈ 2,7
  déplacements contre 3,95 dans l'enquête. C'est le levier « EMC² 2023 comme enquête
  d'appariement », un autre ticket.
- Il ne touche pas au cadre de tirage (Haute-Garonne) : la composition interne de la 3ᵉ
  couronne reste à déclarer.
- Il ne modifie pas la population scellée v2 : un nouveau dossier `population_1000_AAMAS_v3`.

## Critères d'acceptation
- [x] `cibles_marges_personne.yaml` gelé (`cm1`) : 7 marges sommant à 100, immobiles 10,64 %,
      abonnés 25,85 % (26 % publiés p. 24 ; P12 ne porte que les codes 4 et 6), permis adultes
      85,86 %, mobilité recalculée 3,529 (3,5 publiée).
- [x] Sélection v3 sur le vivier de 11 922 (10 000 demandés) : 1 000 personas en **514 ménages
      entiers** (tous les membres de 5 ans et + retenus), cellules exactes, 0 déficit, 364 enfants
      de moins de 5 ans exclus ; descente 279 échanges en 5 passes, perte 39,9 → 6,1 pt ; après
      descente, écart maximal ≤ 0,3 pt sur sept marges (taille de ménage 2,2 pt, la seule que des
      échanges à taille égale ne bougent pas).
- [x] Export eqasim : 1 798 immobiles gardés (15,1 % du brut, 12,4 % des 5 ans et +), compteur
      affiché ; la chaîne 2 → 9 passe (deux gardes corrigées : `ajuster_planning` et
      `check_temporal_order` sur une journée à une activité) ; le contrôle mesure 10,6 %.
- [x] `make control-population` sur la v3 : **13 marges conformes, 0 à corriger, 0 à publier,
      0 non mesurable** ; 514 ménages, 485 complets au sens strict de la taille déclarée (94,4 % —
      les 29 autres n'ont que des enfants de moins de 5 ans absents), 96,7 % des membres déclarés
      présents ; audit A8 : 2,5 % de membres absents (54,6 % en v2).
- [x] Tests `scripts/tests/test_aamas_population.py` : 13 verts.
- [x] Scellé `data/population/population_1000_AAMAS_v3/` (sha256 `8d8bfa3645fa77fb…`), sauvegarde
      `sauvegardes/population_1000_AAMAS_v3_2026-09-03.tar.gz` avec le vivier, runtime repointé
      (`data.population_file`). Le runtime GAMA avec agents immobiles reste **à vérifier au
      premier run** (chemin « pas de déplacement (même localisation) » attendu).
