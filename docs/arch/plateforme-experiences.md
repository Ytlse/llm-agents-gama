# Plateforme d'expériences — design (ticket 035)

> Document de **design** du ticket 035. Le ticket dit ce que l'utilisateur doit pouvoir faire
> ([`ticket_035_…_spec_fonctionnelle.md`](../tickets/ticket_035_plateforme_gestion_experiences_decouplage_spec_fonctionnelle.md)),
> les six specs disent ce qui est vrai ou faux d'une exécution ([`specs/ticket_035/`](../../specs/ticket_035/00-index.md)),
> ce document dit **comment c'est construit** : modules, formats, flux. Il a été écrit avant le code
> et **n'a pas reçu de validation humaine** : l'implémentation a démarré sur instruction explicite
> (« vas aussi loin que possible, garde les questions pour la fin »), sous les hypothèses listées
> dans [`specs/ticket_035/questions.md`](../../specs/ticket_035/questions.md). Tout ce qui est
> construit ici est réversible ; ce qui dépend d'une question ouverte est marqué **[H]**.

## 1. Vue d'ensemble

```
                 ┌───────────────────────────┐
  population ───▶│ experiences/jeu.py         │───▶ data/jeux/<nom>/{MANIFEST.yaml, propositions.jsonl}
  (scellée ou non)│ préparer / consulter /     │        (spec 01 — objet nommé, daté, transportable)
                 │ vérifier / péremption      │
                 └───────────────────────────┘
                              │ lecture seule
        ┌─────────────────────┴─────────────────────┐
        ▼                                           ▼
┌──────────────────────┐                  ┌──────────────────────────┐
│ experiences/runner.py│                  │ simulation_controller.py │
│ sans simulateur      │                  │ avec GAMA (spec 04)      │
│ (spec 03)            │                  │ sert le jeu, recalcule   │
└──────────┬───────────┘                  │ sous conditions          │
           │                              └────────────┬─────────────┘
           │        UNE SEULE fonction de décision      │
           └────────────▶ experiences/decision.py ◀─────┘
                          (spec 02 : filtre, ordre, trace)
                                    │
                          experiences/decideurs.py
                          (passerelle épinglée · antigravity · durée minimale ·
                           rejeu · aléatoire · modèle tabulaire · majoritaire voiture)
                                    │
                          experiences/archive.py  ──▶ data/experiences/<exp>/executions/<horodatage>/
                          (spec 05/06 : decisions.jsonl atomique, etat.json, moves.csv, synthese)
                                    │
                          experiences/registre.py ──▶ CLI `registre`, `comparer` · onglet dashboard
```

Tout le code neuf vit dans le paquet **`services/llm-agents/experiences/`** (importable depuis le conteneur
`controller`, où tournent déjà `models`, `settings`, `trip_helper`, `text_helper`). Les tests sont
dans `services/llm-agents/tests/test_035_*.py`, un fichier par spec, un test par règle (`test_J3_…`).

## 2. Spec 02 — la décision unique (`experiences/decision.py`)

**Extraction préalable.** Les helpers de la chaîne des véhicules (`_can_drive`, `_is_car_passenger`,
`_owns_*`, `_same_place`, `_vehicle_position`, `_vehicle_available`, `_vehicles_parked_at`,
`_park_vehicles`, `_orphaned_vehicles`, `_chain_stake_modes`, `_vehicle_mode`, `_road_distance_km`,
constantes `RETURN_LOCK_MIN_DISTANCE_KM`, `DRIVING_AGE`, `_VEHICLE_MODES`, métrique
`VEHICLE_CHAIN`) sortent de `simulation_controller.py` vers
**`urban_mobility_agents/vehicle_chain.py`**, sans changement de comportement. Le contrôleur les
ré-importe (les 73 tests de `test_vehicle_chain.py` continuent d'importer depuis le contrôleur).
Sans cette extraction, `decision.py` ne peut pas importer le filtre sans importer tout le contrôleur
(import circulaire).

**Structures** (dataclasses / Pydantic) :

```python
Proposition(plan: TravelPlan, source: str)          # source ∈ enregistree | recalculee:offre:<id> |
                                                     #   recalculee:horaire:<ecart_min>/<tol> |
                                                     #   en_vol | hors_jeu | locale
Ecart(code: str, mode: str, motif: str)              # motif ∈ non_possede | pas_de_conducteur |
                                                     #         vehicule_ailleurs | retour_force | plafond
ContexteDecision(timestamp, activity_id, purpose, departure_time, from_location, destination,
                 anticipation: dict|None, evenement: dict|None,
                 periode_evenement: str|None,           # avant | pendant | apres
                 graine_ordre: int, graine_tirage: int, max_candidats: int)
ReponseDecideur(index: int|None, fournisseur: str, distribution: dict, poids: list[float],
                reponse_brute: str|None, raison: str, souvenirs: list[str],
                presente: dict|None, repli_uniforme: bool, erreur: str|None,
                identifiant_lot: str|None, non_imputable: bool, reprise_a: str|None,
                modele_verifie: bool|None, sortie_litterale: str|None)
Decision(retenue: Proposition|None, methode: str, trace: dict,
         reponse: ReponseDecideur|None, sollicite: bool)
# La trace n'est pas une dataclasse : `construire_trace()` rend le dict archivé tel quel dans
# decisions.jsonl — person_id, activity_id, purpose, timestamp, departure_time, methode,
# presentees, ecartees, retenue (+ index_presente), distribution, poids_presentes,
# reponse_brute, sortie_litterale, sources, fournisseur, raison, souvenirs, presente,
# identifiant_lot, graine_ordre, graine_tirage, contrainte_chaine, periode_evenement,
# anticipation (+ modele_verifie quand le décideur l'atteste).
```

**Fonctions**, appelées à l'identique par les deux modes :

- `eligibilite(person, from_location, propositions, purpose, od_km) -> (eligibles, ecartees)` :
  D2/D3, délègue chaque test à `vehicle_chain` (aucune règle réécrite). Ordre : possession →
  conducteur/passager → position → verrou de retour (seuil 1 km via `_road_distance_km`).
  Le contrôleur en mode « en vol » continue d'envoyer `include_car/include_bike` à OTP pour ne pas
  router ce qu'il écartera : ces deux booléens sont désormais calculés par
  `decision.modes_vehicules_eligibles(person, from_location)` — même fonction, même résultat.
- `plafonner(eligibles, max_n) -> (retenues, ecartees_plafond)` : `_select_candidates` du
  contrôleur, déplacé ici ; les écartées reçoivent le motif `plafond` (elles sont traçables).
- `ordre_presentation(propositions, graine, person_id, activity_id) -> list` : D7, mélange
  déterministe (`random.Random(sha256(graine|person|activité))`). Remplace le `random.shuffle`
  non graîné de `LlmAgent.evaluate_and_choose_travel_plan`.
- `async decider(person, ctx, propositions, decideur) -> Decision` : D5 (0 → `sans_solution`,
  1 → `choix_unique`, sans solliciter), sinon appelle `decideur.choisir(person, ctx, presentees)`,
  puis assemble la trace D6. D10 : une réponse inexploitable rend `repli_uniforme`.
- `avancer_chaine(person, decision, from_location, destination)` : D4, `_park_vehicles` puis
  rattrapage des orphelins (`_orphaned_vehicles` + reset) — l'équivalent de
  `_settle_vehicles_at_home` sans les métriques de classe du contrôleur.

D11 : aucune lecture d'horloge ; tout horodatage vient de `ctx`.

## 3. Spec 01 — le jeu enregistré (`experiences/jeu.py`)

Répertoire `data/jeux/<nom>/` :

```
MANIFEST.yaml        version: jeu1 · nom · cree_le · clos: bool
                     population: {nom, fichier, sha256, scellee: bool}
                     heure_reference: depart_programme      # [H] question 11
                     jour_simule: "2026-03-16"              # base des horodatages
                     dependances: {commit, arbre_propre, gtfs: {fichier: sha256}, osmnx_graph_key,
                                   congestion: sha256, terminal_time: sha256, osmnx_yaml: sha256}
                     attendus: {deplacements, personnes}    # DÉRIVÉS des agendas (J2)
                     couverts: {deplacements, personnes}
                     sans_proposition: [{person_id, activity_id, motif}]
                     propositions_sha256: <sha256 de propositions.jsonl>   # identité du jeu (J5)
propositions.jsonl   une ligne par déplacement :
                     {person_id, activity_id, origine_activity_id, ordinal, purpose,
                      depart_24h, depart_ts, origine: {lat,lon}, destination: {lat,lon},
                      propositions: [TravelPlan.model_dump()…], motif_absence: str|null}
```

- **Déplacement** = paire d'activités **localisées** de l'agenda, sur une chaîne **cyclique**
  (J2, ticket 045). Une journée de n activités vaut **n déplacements**, pas n − 1 : la dernière
  activité est suivie d'un retour à la première, qui est le domicile dans la quasi-totalité des
  cas. L'énumération est unique, dans `chaine_activites.py`, et partagée avec le contrôleur de
  simulation — c'est la divergence entre les deux implémentations qui faisait manquer à la
  plateforme 27 % de la journée, précisément la part où la contrainte de chaîne des véhicules
  pèse le plus. Heure = règle du contrôleur (`scheduled_start_time` sinon `end_time`,
  `to_timestamp_based_on_day`, +24 h si déjà passé) ; pour la fermeture, elle désigne le même
  instant que « fin de la dernière activité », les populations scellées encodant le bouclage.
- **Deux dénominateurs, et il faut les distinguer.** `deplacements_attendus` est le décompte
  **brut** ; `deplacements_exploitables` en retire ce qui ne PEUT pas être couvert, c'est-à-dire
  les déplacements dont l'origine est la destination (138 sur la cohorte v5 : 77 fermetures de
  journée et 61 trajets entre deux activités au même lieu). `est_complet` et le
  taux de couverture se mesurent sur les **exploitables** : les exiger sur le brut rendait la
  complétude inatteignable pour toute population dont les journées reviennent au domicile.
  `est_defaillance_moteur(motif)` porte cette distinction en un seul endroit.
- **Préparation** : `trip_helper.get_itineraries(include_car=True, include_bike=True, arrive_by=False)`
  — tous modes, **aucun** plafond, plus l'option car scolaire (`build_school_bus_option`, locale,
  déterministe) pour que le jeu soit un vrai sur-ensemble. Aucun attribut du persona n'est écrit (J16).
- **Reprise** (J11) : les lignes existantes sont indexées par `(person_id, activity_id)` et sautées.
  Écriture ligne par ligne, `flush + fsync`.
- **Clôture** (J14) : `clos: true`, `propositions_sha256` calculé ; ensuite `ouvrir()` refuse toute
  écriture ; `charger()` refuse un jeu altéré (J12), sans bloc `dependances` (J9), ou malformé (J13 :
  JSON strict, position de l'erreur ; jamais de pickle).
- **Péremption** (J10) : `dependances_courantes()` recalcule le même bloc ; `perime(jeu)` rend la liste
  des dépendances qui diffèrent (`commit` et `arbre_propre` sont informatifs pour la traçabilité sans périmer le jeu). Le lancement d'une expérience l'affiche et exige
  `--accepter-perime` pour continuer **[H]** si une dépendance de transport (GTFS, graphe, config) a changé.
- **Journalisation** (J15) : début/fin/durée/compteurs, ligne de succès, ALARME à front montant si la
  part de **défaillances de moteur** dépasse `--seuil-sans-proposition`. Les fermetures sur place
  en sont exclues : il n'y a pas d'itinéraire à calculer entre un point et lui-même, et les
  compter faisait franchir le seuil de 5 % à chaque préparation (5,5 % sur la cohorte v5), ce qui
  revient à éteindre l'alarme en la faisant hurler tout le temps.
- **État du dépôt** (ticket 045, A4) : `git` n'est pas installé dans l'image `controller`, si bien
  que `commit` et `arbre_propre` étaient nuls dans toute exécution lancée depuis le tableau de
  bord. L'hôte les mesure et les transmet par `EXP_DEPOT_COMMIT` / `EXP_DEPOT_ARBRE_PROPRE`
  (posées par le Makefile) ; `etat_depot()` les lit, et retombe sur `git` pour un lancement direct
  sur l'hôte. `osmnx_graph_key` enregistre la clé **effective** (`graph_key()`), non le réglage
  brut qui vaut `None` dans le cas courant.

## 4. Spec 06 — l'expérience (`experiences/experience.py`) et l'archive (`experiences/archive.py`)

`data/experiences/<nom>/experience.yaml` — **tous** les champs E1 obligatoires (Pydantic, `extra=forbid`) :

```yaml
nom, population: {chemin}, jeu: {nom}, gabarit: {categorie: itinary_multi_agent}   # empreinte = texte effectif
decideur: {type: passerelle|antigravity|duree_minimale|rejeu|aleatoire|modele|majoritaire_voiture|typesafe,
           modele, portee: local|distant|null, parametres: {temperature, top_p, max_tokens},
           rejeu_de: <exec>|null, graine: <int>|null, artefact: <chemin>|null}
mode: sans_simulateur | simulateur
calendrier: {politique: commune|propre|aleatoire, date: "2026-03-16", graine: 42}
horizon_jours: 1                         # 1 à 50 (garde-fou de coût, 2026-09-22 ; cf. plus bas)
memoire: false
evenements: []
graine_ordre: 42
graine_tirage: 42
regroupement: {parallelisme: 8}          # régime DEMANDÉ ; l'appliqué est archivé
tolerances_horaires: {walk: insensible, bike: insensible, car: heure, transit: {pas_min: 10}, rail: {pas_min: 10}}
max_candidats: 6
derive_de: <nom>|null                    # « copiée de » — filiation (E4)
renomme_de: <nom>|null                   # « c'est la même, sous son ancien nom » — migration du nommage calculé
```

`nom` n'est pas un champ libre : il se calcule des autres (cf. « Le nom EST l'identité — et il se
CALCULE » plus bas). Une définition écrite à la main est refusée par `definir` si son `nom` n'est
pas celui de ses paramètres.

`Experience.empreintes()` : population (MANIFEST sha256 ou sha256 fichier + `scellee`), jeu
(`propositions_sha256`), gabarit (sha256 du prompt système actif de la catégorie **+** du template
`categories/itinary_multi_agent/template.md.j2` **+** de `travel_plan_describe_v2.j2`), décideur (modèle + paramètres),
dépôt (commit + arbre propre).

`refuser_si_impossible(exp)` (E6) : jeu ≠ population, décideur sans instance disponible (lecture de
`providers.yaml` puis `/health`), sans simulateur avec mémoire/événement/horizon > 1 (S3), date hors
période couverte (E9 : `calendar*.txt` des feeds, bornes du CSV météo), jeu périmé non accepté.

**L'horizon se déclare entre 1 et 50 jours** (`HORIZON_MAX_JOURS`, `scripts/dashboard/experiences.py`).
Cinquante n'est pas une durée attendue mais un garde-fou de coût : un run d'événement s'arrête
normalement sur l'extinction du souvenir — sept jours vécus après sa sortie du bloc « ce qui a
changé récemment », `run_sequential_cohort.py --arret-sur-extinction` — et les cinq niveaux de
gravité servent des souvenirs de 4,70 à 20,58 jours, 31,49 au plus avec les rappels. La borne ne
mord donc que sur un run qui ne s'éteindrait jamais. Elle reste sous la fenêtre d'âge du rappel
(`memoire__fenetre_age_max_jours`, 60 j), qui vaut l'horizon plafonné : aucun horizon déclarable
ne la fait mordre.

**« Disponible » lit deux signaux, tous deux mesurés** (`MoniteurRessources.disponible`). Une
instance est servable si la passerelle ne l'a pas mise **hors service** (`/health` : `disabled`,
désactivée après des erreurs consécutives, ou `cooldown`) et si son quota du jour n'est pas
`quota_exhausted`. La marge `rpd_limit − daily_requests` est toujours calculée et affichée
(`marge()`, panneau des ressources, `raison_epuisement`), mais depuis le 2026-09-21 (ticket 097)
**elle n'écarte plus** : `rpd_limit` est déclaré dans `providers.yaml`, pas observé. Trois pannes
ont fixé cette lecture :

- 2026-09-07 : le go/no-go ne lisait que le quota. `cerebras_gpt-oss-120b`, désactivée après une
  HTTP 402, restait `quota_exhausted: false` (son seau du jour était intact) et l'expérience était
  admise sur une instance morte, qu'elle ne découvrait qu'en brûlant ses requêtes.
- 2026-09-08 : la correction lisait `available`, qui répond à une autre question — « peut-elle
  prendre une requête *maintenant* ? » — et vaut aussi faux quand l'instance est seulement
  **occupée** (`active_tasks` ≥ `concurrency_limit`). Sur `lmstudio_muse_glimmer_28b_key1`, un
  modèle local à un appel à la fois, `available` passait à faux pendant chaque génération : deux
  décisions après sa reprise, l'exécution a été déclarée épuisée jusqu'au lendemain 07:00, sans
  quota ni panne. Depuis, `hors_service()` lit `disabled` et `cooldown` ; « occupée » est une
  information du tableau (`occupee`), jamais un refus.
- 2026-09-21 : le troisième signal, la marge, écartait des instances sur un plafond que personne
  n'avait mesuré. Les `rpd_limit` de `providers.yaml` sont recopiés de documentations fournisseur
  périmées ou muettes — Groq n'annonce sa limite journalière que dans le corps de ses 429, et le
  RPM réellement servi par Mistral valait le double du chiffre inscrit. Une clé pouvait donc être
  déclarée pleine avec des centaines de requêtes encore servables. Depuis, le plafond informe, il
  ne décide pas : seul le fournisseur ferme une clé.

**Ce qu'il reste au plafond déclaré : journaliser.** Ne fermant plus de clé, il ne resterait rien
de lui sans trace, et l'écart entre `providers.yaml` et la limite réelle passerait inaperçu.
`MoniteurRessources` en tire deux WARNING, posés à la lecture de `/health` et **sur front montant**
— une ligne par instance et par fenêtre, pas une par rafraîchissement :

- `[ressources] [PLAFOND] g1 : 612/500 requêtes/jour — plafond déclaré dépassé de 112 et le
  fournisseur sert toujours` : le chiffre inscrit est trop bas, et c'est la seule occasion de
  l'apprendre. Strictement au-delà : à `612 == 612`, le plafond n'est pas encore démenti.
- `[ressources] [PLAFOND] g1 refusée par le fournisseur (429) à 412 requêtes/jour — limite réelle
  observée ; plafond déclaré 500 (écart -88)` : `daily_requests` au moment du refus **est** la
  limite du fournisseur. C'est ce chiffre-là qui alimente la remesure de `providers.yaml`
  (`make providers`, en-têtes `x-ratelimit-*`).

Sans `rpd_limit` déclaré ou sans compteur publié, rien n'est journalisé : il n'y a pas de
comparaison à faire, et supposer un chiffre est exactement ce que le ticket 097 corrige.

Une passerelle ancienne qui ne publie ni `disabled` ni `cooldown` est lue sur `available`, seul
signal disponible ; une passerelle qui ne publie rien reste permissive : l'absence de mesure ne
doit pas bloquer, mais elle ne doit pas non plus passer pour un feu vert.

`estimer(exp)` (E5) — **deux unités, nommées séparément** : `deplacements` (= déplacements
couverts du jeu, l'ancien champ `sollicitations`, conservé) et `requetes` (= appels fournisseur,
ce que le quota décompte). La passerelle groupe environ huit agents par requête ; le diviseur
vient de `experiences/lots.py` — plafond dérivé de `batch_max_agents` borné par le parallélisme,
facteur observé sur les exécutions archivées comparables. Trois chiffres de requêtes sont
publiés (`plancher`, `attendue`, `prudente`) et **seul `prudente` décide** ; sans mesure il vaut
le nombre de déplacements, si bien que le verdict ne peut pas devenir plus permissif qu'avant le
2026-09-22. Jetons/sollicitation = médiane mesurée sur les journaux d'échange archivés du même
gabarit, **ramenée à l'agent** (une ligne porte les jetons du lot entier), sinon
`docs/paper/methode/experience_plan/experiments.yaml: measured_ratios` (cité) ; quotas =
`providers.yaml` `rpd_limit` + `/health.daily_requests`. Un jeu non clos ne déclare aucun
attendu : `non_couverts` vaut alors `null` et la source le dit, au lieu d'un nombre négatif.
Aucun littéral dans le code.

**Exécution** — `data/experiences/<nom>/executions/<AAAA-MM-JJ_HH_MM_SS>/` :

```
execution.yaml    configuration figée + empreintes + regime_applique + sources_alea + interruptions[]
etat.json         {etat: definie|en_cours|en_pause|epuisee|arretee|terminee, raison, reprise_possible_a, maj}
decisions.jsonl   une TraceDecision complète par décision (texte présenté inclus), append atomique
moves.csv         mêmes colonnes que la simulation (+ « Source des propositions ») → `make report`, synthèse
compteurs.json    décidés / non couverts / sans solution / choix unique / replis / erreurs / sollicitations / requetes (delta passerelle)
synthese.json     parts modales par mode canonique AVEC couverture, référentiel cité (chemin + sha256)
synthese.html     rendu de synthese.json — ne calcule rien que le JSON n'ait (E16)
```

Écriture atomique (Q9) : `etat.json`/`compteurs.json` via fichier temporaire + `os.replace` ;
`decisions.jsonl` en append d'une ligne complète + `fsync` ; au chargement, une dernière ligne
tronquée est écartée avec un WARNING qui la nomme.

**Registre** (`experiences/registre.py`, même règle dans l'onglet dashboard) : parcours de
`data/experiences/*` ; une ligne par exécution présente sur disque. Le **décideur d'une ligne est
celui figé dans son `execution.yaml`** (`experience.decideur`), pas celui — mutable — de la
définition courante : réenregistrer une expérience change sa définition pour les runs futurs sans
réétiqueter les exécutions passées, chacune gardant sa copie figée (R6). Une exécution dont le
dossier a disparu mais qui figure dans `experience.yaml: executions_connues` reste listée
« archive manquante » (E20) ; `executions_connues` est tenu par **union avec le disque** à chaque
lancement, jamais réinitialisé. `comparer(a, b)` : comparable ⇔ empreintes partagées identiques
(population, jeu, gabarit si commun, calendrier, graines, tolérances) ; sinon liste des différences en
tête et mention « non comparable ». **[H]** le régime de regroupement n'entre pas dans la règle.

**Appariement décision par décision** (`scripts/analysis/appariement_executions.py`, CLI
`make apparier A=… B=…`, ticket 073 axe 0). `comparer` répond « ces deux mesures sont-elles
comparables ? » ; `apparier` répond « de combien le décideur a-t-il bougé, décision par
décision ? ». Il appelle d'abord `comparer` — apparier deux conditions différentes ne mesure
pas le non-déterminisme du fournisseur, et le refus est la garde — puis lit les deux
`decisions.jsonl` en appariant sur `(person_id, activity_id)`. Lecture seule.

Le classement des couples communs EST la mesure, et confondre ses familles fausse le chiffre :

| famille | critère | sort |
|---|---|---|
| `cascade_amont` | les options offertes diffèrent | écartée — l'écart est hérité du déplacement précédent, pas produit ici |
| `methode_dissymetrique` | même offre, méthode différente | écartée et **signalée** : le décideur a répondu d'un côté seulement |
| `choix_unique` | une seule option des deux côtés | écartée — aucune sollicitation |
| `hors_mesure` | même méthode, rien à comparer (`inexploitable`, `sans_solution`) | écartée |
| `appariables` | même offre **et** décideur sollicité des deux côtés | **la seule population chiffrée** |

Les masses se lisent dans `poids_presentes`, **jamais** dans `distribution` : celui-ci agrège sur
les six modes canoniques et écrase deux options d'un même mode. Sur les 120 premières décisions du
réplicat, `distribution` annonçait 5 bascules « à masses égales » contre UNE pour
`poids_presentes` — or le ticket qualifie ce cas de défaut du dispositif, donc le mauvais vecteur
invente un bug. Ces bascules sortent **nommées** (personne, poids, index de part et d'autre,
graine de tirage, lot), pas résumées en taux.

Deux `[ALARME]` : une bascule à masses strictement identiques (le tirage devrait être
reproductible à graine égale), et une **couverture** — `communes / max(|A|, |B|)` — sous 80 %.
La seconde vise le défaut du 2026-09-15 : un `moves.csv` tronqué à 274 lignes lu comme s'il
portait les 3 299 décisions. Le taux se calcule ainsi, et non `appariables / communes`, parce que
les choix uniques feraient chuter ce dernier alors qu'ils sont légitimes.

## 5. Spec 03 + 05 — le runner (`experiences/runner.py`, `experiences/decideurs.py`)

Boucle asynchrone : `parallelisme` personnes en vol (sémaphore), les déplacements d'une personne
**séquentiels** (S4 : jamais deux déplacements d'une même personne en parallèle). Pour chaque
déplacement : propositions du jeu (absent → `non_couvert`), `decision.decider`, `archive.ajouter`,
`decision.avancer_chaine`. Progression journalisée toutes les 5 s (S6). Fin : ligne de succès avec
durée et six compteurs (S8).

**Décideurs** (`Decideur.choisir(person, ctx, presentees) -> ReponseDecideur`) :

- `DecideurPasserelle` : réutilise `LlmAgent.build_travel_plan_payload` (même texte que la
  simulation, J4) et `LlmAgent.evaluate_and_choose_travel_plan` enrichi de trois kwargs optionnels
  (`force_provider`, `allowed_providers`, `trace`) — le contrôleur ne les passe pas, son comportement
  est inchangé. **Épinglage** (Q2) : les instances admises sont celles de `providers.yaml` dont
  `default_model` = modèle demandé ; le runner tourne sur ces instances, en `force_provider`. Une
  réponse dont `provider_used` n'est pas admis est **refusée** et comptée `substitution_refusee` (Q3 —
  la passerelle rejoue un lot sans `force_provider` sur erreur de parse).
  **Portée** (`decideur.portee`, depuis le 2026-09-11) : le même identifiant de modèle est parfois
  servi des deux côtés — `qwen/qwen3.8-27b` est chez Groq **et** dans LM Studio, deux
  quantifications. L'épinglage par égalité de modèle admettait alors les deux, et la bascule en
  série (ci-dessous) faisait finir en local ce qui avait commencé chez Groq, sous un seul nom.
  `portee: local | distant` restreint les instances au bord voulu ; les deux usages restent
  ouverts, ce sont **deux expériences** (le nom porte `_local`, cf. N4b). Une définition qui ne la
  pose pas alors que son modèle est servi des deux côtés est **refusée au lancement**, en nommant
  les deux instances — on ne choisit pas à la place de l'expérimentateur. Absente et sans
  ambiguïté, elle ne change rien : les archives d'avant le champ gardent leur empreinte.
- `DecideurDureeMinimale` : déterministe, local, `sans quota` (S10/Q12) — plancher `exp_00c`.
- `DecideurRejeu(execution)` : sert `reponse_brute`/`distribution` archivées par `(person_id, activity_id)`.
- `DecideurAleatoire(graine)` : uniforme, graîné (plancher `exp_00a` du plan).
- `DecideurMajoritaireVoiture` (`type: majoritaire_voiture`) : plancher `exp_00b` — retient l'option
  dont le **mode principal** est la voiture (`_primary_mode`, hiérarchie EMC² ; distinct de la chaîne
  `_vehicle_mode`, donc un rabattement voiture+train n'est pas « la voiture »), la plus rapide entre
  plusieurs ; sinon repli déterministe sur la première option présentée. Local, déterministe, sans quota.
- `DecideurAntigravity` (`type: antigravity`) : délègue chaque décision à un sous-agent Antigravity
  via IPC sur disque (`echanges/{demandes,reponses}/`), sans quota d'API. Le modèle est déclaré mais
  invérifiable par le code (P1 : `modele_verifie: false` scellé dans l'empreinte et les traces) ;
  une exécution ne fournit aucune mesure publiable de parts modales (P2), valant comme banc d'essai
  et mesure à coût nul. Local, asynchrone, sans quota.

- `DecideurTypesafe` (`type: typesafe`, ticket 096) : Jev, un **classifieur zéro-shot à sortie
  typée** — troisième famille, ni modèle de langage génératif ni modèle tabulaire entraîné sur
  l'enquête. On lui envoie un `state` et une question `Choice` ; il rend la distribution complète
  sur les options et une confiance, sans produire une ligne de texte. Quatre conséquences, toutes
  voulues :
  - la **présentation ne se réimplémente pas** : le texte servi sort du même
    `LlmAgent.build_travel_plan_payload` que les bras LLM. Ce qui change est la FORME — les options
    quittent le texte pour `criteria` (clés `option_<i>`, indexées et non nommées par mode, deux
    itinéraires partageant souvent le même), et la consigne perd son bloc `[Output instructions]`
    que le type `Choice` remplace ;
  - l'empreinte porte le **sha du texte réellement envoyé** (`instructions_sha256`) en plus de
    l'empreinte de gabarit : celle-ci hache la variante entière, donc changer la règle d'amputation
    ne la ferait pas bouger, et deux exécutions incomparables porteraient la même signature ;
  - la **version est figée** (`jev-1.13.0`) : un alias (`jev-latest`, `jev-preview`) est **refusé**
    à la validation, jamais résolu au lancement — un alias résolu scelle une version que
    l'`experience.yaml` ne porte pas ;
  - `raison` reste **vide**. Jev ne rédige pas, et une phrase fabriquée à partir des probabilités
    se lirait comme une sortie de modèle dans les traces et les rapports mémoire.

  Jev rend ses probabilités **arrondies à deux décimales** : une somme à 0,99 ou 1,01 est normale,
  tolérée à 0,02 et renormalisée. Au-delà, clé d'option manquante ou masse nulle : **non-décision
  explicite** (`non_imputable`), archivée, comptée, jamais réessayée. À distinguer d'un échec de
  transport (429, 529, timeout, coupure), qui est une **erreur** réessayée par le runner sous
  `passerelle_occupee:` — et d'une erreur de configuration (401, 422) qui se dit `configuration:`,
  parce qu'il y a une ligne de YAML à corriger et non un quota à attendre. Local au sens des
  quotas : `sans_quota`, aucune clé réservée, aucune rotation (1 200 req/min annoncés). Clé API :
  `PROVIDER_KEYS__typesafeAI`, passée explicitement au SDK — le laisser résoudre son propre
  `TYPESAFE_API_KEY` ferait servir une clé traînant dans l'environnement à l'insu de l'empreinte.
  **Sans mémoire par construction** : les catégories STM/LTM produisent du texte, Jev n'en produit
  pas. Le bras se nomme par sa version et sa variante de prompt (`exp_jev-1130_proexp05_…`), sans
  segment de température — Jev n'en a pas, en écrire un scellerait un réglage inexistant.

**Ressources** (Q1–Q12) : `/health` de la passerelle lu avant chaque vague (Q11, depuis le
2026-09-21 : la marge déclarée n'écarte plus ; seul un `quota_exhausted` réel écarte, et `epuisee`
survient donc **après** le premier 429, plus avant) ;
`reprise_possible_a` = réouverture de la fenêtre `rpd` du fournisseur ; pause manuelle par fichier `PAUSE` dans le
dossier d'exécution ou `SIGINT` → point sûr → `en_pause`, **en quelques secondes** (voir
« Pause effective en quelques secondes » ci-dessous). Reprise : `decisions.jsonl` relu,
décisions archivées **resservies** (Q5) et leur effet sur la chaîne rejoué sans sollicitation ;
historique des interruptions dans `execution.yaml` (Q6). Une exécution rouverte alors qu'elle était
restée `en_cours` (processus tué sans clôture) consigne une interruption `arret_force` (R3).

**Quelles exécutions se reprennent** (`lancer --reprendre`, bouton « Reprendre ») : toute exécution
dont l'archive n'est **pas clôturée** — en pause, épuisée (le runner la marque sans sceller, R4),
interrompue, ou en cours sans runner. Une archive clôturée (terminée, ou arrêtée par `STOP`) est
immuable (E19) : « Rejouer » en crée une nouvelle. Jusqu'au 2026-09-08 la CLI refusait « épuisée »
au titre des états finaux, en contradiction avec son propre message, cette spec et le tableau de
bord ; le critère est désormais `cli.motif_non_reprenable`, partagé par les deux chemins.

**Arrêt du conteneur et `arret_force` (correctif 2026-09-07).** Le runner tourne en
`docker compose exec` **dans le conteneur `controller`** : il meurt avec lui. La commande du service
préfixe désormais hypercorn par **`exec`**, pour qu'hypercorn soit **PID1** et reçoive SIGTERM.
Auparavant PID1 était le `sh -c` englobant, qui ne relaie pas le signal : tout
`docker stop`/`compose restart` épuisait le délai de grâce puis SIGKILL — le conteneur sortait en
**137** et le runner tombait sans préavis, `etat.json` restant figé sur `en_cours`.
**Limite résiduelle assumée** : Docker n'envoie SIGTERM qu'à PID1, jamais aux processus lancés en
`exec`. Un arrêt du conteneur reste donc brutal *pour le runner* — il ne peut pas rendre la main à
un point sûr comme le font `SIGINT` ou le fichier `PAUSE`. Le filet reste la relecture de
`decisions.jsonl` : la reprise repart du dernier déplacement archivé et consigne `arret_force`.
Pour interrompre proprement une exécution en cours, **poser le fichier `PAUSE`** dans le dossier
d'exécution (ou envoyer `SIGINT` au runner) *avant* d'arrêter le conteneur.

**Une sentinelle ne vaut que pour le run qui l'a reçue (correctif 2026-09-08).** `executer()`
purge `PAUSE` et `STOP` **au démarrage**, et journalise ce qu'elle a retiré. Auparavant
`Controle.nettoyer()` n'était appelé qu'à la clôture : un runner tué net laissait sa sentinelle
sur le disque, et la reprise suivante l'honorait comme si elle venait d'être demandée — un
`PAUSE` la remettait en pause en quelques secondes (l'exécution paraissait irréprenable), un
`STOP` **scellait l'archive** en `arretee`, donc non reprenable pour toujours. Le dépôt d'une
sentinelle dans une exécution morte est par ailleurs désormais refusé côté tableau de bord
(voir `docs/arch/dashboard.md`), mais le runner ne s'en remet pas à cette garde : la purge au
démarrage protège aussi les dépôts faits à la main ou par un script.

**Aucun déplacement sauté (R1, correctif 2026-09-07).** La décision d'un déplacement est réessayée
**jusqu'à aboutir** : plus de maximum de tentatives. Une erreur transitoire (passerelle occupée,
timeout, réseau) déclenche une pause croissante `PAUSE_BASE_S × tentative` plafonnée à 60 s,
**interruptible** (pause/arrêt/signal rendent la main à un point sûr, le déplacement non archivé
étant repris tel quel). `attente_max_s` **ne borne plus** l'attente : c'est un **seuil d'`[ALARME]`**
levé sur **front montant** (une fois par déplacement) — le journal ne devient jamais muet, mais on
ne saute rien. `progression.json` expose `en_attente`, `en_attente_depuis_s` et `en_attente_quota_jusqu`.

**Pause effective en quelques secondes, et chien de garde (2026-09-08).** Une pause ou un arrêt
n'attend plus le retour de la sollicitation en vol. Une tâche de surveillance
(`runner.surveiller`, tick 0,5 s) regarde les fichiers `PAUSE`/`STOP`, les signaux **et**
l'inactivité :

| Réglage | Défaut | Rôle |
|---|---|---|
| `EXP_PAUSE_GRACE_S` | 15 s | délai laissé à une sollicitation **déjà en vol** après la demande ; passé ce délai l'appel est **abandonné** (`Controle.abandonner_en_vol`) |
| `EXP_INACTIVITE_PAUSE_S` | 420 s (7 min) | sans **aucun** déplacement réglé pendant ce délai, l'exécution lève une `[ALARME]` et se met en pause d'elle-même ; `0` désactive |
| `EXP_RAFRAICHIR_QUOTAS_S` | 30 s | âge maximal de l'instantané des quotas **pendant** le run : au-delà, `veiller_quotas` relit `/health` pour que le décideur cesse d'épingler une clé épuisée ; `0` désactive |

L'annulation ne touche **que** l'appel réseau (la sollicitation est lancée comme tâche suivie),
jamais une écriture d'archive : le déplacement reste **non archivé**, donc redemandé tel quel à la
reprise. Rien n'est sauté, rien n'est fabriqué, le résultat final ne change pas (Q6) ; le seul coût
est monétaire, borné par le parallélisme. *Avant ce correctif*, la pause attendait le retour de
l'appel — jusqu'à `remote_llm_poll_timeout` (120 s) : elle pouvait devenir effective deux minutes
après le clic, et le tableau de bord n'affichait rien entre-temps.

Le chien de garde compte comme **avancée** tout déplacement réglé, quelle qu'en soit l'issue —
décidé, resservi depuis l'archive, non couvert, inexploitable, sans solution
(`Progression.avancement()`). Il se **tait** pendant l'attente de la fenêtre de quota (R4,
attente de fenêtre quota) : cette immobilité est demandée. `progression.json` expose
`immobile_depuis_s` (`null` pendant une fenêtre de quota), que le tableau de bord écrit sur la
barre dès une minute d'immobilité. Une pause automatique se relit dans l'état
(`raison: pause automatique — …`) et dans l'historique des interruptions
(`cause: pause`, `raison: inactivite:<n>s`).

**Classement des erreurs (R2).** `decideurs.py` réserve `epuise` au quota (429) ou au crédit (402)
**confirmé** ; « saturés / indisponibles / timeout » devient `passerelle_occupee`, transitoire. Un
`epuise` n'arrête que si l'épuisement est confirmé — et il y a deux façons de le confirmer :

- **le fournisseur l'annonce** (`genre_erreur = "quota_journalier"`, issu d'un 429 dont le corps
  désigne un quota du jour). Cela suffit, et l'heure de réouverture qu'il donne fait foi. Le
  moniteur n'est pas consulté : il lit `/health`, donc un compteur qui ne voit que le trafic de
  la passerelle — le 2026-09-08 il affichait « 49/500, disponible » pendant que Google refusait,
  et l'exécution a attendu quinze minutes une clé fermée pour sept heures ;
- **sinon**, le moniteur tranche : `epuise` est transitoire tant qu'une instance du modèle
  épinglé reste disponible.

`reprise_possible_a` vaut l'heure annoncée par le fournisseur, à défaut le prochain minuit dans
son fuseau (`prochaine_fenetre_quota`, `America/Los_Angeles` par défaut — un quota Gemini rouvre
à 09:00 à Paris l'été, pas à 02:00 comme le supposait le calcul en UTC).

**L'instantané des quotas se relit pendant le run (correctif 2026-09-08).** Une tâche dédiée,
`veiller_quotas`, relit `/health` dès que l'instantané dépasse `EXP_RAFRAICHIR_QUOTAS_S` (30 s),
et ne journalise que les **changements** — la bascule se dit par le **rang** de la clé, jamais
par son nom, qui désigne un compte.

Sans elle, `moniteur.etat` restait celui du **démarrage** pour toute la durée du run. Le seul
autre rafraîchissement vit dans `_confirme_epuise`, qui n'est atteint que par une erreur classée
`epuise` : or « Providers saturés ou indisponibles », le message que le worker émet quand la clé
forcée est au quota du jour, tombe dans `_RE_OCCUPEE` — donc transitoire, **à dessein** (frontière
`satur` → occupée, décision du 2026-09-07). Le chemin ne s'ouvrait jamais. Conséquence : une clé
épuisée en cours de route restait « disponible », `DecideurPasserelle._prochaine_instance`
continuait de l'épingler, et comme `force_provider` est **strict** côté passerelle
(`select_provider` lève plutôt que de substituer, pour ne pas changer d'instance dans le dos de
l'expérience), chaque lot partait vers une clé fermée. Le 2026-09-08, un run de 1000 personnes
s'est arrêté à **70,5 %** avec **500 requêtes intactes** sur la seconde clé ; relancé, il a
terminé les 30 % restants en **64 requêtes** (le lot regroupe jusqu'à 15 agents).

Deux contraintes de mise en œuvre portent du sens. La lecture passe par `asyncio.to_thread` :
`lire_etat_passerelle` est un `httpx.get` **bloquant** (jusqu'à 5 s) qui figerait la boucle
d'événements, donc la grâce de pause et le chien de garde avec elle. Et la veille est **fail-open**
de bout en bout : une passerelle injoignable laisse l'instantané précédent en place (jamais un état
vide, qui ferait croire à l'épuisement de toutes les clés), l'âge reste celui de la dernière
lecture **réussie** — on réessaie à l'échéance normale sans marteler une passerelle en panne — et
aucune erreur de lecture n'interrompt le run.

**Attente de la fenêtre quota (R4) — comportement par défaut depuis le 2026-09-08.** Sur
épuisement confirmé, l'exécution **dort en process** jusqu'à `reprise_possible_a` (état
`en_attente_quota`, non final, un seul dormeur sous verrou), rafraîchit le moniteur, puis repart
seule et retente le même déplacement. Aucune substitution, aucune décision par défaut : en
pénurie, on attend. Une expérience lancée le soir franchit donc la nuit au lieu de mourir sur un
quota du jour.

L'attente reste visible et interruptible : état `en_attente_quota`, `en_attente_quota_jusqu` dans
`progression.json`, sortie sur PAUSE/STOP/SIGINT. `--ne-pas-attendre-fenetre` restaure l'arrêt
immédiat en `epuisee` (l'ancien défaut) ; `--attendre-fenetre` est encore accepté, sans effet.

**Traçabilité (R3).** Chaque tentative ratée est archivée dans `erreurs.jsonl` (horodatage,
person_id, activity_id, tentative, type, message échappé, fournisseur, attente) ; tout le journal de
l'exécution est aussi écrit dans `execution.log` (sink loguru ajouté par `cmd_lancer`). La commande
`experiences erreurs <exec>` (`make experience-erreurs EXP=`, module `experiences/erreurs.py`)
rapproche `decisions.jsonl` du jeu : tentatives par type, déplacements manquants, journées à trous
(un manquant *suivi* d'un décidé — chaîne potentiellement faussée) et décisions après un trou.

## 6. Spec 04 — GAMA sur jeu enregistré (`simulation_controller.py`, Makefile)

- `settings.data.jeu_enregistre: Optional[str]` (env `JEU_ENREGISTRE`, posé par `make run JEU=<nom>`).
  Au démarrage : `jeu.charger()` + contrôle d'empreinte de population (G1 → refus explicite).
- `_compute_move_for_activity` : si le jeu couvre `(person_id, activity_id)` → propositions servies du
  jeu, marquées `enregistree`, **aucun** appel `trip_helper` ; sinon comportement actuel (source
  `en_vol`, compté). Compteur d'appels par moteur (`otp`, `osmnx`) exposé dans
  `experiments/<run>/jeu_stats.json` et dans `make report` (G3/G14).
- **Tolérance horaire** (G5) : écart = `departure_time` réel − `depart_ts` du jeu ; par groupe de mode,
  `insensible` / `heure` (heure pleine différente) / `pas_min`. Un groupe hors tolérance est recalculé
  pour ce seul groupe (`recalculee:horaire`), les autres servis. Résultat identique aux enregistrées à
  la minute ⇒ `recalcul_sans_effet` (G7, ALARME au-dessus d'un seuil déclaré). Déclencheur jamais
  déclenché ⇒ signalé dans `jeu_stats.json`.
- **Événements** (G4a, G9) : **[H]** aucun mécanisme d'incident n'existe dans le code ; le champ
  `evenements` est accepté, archivé, et la simulation le **refuse** tant qu'il n'est pas implémenté
  (plutôt qu'un déclencheur fantôme).
- **Pause à chaud** (G10) : **[H]** granularité « début de la journée en cours » : `make run CONT=1`
  rejoue la journée ; les décisions archivées dans `decisions.jsonl` du run sont resservies par
  `DecideurRejeu` (aucune sollicitation), positions et mémoire suivent. La reprise à l'instant exact
  exige un gel d'état côté GAMA (ticket 002), hors de ce lot.

## 6 bis. Un seul substrat : le garde d'archive (ticket 045)

Les 36 premières exécutions de la plateforme ont **toutes** lu la cohorte v1 quand la référence
de l'article était la v5. Aucune n'était fautive isolément : deux mécanismes se renforçaient, et
le troisième garde-fou n'existait pas.

| Mécanisme | Avant | Après |
|---|---|---|
| Défaut du formulaire | `populations()[0]`, soit le premier par **ordre alphabétique** — la v1 précède `_v3`, `_v4`, `_v5` | `population_par_defaut()` : la **dernière scellée par date de sceau**. Une cohorte sans `scelle_le` ne peut pas prendre la tête |
| Nom de l'expérience | `population_1000_AAMAS` était une valeur muette du nommage (N7) : aucun des 46 noms ne mentionnait de substrat | la population entre **toujours** dans le nom, via `abreger_population` — qui retire le préfixe commun `population_` avant de tronquer, faute de quoi la coupe à 16 caractères effaçait exactement le suffixe de version |
| Lecture d'une cohorte périmée | rien ne s'y opposait | `resoudre_population()` **refuse** tout chemin sous `data/population/archive/` |

**Le garde est dans le code, pas dans un README.** Un garde-fou qui n'existe que dans la prose ne
se déclenche jamais. Sa levée demande un **motif**, pas un booléen :

```yaml
population:
  chemin: data/population/archive/population_1000_AAMAS
  archivee_confirmee: "témoin du ticket 045"      # journalisé à chaque lecture
```

`archivee_confirmee: true` ne lève rien : il faut écrire pourquoi. Le motif part en WARNING avec
le rappel que la mesure ne se compare pas à celles faites sur la cohorte de référence.

**Le tableau de bord ne propose rien d'archivé**, nulle part. Deux notions distinctes portaient le
même mot « obsolète », et il faut les tenir séparées : une exécution *obsolète* est une exécution
qu'une plus récente de la même expérience a remplacée, et c'est elle que la case « Masquer les
obsolètes » gouverne ; une expérience *archivée* est une décision de retrait, que cette case n'a
jamais eu à gouverner. `experiences()` filtre désormais les statuts `archivee` et `invalide` —
c'était la lacune : le tableau « Mes expériences » filtrait, mais « S'inspirer d'une expérience
existante » et « Dupliquer » lisaient la liste brute. `experiences(inclure_masquees=True)` reste
disponible pour la **lecture** par nom : on cesse de les proposer, on ne les rend pas illisibles.

**Les parts modales se publient des deux façons** (R10-R12). Une décision à itinéraire unique
n'a été prise par personne : une seule option existait. Elle compte pourtant dans les parts, et
son nombre **dépend du bras**, puisqu'il découle de ses propres choix antérieurs — 393 pour
`duree_minimale`, 286 pour `aleatoire` sur le même substrat, soit 11 à 15 % de journée identique
et non décidée, ce qui comprime mécaniquement les écarts qu'on mesure.

La chaîne n'est pas neutralisée : un trajet contraint par un choix antérieur reste un fait de la
journée simulée, et une vraie journée en comporte. Une synthèse porte donc trois blocs :

| Bloc | Ce qu'il dit |
|---|---|
| `parts_modales` | toutes décisions, choix forcés compris — **porte la conclusion** |
| `parts_modales_hors_choix_unique` | ce que le décideur a réellement décidé |
| `choix_forces` | leur nombre, leur part, et le rappel que ce nombre dépend du bras |

Pour comparer deux bras **terme à terme**, ni l'un ni l'autre ne suffit : « hors itinéraire
unique » retire des trajets *différents* selon le bras, donc ne rend pas la comparaison plus
juste, il la déplace. `perimetre_commun(traces_par_bras)` rend l'intersection des déplacements
que **tous** ont réellement décidés, avec son effectif et ce que chaque bras y perd.

**L'empreinte du substrat s'affiche avant le lancement** (R19), pas seulement dans la synthèse
écrite après coup : `_bandeau_substrat` place au-dessus des boutons le nom de la cohorte, son
empreinte, sa date de sceau et le jeu. Une cohorte non scellée se signale ; un jeu préparé pour
une autre cohorte bloque avant le clic — la garde `verifier_population` (G1) existait déjà au
lancement, mais découvrir l'incohérence après avoir payé n'a pas le même prix que la lire.

**Interrupteurs de chaîne dans la définition** (R13). `vehicule_chaine` et `verrou_retour` sont
des champs de `experience.yaml`, entrent dans `reglages_herites` et dans le nom (`nochn`,
`noret`) dès qu'ils s'écartent de la référence, qui est **actif**. Sans cela, les deux conditions
du 2×2 chaîne auraient porté la même définition, la même signature et le même nom. Ces deux
drapeaux coupent la **position** du véhicule et le **verrou de retour**, jamais la possession, le
permis ni l'âge — attributs de la personne que les deux décideurs voient légitimement.

## 6 quater. Archive FROIDE : restaurable, auditable, jamais référencée (ticket 074)

Le statut `archivee` d'une expérience (§ 7 quater) et le garde de cohorte du § 6 bis règlent la
**visibilité** : les fichiers restent en place et restent lisibles. La bascule du dispositif en
anglais demandait autre chose — geler l'état français **hors de portée du code**.

    Froid = restaurable et auditable, jamais utilisé ni référencé.

`archive/2026-09-14_avant_bascule_anglaise/` porte, à la racine du dépôt et hors git :

| Dossier | Contenu | Mode |
|---|---|---|
| `prompts/` | `prompts.yaml` (22 variantes françaises), les 4 gabarits, les 4 schémas | copie |
| `rendu/` | les 7 gabarits de description, `terminal_time.yaml`, les 2 tables de conditions météo | copie |
| `code/` | `llm_agent.py`, `weather_loader.py` | copie |
| `plateforme/` | les 24 définitions d'expériences **et leurs exécutions**, les jeux scellés v5 | déplacement |
| `population/` | la cohorte v5, sa variante escorte, et la source déclarée par son MANIFEST | déplacement |

La distinction copie / déplacement n'est pas cosmétique. Ce que git suit déjà est **copié** : ces
fichiers restent en place, ce sont eux qu'on traduit, et git porte l'historique — la copie n'existe
que pour qu'un auditeur lise l'état français sans faire d'archéologie dans les commits. Ce que git
ne suit pas et qui ne doit plus servir est **déplacé**. Rien n'est supprimé.

`MANIFEST.yaml` porte le commit du gel, le `sha256` de chaque entrée, son chemin d'origine, et la
liste des chiffres de l'article qui en dérivent. `scripts/archiver_avant_bascule_anglaise.py` est
idempotent, vérifie par défaut sans rien écrire, refuse de démarrer si une exécution a écrit sa
progression depuis moins de deux minutes, et revérifie l'empreinte **à l'arrivée**.

### Le garde est commun aux trois chargeurs

`experiences/froid.py` porte la règle une seule fois ; trois points de passage obligés
l'appliquent :

| Chargeur | Ce qui y passe | Dérogation |
|---|---|---|
| `population.resoudre_population` | toute lecture de cohorte | `population.archivee_confirmee: <motif>` dans la définition |
| `jeu.Jeu.charger` | toute lecture de jeu scellé | `archive_confirmee="<motif>"` |
| `llm_gateway.prompts.engine.PromptManager` | tout service de prompt système | **aucune** — un prompt archivé ne se sert jamais |

Le garde porte sur l'**emplacement**, jamais sur une correspondance de texte dans le nom : il
suffit qu'un segment du chemin s'appelle `archive`. Une cohorte nommée `population_archivistes`
reste parfaitement lisible. La dérogation exige un **motif écrit** — `confirme=True` se coche sans
y penser, `confirme="garde de comparabilité D-7"` s'écrit, se journalise et se relit.

Le registre et la file d'attente ne voient jamais l'archive, et ce n'est pas un filtre ajouté
quelque part : `dossier_experiences()` et `dossier_jeux()` s'ancrent sous `data/`, l'archive vit à
côté. `scripts/tests/test_074_archive_froide.py` verrouille la propriété plutôt que de la
promettre — c'est la leçon du ticket 045, où 36 exécutions ont lu la mauvaise cohorte sans que
rien s'y oppose.

### Ce que le gel a coûté, et ce qu'il a rendu

Entre l'archivage et le scellement de la v6, `data/population/` et `data/experiences/` étaient
vides : une quarantaine de tests sont passés en **veille**, en disant pourquoi (« aucune cohorte
scellée sur disque (substrat en archive froide, ticket 074 lot A) »), au lieu de tomber sur un
`FileNotFoundError` qui aurait fait chercher une régression du tableau de bord. Le compte de
tests en veille servait d'indicateur : il est redescendu de 41 à 25 au scellement de la v6.

### ⚠ Un montage Docker suit l'inode, pas le nom (2026-09-14)

**Le piège, et il a mordu.** L'archivage *déplace* `data/experiences/` et `data/jeux/`. Sur
l'hôte, ces dossiers disparaissent. Dans un conteneur **déjà démarré**, `/app/data/experiences`
désigne toujours le même inode — c'est-à-dire le dossier maintenant rangé sous `archive/`.

Rien ne plante. La plateforme continue de tourner, lit ses 26 définitions et écrit ses nouveaux
jeux **dans l'archive froide**. Le garde de `experiences.froid` ne peut rien voir : il inspecte
des chemins, et le conteneur ne voit que `/app/data/…`, où le mot `archive` n'apparaît pas.
Constaté en construisant le jeu v6, qui a écrit 2 Mo dans l'archive avant qu'on s'en aperçoive.

**La parade** : `scripts/archiver_avant_bascule_anglaise.py` redémarre `controller`, `api` et
`worker` dès qu'il a déplacé quoi que ce soit, et le dit. Fail-open — Docker absent n'est pas
une anomalie — mais alors il imprime la commande à lancer à la main.

**À retenir au-delà de ce ticket** : seul un *déplacement* casse un montage. L'archivage de
`data/population/population_1000_AAMAS_v5` n'a rien cassé, parce qu'il déplaçait un ENFANT du
dossier monté, pas le dossier lui-même.

### Une seconde archive froide : l'ancien jeu v6 EN (ticket 098, 2026-09-21)

`archive/2026-09-21_ancien_jeu_v6_EN/` gèle le substrat remplacé le 2026-09-16 par sa version
corrigée (ticket 088) et **tout ce qui a été décidé dessus** : 36 définitions, 31 exécutions,
et le jeu scellé lui-même — 345,3 Mo, 647 fichiers, tous en **déplacement**.

Rien n'est copié cette fois : contrairement au 074, aucune de ces pièces n'est une surface qu'on
réécrit sur place. Elles ne doivent plus servir, point.

**Pourquoi le jeu part avec ses exécutions.** Une exécution ne se rejoue pas sans son substrat
(`journal.regenerer` recharge jeu **et** cohorte). Et un jeu laissé sous `data/jeux/` resterait
proposé : la règle R17 n'écarte que ce qui est *déjà* sous `archive/`. Rien n'aurait empêché de
définir demain une expérience neuve sur le substrat daté du 17 mars — le défaut du ticket 045, à
un substrat près. La **cohorte**, elle, reste vivante : la correction portait sur le calcul de
l'offre, pas sur les personas.

**La garde de démarrage est scopée, et c'est une différence assumée.** Le script du 074 refusait
de démarrer si une exécution QUELCONQUE du dépôt avait écrit depuis moins de deux minutes —
c'était juste, il déplaçait `data/experiences` en entier. Ici l'ensemble déplacé est disjoint du
reste : `scripts/archiver_ancien_jeu_v6_en.py` refuse sur les seules pièces concernées, et se
contente d'**avertir** pour le travail vivant ailleurs (que le réancrage Docker fera néanmoins
sursauter). Une garde globale aurait interdit le gel dès qu'une expérience sans rapport tourne.

**Ce que le gel a coûté : rien de mesurable, et c'était la condition.** Vérifié avant de déplacer
quoi que ce soit — aucun bras portant une exécution `terminee` sur l'ancien jeu n'est dépourvu de
contrepartie `terminee` sur le jeu corrigé, et `plot_chapitre6.py` journalisait déjà
`13 sur 13, 0 sur l'ancien jeu`. Les PNG des huit figures sont **identiques bit à bit** après le
gel. Le repli de `resoudre()` sur l'ancien jeu était mort avant ; il nomme désormais l'archive
au lieu de rendre un `None` muet, pour qu'un rejeu incomplet ne se diagnostique pas comme un
substrat gelé.

**Un effet de bord qui reste ouvert.** La sélection des 10 personas mesurables du ticket 093 a
été dérivée d'un run de l'ancien jeu, et
`data/population/population_10_mesurables_093/MANIFEST.yaml` le scelle (`run_de_reference`,
`candidats: 234`). Ce run est maintenant gelé, et le même critère appliqué à sa contrepartie
corrigée donne **246 candidats**, avec un persona de la démonstration (41275) qui cesse de
passer. Les deux tests concernés de `test_093_selection_personas.py` sautent désormais, avec un
motif qui le DIT. Re-dériver la sélection est une décision scientifique, pas un ajustement de
test : elle n'a pas été prise ici.

## 6 quinquies. Nommage des variantes de prompt (ticket 074, C-4/C-5)

Le nom d'une variante entre dans le nom de l'expérience (`abreger_variante`), donc dans son
identité. Il doit dire **la famille** et **la place dans la série** :

    prompt_<famille>_<nn>        famille ∈ {minimal, expert}

La numérotation suit la **généalogie** (`_provenance.derive_de`), racines d'abord, puis chaque
lignée en profondeur. Ni l'alphabet ni la date : les cinq `persona_*` portaient toutes la date de
leur archivage, et un tri par date les aurait séparées de leurs parents.

Ce que le renommage a réparé, et qu'aucun test ne voyait : `expert_gem_3.8_v2` et
`expert_gem_3.8_v2_neutre_justif` s'abrégeaient **tous deux** en `expgem38v2`. Deux expériences
portaient le même segment de variante, distinguées par un indice `_2` qui ne disait pas ce qui
changeait — une collision dans l'identité d'une mesure, pas une gêne cosmétique.

**Un ancien nom se résout encore, mais en LECTURE seulement.** `PromptManager` tient un index
`_ancien_nom → nom canonique` et avertit à chaque résolution. Sans lui, `empreinte_gabarit` ne
pourrait plus recalculer l'empreinte d'une exécution archivée : ses définitions gelées portent
`variante: expert_gem_3.8_v2` et ne seront jamais réécrites, l'archive étant froide (§ 6 quater).
Un nom vraiment inconnu reste refusé, et le message liste les deux jeux de noms — résoudre en
silence ferait reconduire l'ancien nom de trace en trace.

`scripts/migrations/renommer_prompts.py`, à blanc par défaut, réécrit les clés **et** toutes les
références internes : `active:`, `familles.minimale`, `derive_de`, `_calibration.seed`,
`_invalidation.remplace_par`, ainsi que les définitions d'expériences vivantes.

## 6 ter. Substrat dérivé de sonde (`scripts/deriver_sonde_escort.py`, ticket 027)

Certaines questions se posent sur le **contenu** du substrat — « le modèle réagit-il à cette
valeur ? » — et n'exigent pas de régénérer une population. La réponse tient dans un substrat
*dérivé* : mêmes personnes, mêmes lieux, mêmes horaires, mêmes propositions, **un champ changé**.

Trois contraintes gouvernent la fabrique, et aucune n'est cosmétique.

**Il faut dériver la population, pas seulement le jeu.** Le motif servi au décideur vient de
l'agenda de la personne (`runner.py` : `deplacements_attendus(personnes, …)`), jamais de la ligne
de jeu ; le jeu n'est interrogé que pour ses propositions. Réécrire le jeu seul ne changerait rien
au prompt — et la mesure rendrait un écart nul parfaitement trompeur.

**Il faut donc aussi dériver le jeu**, parce qu'un jeu est lié à sa population par empreinte
(`verifier_population`, G1) et serait refusé au lancement. Ce jeu-là se fabrique par **copie** :
les lignes hors tirage sont recopiées à l'octet, les lignes tirées re-sérialisées avec le champ
changé, l'empreinte recalculée, les `dependances` héritées telles quelles. Rejouer les moteurs
rendrait un jeu *presque* identique — et cette dérive-là se confondrait avec le traitement.

**La copie doit rester justifiée.** Elle ne vaut que tant que le champ dérivé n'entre dans aucun
calcul de proposition. Pour le motif, deux emplois seulement : l'étiquette recopiée sur
l'itinéraire, et l'option bus scolaire, qui ne se déclenche que sur `education`. Le script le
**vérifie avant de dériver** et refuse si le code a changé, plutôt que de rendre une mesure fausse.

Un substrat de sonde **ne se scelle pas** : pas de `MANIFEST.yaml`, un `PROVENANCE.yaml` à la
place. Ce n'est pas un détail de rangement — `populations()` ne liste que les dossiers scellés et
`population_par_defaut()` choisit la dernière scellée par date. Une sonde scellée aujourd'hui
deviendrait le défaut du formulaire demain, ce qui est exactement la cause racine du ticket 045.
Le jeu dérivé, lui, apparaît dans la liste des jeux : choisi avec la mauvaise population, le
lancement est refusé — la garde échoue fermée.

```bash
python scripts/deriver_sonde_escort.py --verifier   # chiffre, n'écrit rien
python scripts/deriver_sonde_escort.py              # écrit population + jeu dérivés
```

Ce que la sonde mesure, et ce qu'elle ne mesure pas, s'écrit dans son `PROVENANCE.yaml` — le
tirage étant aléatoire, elle borne la sensibilité au **libellé** et ne dit rien de la justesse de
l'affectation. Spec : `specs/ticket_027/sonde-motif-escort.md`.

## 6 sexies. La campagne (`experiences/campagne.py`, ticket 074 lot D)

Une **campagne** est un lot nommé d'expériences menées jusqu'au bout, à travers plusieurs
renouvellements de quota, sans qu'un humain relance la suivante à trois heures du matin.
Elle **assemble** ce qui existe — elle ne réimplémente ni le lancement, ni la file, ni
l'attente de fenêtre.

    campagnes/<nom>.yaml        la définition : phases, expériences, substrat
    campagnes/<nom>/etat.json   l'état, réécrit atomiquement à chaque transition
    campagnes/<nom>/STOP        l'arrêt demandé, relu à chaque tour

### Ce qu'elle apporte, et rien de plus

**Des phases.** Une phase ne démarre que si la précédente est close. Une seule dépendance,
et elle sert : les quatorze témoins déterministes ne consomment aucun quota, ils passent
donc d'abord. Si le substrat est cassé, on l'apprend gratuitement.

**Un sommeil au niveau du LOT.** `--attendre-fenetre` fait dormir *une* exécution. Quand
**tout** ce qui vole dort, la campagne n'a rien à faire non plus : elle le dit, consigne
l'heure de réveil, et reprend **à l'expérience courante**. C'est la différence entre « la
machine est bloquée » et « la campagne attend 07:00 UTC, il reste 4 h 12 ».

**Un état qui survit à un redémarrage.** Écriture atomique (`os.replace`) : un `etat.json`
tronqué par une coupure ferait repartir la campagne du début, c'est-à-dire redépenser tout
le quota déjà consommé.

**Un report, distinct d'un échec** (2026-09-17). Trois situations que la campagne confondait :

| Situation | Ce qu'elle fait | Décompte une tentative ? |
|---|---|---|
| Quota du jour épuisé, en vol ou au lancement | **reporte** — l'expérience sort de l'observation et repasse au repêchage | non |
| Charge supérieure au quota journalier | échoue, en nommant la cause | oui |
| Configuration invalide, jeu périmé, lancement muet | échoue comme avant | oui |

Le canal est un **marqueur** `lancements/<horodatage>.refus.json` que le lanceur dépose quand il
refuse de créer une exécution : la campagne lance en tâche de fond, elle ne lit ni la sortie
standard ni le code de retour du lanceur. `experiences/refus.py` porte la règle de classement, à
un seul endroit et testée. Un marqueur antérieur au dernier journal de lancement est ignoré.

Sans cela, le 2026-09-16, quatre bras attendant du quota ont été déclarés « lancée 3 fois sans
jamais écrire d'état » — un message qui envoie chercher une panne inexistante.

**Une passe de repêchage.** À la fin des phases, tout ce qui a été reporté ou a échoué repasse,
compteurs remis à neuf pour les reports, une relance de plus par passe pour les échecs. Deux
passes au maximum : une campagne qui boucle sans fin ne se voit pas.

### Où ça tourne, et pourquoi

Sur l'**hôte**, comme l'ordonnanceur : le lancement passe par `docker compose exec`, qui n'a
aucun sens depuis l'intérieur du conteneur. La campagne appelle `ordonnanceur.tour()`
elle-même — inutile de faire tourner l'ordonnanceur à côté, et le faire ne gêne pas.

### Le délai de grâce, et ce qu'il évite

Une expérience qu'on vient de lancer n'a pas encore écrit son `etat.json` : le temps que
`lancer` démarre, réserve ses clés et ouvre son dossier, elle se lit encore `definie`. Sans
délai de grâce (120 s), la campagne la relançait **à chaque tour** — et une expérience lancée
deux fois écrase sa propre exécution. Au-delà du délai, c'est que le lancement a échoué avant
d'ouvrir son dossier : on le dit, et on relance.

### Ce qui se reprend, et ce qui ne se reprend pas

`en_pause` recouvre trois situations que le runner distingue et que l'état seul confond :

| Origine | `interruptions[].raison` | La campagne |
|---|---|---|
| chien de garde — 420 s sans avancée | `inactivite:<N>s` | **reprend** : le processus est mort, personne d'autre ne le fera |
| exécution arrêtée **incomplète**, pause jamais demandée | *(aucune interruption)* | **reprend** : son propre message dit « reprendre » |
| pause demandée par un **humain** | `manuelle` | **laisse** : elle attend une décision humaine, pas un ordonnanceur |

Le discriminant est la trace **structurée** d'`execution.yaml`, jamais le message de
`etat.json` — celui-ci s'adresse à des humains et peut être reformulé sans que rien ne casse
visiblement. Un `execution.yaml` illisible penche vers la reprise : elle est plafonnée par
`TENTATIVES_MAX`, alors qu'un blocage n'a aucun plafond.

Mesuré le 2026-09-16 : sans cette distinction, une pause de chien de garde figeait la
campagne pour de bon. Comptée « en vol », l'expérience n'était ni reprise (`en_pause` n'est
pas dans `ETATS_REPRENABLES`), ni endormie (ce n'est pas un quota), ni relancée (le délai de
grâce ne surveille que les lancements du processus courant). Six heures sans un mot, et les
expériences derrière elle jamais lancées.

### Alarmes (doctrine du dépôt, front montant)

| Quand | Ce qui est dit |
|---|---|
| une expérience échoue 2 fois de suite | `[ALARME]` — elle est déclarée en échec, **la campagne continue sans elle** |
| un sommeil dépasserait 26 h | `[ALARME]` — une fenêtre de quota en fait 24 ; c'est l'horloge ou les fuseaux qu'il faut regarder |
| une expérience « en vol » dont l'état n'a pas bougé depuis 30 min | `[ALARME]` — elle nomme l'expérience, son état, son dossier, et les deux commandes qui débloquent (`experience-reprendre`, `experience-arreter`). **La campagne ne touche à rien** : elle dit qu'elle attend, et qui |

Cette dernière ne teste aucun pid — la campagne tourne sur l'hôte et les pid des exécutions
appartiennent au namespace du conteneur. Elle regarde si l'`etat.json` bouge, ce qu'une
exécution vivante fait à chaque archivage. Ce qui **dort sur son quota** en est exclu : son
état ne bouge pas non plus, mais c'est une attente comprise, déjà couverte par le sommeil de
lot — l'alarmer ferait passer une attente normale pour une anomalie.

### Ce qu'elle ne fait pas

Elle ne juge pas un résultat : une exécution `terminee` est faite, point. Le score, la
conformité et la comparabilité ont leurs propres outils (`score`, `registre.comparer`, règle
P6), et les mêler à l'ordonnancement rendrait les deux illisibles.

### Refus au chargement

`charger()` refuse plutôt que de corriger : version inattendue, phase vide, expérience citée
dans deux phases, expérience inexistante. La raison est toujours la même — une campagne qui
s'arrête au milieu a déjà dépensé le quota de ce qui précède.

## 7. Interfaces utilisateur

- **CLI** `python -m experiences <commande>` (dans le conteneur : `docker compose exec controller …`) :
  `preparer-jeu`, `consulter-jeu`, `verifier-jeu`, `definir`, `estimer`, `lancer`, `pause`,
  `reprendre`, `arreter`, `registre`, `comparer`, `synthese`.
- **Makefile** : `make jeu POP=<population> NOM=<jeu>`, `make jeu-consulter NOM=<jeu> [PERSONNE=…]`,
  `make experience-lancer EXP=<nom>`, `make experience-reprendre EXP=<nom>`,
  `make experience-pause EXP=<nom>`, `make registre`, `make run JEU=<nom>`.
  `experience-lancer`, `experience-reprendre`, `experience-lancer-arret` et `jeu` **garantissent
  leurs services** avant de lancer : `make services-pretes REQUIS="…"` (`docker compose up -d
  --no-recreate --wait`, idempotent, borné par `ATTENTE`, 600 s par défaut ; `--no-recreate`
  protège le runner d'une expérience en cours, qui vit dans `controller`). `REQUIS=` est ce qu'on démarre
  avant, `SERVICES=` ce qu'on arrête après : deux listes distinctes.
- **Dashboard** : onglet « 🧪 Expériences » (registre triable/filtrable, détail exécution → personne →
  déplacement → trace, comparaison côte à côte). La maquette HTML du ticket est une référence
  ergonomique, pas un critère.

## 7 bis. Score composite et formule révisable (`experiences/formule.py`, `score.py`, `rendu_scores.py`)

Spec : `specs/scoring_composite_experiences.md`. Une exécution **terminée** est scorée face à
l'enquête EMC² 2023 ; le composite n'est **pas réimplémenté** — il sort du `Scorer` de
`scripts/synthesis/frames.py`, qui importe la loss de `prompt_calibration/calibration/metrics.py`.
`score.py` est un adaptateur : il lit `moves.csv`, le passe au même pipeline que la page
`docs/synthesis`, et écrit `scores.json` (composite `emd_jsd` + `l1`, **scores bruts par
dimension**, **détail par strate** cible/obtenu/L1/effectif, couverture, volet, empreinte de
formule et de `moves.csv`). `rendu_scores.py` écrit `synthese_scores.html` avec le **même**
`_dimension_blocks()` que la page historique : les cellules par sous-catégorie ne peuvent pas
diverger.

### Deux lectures du composite, mesurées systématiquement (ticket 047)

Quand une seule option existait, le décideur **n'est pas interrogé** : le mode est celui de
l'unique itinéraire (`moves.csv`, méthode « Un seul itinéraire disponible »). Ces lignes
restent dans le composite — la journée les a jouées — mais chaque scoring produit aussi la
lecture **sans** elles, sans qu'aucune option soit passée :

| Champ de `scores.json` | Ce qu'il porte |
|---|---|
| `composite.emd_jsd` / `.l1` | toutes décisions, choix forcés compris |
| `composite.emd_jsd_hors_choix_unique` / `.l1_hors_choix_unique` | les mêmes, sans les décisions à itinéraire unique |
| `scores_bruts_hors_choix_unique` | scores par dimension de la seconde lecture — ce qui rend son rejeu de formule exact, comme pour la première |
| `choix_forces` | le compte : `n`, `part`, `n_scorees`, `n_hors_choix_unique`, et le compte de l'exécution entière (`n_execution`) avec son périmètre |

**Pourquoi ce n'est pas facultatif.** Mesuré le 2026-09-12 sur les 16 exécutions du 11/09
(même population, même jeu), retirer ces lignes déplace le composite EMD de **−3,75**
(`durmin`) à **+12,22** (`alea`) et **change le classement** : `lgbm` est premier à 4,50 toutes
décisions comprises, mais passe à 10,46 et derrière `klr` (9,95) hors itinéraire unique. Chaîne
coupée, le même écart plafonne à 0,32 — ces lignes viennent de la chaîne des véhicules, donc
des choix antérieurs du bras lui-même, et leur nombre en dépend (279 pour le tirage uniforme,
811 pour le plus rapide).

**Deux comptes, deux périmètres, tous deux nommés.** `synthese.json` compte sur toutes les
décisions archivées ; le composite ne porte que sur le premier jour simulé et la dernière
tentative. Les deux diffèrent de 14 à 19 lignes sur chaque exécution du 11/09 — soit 27,0 %
contre 20,6 % de part forcée sur `exp_lgbm`. `scores.json` publie donc les deux, chacun avec
son périmètre écrit : un compte posé à côté d'un chiffre qu'il ne recouvre pas se lit de
travers sans jamais le dire.

**Alarme.** Au-delà de 1,0 point EMD d'écart entre les deux lectures, le scoring journalise une
`[ALARME]` nommant l'exécution et les deux valeurs (seuil calé sur la mesure ci-dessus : il
sépare exactement le régime chaîne coupée du régime chaîne active). Le tableau de bord porte le
même avertissement au-dessus du registre, et la page d'exécution dans son en-tête.

**Un `scores.json` sans seconde lecture est périmé** et se recalcule à plein plutôt que de se
rejouer : sans cette règle, le rejeu hors-ligne — qui recompose depuis les scores bruts —
laisserait tout l'historique antérieur au ticket à « non mesuré », définitivement.

**La formule est versionnée et empreinte.** Ses 7 poids (`global`, `absent_penalty`, `age`,
`occupation`, `genre`, `motif`, `distance` — `length_penalty` reste hors composite) vivent dans
`experiences/formules/reference.yaml`, une seule marquée `reference: true`. Le `formule_sha256`
est **canonique** (indépendant de l'ordre des clés et de l'écriture des flottants). Toute
formule ayant servi de référence est conservée, pour que n'importe quel SHA estampillé se
résolve encore en ses poids.

**Le rejeu d'une formule est exact et hors-ligne.** Le composite est linéaire dans les
dimensions : changer les poids, c'est refaire une somme pondérée depuis les scores bruts déjà
stockés (`weighted_composite`), sans relire `moves.csv` ni appeler le moindre modèle.
`experiences score --toutes` (ou le bouton « Recalculer toutes les expériences » du dashboard)
réévalue tout l'historique instantanément et réécrit `scores.json` en estampillant le nouveau
SHA. Le drapeau « **⚠ formule périmée** » est **dérivé à la lecture** en comparant le SHA stocké
à celui de la référence courante — éditer la formule bascule toutes les lignes non re-scorées
sans les toucher.

**Le premier score est automatique (R23).** Le runner appelle `score.scorer_a_la_cloture()`
juste après avoir écrit la synthèse, dès que l'exécution passe `terminee` : une exécution qui
vient de finir porte son composite sans qu'aucune commande soit lancée. Le calcul est
hors-ligne (~0,5 s pour 2 700 décisions, aucun appel LLM ni réseau) et **fail-open par
construction** : `scorer_a_la_cloture` ne lève jamais. Si le moteur manque ou que le calcul
échoue, l'exécution **reste `terminee`**, `scores.json` est absent, la table affiche « — » et
une `[ALARME]` nommant l'expérience et l'exécution part dans le journal ; le bouton global
reste la porte de secours. Un rendu ne met jamais en échec une exécution qui a produit toutes
ses décisions. Le tableau de bord, lui, n'a rien à déclencher : il lit `scores.json`.

**Garde-fous.** Seule une exécution `terminee` est scorée — une exécution **arrêtée n'est pas
prise en compte**, même largement remplie, et affiche « — », jamais 0. Une dimension sans effectif mesuré est déclarée « non mesuré » (repli vers la perte
maximale côté moteur), jamais un 0 flatteur. Un `scores.json` calculé sur un `moves.csv` qui a
changé depuis est réputé périmé et recalculé. Sans le moteur de calibration, aucun score n'est
produit et le tableau affiche « — ». Les chemins (référentiel d'enquête, racine
`data/experiences`, dépôt de calibration) se résolvent sur `scripts.synthesis.sources.REPO_ROOT`,
juste des deux côtés : racine du dépôt sur l'hôte, `/app` dans le conteneur `controller` où
`llm-agents` est monté — c'est ce qui rend le scoring de clôture possible côté conteneur, là où
tourne le runner.

Le **volet** suit le décideur : décideur LLM → volet 1 ; décideur modèle tabulaire (booster
LightGBM ou logit multinomial, cf. §7 ter) → volet 3, avec le SHA de la version du modèle.

## 7 ter. Décideur modèle tabulaire — booster ou logit (`experiences/decideur_modele.py`)

Un décideur de plus, au même contrat que la passerelle : `type: modele` dans le spec (avec un
`artefact` optionnel — vide = version par défaut `scripts/progedo_logit/mode_choice_policy.json`).
Le modèle **décide** (il ne score pas en parallèle) : par décision, il lit les traits du persona
(`persona_features`), l'OD (coordonnées de `ctx.from_location`/`ctx.destination` → couche de
zones fines), prédit `P(mode)` sur 4 classes, **renormalise sur les modes offerts** (IIA), répartit
la masse d'une catégorie entre ses propositions, puis **tire** un index avec la graine de
l'expérience — exactement comme la lecture « attendu / tiré » du LLM. Rien de la prédiction n'est
réécrit : `persona_features`, `renormalize`, `load_policy` et `predict` viennent de
`scripts/synthesis/model_on_common_set.py`, l'encodage du script d'entraînement.

**Trois familles, un seul chemin de décision (tickets 042 et 043).** Le même décideur joue le
booster LightGBM, le logit multinomial de parité stricte **et** la régression logistique à noyau :
`load_policy` reconnaît les trois formats d'artefact et rend, dans les trois cas, un objet à
`predict`/`feature_name`. Tout ce qui suit — encodage, renormalisation, tirage, journal — est le
même code, condition pour que les exécutions soient comparables.

```bash
# ouvrir la variante logit d'une expérience modèle existante
python -m experiences dupliquer --de exp_lgbm_jtir_nosim --vers exp_mnl_jtir_nosim \
  --artefact scripts/progedo_logit/mnl_model.json

# et la variante à noyau (make klr)
python -m experiences dupliquer --de exp_lgbm_jtir_nosim --vers exp_klr_jtir_nosim \
  --artefact scripts/progedo_logit/klr_model.json
```

Le chemin peut être **relatif** : il se résout depuis la racine du dépôt, de sorte que le même
`experience.yaml` désigne le même modèle sur l'hôte et dans le conteneur.

⚠ **Les libellés de famille sont DÉRIVÉS du `format` de l'artefact**, jamais écrits en dur —
`modele:mnl@b365fb7d1ff2` dans `regime_applique.decideur`, `mnl_mode_choice_policy` dans
l'empreinte, `{"modele": "mnl", …}` dans la réponse brute. Avant le ticket 042 ils disaient
« lightgbm » quel que soit l'artefact chargé : le SHA restait juste (la version était donc
scellée) mais toute comparaison lue dans les traces désignait le mauvais modèle. Un format hors
de la table `FAMILLES` est **refusé au démarrage** plutôt que nommé « inconnu » — ce libellé entre
dans le nom canonique de l'expérience. C'est ce qui a permis au ticket 043 d'ajouter la famille
`klr` en une ligne de table, sans toucher au chemin de décision.

**Version scellée (R12).** L'empreinte `empreintes.decideur` porte le **SHA du fichier** de
l'artefact : relancer avec un autre modèle donne un résultat distinct, le même modèle le même SHA.
On relance donc une expérience en échangeant seulement le décideur (« s'inspirer d'une expérience
existante » dans le dashboard → décideur « modèle LightGBM »).

**Premier résultat comparé** (jeu gelé `population_1000_AAMAS_20260316`, 2 634 décisions,
couverture 99,6 %, 28 s d'exécution, aucun appel LLM) :

| Décideur | composite `emd_jsd` | mode tiré | L1 |
|---|---|---|---|
| `exp_lgbm_jtir_nosim` — booster | **4,9182** | 4,9735 | 51,37 |
| `exp_mnl_jtir_nosim` — logit | 6,1734 | 7,3171 | 56,98 |
| `exp_klr_jtir_nosim` — logistique à noyau | 5,0300 | 5,3907 | **48,59** |

L'écart de 1,26 point ne se transpose pas depuis le run épinglé, où il valait 0,71 : il se mesure
par substrat. Le logit y sous-estime la marche de 2,96 points (booster : 1,00) et surestime les
transports collectifs de 4,62 (booster : 3,79).

**La troisième famille se range entre les deux** (ticket 043, 49 s d'exécution, même couverture
99,6 %, aucun appel LLM) : composite 5,0300, à 0,11 point du booster et 1,14 devant le logit.
Elle porte en revanche la **meilleure L1 des trois** (48,59) — cohérent avec ce que le split test
scellé dit d'elle : non linéaire comme le booster sur l'exactitude, et meilleure que les deux sur
les parts modales agrégées.

**Non imputable (R13, RG-2).** Persona sans traits, aucune offre de mode prédictible, OD hors de
la couche de zones : le décideur rend une **non-décision terminale**
(`METHODE_MODELE_NON_IMPUTABLE`) — comptée, sans mode retenu (donc exclue des parts), **ni
réessayée** (contrairement à une erreur transitoire) **ni fabriquée** en repli uniforme. Un
décideur modèle **refuse de démarrer** (R14) si l'artefact ou la couche de zones (`make zones`)
manquent : l'exécution ne commence pas dégradée.

**Prérequis d'image.** Ne concerne que la famille booster : le logit s'évalue en pur numpy
(`scripts/progedo_logit/mode_choice_logit.py`) et n'a aucune de ces dépendances. Le décideur
charge le booster avec LightGBM : `lightgbm==4.7.0` est dans
`services/llm-agents/requirements.txt` et `libgomp1` (runtime OpenMP du wheel) dans le `Dockerfile` — donc
dans l'image du `controller`, et par ricochet dans celle d'`osmnx1`, qui partage ce Dockerfile.
Après modification de l'un ou l'autre, `docker compose build controller osmnx1`. La version est
épinglée sur le `booster.version` de l'artefact : un booster rechargé par une autre version de la
bibliothèque n'est pas garanti identique, et `load_policy` vérifie le contrat de features, pas la
version. Ordre de grandeur mesuré : l'expérience `Light_GBM` (1 000 personnes, 2 645 déplacements
exploitables) s'exécute en **26 s**.

**Limite connue.** `departure_hour` est dérivé en heure UTC du timestamp de départ ; si l'horloge
simulée écrit une heure locale, un décalage d'au plus l'offset local est possible sur cette seule
variable (parmi 21). Sans effet sur le score (qui ne lit pas `departure_hour`).

## 7 quater. Statut d'expérience (`experiences/statut.py`)

Une expérience porte un statut, marqué dans `data/experiences/<exp>/statut.json` :
`actif` (défaut, aucun fichier écrit), `archivee`, `invalide`.

**Le marqueur ne supprime et ne déplace rien.** Exécutions, traces, `moves.csv`, `scores.json`
et empreintes restent où ils sont, lisibles et vérifiables. Ce qui change :

- `registre.lister()` masque `archivee` et `invalide` par défaut ; `inclure_masquees=True`
  (`make registre TOUT=1`, `--inclure-masquees`) les réaffiche. Chaque ligne porte `statut` et
  `statut_motif`, pour afficher la raison plutôt que d'escamoter la ligne.
- `rendu_scores` coiffe la page d'un bandeau nommant le statut, la date et le motif. Le chiffre
  reste affiché — il vient de l'archive scellée, il est exact ; le bandeau dit de ne pas le
  citer sans son motif.
- le tableau de bord expose `statut` sur chaque ligne et un helper `masquee(ligne)`. Sa propre
  `lister()` ne filtre rien : les vues « activités en cours » et « à reprendre » doivent voir
  toutes les lignes, c'est la vue qui décide.

Le motif est **obligatoire** hors `actif` : un marqueur sans raison est illisible six mois plus
tard. Chaque transition est empilée dans `historique`, donc réactiver une expérience ne fait pas
disparaître la trace de son archivage. Un `statut.json` illisible ou inconnu vaut `actif` : le
pire résultat acceptable pour un registre est « on affiche tout », jamais « on n'affiche rien ».

Distinction d'usage retenue le 2026-09-10 :

| Statut | Quand |
|---|---|
| `invalide` | une **mesure publiée** (`scores.json`) est fautive pour une raison nommée — typiquement un gabarit invalidé (cf. `_invalidation` dans `prompts.yaml`) |
| `archivee` | rien de mesuré à défendre : définition jamais exécutée, exécution avortée ou partielle sans score, doublon de nommage |

Commandes : `make experience-statuts` (tout, masquées comprises),
`make experience-statuer EXP=<nom> STATUT=<...> MOTIF="..." [REF=specs/x.md]`.

Spec : `specs/hygiene-prompts-et-plateforme-experiences.md` §3.2 et §5.

## 7 quinquies. Un réglage d'expérience appartient au run (ticket 077, lot K)

**La règle.** Ce qu'un bras d'expérience fait varier se pose par l'**environnement** et s'inscrit
dans `identite_run.json`. Ce qui appartient au projet reste dans `config/config.yaml`.

| | `config/config.yaml` | Environnement (`AGENT__…`) |
|---|---|---|
| Portée | tout run du dépôt, mesuré ou non | ce run-là |
| Durée de vie | jusqu'à ce que quelqu'un le remarque | celle du processus |
| Trace | aucune | `identite_run.json`, et une reprise qui diffère est refusée |

⚠ **Pourquoi la règle existe.** Le 2026-09-18, quatre réglages d'expérience ont été posés dans
`config.yaml` — chaînage des véhicules, verrou de retour, seuil de troncature du tirage, plancher
de réflexion — plus un seuil de mémoire. Deux conséquences :

1. ils sont devenus le **défaut du dépôt**. Trente tests énonçant les règles que ces réglages
   contredisent sont restés rouges pendant que personne ne pouvait dire s'ils signalaient une
   régression ou une configuration ;
2. ils ne figuraient dans **aucune identité de run**. Trois bras aux réglages opposés portaient
   la même identité, et rien ne permettait, après coup, de dire sous quels réglages un run avait
   tourné. C'est précisément ce que le ticket 091 existait pour empêcher.

**Ce que l'identité porte désormais**, en plus des onze champs du 091 : chaînage des véhicules,
verrou de retour au domicile, seuil de troncature du tirage, seuil de choc en mémoire, fenêtre et
plafond du bloc « ce qui a changé récemment », plancher d'entrées avant réflexion, météo par agent.

Un run antérieur au 2026-09-19 n'est donc plus reprenable, et le refus le dit dans ces mots :
**« absent du run repris »** — la cause est l'âge du run, pas un réglage différent. C'est le bon
comportement : on ne sait pas sous quelles valeurs ces runs ont tourné.

⚠ **Conséquence pratique.** Un `make run` lancé à la main tourne aux valeurs par défaut du dépôt.
Pour reproduire un bras d'expérience, passer par `scripts/experiment/run_sequential_cohort.py`,
qui pose les réglages et les fait enregistrer. C'est l'inverse du piège précédent : un run manuel
ne porte plus en silence les réglages d'une expérience.

### Le nom de la variable est le nom NU du champ

`VEHICLE_CHAIN_ENABLED`, `MEMOIRE__FENETRE_CHANGEMENTS_JOURS`. **Pas** `AGENT__…`.

Les sous-configurations de `settings.py` sont des `BaseSettings` instanciées sans préfixe : le
préfixe `AGENT__` n'est lu par personne. `run_sequential_cohort.py` l'a posé pendant des semaines
sans le moindre effet, et le premier bras de campagne du 2026-09-19 a tourné aux valeurs par
défaut du dépôt.

Et il ne suffit pas de poser la variable sur l'hôte : **Docker Compose ne transmet au conteneur
que ce qu'il déclare.** Chaque réglage figure donc en passe-plat dans `infra/docker-compose.yml`,
avec un défaut égal à celui de `settings.py` — deux valeurs par défaut écrites à deux endroits
divergent, et `test_077_lotL_passage_reglages.py` les tient ensemble.

### Les réglages du ticket 095

| Variable | Défaut | Ce qu'elle décide |
|---|---|---|
| `MEMOIRE__MODE_FENETRE_CHANGEMENTS` | `derivee` | `derivee` : la durée d'un souvenir de choc se calcule depuis sa gravité. `fixe` : coupure franche à `MEMOIRE__FENETRE_CHANGEMENTS_JOURS`, comportement d'avant le ticket — c'est le bras de contrôle méthodologique |
| `MEMOIRE__SEUIL_SERVICE_CHANGEMENT` | `0.35` | Le poids sous lequel le souvenir quitte le bloc. Domaine ouvert `]0, 1[` |
| `MEMOIRE__PLANCHER_CHANGEMENT_JOURS` | `2.0` | Borne de sûreté basse. Ne mord pas aux valeurs du dépôt |
| `MEMOIRE__PLAFOND_CHANGEMENT_JOURS` | `30.0` | Borne haute. Mord par le renforcement au rappel, jamais par la gravité |
| `EXPERIMENT_SURVEY_MODES` | *(vide)* | Modes interrogés par l'enquête du soir. Vide = les quatre d'Adam & Gaudou ; à étendre à `train` ou `deux_roues` quand le choc du run les vise |
| `RUN_PARENT` | *(vide)* | Nom ou chemin du run **parent** dont ce bras hérite le socle commun (run enfant, lot D) |
| `CHAMPS_LIBRES` | *(vide)* | Les champs d'identité que cet enfant déclare faire varier par rapport à son parent. Tout autre écart fait refuser le démarrage |

⚠ **`MEMOIRE__MODE_FENETRE_CHANGEMENTS` change le comportement par défaut de tout run.** Un run
archivé avant le 2026-09-21 ne se compare à un run neuf qu'en déclarant `fixe`.

### Un modèle par fonction (ticket 095, lot C)

`LLM__INSTANCES_ADMISES` accepte, en plus d'une liste plate, une **table `catégorie →
instances`** :

```
LLM__INSTANCES_ADMISES='{"defaut": ["google_gemini31_key1", "google_gemini31_key2"],
                         "stm_reflection": ["google_gemini35_key1", "google_gemini35_key2"],
                         "enquete_affinite": ["google_gemini35_key1", "google_gemini35_key2"]}'
```

La clé `defaut` est le repli de toute catégorie non nommée. **Minimum deux instances par
catégorie** : en deçà, une alarme se lève, parce qu'un HTTP 503 devient alors un échec sec — les
quatorze `high demand` de la campagne du 2026-09-19 sont passés précisément parce qu'il restait
une seconde clé. `force_provider` n'est jamais posé par ce chemin : `task_worker` ne retente que
si `force_provider is None`.

⚠ **Ce n'est pas un réglage d'infrastructure.** Changer le modèle des réflexions STM change le
contenu de la mémoire, donc les décisions. Le binding entre dans `identite_run.json`
(`routage_instances`), se gèle avant la campagne et reste identique dans tous les bras — sinon
l'écart mesuré n'est plus attribuable au choc.

### Runs enfants (ticket 095, lot D)

Les quatorze premiers jours des trois bras de la campagne du ticket 077 étaient identiques — 44
décisions, 0 écart — et payés trois fois. Un run **parent** joue le socle commun jusqu'à la veille
du choc et se fige ; chaque bras démarre depuis son dernier point de reprise :

```bash
RUN_PARENT=2026-09-21_socle CHAMPS_LIBRES=choc,mode_fenetre_changements make run OFFLINE=1
```

L'enfant hérite de la **mémoire** de son parent. Si la population, le modèle ou les graines
diffèrent, cette mémoire décrit une autre expérience que celle qu'il va jouer — et rien, dans les
sorties, ne le dirait. D'où le refus par défaut : tout écart d'identité non nommé dans
`CHAMPS_LIBRES` fait échouer le démarrage en citant le champ. Un champ libre inconnu est refusé
lui aussi, sans quoi une faute de frappe laisserait passer l'écart qu'on croyait avoir déclaré.

Au dégel du rejeu, la **recette de reproduction** compare décision par décision l'enfant et son
parent sur les jours communs, et lève une `[ALARME] [filiation]` chiffrée en cas d'écart. Sans
elle, l'économie serait une promesse : deux bras croiraient partager une baseline qu'ils ne
partagent plus.

⚠ **Une clé présente dans `config.yaml` l'emporte sur l'environnement** : le YAML est passé à
l'initialisation, qui prime. C'est pour cela que ces clés en ont été retirées.

La règle ne vaut pas que pour les réglages d'agent. Le 2026-09-21, les quatre variables
`EXPERIMENT_SURVEY_ENABLED`, `EXPERIMENT_SURVEY_DAYS`, `EXPERIMENT_TARGET_PERSONAS` et
`EXPERIMENT_HIBERNATE_ON_QUOTA` ont été ajoutées au passe-plat : elles manquaient depuis
l'origine, et **l'enquête du soir comme la mise en veille sur quota n'ont jamais tourné** —
sans alarme, sans ligne de journal, dans les trois bras de la campagne du ticket 077. Un
dispositif qui ne s'annonce pas quand il démarre ne se distingue pas d'un dispositif absent :
c'est la raison d'être de la journalisation du succès.

### `make run` ne bloque pas, et l'orchestrateur ne doit pas le croire

La recette lance `launch_headless.py` en arrière-plan (`&`) : `make run OFFLINE=1` rend la main
en une vingtaine de secondes, alors que le run dure des heures. C'est cohérent avec l'usage
humain — on lance, puis on regarde les journaux — mais un orchestrateur qui attend `make` croit
le bras terminé.

Le 2026-09-19 à 16:44, il a donc enchaîné sur le bras suivant, dont la première étape
(`make stop-run`) a **tué le bras précédent trente-quatre secondes après son démarrage**.

Le signal franc est le lanceur lui-même : GAMA Server tue l'expérience dès que son client
WebSocket se déconnecte, donc `launch_headless.py` vit exactement le temps du run. L'orchestrateur
attend sa disparition, journalise la journée simulée atteinte toutes les cinq minutes, et refuse
de démarrer un bras si un lanceur tourne déjà — `make run` se contenterait d'écrire « Lancement
ignoré » et de rendre 0.

### Un bras se vérifie en vingt secondes, pas en trois heures

`identite_run.json` est écrit au démarrage du contrôleur. L'orchestrateur le relit dès qu'il
apparaît, le compare aux réglages demandés, et **arrête le bras** au premier écart, en nommant
attendu et obtenu. La campagne s'interrompt : un bras qui échoue laisse la pile dans un état dont
le suivant hériterait.

## 8. Ce que ce design ne fait pas

- Aucune valeur d'enquête dans le code : la synthèse lit `scripts/data/population/cerema_values.yaml`
  et cite chemin + sha256 (E17, test par grep).
- Pas de migration des runs `experiments/archive/*`.
- Pas de nouveau protocole GAMA : les commandes passent par GAMA Server.
- Pas de suppression des caches techniques : ils restent internes.

## 9. État de l'implémentation (2026-09-05)

Ce qui existe, testé (`services/llm-agents/tests/test_035_*.py`, un test par règle) :

| Spec | Livré | Tests | Reste |
|---|---|---|---|
| 02 — décision unique | `vehicle_chain.py` et `candidats.py` extraits du contrôleur ; `experiences/decision.py` (éligibilité motivée, plafond tracé, ordre déterministe D7, trace D6, `decider`, `avancer_chaine`) ; le contrôleur et `LlmAgent` l'utilisent | D1, D2, D4–D7, D10, D11, plafond | **D8** (égalité GAMA ↔ runner sur 100 personnes) exige un run réel ; D3 = les 73 tests existants, verts |
| 01 — jeu enregistré | `experiences/jeu.py` : préparation tous modes sans plafond, reprise, clôture, empreinte, dépendances, péremption, consultation ; CLI `preparer-jeu`, `consulter-jeu`, `verifier-jeu` ; `make jeu` | J1–J16 | préparation sur la population réelle (services OTP/OSMnx requis) non exécutée ici |
| 03 — sans simulateur | `experiences/runner.py` : ordre horaire par personne, parallélisme, non couverts, avancement, journal, `moves.csv` compatible `make report` | S1–S4, S6–S10 | S5 : la taille réelle des lots de la passerelle n'est pas rendue au client (question 15) |
| 05 — ressources | `experiences/ressources.py` + `decideurs.DecideurPasserelle` : instances du modèle épinglées, substitution refusée, épuisement sur refus réel du fournisseur et arrêt propre, attente bornée, pause/arrêt par fichier ou signal, reprise depuis l'archive, dernière ligne tronquée réparée | Q1–Q3, Q4, Q5–Q9, Q11, Q12 | Q1/Q4 contre la passerelle réelle (non exercés hors réseau) |
| 06 — expérience, registre | `experiences/experience.py` (E1–E9, estimation citant ses sources), `archive.py` (E10, E11, E19), `registre.py` (E12–E17, E20), CLI, onglet dashboard « 🧪 Expériences » | E1–E14, E16–E20, E22 | E15 = onglet dashboard (non testé automatiquement) ; E21 (grep des clés) à ajouter |
| 04 — simulation sur jeu | `settings.data.jeu_enregistre` + tolérances ; `/init` charge et refuse (G1, G5) ; contrôleur : servi du jeu (G3), recalcul par groupe hors tolérance (G5), sources (G6), recalcul sans effet + ALARME (G7), `jeu_stats.json` + rubrique `make report` (G14), colonne « Source des propositions » de `moves.csv` ; `make run JEU=<nom>` (G2) | G1, G3, G5–G7, G13, G14 | **G8/G9** événements : refusés au lancement (question 14) ; **G10** pause à chaud GAMA : non câblée (le `DecideurRejeu` existe, la reprise `CONT=1` ne l'appelle pas encore) ; G12 exige un run réel |

Hypothèses **[H]** en vigueur : voir `specs/ticket_035/questions.md`. Rien de ce qui précède n'a été
validé sur un run GAMA réel ni contre la passerelle réelle : les tests couvrent la logique, pas
l'intégration de bout en bout.

## 10. Relecture du 2026-09-06

Huit questions tranchées par l'auteur (4, 5, 7, 10, 12, 13, 14, 15, 16, 17, 18 — voir
`specs/ticket_035/questions.md`, « Décisions prises »). Conséquences dans le code : règle
« le mardi joue l'offre du mardi » (recalcul TC pour tout autre jour que celui du jeu, sauf
équivalence mesurée par `verifier-jours` et déclarée dans `EQUIVALENCES.yaml` à côté du MANIFEST,
qui reste immuable) ; refus sans simulateur d'une date non équivalente ; `moves.csv` enrichi
(écartées par motif, identifiant de lot) ; format `Evenement` figé pour GAMA ; recréation du
contrôleur dès que `config.yaml` change. Restent ouvertes, réécrites avec des exemples : 1, 2, 3,
6, 8, 9 (mesure à faire, services requis), 11.

**Second tour (même jour).** Décisions 1, 2, 6, 11, 15, 16 enregistrées ; 3 et 8 répondues par
la mesure (dernier run) ; 18 précisée : l'offre d'un autre jour se **lit dans le GTFS**
(`experiences/offre_jour.py`) — identique ⇔ grille horaire identique ; sinon un déplacement n'est
servi que si aucun passage différent ne tombe dans sa fenêtre (départ → +4 h) — déclarée par
déplacement dans `EQUIVALENCES.yaml` ; le contrôleur sert ce qui est valide, recalcule les TC du
reste. 3 : les déplacements sans aucune proposition sont « inexploitables », exclus des attendus
et remontés en WARNING. 8 : tolérances maintenues (le retard de départ est un sujet GAMA à part).
**Plus aucune question ouverte** ; reste à faire la vérification GTFS sur un jeu réel v5.

## 11. Ordonnancement parallèle par clé API (`experiences/reservations.py`, `file.py`, `ordonnanceur.py`)

Spec : `specs/parallelisation_experiences.md` (R1–R12). Problème résolu : lancer une deuxième
expérience tuait la première (toutes s'exécutent dans le conteneur `controller`, et
`experience-lancer-arret` arrêtait ce conteneur partagé), et deux expériences sur le même
modèle se seraient de toute façon disputé le même quota — le débit LLM est plafonné **par clé
API**, pas par instance.

**Règle.** Deux expériences tournent en parallèle **si et seulement si leurs jeux de clés sont
disjoints** (R1). Le jeu de clés se dérive du **modèle** épinglé (`experiences/cles.py`) :
modèle **et portée** → instances qui le servent (`instances_pour_modele`) → **identité de clé** de chaque
instance = `adapter` (à défaut le nom d'instance), un override par instance dans
l'environnement étant respecté. L'identité par adapter est **conservatrice** : deux modèles
d'un même fournisseur (ex. plusieurs `gemini*`, adapter `google`) sont réputés partager une clé
— on sérialise au pire, on ne parallélise jamais à tort (fail-safe, R12).

**Le nom EST l'identité — et il se CALCULE.** Une expérience = un nom = un dossier
`data/experiences/<nom>/` = une clé de dédoublonnage dans la file FIFO = la cible de
`pause`/`arreter`. `experience.yaml` ne porte qu'**un** décideur : changer de modèle et relancer
sous le même nom ne crée pas une seconde expérience, ça réécrit la première. Le 2026-09-07, trois
exécutions de `Prompt_Minimaliste` ont mesuré gemini, gpt-oss et mistral sous une seule identité —
chaque `execution.yaml` avait bien figé son modèle, mais le fichier d'expérience ne gardait que le
dernier, et deux lancements du même nom se disputaient la même clé au lieu de tourner en parallèle.

Le nom n'est donc plus saisi : il est **dérivé des paramètres** (`experiences/nommage.py`, spec
`specs/nommage-canonique-experiences.md`), et identité et paramètres ne peuvent plus diverger.
Grammaire : `exp_<décideur>[_<prompt>][_<calendrier>][_<écarts>][_t<T>]_<mode>` — le décideur
toujours (le modèle pour une passerelle, abrégé sans table à tenir à jour : `gemini-31-fl`,
`mistral-s`, `qwen36-27b`), le prompt seulement s'il décide quelque chose, le calendrier et les
écarts aux valeurs de référence (`DEFAUTS_NOMMAGE`) seulement quand ils s'écartent, la
température et le mode toujours. Exemple : `exp_gemini-31-fl_minper_jtir_t0_nosim`,
`exp_lgbm_jtir_nosim`, `exp_durmin_nosim`.

**Collision.** La *signature* d'une expérience est le sha256 de sa définition privée de son
identité (`nom`, `derive_de`, `renomme_de`, `executions_connues`). Même nom calculé et même
signature = **la même expérience** : elle est réutilisée, une exécution s'ajoute à ses archives,
rien n'est réécrit. Même nom mais signature différente (deux réglages que la grammaire abrège
pareil) = un indice, `_2`, `_3`, comme une copie de fichier.

Ce qui existait a été renommé une fois, explicitement, par `make experiences-renommer
APPLIQUER=1 FUSIONNER=1` (`scripts/migrations/renommer_experiences.py`) : la définition, la copie
figée de chaque exécution, les restitutions et leurs rendus, les masques, la file et le brouillon
du formulaire suivent ; l'ancien nom reste écrit dans `renomme_de` et dans
`data/experiences/.renommages.json`. `experiences definir` refuse depuis lors un fichier dont le
`nom` n'est pas celui de ses paramètres (`--accepter-nom` passe outre), et `dupliquer` sans
`--vers` calcule le nom de la copie. Les identifiants du plan AAMAS
(`docs/paper/methode/experience_plan/experiments.yaml`) ne bougent pas — ils portent la phase et l'ordre
des sections du papier — et pointent le dossier par une clé `nom_runtime`.

**Registre de réservation** (`reservations.py`). Source de vérité partagée `data/experiences/
.reservations.json` (bind-mount visible hôte ↔ conteneur), protégée par un verrou global
(`mkdir` exclusif, vol après `VERROU_TTL_S`). `admettre()` fait, sous un seul verrou (R6) :
clés libres → réserve et renvoie `lance` ; sinon → met en **file** FIFO (`.file.json`,
`file.py`) et renvoie `file`. La clé se libère au **statut terminal** de l'exécution (R7) : le
cas normal libère dans le `finally` de `cmd_lancer` ; un processus **tué durement** laisse une
réservation orpheline, rattrapée par `reconcilier()` — qui teste la vie du pid (valable
uniquement **dans** le namespace du conteneur) et réconcilie l'exécution fantôme en nouvel état
terminal **`interrompue`**.

**Ordonnanceur** (`ordonnanceur.py`, côté **hôte**, `make experience-ordonnancer`). Chaque tour :
(1) `docker compose exec controller … reconcilier` ; (2) `promouvoir_pretes()` sort de la file,
en FIFO et sans jamais préempter une exécution active (R2c), celles dont **toutes** les clés
sont libres ; (3) relance chacune via `docker compose exec … lancer` — qui réserve à son
démarrage et rejoue les contrôles de lancement (péremption → l'expérience quitte la file, R2d).
Le tableau de bord affiche les clés tenues / la file et supervise ce job.

**Arrêt des services partagés** (R5). `experience-lancer-arret` n'arrête `controller`/`api`/…
que si `experiences actives --est-vide` : tant qu'une autre expérience tient une clé, les
services restent debout.

Tests : `tests/test_035_11_reservations.py`, `tests/test_035_12_ordonnanceur.py` (un par règle).
