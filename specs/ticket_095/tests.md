# Ticket 095 — Contrat de tests

Écrit AVANT le code, le 2026-09-21. Les prédictions chiffrées du lot A et de l'expérience E3
sont posées ici **avant** tout run : elles ne se réécrivent pas après mesure.

## Le besoin

La campagne appariée du ticket 077 a montré un effet de choc qui s'éteint **le jour exact où le
souvenir sort du bloc de prompt** — 13 avril à fenêtre 14, 6 avril à fenêtre 7, pas un jour plus
tard. La durée d'un effet est donc aujourd'hui un entier posé dans `settings.py`, pas une
conséquence de l'événement. Et la seule trace de l'effet est la part modale : on ne sait pas dire
si l'agent a changé d'avis ou seulement d'itinéraire.

Vérifié dans le code avant d'écrire ce contrat :

- `llm/gravite.py:219` calcule bien `force = min(S0 × (1 + k × I), FORCE_MAX)`, et
  `longterm.py:435` l'écrit sur chaque entrée. `llm/noyau.py:236` **ne la lit pas** : il compare
  l'âge du souvenir à `memoire__fenetre_changements_jours`. Les deux explications du run du
  19 septembre — décroissance et fenêtre — prédisaient la même date parce que 14,6 ≈ 14.
- `enquetes.py:167` sert au modèle quatre champs — nom, âge, genre, occupation. Ni mémoire, ni
  habitudes, ni concepts, ni bloc de changements. Le constat du ticket est exact.
- `TaskResult` (`sdk/client.py:86`) porte `provider_used`, le nom d'**instance**, et pas le
  modèle. Celui-ci se dérive de `settings.llm.providers[<instance>].default_model` — c'est déjà
  ce que fait `identite_run._modeles_des_instances`. Le lot E ne touche donc pas la passerelle.
- Le SDK accepte déjà `instances_admises` **par appel** dans le payload (`sdk/client.py:212`).
  Le lot C n'a besoin que d'un résolveur côté appelant.

## Le principe

**La durée d'un souvenir se déduit de sa gravité, et se journalise avec ce qui l'a produite.**
Un nombre servi sans sa cause ne se vérifie pas : la ligne de sortie de fenêtre porte la durée,
la gravité, la force, et le nom de la borne quand une borne a mordu.

**Le mode de fenêtre est déclaré, jamais deviné.** `derivee` est le défaut (décision de l'auteur,
2026-09-21) ; `fixe` reste disponible et lit `memoire__fenetre_changements_jours`. Le mode entre
dans `identite_run.json` : deux bras qui n'ont pas le même mode ne portent pas la même identité.

**L'enquête est étanche en SORTIE, fidèle en ENTRÉE.** Deux exigences distinctes. En sortie :
rien n'entre en STM, LTM, ChromaDB ni dans la réflexion nocturne. En entrée : exactement le même
bloc mémoire que le prompt de décision. Une sonde alimentée par quatre champs d'identité mesure
le modèle de base, pas l'agent.

**L'enquête ne RAPPELLE pas.** Elle lit `memoire_noyau`, qui ne touche ni `force` ni
`dernier_rappel`. Elle n'emprunte pas le chemin de rappel vectoriel, où `llm_agent.py:1992`
renforce la force de chaque souvenir servi : une sonde qui prolonge la durée de vie de ce qu'elle
observe modifie ce qu'elle mesure.

**Jamais `force_provider`.** `task_worker.py` ne retente que si `force_provider is None`. Le lot C
route par liste blanche, avec un minimum de deux instances par catégorie, et refuse bruyamment en
deçà.

**Un run enfant ne diffère de son parent que par ce qu'il déclare.** La filiation est écrite ; les
champs d'identité que l'enfant a le droit de faire varier sont nommés un par un. Tout autre écart
fait refuser le démarrage, comme pour une reprise.

---

## Les nombres, posés avant le code

`force = min(2,8 × (1 + 6 × gravité), 30)` · `durée = force × ln(1/0,35)` ·
`ln(1/0,35) = 1,049822` · durée servie = `max(2, min(30, durée))`.

| Gravité | force (j) | durée (j) | Remarque |
|---:|---:|---:|---|
| 0,10 | 4,480 | **4,703** | contrariété |
| 0,30 | 7,840 | **8,231** | incident mineur |
| 0,37 | 9,016 | **9,465** | C1 jour 3 |
| 0,62 | 13,216 | **13,875** | bouchon C1 au jour 2 (25 min + incident) — SOUS le seuil du bloc |
| 0,70 | 14,560 | **15,285** | C6, la valeur mesurée au ticket 077 |
| 0,90 | 17,920 | **18,813** | C3 mesuré |
| 1,00 | 19,600 | **20,577** | gravité maximale |

⚠ **La ligne « ≥ 1,30 » du ticket n'est pas atteignable, et le plafond de 30 jours ne mord jamais
par la gravité.** `gravite.borne_0_1` plafonne la gravité à 1,0 ; la force maximale issue de la
gravité vaut donc 19,6 j et la durée 20,577 j, sous le plafond de 30. Le plafond mord par le
**renforcement au rappel** (`force_apres_rappel`, +1 j par rappel, plafonnée à 30) : à force = 30,
la durée calculée vaut 31,495 j et c'est le plafond qui la ramène à 30. C'est le cas que B8 exerce
en test unitaire, et c'est par là que E4 doit passer — pas par une gravité de 1,30. Cf.
`questions.md`.

---

## Cas

### A — Durée de service dérivée de la gravité (`llm/noyau.py`)

| Cas | Ce qui est vérifié |
|---|---|
| A1 | `duree_service_jours` rend 15,285 j pour une entrée de gravité 0,70 sans force écrite — la force est recalculée par `force_initiale`, pas supposée |
| A2 | Une entrée qui PORTE une force l'utilise telle quelle : une force de 20 j rend 20,996 j, et non la force recalculée depuis sa gravité |
| A3 | Trois gravités croissantes rendent trois durées strictement croissantes |
| A4 | Gravité 0,01 : force 2,968 j, durée brute **3,116 j** — au-dessus du plancher, donc servie telle quelle. Le plancher n'est pas une valeur par défaut |
| A5 | Gravité 0,0 : durée brute 2,939 j, servie telle quelle. Le plancher de 2 j ne mord qu'en dessous, donc seulement si `S0` ou le seuil changent |
| A6 | Force 30 (souvenir rappelé jusqu'au plafond) : durée brute 31,495 j, **servie 30 j** — le plafond mord et il est nommé |
| A7 | Un souvenir de gravité 0,70 est servi au jour 15 après l'événement et ne l'est plus au jour 16 |
| A8 | Un souvenir de gravité 0,90 est encore servi au jour 16, où celui de gravité 0,70 a disparu : la date d'extinction se déplace avec la gravité |
| A9 | L'âge se compte depuis `e.timestamp` — l'instant de l'ÉVÉNEMENT — et non depuis `dernier_rappel` : le bloc annonce l'ancienneté d'un changement, pas celle de sa dernière lecture |
| A10 | Une entrée sous le seuil de choc n'entre jamais dans le bloc, quelle que soit sa durée |

### B — Mode de fenêtre, réglages et bornes

| Cas | Ce qui est vérifié |
|---|---|
| B1 | Mode `derivee` (défaut) : `memoire__fenetre_changements_jours` n'est **pas lu** — le porter à 1 ou à 40 ne change rien à ce qui est servi |
| B2 | Mode `fixe` : comportement d'avant le lot, coupure franche au jour déclaré, la gravité n'y change rien |
| B3 | Mode `fixe` et fenêtre 0 : ablation déclarée, aucun souvenir de choc, y compris celui de l'instant même |
| B4 | Mode `derivee` et seuil de service ≥ 1 : refus journalisé en `[ALARME]` et repli sur 0,35 — un seuil ≥ 1 rendrait une durée nulle ou négative, donc une ablation silencieuse |
| B5 | Un mode inconnu (`« glissante »`) ne s'interprète pas : `[ALARME]`, repli sur `derivee`, et la valeur fautive est citée |
| B6 | Plancher > plafond : refus journalisé, bornes remises dans l'ordre, les deux valeurs citées |
| B7 | Les quatre réglages sont lus à CHAQUE appel, jamais figés à l'import — sinon une surcharge d'environnement, donc un bras, ne servirait à rien |
| B8 | Le plafond a une trace propre : la ligne de sortie dit « plafond » et non seulement une date |

### C — La ligne de sortie de fenêtre (journal)

| Cas | Ce qui est vérifié |
|---|---|
| C1 | La ligne porte la durée calculée, la gravité, la force et le mode — pas seulement la date |
| C2 | Front montant conservé : deux décisions successives après la sortie n'écrivent qu'une ligne |
| C3 | Deux souvenirs de gravités différentes sortent à deux dates différentes et produisent **deux** lignes, chacune nommant sa gravité |
| C4 | En mode `fixe`, la ligne nomme la fenêtre en jours et ne prétend pas à une durée dérivée |

### D — L'enquête du soir : fidélité en entrée

| Cas | Ce qui est vérifié |
|---|---|
| D1 | La perception servie contient les trois blocs de `memoire_noyau` — « Mes habitudes », « Ce que je sais », « Ce qui a changé récemment » — quand ils existent |
| D2 | Elle contient le récit d'identité complet, celui-là même que le prompt de décision utilise (`get_person_identity_description`) |
| D3 | Un bloc mémoire vide ne fabrique pas de titre creux : la section est absente, pas présente et vide |
| D4 | Le jour J17 (lendemain du choc) et le jour J40 ne produisent pas la même perception : la sonde voit passer le temps |
| D5 | Le bloc mémoire servi à l'enquête est **égal**, caractère pour caractère, à celui que `memoire_noyau` rend au même instant pour le prompt de décision |

### E — L'enquête du soir : étanchéité en sortie

| Cas | Ce qui est vérifié |
|---|---|
| E1 | Après une enquête, la mémoire courte de l'agent est inchangée |
| E2 | Aucune entrée n'est ajoutée en mémoire longue, et aucun `doc_id` n'apparaît dans l'index |
| E3 | Aucune `force` ni aucun `dernier_rappel` n'a bougé : l'enquête n'est pas un rappel |
| E4 | Le journal de mémoire ne porte aucune trace d'enquête |
| E5 | La réponse n'atteint que `affinites_declarees.csv` |

### F — L'enquête du soir : les cinq prompts et leur sortie

| Cas | Ce qui est vérifié |
|---|---|
| F1 | Un jalon déclenche **cinq** appels par persona : quatre modes + les priorités |
| F2 | Un prompt de mode nomme son mode et **ne cite aucun des trois autres** |
| F3 | Le prompt de priorités ne nomme aucun mode |
| F4 | Les six critères sont posés dans l'ordre déclaré, avec leurs ancrages 0/5/10, à chaque appel |
| F5 | Une seule justification par appel, jamais une par question |
| F6 | Les modes interrogés sont déclarés (`EXPERIMENT_SURVEY_MODES`) : ajouter `train` porte l'enquête à six appels |
| F7 | Le CSV est en format LONG : une ligne par (jour, persona, mode, critère, score) |
| F8 | Les six priorités s'écrivent en lignes `critere_priorite`, dans le même fichier et le même format |
| F9 | Chaque ligne porte le fournisseur ET le modèle qui l'ont produite |
| F10 | Un score hors 0-10 lève `[ALARME] [enquete]`, et la ligne fautive est écrite avec sa valeur brute — jamais rabotée en silence |
| F11 | Un jalon qui passe sans aucune réponse lève `[ALARME] [enquete]` en nommant le jour et le persona |
| F12 | Un appel en échec n'empêche pas les quatre autres : l'enquête est partielle et le dit |
| F13 | La formule `score(mode) = Σ val(mode, critère) × prio(critère)` se calcule depuis le seul CSV, sans autre source |

### G — Le modèle journalisé (lot E)

| Cas | Ce qui est vérifié |
|---|---|
| G1 | La ligne de décision porte le fournisseur ET le modèle |
| G2 | Idem pour la réflexion STM, l'auto-réflexion LTM et l'enquête |
| G3 | Le modèle se dérive de l'instance servie ; une instance inconnue rend `?` et ne lève pas d'exception |
| G4 | Une décision servie par le cache le dit, et ne prétend pas à un fournisseur |

### H — Un modèle par fonction (lot C)

| Cas | Ce qui est vérifié |
|---|---|
| H1 | Une liste plate se comporte comme avant : toutes les catégories la reçoivent |
| H2 | Une table `catégorie → instances` route chaque appel vers sa liste |
| H3 | Une catégorie absente de la table retombe sur la liste plate, et non sur rien |
| H4 | Une catégorie à une seule instance lève `[ALARME]` : sans seconde clé, un 503 est un échec sec |
| H5 | Le ROUTAGE ne produit jamais d'épinglage dur : ni `routage.py` ni l'enquête ne posent `force_provider`, et aucune instruction de l'agent ne mêle `instances_pour` et `force_provider`. Le paramètre existant reste — la plateforme d'expériences épingle délibérément (`experiences/decideurs.py`) |
| H6 | Le binding entre dans `identite_run.json`, et deux bras aux bindings différents ne portent pas la même identité |
| H7 | Table vide `{}` : traitée comme « aucune restriction », pas comme « aucune instance admise » |

### I — Runs enfants (lot D)

| Cas | Ce qui est vérifié |
|---|---|
| I1 | `identite_run.json` d'un enfant porte `run_parent` et la liste des champs qu'il fait varier |
| I2 | Un enfant qui diffère de son parent sur un champ NON déclaré est refusé, en nommant le champ |
| I3 | Un enfant qui diffère sur un champ déclaré démarre |
| I4 | Un parent sans point de reprise fait refuser l'enfant, en le disant |
| I5 | L'amorçage copie le point de reprise du parent et pose le gel jusqu'à son instant |
| I6 | Le rejeu de l'enfant reproduit les décisions du parent sur les jours communs, décision par décision |
| I7 | Un écart sur un jour commun est refusé avec le compte des décisions divergentes, jamais absorbé |
| I8 | Un enfant n'écrit jamais dans le répertoire de son parent |
| I9 | Sans parent déclaré, rien ne change : la filiation est un mode, pas un chemin obligatoire |

### J — Les expériences, et ce qui les falsifierait

Prédictions posées avant tout run.

⚠ **CORRIGÉ le 2026-09-21.** Une première version de ce contrat affirmait que C2, C3 et C6
partageaient un plancher déterministe de 0,50 et que l'ordre de leurs gravités dépendait du
jugement du modèle. C'est faux : la composante `incident_reseau` (0,20) est portée par toute
déclaration de choc, et la gravité déterministe est donc **entièrement décidée par la
déclaration**, sans le modèle. Les valeurs réelles, depuis `docs/arch/chocs-declares.md` :

| Choc | Retard | Gravité |
|---|---|---:|
| Bouchon C1, jour 3 | 12 min | **0,40** |
| Orage C5 | 15 min | **0,45** |
| Moteur C6, jour 2 | 20 min | **0,53** |
| Bouchon C1, jour 2 | 25 min | **0,62** |
| Moteur C6, jour 1 | 30 min | **0,70** |
| Crevaison C2 | 35 min | **0,77** |
| Train supprimé C4 | 50 min | **0,86** |
| Bouchon C1, jour 1 | 60 min | **0,88** |
| Panne réseau C3 | 45 min + correspondance ratée | **1,00** |

L'échelle de gravité est **déclarable et reproductible**.

⚠ **Le palier de retard a été supprimé le 2026-09-21** (même ticket). Avant, la composante de
retard faisait palier à 30 minutes et les quatre chocs de 30 à 60 minutes rendaient tous 0,70 :
E3 aurait produit trois fois la même date d'extinction. En dessous de 30 minutes, rien n'a
changé.

| Cas | Attendu |
|---|---|
| J1 (E1) | Deux témoins identiques, mêmes graines, aucun choc : **0 écart de mode**. Un seul écart invalide la campagne |
| J2 (E2) | « fixe 14 » et « dérivée » indiscernables jusqu'au jour 29, puis divergents — la durée dérivée à gravité 0,70 vaut 15,285 j contre 14 |
| J3 (E3) | Les dates d'extinction se déplacent avec la gravité mesurée, dans l'ordre et à ± 1 jour des durées du tableau ci-dessus |
| J4 (E3) | **Falsifie :** des extinctions au même jour malgré des gravités différentes (le calcul n'est pas branché), ou dans le désordre (la gravité ne mesure pas ce qu'on croit) |
| J5 (E4) | Le plafond mord et se nomme — par un souvenir dont la force a atteint 30, ou par un `k` relevé ; **pas** par une gravité ≥ 1,30, qui n'existe pas |
| J6 (E5) | Sécurité et rapidité de la voiture chutent entre J12 et J17 |
| J7 (E5) | **Écologie de la voiture immobile.** Question témoin : si elle bouge, l'instrument est invalide et le reste de E5 ne s'interprète pas |
| J8 (E5) | Les six critères d'un même mode ne corrèlent pas au-delà de 0,9 ; au-delà, il faut descendre à six prompts par soir |
| J9 (E5) | Le mode prédit par `Σ val × prio` coïncide avec le mode choisi le lendemain dans une majorité de cas — une divergence durable est un résultat, pas un échec |
| J10 (E5) | f7 et f14 divergent sur les scores déclarés au J29, pas seulement sur les parts modales |

---

## Ce que ce contrat ne couvre pas

- **L'empilement sans révision.** Zéro contradiction de concept dans les trois bras du 077, la
  croyance pro-voiture restant à 17-18 observations après quatorze jours sans voiture. Hors
  périmètre, déclaré tel dans le ticket : le traiter ici rendrait les deux effets inséparables.
- **La comparaison aux 650 répondants humains d'Adam & Gaudou.** Hors périmètre.
- **Les deux sondes écartées le 2026-09-21** — préférence déclarée tous modes en concurrence, et
  rappel libre. Leur absence a une conséquence à écrire dans les limites du papier : la
  dissociation croyance/comportement se lira sur des courbes de perception face aux parts modales,
  et la sortie de fenêtre reste observable depuis le journal, pas depuis l'agent.

---

## Prédiction posée AVANT le premier bras traité (2026-09-21, 14 h 47)

Campagne `e2_derivee_861500`, persona **861500 (Capucine Boulay)**, choc **C6 restreint au mode
`car`**, fenêtre `derivee`, horizon 42 jours, ancre lundi 16 mars 2026.

| Jour du choc | Date | Retard | Gravité | Entre dans le bloc ? | Durée servie | Sortie prédite |
|---:|---|---:|---:|---|---:|---|
| 15 | lun 30 mars | 30 min | **0,700** | oui, **à la frontière exacte** (`>=`) | **15,29 j** | **mar 14 avril, jour 30 du run** |
| 16 | mar 31 mars | 20 min | 0,533 | **non** — sous le seuil de 0,70 | — | — |

**Le second jour de choc ne pèsera pas sur le bloc.** Il reste un souvenir épisodique, rappelé
par le vivier par mode quand la voiture est proposée, mais il n'entre ni dans « Ce qui a changé
récemment » ni dans le vivier des chocs. Un effet qui s'éteindrait le 15 avril plutôt que le 14
ne s'expliquerait donc PAS par lui.

Les quatre jalons d'enquête encadrent la prédiction sans avoir été choisis pour elle :

| Jalon | Date | Position |
|---|---|---|
| J12 | 27 mars | avant le choc — état de référence |
| J17 | 1er avril | lendemain du second jour de choc |
| **J31** | **15 avril** | **le lendemain de la sortie prédite** |
| J40 | 24 avril | longtemps après |

**Ce qui falsifierait.** Une extinction au jour 29 ou avant (le calcul sert moins longtemps que
la durée calculée), au jour 32 ou après (il sert plus longtemps), ou aucune extinction du tout.

**Le plancher de bruit contre lequel se lit l'enquête**, mesuré sur le bras témoin
`2026-09-21_11_11`, quatre jalons, aucun choc : **zéro variation sur les six critères de la
voiture** (rapidité 9, praticité 9, confort 8, sécurité 8, coût 6, écologie 3 — identiques aux
quatre jalons). Tout mouvement de la voiture dans le bras traité est donc attribuable au choc.
Le bruit résiduel se concentre sur le train (7 points sur 36 cases), mode que cette persona
n'emprunte presque jamais.

---

## Lot F — Le reliquat du ticket 048, contrat posé le 2026-09-21

Le ticket 048 est clos ce jour, ses trois points de code étant en service depuis le 2026-09-11.
Ce qu'il n'a pas exécuté est versé ici. Aucun code n'est écrit à ce jour pour ce lot ; ce contrat
se pose avant, comme les cinq autres.

### Les nombres, posés avant le code

| Grandeur | Valeur attendue | D'où elle vient |
|---|---:|---|
| `long_term_retrieval__force_base_jours` par défaut | **2,8 j** | ticket 048, reproduit à 1e-3 l'ancienne base 0,7 |
| Conversion du bras `exp_04a`, `S = 1 / λ` avec λ = 0,4 | **2,5 j** | déclaration actuelle d'`experiments.yaml:390` |
| Appel mémoire par déplacement, plancher journalier | **0,69 à 0,96** | chiffrage du 048, borne haute pessimiste par construction |
| Appel mémoire par déplacement, régime par déplacement | **1,05** | idem, soit +22 % sur la campagne |

### Cas

| # | Cas | Attendu |
|---|---|---|
| F-1 | `experiments.yaml` ne déclare plus aucune clé `memory_decay_lambda` ni `memory_horizon_days` | Épreuve de dépôt : ces deux noms sont absents du fichier. Aucun code ne les lit — une fiche qui les déclare promet un réglage que le run n'applique pas |
| F-2 | Le bras `exp_04a` déclare la constante en jours | La valeur convertie vaut **2,5** à 1e-6, et la clé porte le nom exact du réglage lu par le code |
| F-3 | Toute clé de mémoire déclarée dans `experiments.yaml` est lue par le code | Épreuve générique, qui empêche la réapparition du défaut : chaque clé du bloc `engine` préfixée `memory` ou `long_term` correspond à un attribut de `settings.agent` |
| F-4 | Le relevé du taux d'entrées par agent-jour se calcule depuis les journaux d'un run | La fonction de relevé rend, pour un répertoire de run, le nombre d'entrées de mémoire courte et le nombre de déplacements, et leur rapport. Sur un run sans observation (exécution hors simulateur) elle rend 1,0 et **le dit**, au lieu de laisser croire à une mesure |
| F-5 | La valeur relevée sur E2 tombe dans la fourchette annoncée | **0,69 ≤ appels mémoire par déplacement ≤ 0,96.** Hors fourchette, c'est le chiffrage du 048 qui est faux, pas le run — et l'arbitrage du régime se rouvre |
| F-6 | La garantie « avant le réveil » tient sous le volume mesuré | Aucune réflexion de plancher ne s'achève après le réveil de son agent sur la campagne E2. Un dépassement lève `[ALARME]` et nomme l'agent, l'heure d'échéance et l'heure réelle |

### Ce que le lot F ne couvre pas

- **Le rejeu des mesures publiées qui dépendaient de la min-max** (F3 du ticket) n'est pas un test :
  c'est un recensement suivi d'un rejeu ou d'un marquage « daté ». Il se solde par une liste, pas
  par une assertion.
- **L'admission d'un modèle local** n'est pas ici : elle est au lot C, et son protocole est un
  protocole de mesure sur jeux gelés, pas une épreuve unitaire.

### Prédiction posée avant le relevé

Le plancher journalier a été retenu par l'auteur le 2026-09-11 sur un chiffrage, jamais sur une
mesure. **Prédiction : la valeur réelle sera proche de la borne basse, 0,69 à 0,75.** La borne
haute suppose que *tous* les agents ont besoin du plancher chaque jour, ce que la cohorte v5
contredit — elle compte 10,6 % d'immobiles et 3,69 déplacements par persona mobile, donc la
plupart des agents mobiles franchissent le seuil volumétrique d'eux-mêmes.

**Ce qui falsifierait le choix du régime :** une valeur au-delà de 0,96, qui signifierait que le
plancher se déclenche bien plus souvent que prévu et que le seuil volumétrique ne sert plus à
rien ; ou une valeur sous 0,69, qui signifierait que les agents consolident moins qu'avant le
plancher — un défaut de branchement, pas un résultat.
