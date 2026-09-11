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
                          (passerelle épinglée · durée minimale · rejeu · aléatoire)
                                    │
                          experiences/archive.py  ──▶ data/experiences/<exp>/executions/<horodatage>/
                          (spec 05/06 : decisions.jsonl atomique, etat.json, moves.csv, synthese)
                                    │
                          experiences/registre.py ──▶ CLI `registre`, `comparer` · onglet dashboard
```

Tout le code neuf vit dans le paquet **`llm-agents/experiences/`** (importable depuis le conteneur
`controller`, où tournent déjà `models`, `settings`, `trip_helper`, `text_helper`). Les tests sont
dans `llm-agents/tests/test_035_*.py`, un fichier par spec, un test par règle (`test_J3_…`).

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
                                                     #          recalculee:horaire:<ecart_min>/<tol> | en_vol | locale
Ecart(code: str, mode: str, motif: str)              # motif ∈ non_possede | pas_de_conducteur |
                                                     #         vehicule_ailleurs | retour_force | plafond
ContexteDecision(timestamp, purpose, departure_time, activity_id, from_location, destination,
                 anticipation: dict|None, memoire_presentee: list[str], evenement: dict|None,
                 graine_ordre: int, max_candidats: int)
Decision(retenue: Proposition|None, index_presente: int|None, methode: str,
         distribution: dict, reponse_brute: str|None, fournisseur: str,
         trace: TraceDecision)
TraceDecision(presentees: list[dict], ecartees: list[Ecart], retenue: dict|None,
              distribution: dict, reponse_brute: str|None, sources: dict[code→source],
              methode: str, graine_ordre: int, souvenirs: list[str], periode_evenement: str|None)
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

- **Déplacement** = paire d'activités consécutives **localisées** de l'agenda (J2) ; heure = règle du
  contrôleur (`scheduled_start_time` sinon `end_time`, `to_timestamp_based_on_day`, +24 h si déjà
  passé).
- **Préparation** : `trip_helper.get_itineraries(include_car=True, include_bike=True, arrive_by=False)`
  — tous modes, **aucun** plafond, plus l'option car scolaire (`build_school_bus_option`, locale,
  déterministe) pour que le jeu soit un vrai sur-ensemble. Aucun attribut du persona n'est écrit (J16).
- **Reprise** (J11) : les lignes existantes sont indexées par `(person_id, activity_id)` et sautées.
  Écriture ligne par ligne, `flush + fsync`.
- **Clôture** (J14) : `clos: true`, `propositions_sha256` calculé ; ensuite `ouvrir()` refuse toute
  écriture ; `charger()` refuse un jeu altéré (J12), sans bloc `dependances` (J9), ou malformé (J13 :
  JSON strict, position de l'erreur ; jamais de pickle).
- **Péremption** (J10) : `dependances_courantes()` recalcule le même bloc ; `perime(jeu)` rend la liste
  des dépendances qui diffèrent. Le lancement d'une expérience l'affiche et exige
  `--accepter-perime` pour continuer **[H]**.
- **Journalisation** (J15) : début/fin/durée/compteurs, ligne de succès, ALARME à front montant si la
  part de déplacements sans proposition dépasse `--seuil-sans-proposition`.

## 4. Spec 06 — l'expérience (`experiences/experience.py`) et l'archive (`experiences/archive.py`)

`data/experiences/<nom>/experience.yaml` — **tous** les champs E1 obligatoires (Pydantic, `extra=forbid`) :

```yaml
nom, population: {chemin}, jeu: {nom}, gabarit: {categorie: itinary_multi_agent}   # empreinte = texte effectif
decideur: {type: passerelle|duree_minimale|rejeu|aleatoire, modele, parametres: {temperature, top_p, max_tokens}, rejeu_de: <exec>|null}
mode: sans_simulateur | simulateur
calendrier: {politique: commune|propre|aleatoire, date: "2026-03-16", graine: 42}
horizon_jours: 1
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
`itinary_multi_agent.md.j2` **+** de `travel_plan_describe_v2.j2`), décideur (modèle + paramètres),
dépôt (commit + arbre propre).

`refuser_si_impossible(exp)` (E6) : jeu ≠ population, décideur sans instance disponible (lecture de
`providers.yaml` puis `/health`), sans simulateur avec mémoire/événement/horizon > 1 (S3), date hors
période couverte (E9 : `calendar*.txt` des feeds, bornes du CSV météo), jeu périmé non accepté.

**« Disponible » lit trois signaux, pas un** (`MoniteurRessources.disponible`). Une instance est
servable si la passerelle ne l'a pas mise **hors service** (`/health` : `disabled`, désactivée après
des erreurs consécutives, ou `cooldown`), si son quota du jour n'est pas `quota_exhausted`, et si sa
marge `rpd_limit − daily_requests` couvre le besoin. Deux pannes ont fixé cette lecture :

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

Une passerelle ancienne qui ne publie ni `disabled` ni `cooldown` est lue sur `available`, seul
signal disponible ; une passerelle qui ne publie rien reste permissive : l'absence de mesure ne
doit pas bloquer, mais elle ne doit pas non plus passer pour un feu vert.

`estimer(exp)` (E5) : sollicitations = déplacements couverts du jeu ; jetons/sollicitation = médiane
mesurée sur les `decisions.jsonl` archivés du même gabarit (source citée), sinon
`docs/paper/methode/experience_plan/experiments.yaml: measured_ratios` (cité) ; quotas = `providers.yaml`
`rpd_limit` + `/health.daily_requests`. Aucun littéral dans le code.

**Exécution** — `data/experiences/<nom>/executions/<AAAA-MM-JJ_HH_MM_SS>/` :

```
execution.yaml    configuration figée + empreintes + regime_applique + sources_alea + interruptions[]
etat.json         {etat: definie|en_cours|en_pause|epuisee|arretee|terminee, raison, reprise_possible_a, maj}
decisions.jsonl   une TraceDecision complète par décision (texte présenté inclus), append atomique
moves.csv         mêmes colonnes que la simulation (+ « Source des propositions ») → `make report`, synthèse
compteurs.json    décidés / non couverts / sans solution / choix unique / replis / erreurs / sollicitations
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

**Ressources** (Q1–Q11) : `/health` de la passerelle lu avant chaque vague (Q11 : marge <
sollicitations à soumettre ⇒ instance écartée ; plus aucune ⇒ `epuisee` avant le premier 429) ;
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

Le **volet** suit le décideur : décideur LLM → volet 1 ; décideur modèle (LightGBM) → volet 3,
avec le SHA de la version du modèle.

## 7 ter. Décideur modèle LightGBM (`experiences/decideur_modele.py`)

Un décideur de plus, au même contrat que la passerelle : `type: modele` dans le spec (avec un
`artefact` optionnel — vide = version par défaut `scripts/progedo_logit/mode_choice_policy.json`).
Le modèle **décide** (il ne score pas en parallèle) : par décision, il lit les traits du persona
(`persona_features`), l'OD (coordonnées de `ctx.from_location`/`ctx.destination` → couche de
zones fines), prédit `P(mode)` sur 4 classes, **renormalise sur les modes offerts** (IIA), répartit
la masse d'une catégorie entre ses propositions, puis **tire** un index avec la graine de
l'expérience — exactement comme la lecture « attendu / tiré » du LLM. Rien de la prédiction n'est
réécrit : `persona_features`, `renormalize`, `load_policy` et `predict` viennent de
`scripts/synthesis/model_on_common_set.py`, l'encodage du script d'entraînement.

**Version scellée (R12).** L'empreinte `empreintes.decideur` porte le **SHA du fichier** de
l'artefact : relancer avec un autre modèle donne un résultat distinct, le même modèle le même SHA.
On relance donc une expérience en échangeant seulement le décideur (« s'inspirer d'une expérience
existante » dans le dashboard → décideur « modèle LightGBM »).

**Non imputable (R13, RG-2).** Persona sans traits, aucune offre de mode prédictible, OD hors de
la couche de zones : le décideur rend une **non-décision terminale**
(`METHODE_MODELE_NON_IMPUTABLE`) — comptée, sans mode retenu (donc exclue des parts), **ni
réessayée** (contrairement à une erreur transitoire) **ni fabriquée** en repli uniforme. Un
décideur modèle **refuse de démarrer** (R14) si l'artefact ou la couche de zones (`make zones`)
manquent : l'exécution ne commence pas dégradée.

**Prérequis d'image.** Le décideur charge le booster avec LightGBM : `lightgbm==4.7.0` est dans
`llm-agents/requirements.txt` et `libgomp1` (runtime OpenMP du wheel) dans le `Dockerfile` — donc
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

## 8. Ce que ce design ne fait pas

- Aucune valeur d'enquête dans le code : la synthèse lit `scripts/data/population/cerema_values.yaml`
  et cite chemin + sha256 (E17, test par grep).
- Pas de migration des runs `experiments/archive/*`.
- Pas de nouveau protocole GAMA : les commandes passent par GAMA Server.
- Pas de suppression des caches techniques : ils restent internes.

## 9. État de l'implémentation (2026-09-05)

Ce qui existe, testé (`llm-agents/tests/test_035_*.py`, un test par règle) :

| Spec | Livré | Tests | Reste |
|---|---|---|---|
| 02 — décision unique | `vehicle_chain.py` et `candidats.py` extraits du contrôleur ; `experiences/decision.py` (éligibilité motivée, plafond tracé, ordre déterministe D7, trace D6, `decider`, `avancer_chaine`) ; le contrôleur et `LlmAgent` l'utilisent | D1, D2, D4–D7, D10, D11, plafond | **D8** (égalité GAMA ↔ runner sur 100 personnes) exige un run réel ; D3 = les 73 tests existants, verts |
| 01 — jeu enregistré | `experiences/jeu.py` : préparation tous modes sans plafond, reprise, clôture, empreinte, dépendances, péremption, consultation ; CLI `preparer-jeu`, `consulter-jeu`, `verifier-jeu` ; `make jeu` | J1–J16 | préparation sur la population réelle (services OTP/OSMnx requis) non exécutée ici |
| 03 — sans simulateur | `experiences/runner.py` : ordre horaire par personne, parallélisme, non couverts, avancement, journal, `moves.csv` compatible `make report` | S1–S4, S6–S10 | S5 : la taille réelle des lots de la passerelle n'est pas rendue au client (question 15) |
| 05 — ressources | `experiences/ressources.py` + `decideurs.DecideurPasserelle` : instances du modèle épinglées, substitution refusée, épuisement anticipé et arrêt propre, attente bornée, pause/arrêt par fichier ou signal, reprise depuis l'archive, dernière ligne tronquée réparée | Q1–Q3, Q4, Q5–Q9, Q11, Q12 | Q1/Q4 contre la passerelle réelle (non exercés hors réseau) |
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
