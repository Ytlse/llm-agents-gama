# Ticket 111 — Plan d'implémentation

> Validé par l'auteur le 2026-09-25. Implémentation différée : rien n'est codé à la date
> d'écriture. Ticket : [`docs/tickets/ticket_111_…`](../../docs/tickets/ticket_111_la_lecture_precede_la_decision_et_se_transmet_au_foyer.md).
> Tests : [`tests.md`](tests.md). Décisions et hypothèses : [`questions.md`](questions.md).
>
> Écrit sur le code de `main` à `50115a2`. Les numéros de ligne cités datent de ce commit : les
> relire avant de modifier.

## Déroulé pour un foyer exposé

```
Veille du jour de lecture — dès qu'une décision du lendemain se construit pour un membre du foyer
   → un appel « evenement_relais » par foyer : le lecteur lit l'article et la fiche de chacun,
     et dit ce qu'il transmet à qui, ou rien
   → le résultat est gardé tel quel (relais_foyer.jsonl) ; il sert aux décisions ET à l'écriture en mémoire

Jour de lecture, 00:00 (premier pas de simulation après minuit)
   lecteur       : jugement de l'article, mémoire courte + longue (écriture longue ATTENDUE)
   informés      : chacun juge le message reçu, mémoire courte + longue, origine « entendu »
   non informés  : rien — témoins internes, par le choix du lecteur

Pendant 5 jours de déplacement (lundi–vendredi), à chaque décision et chaque enquête
   lecteur       « [ PRESSE ] This morning I read in the paper: « … » »
   adulte        « [ FOYER ] Arthur told me this morning: « … » »
   mineur        « [ FOYER ] My parents decided this morning: « … » »
   → dans « Ce qui a changé récemment », quelle que soit la gravité jugée

6e jour de déplacement → règles ordinaires : gravité, rappel, concepts
```

**Pourquoi au rendu du prompt, et pas en touchant au pré-calcul.** Une décision du jour de
lecture se calcule la veille. Deux autres voies ont été examinées et écartées (voir
`questions.md`, D2) : invalider puis recalculer, parce que `_compute_move_for_activity` écrit dès
le calcul une ligne de `moves.csv`, gare les véhicules (`_park_vehicles`), renforce les
souvenirs servis et trace le rejeu ; retenir le pré-calcul, parce qu'il faut garder cinq sites de
dispatch et trois branches du scan, reconstruire la profondeur de file, et que le lecteur
déciderait avec une mémoire plus fraîche que le bras témoin. La ligne servie au rendu est
déterministe pour le lecteur, et figée dès sa production pour les informés : elle ne dépend ni du
moment du calcul ni de l'état du rappel.

## Lot 1 — La déclaration

**`services/llm-agents/llm/evenements/declaration.py`**

```yaml
service:
  jours_de_deplacement: 5      # présence garantie au prompt, lecteur ET informés
relais:
  mode: par_destinataire       # un message par membre ; pour un mineur, la décision des parents
```

- Deux dataclasses sur `Evenement` : `Service(jours_de_deplacement: int)` et `Relais(mode: str)`.
- Refus explicite au chargement (`RefusDEvenement`) : `relais` sur un canal autre que `lu`, ou
  sans la règle d'exposition `foyers` ; `mode` inconnu ; `jours_de_deplacement` < 1 ou non
  entier.
- Clés absentes : comportement d'avant ce ticket, **journalisé au chargement**, comme la cadence
  par défaut. Un fichier muet ne doit pas changer de comportement en silence.
- Les deux clés sont posées dans les cinq articles `a07`, `a09`, `a13`, `a18` et `a25`
  (hypothèse H1 de `questions.md`).

**`services/llm-agents/llm/evenements/calendrier.py`**

- `jours_de_service(debut: date, n: int, sans_week_end: bool) -> tuple[date, ...]` : `debut`
  compte comme jour 1 s'il est ouvrable ; le samedi et le dimanche sont sautés quand
  `settings.agent.no_weekend_departures` est vrai. Calendrier **mural** (`wall_clock`), comme
  `jours_ecoules`.
- Déterministe, donc indépendant du moment où la décision est pré-calculée.

## Lot 2 — La ligne servie au prompt

**`services/llm-agents/llm/evenements/registre.py`**

- `lecteurs(population)` est appelé par le contrôleur dès le chargement de la population, avant
  le bootstrap. Aujourd'hui les lecteurs ne sont connus qu'au premier `/sync`, donc une lecture au
  jour 1 serait invisible des décisions du bootstrap. Si la question est posée alors qu'ils sont
  encore inconnus : une seule `[ALARME]`, puis `None`.
- `async lignes_du_jour(person_id, timestamp) -> list[str]` :
  - lecteur, et jour de `timestamp` dans ses jours de service → `entree_de_lecture(applique)`,
    construite depuis la déclaration (`texte_cite.servi`), soit la même chaîne que l'entrée de
    mémoire longue ;
  - membre d'un foyer exposé, jour dans les jours de service de ce membre → sa ligne `[ FOYER ]`,
    tirée du relais (lot 3), produit à la demande s'il ne l'est pas encore ;
  - personne marquée non avenue → rien.
- État : `_non_avenus: set[str]`, `_servies: Counter[(person_id, jour)]`,
  `_servies_avant_injection: Counter[person_id]`, `_relais: dict[household_id, asyncio.Task]`.
- `declarer_non_avenue(person_id, motif)`.

**`services/llm-agents/llm/evenements/__init__.py`** — façade `lignes_du_jour(person_id, ts)` :
liste vide sans registre ; ne lève jamais vers l'appelant (une `[ALARME]` à la place).

**`services/llm-agents/llm/noyau.py`**

- `bloc_changements(entrees, maintenant, person_id=None, lignes=())` et
  `memoire_noyau(journal, entrees, maintenant, person_id=None, lignes=())`.
- Les `lignes` passent **en tête** du bloc et ne sont jamais évincées par
  `memoire__changements_max`.
- Une entrée de mémoire longue dont le contenu est identique à une ligne n'est pas servie une
  seconde fois (lecteur jugé grave, ou jour 0 après l'injection).
- Sans `lignes`, le bloc est **identique octet pour octet** à celui d'aujourd'hui.

**`services/llm-agents/urban_mobility_agents/agents/llm_agent.py`** (~l. 922, appel de
`memoire_noyau`, et ~l. 1202, garde du cache)

- Les lignes sont calculées **avant** la consultation du cache. Une décision qui doit porter une
  ligne ne consulte **jamais** le cache (compté). Sans cela, un jour de service situé après la
  fenêtre de tirage — où `cache_coupe` ne coupe plus — pourrait ressortir une décision prise sans
  l'article.
- Journal INFO au premier service de chaque personne pour chaque jour : « article du jour servi à
  la décision du 26/03 05:57, calculée 17 h avant l'injection ».

**`services/llm-agents/urban_mobility_agents/enquetes.py:274`** — même argument : une enquête
d'affinité tenue un jour de service voit la même ligne que la décision (décision D6).

## Lot 3 — L'appel de relais

**Catégorie `evenement_relais`** — `packages/mobility_llm/src/mobility_llm/categories/evenement_relais/`
(`template.md.j2`, `output_schema.json`), enregistrée dans `CATEGORIES`
(`packages/mobility_llm/src/mobility_llm/__init__.py`). Routage par `instances_pour`, repli sur
la clé `defaut`.

Charge utile, sur le modèle de `jugement.charge_utile` :

```python
{
  "category": "evenement_relais",
  "instances_admises": instances_pour("evenement_relais"),
  "agents": [{
      "agent_id": lecteur_id,
      "perception": identite_du_lecteur,           # get_person_identity_description
      "article": texte_cite,                       # tel qu'il est servi au lecteur
      "membres": [{"agent_id", "prenom", "age", "mineur", "occupation",
                   "modes_habituels", "trajets_du_jour"}, ...],
  }],
  "parameters": {"temperature": 0.2, "max_tokens": 2048},
}
```

Sortie attendue :

```json
{"agents": [{"agent_id": "<lecteur>",
             "destinataires": [{"agent_id": "<membre>", "parle": true, "message": "…"}]}]}
```

Consignes du gabarit, en anglais comme tout le dispositif depuis le ticket 074 :

- tu es la personne qui vient de lire cet article ; pour chaque membre de ton foyer, écris ce que
  tu lui en dis, avec tes mots — ou rien, si tu ne lui en parles pas ;
- **pour un mineur**, l'autre parent et toi décidez pour lui : écris ce que vous avez décidé pour
  lui, comme tu le lui dirais (décision E1) ;
- n'invente aucun fait que l'article ne contient pas ; ne raconte pas ta journée.

`max_tokens` : 2048, parce que les modèles de raisonnement dépensent leur réflexion dans le budget
(le jugement a dû passer de 256 à 1024 le 2026-09-22 pour la même raison), et que la sortie porte
un message par membre.

**`services/llm-agents/llm/evenements/relais.py`** (nouveau)

- `Message(destinataire_id, parle, texte, mineur, directif)`,
  `RelaisFoyer(household_id, lecteur_id, messages, fournisseur, produit_a, duree_s)`,
  `RelaisRefuse(Exception)`.
- `async produire(llm_client, lecteur, membres, texte, evenement_id, jour) -> RelaisFoyer`.
- **Refus, jamais de repli** : réponse vide, `agent_id` inconnu, membre manquant ou présent deux
  fois, `parle` vrai avec un message vide → `RelaisRefuse` et `[ALARME]`. Aucun message n'est
  alors servi dans le foyer. Pas de délai de repli : en pénurie de quota, on attend (règle du
  jugement).
- Les gardes de contenu (`gardes.py`, familles adresse, verdict, intention) tournent **pour
  tracer** (`directif: true`), pas pour refuser : le message est la cognition du lecteur, pas un
  stimulus que nous écrivons. Une décision parentale est directive par nature.
- Mineur : `exposition.age_de(p) < AGE_ADULTE`. Âge absent : traité en adulte, avec un WARNING,
  comme pour le tirage des lecteurs.
- Un seul appel par foyer : la première demande crée la tâche, les suivantes l'attendent. Le
  producteur est branché par le contrôleur (`registre.brancher_producteur_relais(...)`), seul à
  détenir la population, le client LLM et les identités.
- Chaque relais produit est écrit dans `relais_foyer.jsonl`. **À la reprise, il est relu et jamais
  régénéré** : une reprise qui régénérerait le relais produirait un autre texte pour la même
  expérience.

Lignes rendues (préfixe `PREFIXE_FOYER = "[ FOYER ]"` dans `injection.py`, à côté de
`PREFIXE_VECU` et `PREFIXE_LU`) :

```
adulte : [ FOYER ] {prénom du lecteur} told me this morning: « {message} »
mineur : [ FOYER ] My parents decided this morning: « {message} »
```

Coût et pilotage :

- `scripts/experiment/orchestrateur_memoire.py` : `par_bras["evenement_relais"]` = nombre de
  foyers exposés.
- Page mémoire du tableau de bord (`scripts/dashboard/memoire.py`) : fonction « Transmission au
  foyer », même modèle que le jugement par défaut. Le routage entre dans `identite_run.json`,
  comme les autres fonctions (ticket 095, lot C).

## Lot 4 — L'injection à 00:00

**`services/llm-agents/urban_mobility_agents/simulation_controller.py`,
`_injecter_evenements_du_reveil`**

1. Lecteur : jugement, mémoire courte, mémoire longue — cette dernière **attendue** et non plus
   lancée par `_spawn`. On est déjà dans une tâche de fond : l'attente ne retarde aucune
   synchronisation.
2. Relais du foyer : attendu (déjà produit la veille le plus souvent).
3. Pour chaque membre informé : `juger(...)` avec **son** identité et le message reçu ; mémoire
   courte et longue, `origine: entendu`, préfixe `[ FOYER ]` ; une ligne dans `evenements.jsonl`.
4. Échec du jugement, exception, ou injection refusée par le gel du rejeu :
   `declarer_non_avenue(person_id)`. Si des décisions ont déjà porté la ligne,
   `[ALARME] [evenements] … k décision(s) ont déjà vu …`, levée une seule fois par personne.

**`services/llm-agents/llm/evenements/temoin.py`** (ticket 106) : reconnaître `[ FOYER ]` comme
préfixe d'entrée injectée, pour que les consolidations des informés soient contrôlées elles
aussi.

## Lot 5 — Traces et journal

| Sortie | Contenu |
|---|---|
| `evenements.jsonl` | une ligne par informé, en plus de celle du lecteur : `raison: relais:<lecteur>`, `message`, `mineur`, `directif`, colonnes de jugement |
| `relais_foyer.jsonl` (nouveau) | une ligne par foyer, **qui fait foi** : lecteur, chaque membre (informé ou non), messages, modèle, durée de l'appel |
| `moves.csv` | colonne `Rôle` inchangée : `co_resident` pour tous les non-lecteurs. Un rôle qui changerait en cours de run casserait les séries par rôle |
| `scripts/analysis/figure_evenement.py` | `co_resident` séparé en « informé » et « non informé » à partir de `relais_foyer.jsonl` |
| `scripts/analysis/presse/campagne.py` | `--role` accepte les deux sous-rôles |

Journal :

- début et fin de chaque relais, avec sa durée, le nombre de membres informés et le nombre de
  mineurs ;
- premier service par personne et par jour (lot 2) ;
- compteurs quotidiens dans `journaliser_compteurs`, **même à zéro** : lectures servies, messages
  servis, décisions servies avant l'injection, relais produits et refusés, et décisions d'un jour
  de service construites sans leur ligne — ce dernier compteur doit rester à zéro, sinon
  `[ALARME]`.

## Lot 6 — Le contrôle après run, dans `make report`

**`scripts/analysis/lecture_avant_decision.py`** (nouveau) : `controler(run_dir) -> list[Constat]`
et une ligne de commande.

- Lit `evenements.jsonl`, `relais_foyer.jsonl` et `llm_exchanges.jsonl`. Ce dernier est une suite
  d'objets JSON indentés, pas du JSONL : reprendre la lecture de `run_report._iter_json_concat`.
- Découpe chaque message utilisateur par `--- agent_id=<id> | … ---` et ne teste que le bloc de
  la personne concernée (ticket 110, § 3).
- Pour le lecteur et chaque informé, pour chaque jour de service : nombre de décisions, nombre
  portant la ligne. Le préfixe est rendu mot pour mot : le contrôle est exact, sans heuristique.
- Verdict 🔴 si la première décision du jour 1 ne porte pas la ligne, ou si une décision d'un jour
  de service en est privée. Les succès sont rendus aussi.
- Pour chaque mineur : la décision parentale reçue, à côté des modes réellement choisis pendant
  ses jours de service (depuis `moves.csv`). Pas de score de conformité calculé.

**`scripts/debug/run_report.py`** : `section_lecture_avant_decision`, appelée à côté de
`section_temoin_souvenir`.

Recette sur l'archive : `2026-09-24_17_50` doit sortir 🔴 pour 286920, décision du 26/03 05:57.

## Lot 7 — Documentation

- `docs/arch/evenements.md` :
  - ligne « Quand » du tableau : 00:00, premier pas de simulation après minuit, et non 3 h ;
  - ligne « Ce que l'agent sait en décidant » : le mécanisme au rendu, et les 5 jours de
    déplacement ;
  - le paragraphe « ⚠ L'article écrit AUSSI en mémoire longue » est à réécrire : la garantie du
    jour de lecture ne dépend plus de l'écriture en mémoire longue, qui sert aux jours suivants ;
  - une section « Le lecteur le dit à sa famille », avec la décision parentale pour les mineurs ;
  - les rôles : co-résident informé et non informé ;
  - le constat a13 : le service d'un article dépendait de l'âge de la mémoire.
- `docs/arch/memory-stm-ltm.md` : la règle des lignes servies en tête du bloc.
- `docs/arch/llm-inference.md` : la catégorie `evenement_relais`, et une ligne sur l'horizon
  glissant et ce qu'il impose au canal `lu`.
- `docs/arch/dashboard.md` : la nouvelle fonction de la page mémoire.
- `docs/changelog.md` : entrée en tête, avec des blocs Avant / Après.
- `scripts/dashboard/tickets_status.yaml` : statut du ticket.
- En fin de tâche : signalement d'impact sur l'article (skill `article-impact`), sans y écrire.

## Ordre de livraison conseillé

1. Lot 1 et lot 2 pour le lecteur seul : le test T1 passe, et le défaut de la section 2 du ticket
   est corrigé pour le lecteur.
2. Lot 6 : le contrôle attrape le défaut sur l'archive **avant** qu'on s'appuie sur lui.
3. Lots 3, 4 et 5 : le relais au foyer.
4. Lot 7.
