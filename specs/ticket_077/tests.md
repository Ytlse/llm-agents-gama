# Ticket 077 — Spécification des tests fonctionnels

> Écrite le 2026-09-15, **avant le code**. Même convention que les lots du 071 et du 075 : le
> contrat est écrit d'abord, le code ensuite, et la validation se fait par l'échec — casser une
> règle doit casser un test nommé.
>
> Objet du ticket : la mémoire apprend sur des observations fausses et ne peut pas se corriger.
> Chaque règle ci-dessous est tirée d'un constat mesuré sur `experiments/archive/2026-09-14_23_58`.

---

## A. Le vocabulaire des modes

`mode_canonique()` n'acceptait que les **étiquettes de jambes** de la hiérarchie AUAT/CEREMA
(`foot`, `bus`, `bicycle`), alors que le schéma JSON de `stm_reflection` impose au modèle les
**modes canoniques** (`walking`, `cycling`, `public_transport`…). Un seul mot sur sept traversait.

| # | Cas | Attendu |
|---|---|---|
| A1 | `walking`, `cycling`, `car`, `public_transport`, `train`, `motorbike` | rendus **tels quels** : un mode déjà canonique est son propre canonique |
| A2 | `foot`, `bus`, `bicycle`, `metro`, `rail`, `school_bus` | inchangés par rapport à avant le ticket — `walking`, `public_transport`, `cycling`, `public_transport`, `train`, `public_transport` |
| A3 | `foot,bus,foot` | `public_transport` : le mode principal continue de l'emporter, la règle de hiérarchie n'est pas touchée |
| A4 | `any` | `None` — le schéma le définit comme « pas à propos d'un mode », il ne doit pas devenir un axe |
| A5 | mot hors des deux vocabulaires (`teleport`) | `None`, **compté** dans `MODES_INCONNUS` et journalisé une seule fois |
| A6 | `None`, chaîne vide, chaîne d'espaces | `None`, sans exception |
| A7 | la liste des modes canoniques acceptés | **dérivée de la ressource gelée** (`mode_canonique` du JSON), jamais écrite en dur dans `axes.py` |
| A8 | casse et espaces (`  Walking `, `PUBLIC_TRANSPORT`) | reconnus comme leur forme canonique |
| A9 | concept écrit avec un `mode` renseigné par le modèle | `axe_objet` non vide — **règle de garde du ticket** : c'est le test qui aurait dû échouer au run du 14 septembre |

---

## B. Ce que GAMA raconte à la mémoire

### B1 — L'attente avant le départ n'est pas une marche

`step_started_at` était posé à la réception du plan, alors que l'agent attend `schedule_at` pour
bouger : le premier segment absorbait l'attente. 398 événements sur 412 avaient une distance nulle
et une durée exactement égale au retard au départ.

| # | Cas | Attendu |
|---|---|---|
| B1.1 | plan reçu à `t`, départ prévu à `t + 3600`, premier segment de 5 min | l'observation de marche porte **300 s**, pas 3900 |
| B1.2 | plan reçu et départ immédiat (`schedule_at <= t`) | durée inchangée par rapport à avant le ticket |
| B1.3 | l'attente avant départ | n'apparaît **dans aucune** observation de type `transfer` |
| B1.4 | segments suivants du même trajet | non affectés : leur chronomètre repart à la fin du segment précédent |

### B2 — La voiture n'est pas un transport collectif

Le marqueur `__DIRECT_CAR__` passait par `submit_ob_transit`, puis par un gabarit qui interrogeait
le GTFS et rendait « Trip by Unknown Unknown » — 253 fois sur le run.

| # | Cas | Attendu |
|---|---|---|
| B2.1 | segment `__DIRECT_CAR__` | observation de type `car`, rendue `[ CAR ]` avec durée et distance |
| B2.2 | segment `__DIRECT_BIKE__` | observation de type `bike`, rendue `[ BIKE ]` |
| B2.3 | segment de bus dont la ligne existe au GTFS | inchangé : `[ PUBLIC TRANSPORT ] Trip by Bus L2 …` |
| B2.4 | segment collectif dont la ligne est **introuvable** au GTFS | l'observation est produite sans nom de ligne inventé, et le cas est **journalisé** — jamais « Unknown Unknown » |
| B2.5 | aucune observation rendue au modèle | ne contient la chaîne `Unknown Unknown` |

---

## C. Les trajets à itinéraire unique

116 trajets sur 514 n'écrivaient aucune entrée de décision en mémoire courte, et le journal des
habitudes remontait au dernier `axe_objet` trouvé dans le tampon — donc au trajet précédent.

| # | Cas | Attendu |
|---|---|---|
| C1 | trajet à une seule option (aucun appel LLM) | une entrée `TRAVEL_PLAN` est écrite en STM, avec ses axes, et sa méthode de sélection est lisible |
| C2 | le contenu de cette entrée | dit explicitement que le choix était **contraint**, jamais qu'un modèle a choisi |
| C3 | arrivée d'un trajet `home` suivant un aller `work` | le journal des habitudes enregistre `home`, avec le créneau de **cette** arrivée |
| C4 | arrivée sans entrée de décision retrouvable | rien n'est enregistré, et l'écart est journalisé — jamais d'attribution au trajet précédent |
| C5 | agent dont tous les retours sont contraints | son bloc « Mes habitudes » porte autant de motifs que de motifs réellement parcourus |
| C6 | nombre d'entrées du journal après N arrivées | égal au nombre d'arrivées porteuses d'une décision, et non à une fraction |

---

## D. Ce que le rappel sert

Le lot D1 (servir l'auto-réflexion ou l'éteindre) attend une décision de l'auteur et **n'est pas
couvert ici**. Seule la mesure est contractée.

| # | Cas | Attendu |
|---|---|---|
| D2.1 | fenêtre glissante de décisions | la **concentration des rappels** est journalisée : part du top-K occupée par les dix souvenirs les plus servis |
| D2.2 | concentration au-delà du seuil | alarme `[ALARME]` sur **front montant**, une seule fois tant que le seuil reste franchi |
| D2.3 | retour sous le seuil bas | l'alarme se réarme |
| D2.4 | agent sans aucun rappel | aucune division par zéro, aucune alarme |

---

## E. L'instrumentation du prochain run

| # | Cas | Attendu |
|---|---|---|
| E1 | décision servie par la mémoire | chaque souvenir du top-K est tracé avec son identifiant, son type, son **vivier d'origine** (A/B/C), son score composite et son rang |
| E2 | toute décision, quelle que soit la méthode | l'index proposé et l'index retenu sont dans `moves.csv` — aujourd'hui `plan_selected_index` n'existe que pour 66 trajets sur 514 |
| E3 | options présentées | leur descriptif (mode, durée, correspondances) est tracé à la décision, sans passer par le texte du prompt |
| E4 | appel de réflexion | les `known_beliefs` montrés et l'opération demandée par le modèle sont tracés, pour mesurer le taux de confirmation **possible** contre **réalisé** |
| E5 | décision servie par le cache | tracée comme telle, distinctement d'un appel direct |
| E6 | run repris sans point de reprise valide | n'écrit **pas** dans le même `moves.csv` que le run rejoué — les 84 trajets rejoués du 14 septembre y figuraient deux fois |
| E7 | tout ce qui précède, réglages éteints | aucun coût, aucun fichier, aucune exception |

---

## F. Le rapport d'analyse

| # | Cas | Attendu |
|---|---|---|
| F1 | run comportant un rejeu | les trajets rejoués sont **exclus** et le rapport le déclare, avec leur nombre |
| F2 | `llm_exchanges.jsonl` en JSON concaténé multi-lignes | lu sans erreur (ce n'est pas du JSONL malgré l'extension) |
| F3 | trajet dont l'option n'est pas retrouvée dans les prompts | colonne grise **déclarée**, jamais une case vide muette |
| F4 | tableau d'itinéraires | une ligne par itinéraire distinct, une colonne par jour, bleu clair proposé et bleu foncé retenu |
| F5 | palette des modes | celle du dépôt (voiture rouge, vélo violet, TC vert, marche cyan) |
| F6 | agent sans aucun concept | section produite, vide et déclarée comme telle — l'absence de mesure ne doit pas produire un rapport parfait |
| F7 | rapport produit deux fois sur le même run | octet pour octet identique (aucun horodatage de génération dans le corps) |

---

## G. Le branchement de l'hibernation et des mesures du jour

> Écrite le 2026-09-19, **avant le correctif**. Ajoutée après la relecture du run
> `experiments/archive/2026-09-19_07_31`, qui n'a produit **aucun** des CSV du ticket 093 :
> `_declencher_hibernation_propre` avait été insérée au milieu de `_ecrire_point_de_reprise`, et
> l'appel aux mesures du jour s'est retrouvé après un `sys.exit(0)`, donc inatteignable.
>
> Les tests du 093 sont restés verts pendant toute la durée du défaut : ils vérifiaient le
> module, pas son branchement. C'est la cause 5/6 du § 10.2 du ticket qui se répète, et ces
> règles-ci portent donc sur le **branchement**, pas sur le calcul.

| # | Cas | Attendu |
|---|---|---|
| G1 | point de reprise écrit, `mesures_jour_enabled` vrai | `mesures_jour.ecrire_mesures_du_jour` est **appelée**, avec le workdir du run — la règle qui échoue si on remet le code dans l'état du 19 septembre |
| G1b | même chose, réglage éteint | elle n'est pas appelée, et rien n'est écrit |
| G1c | l'écriture du point lève | les mesures sont **quand même** tentées : le fail-open du point ne doit pas emporter celui des mesures |
| G2 | source de `simulation_controller.py` | aucune instruction ne suit un appel terminal (`sys.exit`, `os._exit`, `os.kill` de soi) dans un même bloc — garde générique sur l'arbre syntaxique, pas sur ce seul endroit |
| G3 | quota journalier épuisé, hibernation armée | `en_attente_quota.json` est écrit **dans le workdir du run** (`settings.workdir`), avec `resume_at`, `person_id`, `timestamp` et `jour_simule` |
| G4 | même cas | l'arrêt est demandé **une seule fois**, par signal au processus (SIGTERM), pas par `sys.exit` dans une coroutine servie par l'ASGI — l'orchestrateur du run séquentiel attend un code de retour 0 |
| G5 | même cas, écriture du marqueur impossible | l'arrêt est demandé quand même, et l'échec est journalisé en `[ALARME]` : perdre le marqueur ne doit pas transformer l'hibernation en run qui continue sur des replis par défaut |
| G6 | `_compute_move_for_activity` revient après une hibernation | rend un **couple** `(None, None)`, conforme à sa signature — un `None` nu casse les quatre appelants à l'unpacking |
| G7 | l'hibernation, collaborateurs réels | n'appelle aucune fonction qui n'existe pas. Trouvé en écrivant G3 : `rejeu_decisions.flush()` n'existe pas — `tracer()` ouvre, écrit et referme à chaque décision. L'hibernation levait `AttributeError` avant d'écrire son point de reprise et avant de demander l'arrêt |

---

## H. Le vécu ne conclut pas, et le choc a une cadence

> Écrite le 2026-09-19, **avant le code**. Tirée de la relecture du run
> `experiments/archive/2026-09-19_07_31`.
>
> La règle R7/R8 refuse déjà un vécu qui **s'adresse** à l'agent (« you should take the bus »).
> Elle laisse passer un vécu qui **conclut à sa place**, à la première personne. Le run du
> 19 septembre l'a payé : le `vecu` disait *« I no longer trust this car at all »* et
> *« I am seriously thinking about not using this car anymore »*, la réflexion nocturne en a
> tiré *« consider alternative transport options »*, et cette phrase a été servie à chacune des
> quarante décisions des quatorze jours suivants. On ne mesurait plus un agent qui apprend, mais
> un modèle qui ne se contredit pas.
>
> La ligne n'est pas inventée ici : elle est déjà tenue par les **cinq autres** fichiers de
> `config/chocs/`, qui ne disent que des faits et des sensations. Seul c6 en sortait. Ces règles
> rendent la pratique existante vérifiable.

### H1 — le vécu ne porte ni verdict ni intention

| # | Cas | Attendu |
|---|---|---|
| H1.1 | `vecu` contenant un **verdict** sur un mode ou un véhicule (« I no longer trust this car », « the bus is unreliable ») | `RefusDeChoc` au chargement, message citant le marqueur et disant quoi écrire à la place |
| H1.2 | `vecu` contenant une **intention modale** (« I am thinking about not using this car anymore », « je ne prendrai plus le bus ») | `RefusDeChoc`, message distinct de H1.1 — les deux familles se relâchent séparément |
| H1.3 | les cinq chocs c1 à c5 du dépôt | se chargent **sans exception** : la règle ne condamne pas la pratique existante |
| H1.4 | « I am starting to wonder whether this is worth it » (c1, jour 14) | **accepté** — un doute n'est ni un verdict ni une intention, et c'est la limite basse volontairement retenue |
| H1.5 | « I had to sort out another way of getting around » (c2, jour 13) | **accepté** — un fait passé, même modal, n'est pas une intention |
| H1.6 | les deux `vecu` de c6 dans leur rédaction du 18 septembre | **refusés**, l'un par H1.1, l'autre par H1.2 — c'est le test qui aurait dû échouer avant le run |
| H1.7 | c6 dans sa rédaction corrigée | accepté, et ne contient ni « trust », ni « anymore », ni nom de mode alternatif |

### H2 — la cadence du choc est déclarée

Le run du 19 septembre a appliqué le choc **quatre fois le même jour**, une fois par trajet en
voiture : quatre pannes, quatre dépannages de trente minutes, quatre fois le même récit. Le
protocole, lui, raisonnait sur un retard de trente minutes. L'intensité réelle valait quatre fois
l'intensité annoncée, et rien ne le disait.

| # | Cas | Attendu |
|---|---|---|
| H2.1 | `cadence: jour` | un agent exposé ne subit le choc qu'à sa **première** arrivée éligible de la journée ; les suivantes sont comptées à part, ni exposées ni épargnées |
| H2.2 | `cadence: trajet` | comportement historique — chaque arrivée éligible subit le choc |
| H2.3 | `cadence` absente | vaut `trajet`, et le chargement le **journalise** : aucun fichier existant ne change de comportement en silence |
| H2.4 | `cadence` de valeur inconnue | `RefusDeChoc` au chargement, comme une règle d'exposition inconnue |
| H2.5 | `cadence: jour`, deux journées de choc | le compteur se réarme à chaque journée — l'agent est touché une fois par jour, pas une fois pour tout le run |
| H2.6 | c6 | déclare `cadence: jour` : une panne réparée ne se reproduit pas à l'identique trois heures plus tard |

### H3 — un jour de choc sans exposé est une alarme

Le second choc de c6 (jour 16) n'a **jamais** été appliqué : l'exposition est restreinte aux
trajets en voiture, et l'agent n'en faisait plus. Le journal l'a dit en INFO, au milieu du run,
et le rapport a continué d'annoncer deux jours de choc.

| # | Cas | Attendu |
|---|---|---|
| H3.1 | journée déclarée dans `jours`, close avec `exposes == 0` | `[ALARME]` en ERROR, nommant le jour et le nombre d'épargnés |
| H3.2 | journée nominale close avec `exposes == 0` | INFO, comme aujourd'hui — c'est le cas normal |
| H3.3 | journée de choc avec au moins un exposé | INFO, aucune alarme |

---

## I. La fenêtre de « ce qui a changé récemment » est un réglage, et sa sortie se voit

> Écrite le 2026-09-19, **avant le code**.
>
> Le bloc « Ce qui a changé récemment » sert un souvenir épisodique de gravité de choc tant
> qu'il a moins de `FENETRE_CHANGEMENTS_JOURS` jours — 14, écrit en dur — puis **plus du tout**.
> Coupure franche, pas décroissance.
>
> Sur le run `2026-09-19_07_31`, le choc tombe le 30 mars et le récit quitte le bloc le
> 13 avril, quatorze jours plus tard **jour pour jour**. Le dernier prompt qui le porte annonce
> P(voiture) = 5 % ; le suivant, qui ne le porte plus, annonce 60 %. Moyennes : **6,9 % tant que
> le texte est là (n = 18), 55,2 % une fois sorti (n = 33)**.
>
> Le rapport du run attribue ce retour à la décroissance exponentielle du souvenir. Les deux
> explications prédisent presque la même date — une durée de vie calculée à ~14,6 jours contre
> une fenêtre de 14 — et **rien dans le dispositif ne permet de les départager**. Ces règles
> rendent l'ablation possible et l'événement visible dans le journal du run, au lieu d'être
> reconstruit après coup depuis le texte des prompts.
>
> ⚠ Ce lot ne change **aucune** règle de mémoire : mêmes valeurs par défaut, même mécanisme.
> Il rend un paramètre caché déclarable, mesurable et enregistrable.

| # | Cas | Attendu |
|---|---|---|
| I1 | réglages par défaut | fenêtre 14 jours, 3 lignes au plus — le comportement historique ne bouge pas d'un iota |
| I2 | `memoire__fenetre_changements_jours` à 7 | un souvenir de choc de 10 jours n'est plus servi ; à 21, il l'est |
| I3 | valeur modifiée entre deux appels | prise en compte au deuxième : la fenêtre est lue à CHAQUE appel, jamais figée à l'import — sans quoi une surcharge d'environnement ne servirait à rien |
| I4 | `memoire__changements_max` à 1 | une seule ligne, la plus récente |
| I5 | fenêtre à **0** | aucun épisodique de choc dans le bloc ; les croyances mises à l'écart y restent. C'est la valeur d'ABLATION du bras « sans fenêtre » |
| I6 | fenêtre négative | ramenée à 0, et journalisée une fois — une fenêtre négative n'a pas de sens et ne doit pas se lire comme un réglage accepté |
| I7 | dernier souvenir de gravité de choc sortant de la fenêtre | journalisé **une seule fois par souvenir et par agent** : identifiant, date du souvenir, fenêtre appliquée. C'est l'événement qui, le 13 avril, coïncide avec le retour de la voiture |
| I8 | souvenir de choc encore dans la fenêtre | rien n'est journalisé — l'événement est la SORTIE, pas la présence |
| I9 | agent sans aucun souvenir de gravité de choc | rien n'est journalisé : ne jamais avoir eu de choc n'est pas en sortir |
| I10 | décisions répétées après la sortie, le jour même puis le lendemain | une seule ligne de journal — front montant sur le souvenir sorti, pas une ligne par décision ni par jour. Un choc NOUVEAU qui sortirait plus tard se journalise, lui |

---

## J. La configuration du dépôt ne redéfinit pas les règles de mémoire

> Écrite le 2026-09-19, **avant le code**.
>
> Le § 9 de ce ticket énonce : « Il ne touche à aucune règle de la mémoire : gravité, oubli,
> viviers, score composite, opérations de concept et seuils restent ceux du 071. » Le
> 18 septembre, `config.yaml` a pourtant abaissé `memoire__importance_choc` de 0,70 à 0,50 —
> donc élargi le **vivier C** (rappel sans aucune condition de contexte) et le bloc noyau à tout
> souvenir de gravité ≥ 0,50.
>
> **Ce réglage n'a rien apporté.** La gravité du premier choc de c6 vaut exactement 0,70, et la
> comparaison est `>=` : il franchissait le seuil d'origine sans qu'on l'abaisse. Seul le second
> choc (0,533) en dépendait — et il ne s'est jamais appliqué. Le seul effet mesurable a été
> d'ajouter six souvenirs au vivier C, sur les 219 entrées de l'agent.
>
> Le commentaire d'origine du fichier de choc argumentait d'ailleurs *pour* le sous-seuil :
> « Le souvenir n'atteint PAS le seuil du vivier des chocs (0,70). Il est donc rappelé par le
> vivier par objet — quand la voiture figure dans les options — et non hors contexte. C'est
> voulu : un moteur qui fait du bruit n'est pas une panne de réseau. » Cet argument a été
> supprimé le 18 septembre, pas réfuté.

| # | Cas | Attendu |
|---|---|---|
| J1 | `config/config.yaml` livré dans le dépôt | ne déclare **aucune** clé `memoire__*`. Une règle de mémoire se varie par l'environnement, où elle appartient au run et se retrouve dans son identité — jamais par la configuration par défaut, où elle devient la norme du dépôt sans que personne ne l'ait décidé |
| J2 | seuil de choc et Θ | reviennent aux valeurs du 071 : 0,70 tous les deux. Déjà couvert par `test_071_lot0_constantes` — ce lot les fait simplement repasser au vert |
| J3 | gravité du premier choc de c6 | ≥ 0,70 **sans abaisser le seuil** : la vérification se fait sur la valeur calculée, pas sur une intention écrite dans un commentaire |
| J4 | c6, second jour de choc | gravité < 0,70 : il n'entre PAS dans la mémoire noyau, et c'est le comportement documenté d'origine. À vérifier explicitement, pour que personne ne le « corrige » à nouveau sans le savoir |

### J5 — les jalons d'enquête suivent le protocole

`enquetes.py` sonde aux jours 5, 9 et 19, commentés « pré-choc », « fin de période péri-choc »,
« post-choc résilience ». Ces libellés datent du protocole où le choc tombait au jour 8. Avec le
choc aux jours 15 et 16, J9 est pré-choc, J19 est à quatre jours du choc, et aucun jalon ne se
situe après la sortie de fenêtre. Trois libellés faux et un sondage payé pour rien.

| # | Cas | Attendu |
|---|---|---|
| J5.1 | jalons non déclarés | valeur par défaut alignée sur le protocole en vigueur, et **journalisée** au premier usage |
| J5.2 | `EXPERIMENT_SURVEY_DAYS="3,11"` | ce sont ces jours-là, et pas les autres — un protocole qui bouge ne doit plus demander de modifier du code |
| J5.3 | déclaration illisible (`"douze"`, valeur vide, jour < 1) | repli sur le défaut, journalisé en `[ALARME]` : un sondage silencieusement éteint ne se distingue pas d'un sondage qui n'a rien trouvé |
| J5.4 | jalon tombant un samedi ou un dimanche | journalisé **une fois** comme inatteignable — la simulation saute les week-ends, ce jalon ne se déclencherait jamais et son absence se lirait comme une panne |
| J5.5 | jalon un jour ouvré | rien n'est journalisé |

---

## K. Un réglage d'expérience appartient au run, et le run le dit

> Écrite le 2026-09-19, **avant le code**.
>
> Quatre réglages posés dans `config/config.yaml` le 18 septembre — chaînage des véhicules,
> verrou de retour, seuil de troncature du tirage, plancher de réflexion — ont deux effets qu'on
> n'a pas voulus :
>
> 1. ils sont devenus le **défaut du dépôt**, donc la norme de tout run, mesuré ou non. Trente
>    tests énonçant les règles que ces réglages contredisent sont rouges depuis ce jour-là ;
> 2. ils ne figurent **nulle part** dans `identite_run.json`. Trois bras d'expérience aux
>    réglages opposés portent aujourd'hui la même identité, et rien ne permet, après coup, de
>    dire sous quels réglages un run a tourné. C'est exactement ce que le ticket 091 existait
>    pour empêcher.
>
> La règle : **ce qu'un bras d'expérience fait varier passe par l'environnement et entre dans
> l'identité du run.** Ce qui appartient au projet reste dans `config.yaml`.

| # | Cas | Attendu |
|---|---|---|
| K1 | `config/config.yaml` livré | ne déclare aucun des réglages d'expérience nommés : `vehicle_chain_enabled`, `vehicle_return_home_lock`, `mode_choice_truncation_threshold`, `stm_reflection_min_entries` |
| K2 | `identite_run.composer` | rend les réglages d'expérience en plus des onze champs du 091 : chaînage, verrou de retour, seuil de troncature, seuil de choc, fenêtre de changements, plafond de changements, plancher de réflexion, météo par agent |
| K3 | deux runs ne différant QUE par le seuil de troncature | `differences()` les sépare et **nomme** le champ en clair |
| K4 | idem par la fenêtre de changements | séparés et nommés — c'est le paramètre du bras d'ablation, il ne doit pas pouvoir passer pour identique |
| K5 | identité écrite AVANT le 2026-09-19 (champs absents) | la reprise est refusée, et le message dit **« absent du run repris »** au lieu de comparer à `None` : la cause est l'âge du run, pas un réglage différent |
| K6 | les champs par défaut | mêmes valeurs que les défauts du dépôt, pour qu'un run nominal ne se croie jamais différent de lui-même |
| K7 | `run_sequential_cohort.py` | pose par l'environnement TOUS les réglages d'expérience que K1 retire de `config.yaml` — sinon la campagne tournerait aux valeurs par défaut sans que rien ne le dise |
| K8 | la campagne, branche traitée et branche témoin | la commande `make run` porte un `CHOC=` **explicite** : le nom du choc pour la traitée, `0` pour la témoin. Sans lui, `make run` laisse la déclaration de `config.yaml` en place et **le témoin subit le choc du bras traité** — le bras de contrôle n'en est pas un |
| K9 | le texte du choc de la campagne | **dérivé** du fichier de référence versionné, jamais recopié dans le lanceur : une copie divergerait du fichier testé, et c'est ce qui s'est produit — les corrections du lot H ne parvenaient pas à la campagne |
| K10 | la campagne | coupe le cache (`CACHE=0`) : la clé du cache sémantique ne porte aucune durée, une décision prise avant le choc serait resservie pendant |

---

## L. Un bras d'expérience tourne avec ses réglages, ou il ne tourne pas

> Écrite le 2026-09-19, **après la première tentative de campagne**, qui a tout révélé en
> quarante-deux secondes.
>
> Trois défauts distincts, tous dans le chemin de lancement :
>
> 1. **`make run OFFLINE=1` ne bloque pas.** Le lanceur GAMA part en arrière-plan (`&` en fin de
>    recette). `make` rend la main en vingt secondes, l'orchestrateur enchaîne, et la première
>    étape du bras suivant — `make stop-run` — **tue le bras précédent**. Mesuré : bras traité
>    lancé à 16:44:29, tué à 16:45:03 par le bras témoin.
> 2. **Les réglages n'atteignaient pas le conteneur.** L'orchestrateur posait `AGENT__…` ; ce
>    préfixe n'existe nulle part dans ce dépôt. Les sous-configurations sont des `BaseSettings`
>    sans préfixe : la variable se nomme `VEHICLE_CHAIN_ENABLED`, pas `AGENT__VEHICLE_CHAIN_ENABLED`.
>    Et rien n'était déclaré dans `docker-compose.yml`, qui ne transmet que ce qu'il déclare.
> 3. **Rien ne le disait.** Le bras a tourné aux valeurs par défaut du dépôt et se serait arrêté
>    trois heures plus tard avec des chiffres inexploitables.
>
> Le lot K a quand même fait son travail : c'est `identite_run.json`, écrit en vingt secondes,
> qui porte la preuve. Ce lot-ci la fait LIRE.

### L1 — les réglages traversent

| # | Cas | Attendu |
|---|---|---|
| L1.1 | `infra/docker-compose.yml`, service `controller` | déclare chaque réglage d'expérience en passe-plat (`${NOM:-<défaut>}`), sur le modèle de `CONTINUE_RUN` |
| L1.2 | chaque défaut déclaré dans le compose | **égal au défaut de `settings.py`**. Deux valeurs par défaut écrites à deux endroits divergent ; un test les tient ensemble |
| L1.3 | nom des variables | le **nom nu du champ** (`VEHICLE_CHAIN_ENABLED`, `MEMOIRE__FENETRE_CHANGEMENTS_JOURS`), jamais un préfixe `AGENT__`, qui n'est lu par personne |
| L1.4 | une clé présente dans `config.yaml` | l'emporte sur l'environnement. C'est la raison pour laquelle le lot K retire ces clés du fichier : tant qu'elles y sont, aucune variable ne peut les changer |

### L2 — l'orchestrateur attend la fin du RUN, pas celle de `make`

| # | Cas | Attendu |
|---|---|---|
| L2.1 | après `make run` | attend que `launch_headless.py` ait disparu. C'est le signal franc : GAMA Server tue l'expérience dès que ce client se déconnecte, donc il vit exactement le temps du run |
| L2.2 | pendant l'attente | journalise l'avancement — dernière journée simulée atteinte — à intervalle régulier, jamais en continu |
| L2.3 | délai de garde dépassé | rend une erreur nommée, sans tuer le run : un run lent n'est pas un run mort, et c'est à l'auteur de trancher |
| L2.4 | un lanceur tourne déjà au démarrage d'un bras | **refus immédiat**. `make run` se contente d'un « Lancement ignoré » sur sa sortie standard, que l'orchestrateur ne lisait pas |

### L3 — un bras se vérifie avant de coûter trois heures

| # | Cas | Attendu |
|---|---|---|
| L3.1 | `identite_run.json` écrit par le bras | relu dès qu'il apparaît, et comparé aux réglages demandés |
| L3.2 | un réglage qui ne correspond pas | le bras est **arrêté**, la campagne s'interrompt, et le message nomme chaque écart — attendu contre obtenu |
| L3.3 | tous les réglages conformes | la campagne continue, et l'accord est journalisé : un contrôle muet ne se distingue pas d'un contrôle qui ne tourne pas |
| L3.4 | `identite_run.json` absent après le délai d'attente | échec nommé : sans identité, on ne peut rien affirmer du bras |
| L3.5 | bras d'ablation (`MEMOIRE__FENETRE_CHANGEMENTS_JOURS=7`) | la valeur attendue suit la variable posée, elle n'est pas écrite en dur |

### L4 — l'identité lue est celle du contrôleur qui sert le run

Le nom du répertoire de run a une granularité à la **minute**. Deux contrôleurs démarrés dans la
même minute le partagent, et `identite_run.ecrire` laisse en place l'identité déjà posée — c'est
la règle du 091, et elle est bonne : à la reprise, l'identité du run repris est la référence.

Mesuré le 2026-09-19 à 16:57 : un contrôleur lancé par `make up`, **sans** les réglages
d'expérience et **sans** le choc, a écrit l'identité à 16:57:12 ; le contrôleur du run l'a
remplacé à 16:57:35. Le bras a été jugé sur l'identité du premier, qui annonçait « choc : aucun »
et les valeurs par défaut — alors que le conteneur qui tournait portait, lui, les bons réglages.

| # | Cas | Attendu |
|---|---|---|
| L4.1 | identité antérieure au démarrage du contrôleur | **ignorée** ; l'orchestrateur continue d'attendre la bonne, et le dit une fois |
| L4.2 | identité postérieure | acceptée et vérifiée |
| L4.3 | aucune identité fraîche au bout du délai | échec nommé, qui mentionne la cause probable : un contrôleur lancé avant `make run` |
| L4.4 | `identite_run.ecrire` refusant d'écraser | le **journalise**. Muet, ce refus ne se distingue pas d'une écriture réussie |
