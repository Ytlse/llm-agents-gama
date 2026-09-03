# Ticket 034 — Vélo personnel : une clé de tirage stable, et une seule loi

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. **Décision non prise** (2026-09-03) : l'auteur du dépôt n'est pas certain de
> l'implémenter. Ce ticket consigne le constat mesuré, ce qu'il faudrait faire et ce que cela
> coûte, pour que la décision se prenne sur des chiffres.

## Le constat, en deux mesures (2026-09-03, soir)

**1. Le vélo d'un persona dépend de sa position dans le fichier.** Comparaison, personne par
personne, du vivier pré-imputé (`Temp/4_zone_enriched/toulouse_population_10000.json`,
11 329 personnes, sha256 `487ff00c…`) et de la cohorte scellée v4 qui en est extraite
(`data/population/population_1000_AAMAS_v4/population.json`, sha256 `9f05c655…`), les deux
ayant reçu le même post-traitement `enrich_personal_bike` :

| Trait | Personas dont la valeur diffère entre vivier et cohorte (sur 1 000) |
|---|---|
| `personal_bike` | **201** — vélo normal → pas de vélo 65, pas de vélo → vélo normal 58, vélo normal ↔ VAE 63, VAE ↔ pas de vélo 15 |
| `housing_type`, `has_driving_license`, `has_pt_subscription`, `residence_zone` | 0 |

Les 201 personas appartiennent à 124 ménages : 22 sont incomplets (membres de moins de 5 ans
absents), 30 partageaient leur adresse avec un autre ménage dans le vivier, les autres n'ont
rien de particulier. La distribution globale ne bouge pas (533 / 422 / 45 dans la cohorte,
douze contrôles du `--check` dans leur tolérance) : c'est **qui** porte le vélo qui change.

Cause, dans `llm_module/core/bike_ownership.py` et `scripts/data/population/enrich_personal_bike.py` :

- l'attribution (`assign`) hache `bike-holder:{clé de ménage}:{member.index}` et le type de vélo
  (`bike_label`) hache `bike-kind:{clé de ménage}:{index}`, où `index` est la **position du
  persona dans le fichier** (`enumerate` dans `enrich`), pas son identifiant ;
- la clé de ménage est l'**adresse** du domicile, suffixée `#s{taille}n{rang}` quand plusieurs
  ménages partagent une adresse (`build_households`) — le suffixe existe dans le vivier et
  disparaît dans la cohorte quand l'autre ménage n'est pas retenu, ce qui change `k` ;
- les places absentes portent la propension moyenne des présents : la composition présente du
  ménage entre dans le tirage.

La page [`velo-equipement.md`](../arch/velo-equipement.md) écrit « déterministe par hachage,
stable entre exécutions et machines » : c'est vrai **à ordre de fichier et à sous-ensemble
fixés**, et faux dès qu'on extrait ou réordonne. L'idempotence en place (rejouer l'étape 8 sur
le fichier scellé redonne le même fichier) tient ; la propriété « le vélo est un attribut de la
personne » ne tient pas.

**2. La même loi vit à deux endroits, contre la décision du 2026-08-24.** Le lot 4 du ticket
015 (porter les trois étages dans le fork eqasim) a été **rejeté** par l'auteur : le
post-traitement étant obligatoire, une loi à deux endroits est une ceinture par-dessus les
bretelles. Or `eqasim-toulouse/synthesis/population/enriched.py::_assign_personal_bike` est
en place et **actif** : le vivier brut livré par eqasim le 2026-09-03 (`Temp/1_raw/…10000.json`)
porte déjà 5 769 « Pas de vélo », 5 063 « vélo normal », 497 « VAE » — la distribution du
modèle appris, pas celle de la recopie ENTD. L'étape 8 réécrit ensuite le trait pour
**538 personnes sur 11 329 (4,7 %)**, parce que ses clés (adresse, index) ne sont pas celles du
fork (`household_id`, identifiant de personne). Les pages `velo-equipement.md` et
`population-post-traitements.md` disaient encore « écrit, non rejoué » : corrigé le 2026-09-03
avec ce ticket.

## Ce que cela change, et ne change pas

- **Ne change pas** : les marges et les douze contrôles vélo de la v4 (le bruit est symétrique),
  la validité du sceau v4, la rejouabilité en place, le comportement du runtime (le garde-fou
  « champ absent ⇒ pas de vélo, alarme » de `simulation_controller._owns_bike` est intact).
- **Change** : une sélection future (v5, ou toute cohorte extraite du même vivier) rebat le vélo
  d'environ un persona sur cinq sans le dire ; la comparaison persona par persona entre vivier et
  cohorte est impossible sur ce trait ; deux populations de même contenu et d'ordre différent ne
  donnent pas le même parc ; et le mode le plus scruté de l'article repose sur deux
  implémentations qui se contredisent pour un persona sur vingt.

## Ce qu'il faudrait faire

### Lot 1 — une clé de tirage stable (`personal_bike_v2`)
- `Member.index` reste l'index technique, mais les hachages de `assign` et `bike_label` prennent
  **l'identifiant de personne** (`person_id`) ; les places absentes gardent une clé synthétique
  `absent:{rang}` (elles n'ont pas d'identifiant, et leur nombre ne dépend pas du fichier).
- Clé de ménage = **`household.id`** quand il est à la racine de l'enregistrement (tous les
  personas depuis l'export du 2026-09-03), repli sur l'adresse sinon — compté et journalisé, pour
  qu'une population ancienne se voie. Plus de suffixe de collision quand la clé est l'identifiant.
- Sel `DRAW_SALT` → `personal_bike_v2` : le parc est rebattu, l'acte est daté au changelog.
- Test : permuter l'ordre du fichier et extraire un sous-ensemble de ménages entiers redonnent
  **exactement** le même trait pour chaque persona ; un ménage incomplet garde le même nombre
  de places absentes, donc le même tirage.
- Coût : la v4 scellée **n'est pas modifiée** (un sceau ne se modifie pas) ; le lot s'applique au
  prochain scellement — à faire **avec la v5** (geste sur la motorisation en base ménage) pour ne
  resceller qu'une fois. Les rapports `--check` sur la cohorte et sur le vivier doivent rester
  au code 0, pente croissante sur le vivier.

### Lot 2 — une seule loi
- Retirer `_assign_personal_bike` du fork (ou le rendre inactif par configuration, journalisé) :
  l'export eqasim ne porte plus `personal_bike`, l'étape 8 le pose. Une population qui n'est
  pas passée par l'étape 8 n'a **aucun** vélo et le runtime l'alarme — c'est le comportement
  voulu depuis le lot 1 du ticket 015.
- Alternative si l'on garde la loi dans le fork : aligner ses clés sur le lot 1 (`household_id`,
  `person_id`, même sel) et faire de l'étape 8 une **recette** (`--dry-run --check`) qui vérifie
  l'identité au lieu de réécrire — mais c'est précisément la double implémentation que la
  décision du 2026-08-24 refuse.
- Documentation : `velo-equipement.md` (déterminisme, voie 2), `population-post-traitements.md`
  (étage A), changelog du fork.

### Lot 3 — registre
- Clore le ticket 015 (`terminé`) une fois les lots 1 et 2 tranchés — livrés ou refusés.

## Critères d'acceptation
1. Sur le vivier v4 et une cohorte extraite par `seal_population select`, **0 persona** dont le
   `personal_bike` diffère entre les deux fichiers.
2. Deux copies du même fichier, l'une réordonnée, donnent le même parc persona par persona (test
   unitaire).
3. `enrich_personal_bike --check` rend le code 0 sur la cohorte et sur le vivier ; pente
   croissante sur le vivier ; rapports `--rapport-json` lus par la synthèse.
4. Une seule implémentation de la loi dans le dépôt (`grep _assign_personal_bike` vide, ou la
   configuration qui l'inactive est documentée) ; les deux pages d'architecture disent ce que
   le code fait.

## Ce que ce ticket ne fait pas
- Il ne touche pas au modèle appris (lois de `k`, de propension et de VAE, `make bike-ownership`).
- Il ne resselle pas la v4 et ne rejoue aucun run.
- Vélo en libre-service, stationnement, week-end : limites déclarées du ticket 015, inchangées.

## Décision attendue
- **(a) Ne rien faire** : la limite est déclarée (phrase ajoutée à `velo-equipement.md`, ce
  ticket), le sceau v4 reste tel quel.
- **(b) Lot 1 seul**, avec le scellement v5.
- **(c) Lots 1 et 2**, avec le v5 — recommandation : c'est la lecture directe de la décision du
  2026-08-24, et le coût est un rescellement déjà prévu.

## Sources
- Mesures du 2026-09-03 au soir : comparaison `Temp/1_raw`, `Temp/4_zone_enriched` et
  `population_1000_AAMAS_v4/population.json` par `person_id` (script ad hoc, chiffres ci-dessus) ;
  rapports vélo `docs/traces/2026-09-03_22-32_synthese_v3_population_v4_velo/velo_{cohorte,vivier}.json`.
- Code : `llm_module/core/bike_ownership.py` (`uniform`, `assign`, `bike_label`, `DRAW_SALT`),
  `scripts/data/population/enrich_personal_bike.py` (`build_households`, `enrich`),
  `eqasim-toulouse/synthesis/population/enriched.py` (`_assign_personal_bike`).
- Décision du 2026-08-24 (lot 4 rejeté) : note du ticket 015 dans `scripts/dashboard/tickets_status.yaml`.
