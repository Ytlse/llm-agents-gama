# Ticket 100 — contrat de tests

Écrit AVANT le code, le 2026-09-21. Plan d'architecture : [`plan.md`](plan.md). Questions
vivantes : [`questions.md`](questions.md).

**Les attendus du 079 ne se réécrivent pas.** Les 36 tests de `test_079_chocs.py` sont la
référence de non-régression de ce ticket : un attendu qui devrait changer pour que la migration
passe est un défaut de la migration, pas un test périmé.

---

## Le besoin

Un choc subi et un article lu entrent par deux chemins de code, l'un livré, l'autre planifié comme
sa copie. Tout leur aval est commun. Ce ticket pose un seul canal — et la seule chose qui puisse
mal tourner, c'est que la migration change en silence ce que le run du § 7.2 a déjà produit. Le
contrat est donc bâti autour d'un test en or, et le reste vient après.

Vérifié dans le code avant d'écrire ce contrat (détail et références au § 1 du plan) : la prise
`arrivee` **annexe** le vécu à l'observation au lieu d'écrire une entrée ; `Person` ne porte pas
`household.id` ; `gravite_jugee` retombe silencieusement hors grille ; `gel_actif()` coupe toute
écriture de mémoire courte pendant un rejeu ; la version du schéma de réflexion entre dans la clé
de mémoïsation ; `moves.csv` porte déjà trois colonnes concernées.

---

## Les principes

**Une migration se prouve par l'égalité, pas par l'argument.** Le lot 1 ne livre aucune fonction
nouvelle. Son seul critère est qu'un rejeu rende le même fichier.

**Un refus vaut mieux qu'un run muet.** Toute faute de déclaration — jour hors run, foyer absent,
empreinte fausse, règle inconnue, gravité posée à la main — arrête le chargement. Un choc fantôme
coûte soixante jours de run et ne laisse aucun symptôme ; c'est la leçon du 079 et elle ne se
rediscute pas.

**Aucun repli silencieux, nulle part.** Un échelon hors grille au jugement est un refus et une
`[ALARME]`, pas un échelon médian. Une pénurie LLM fait attendre, elle ne fait pas baisser la
barre.

**L'absence de mesure n'est pas un zéro.** Une cellule vide reste vide ; un rôle sans effectif
sort « non concluant » ; une `importance_estimee` non demandée est absente, pas nulle. Dans ce
dépôt, zéro est la valeur du trajet parfait et du score parfait — les deux ont déjà menti.

**Un seul saut se teste comme une invariante, pas comme un comportement.** Le test n'est pas « la
croyance ne repart pas dans ce cas-ci » mais « aucune croyance d'origine `entendu` n'est jamais
candidate au partage, quelle que soit son histoire ultérieure ».

---

## Lot 1 — migration

| # | Règle | Comment elle se vérifie |
|---|---|---|
| R1 | **Le test en or.** `c6_voiture_suspecte.yaml`, jugement éteint, rejoué sur le nouveau paquet rend un `evenements.jsonl` égal **champ à champ** à `chocs.jsonl` archivé | comparaison ligne à ligne, aux deux champs ajoutés près (`canal`, `moment`) ; tout champ existant qui diffère fait échouer |
| R2 | Les **36 tests** de `test_079_chocs.py` passent **sans modification de leur attendu** | exécution telle quelle, par l'adaptateur `llm/chocs.py` |
| R3 | Les huit déclarations de `config/chocs/` se chargent au format 079 et journalisent une dépréciation nommant le fichier | chargement des huit, un `warning` attendu par fichier |
| R4 | Les six cas migrés dans `config/evenements/` rendent, pour chaque jour, le **même** `EvenementApplique` que leur original | comparaison croisée ancien format / nouveau format |
| R5 | Une déclaration portant un champ `gravite` est **refusée** | `RefusDEvenement`, message nommant le champ |
| R6 | `canal` ou `moment` inconnu, ou couple impossible (`lu` + `arrivee` sans texte par jour) : refusé | un cas par branche |
| R7 | `Person.household_id` est renseigné par les **deux** chemins de chargement | v6 chargée par chacun, tous les agents portent l'identifiant |
| R8 | `MemoryEntry.origine` : écrit, relu, et **ignoré** par un `from_dict` qui ne le connaît pas | aller-retour `to_dict`/`from_dict` + relecture d'un dict sans le champ |
| R9 | Une entrée sans `origine` se **lit** comme vécue sans le **déclarer** | `origine is None` et `origine_effective == "vecu"` |
| R10 | `valence` et `origine` traversent `add_short_term_memory` jusqu'à la `MemoryEntry` | écriture puis relecture du tampon |
| R11 | `[ALARME]` si une règle `foyers` ou le partage au foyer est actif alors qu'aucun agent ne porte `household_id` | population sans `household`, drapeau posé |

---

## Lot 2 — prise `reveil`, canal `lu`

| # | Règle | Comment elle se vérifie |
|---|---|---|
| R12 | L'injection `reveil` a lieu **avant** la première décision du jour et **une seule fois** par agent et par journée | bascule de journée appelée trois fois dans la même journée simulée : une seule entrée |
| R13 | Une entrée `canal: lu` ne porte **aucun** retard, aucun incident réseau, aucune correspondance ratée | `effet_physique is None`, gravité déterministe nulle |
| R14 | Un `effet_physique` non nul sur `canal: lu` + `moment: reveil` est **refusé** au chargement | message citant le § 9 du ticket |
| R15 | **Garde de citation** : un texte dont l'empreinte diffère de la déclaration **ou** du manifeste est refusé ; les deux comparaisons sont faites | un cas par comparaison, plus un cas où déclaration et fichier concordent contre un manifeste faux |
| R16 | Les cinq articles du 059 se chargent, leur empreinte correspondant au `MANIFEST.yaml` du dépôt | chargement des cinq |
| R17 | La mention `Translated from French` est **dans** l'entrée servie | recherche dans le texte déposé |
| R18 | Règle `foyers` : `lecteurs_par_foyer` lecteurs par foyer, tirage **déterministe** et stable sur trois exécutions, tirage journalisé | même déclaration jouée trois fois |
| R19 | Un foyer déclaré absent de la population, ou sans membre mobile, est refusé | deux cas |
| R20 | Fenêtre tirée : le jour est dans `[a, b]`, **stable** par foyer, et **différent** d'un foyer à l'autre sur un échantillon de vingt | tirage sur vingt identifiants |
| R21 | Fenêtre `[a, b]` avec `b < a`, ou hors horizon du run : refusée | deux cas |
| R22 | Les agents non exposés du même foyer ne reçoivent **rien** — ni texte, ni entrée, ni gravité | témoin interne vérifié explicitement |
| R23 | Un article ne sollicite **aucun** moteur d'itinéraire : ni OTP, ni GTFS, ni OSMnx | doublures qui échouent si appelées, comme R14 du 079 |

---

## Lot 3 — jugement à l'injection

| # | Règle | Comment elle se vérifie |
|---|---|---|
| R24 | Un échelon **hors grille** ou absent : l'exposition est refusée, une `[ALARME]` nomme l'agent, le jour et l'échelon reçu, et **aucune** valeur de remplacement n'est écrite | modèle doublé rendant `"catastrophic"`, puis `""`, puis un champ manquant |
| R25 | Les **deux** vocabulaires d'échelon sont acceptés, anglais et français | `serious` et `grave` donnent la même gravité |
| ~~R26~~ | ⚠ **RETIRÉE par la décision D7 du 2026-09-22.** La règle disait : sur un `canal: vecu`, un jugement inférieur à la gravité déterministe ne la dégrade pas. La gravité est désormais l'estimation de l'agent, **seule**, dans les deux canaux. La règle qui remplace R26 est R26 bis |
| R26 bis | Sur un `canal: vecu`, la gravité retenue **est** l'estimation, quelle que soit la gravité déterministe | dépannage de 30 min jugé `negligible` : gravité retenue = **0,10**, et non 0,70 |
| R27 | Sur un `canal: lu`, le jugement **décide seul** : `gravite_concept(estimée, 0.0) == estimée` | cinq échelons, cinq gravités |
| R28 | `jugement: aucun` : **aucun** appel au modèle, `importance_estimee` **absente** et non nulle, `importance_retenue` = gravité déterministe | doublure qui échoue si appelée |
| R29 | Un appel de jugement par **exposition**, jamais par trajet ni par agent-jour sous `cadence: jour` | compteur d'appels contre compteur d'expositions |
| R30 | Le temps d'attente du jugement est journalisé par exposition et agrégé à la bascule de journée, **même à zéro exposition** | lecture du journal sur une journée nominale |
| R31 | La valence rendue par le jugement atteint la `MemoryEntry` | trois valences, trois entrées |

⚠ **Deux tests déjà écrits contredisent R26 bis** et échoueront tant qu'ils ne sont pas repris :
`test_R26_un_jugement_faible_ne_degrade_pas_un_fait_mesure` dans
`services/llm-agents/tests/test_100_lot3_jugement.py` attend 0,70 là où D7 exige 0,10, et son
docstring cite la protection asymétrique que D7 supprime. `test_R26bis_un_jugement_fort_releve_la_gravite`
reste valable par accident : un jugement fort donne la même valeur avec ou sans plancher. Le code
n'est pas repris ici — `gravite_concept` porte un commentaire « NON NÉGOCIABLE » que seule une
décision explicite peut lever, et D7 est cette décision. Voir le § 5 bis du ticket pour la garde
de remplacement, qui reste à spécifier (Q11).


---

## Lot 4 — le foyer

| # | Règle | Comment elle se vérifie |
|---|---|---|
| R32 | Drapeau **éteint** : aucun bloc de foyer dans l'appel, et le contexte de réflexion est **identique octet pour octet** à celui d'avant le lot | comparaison de contexte sur un même vécu |
| R33 | **Récit du soir** : tous les épisodes de la journée de chaque autre membre présent, **sans** filtre de gravité (D1), lecture du matin comprise | foyer de trois, une journée mixte |
| R34 | Le récit n'est **jamais** écrit dans la mémoire du receveur : il n'existe que dans l'appel | mémoire du receveur inspectée après consolidation |
| R35 | Borne du récit : troncature **comptée** et **alarmée**, tri par gravité décroissante puis par heure | foyer produisant plus d'énoncés que la borne |
| R36 | **Un seul saut** : aucune croyance d'origine `entendu` n'est jamais candidate au partage, y compris après confirmation ultérieure par un trajet du receveur | Q2 testée explicitement, sur trois nuits |
| R37 | Une croyance née de la journée du receveur porte `origine: vecu` et circule normalement, **même si** le sujet a été entendu la veille | le pendant de R36 : D2 ne stérilise pas le receveur |
| R38 | R1 à R6 du 078 : un cas de refus **par règle**, compté séparément | six cas |
| R39 | Le repère `foyer_lu_jusqu_a` est **par receveur**, persisté au point de reprise de 3 h, et une reprise à chaud ne fait **pas** ré-entendre une nuit déjà entendue | reprise simulée |
| R40 | `SCHEMA_REFLEXION_VERSION == 4` et une réponse mémoïsée sous la version 3 fait **manquer** le cache | clé calculée avant/après |
| R41 | Le champ de provenance est demandé **dans les deux bras** ; drapeau éteint, il vaut `lived` partout | comparaison des deux schémas rendus |
| R42 | Un membre `immobile`, ou absent de la cohorte, ne raconte rien et n'entend rien | deux cas |

---

## Lot 5 — sorties et mesure

| # | Règle | Comment elle se vérifie |
|---|---|---|
| R43 | `evenements.jsonl` porte les seize champs annoncés, pour les deux canaux, avec les mêmes noms | une ligne par canal |
| R44 | `moves.csv` : les colonnes renommées sont lues **sous les deux graphies**, et la graphie trouvée est journalisée | un run archivé (ancienne graphie), un run neuf |
| R45 | `evenement_par_jour.csv` : **une** fonction, deux canaux, mêmes colonnes | jeux de forme pour chaque canal |
| R46 | Les quatre règles du 093 : journée à 3 h, veille = jour **vécu** précédent, cellule vide ≠ zéro, jours relatifs **redérivés** des horodatages | quatre tests, comme au 093 |
| R47 | Un rôle sans effectif sort **« non concluant »**, jamais 0,0 | rôle `temoin` vide |
| R48 | Le souvenir non apparié laisse la colonne **vide**, jamais `faux` | vécu reformulé par la réflexion |
| R49 | La figure sort « non concluant » plutôt qu'une courbe vide sous l'effectif minimal déclaré | jeu sous-dimensionné |
| R50 | Le jour relatif est défini **tous** les jours du run, y compris avant et après l'événement | journée nominale |

---

## Lot 6 — leviers et documentation

| # | Règle | Comment elle se vérifie |
|---|---|---|
| R51 | `make run EVENEMENT=<nom>` écrit la clé attendue ; `EVENEMENT=0` la retire ; un nom inconnu **échoue** en listant les cas livrés | trois invocations |
| R52 | `CHOC=` et `PRESSE=` écrivent la même clé et disent lequel a servi | deux invocations |
| R53 | `experiences/experience.py` n'oppose plus le refus E6 aux deux types d'événement | une expérience portant chacun |
| R54 | Après suppression de `llm/chocs.py`, aucun import résiduel dans le dépôt | recherche sur l'arbre, hors archives |
| R55 | Le corpus est lisible **depuis le conteneur** `controller` | lecture d'un `brut.txt` par le chemin monté |

---

## État de couverture au 2026-09-22

| Lot | Fichier | Tests | État |
|---|---|---|---|
| 1 | `tests/test_100_lot1_migration.py` | 21 | **livré** — dont le test en or (R1) |
| 1 | `tests/test_079_chocs.py` | 36 | **passent inchangés** contre le paquet neuf |
| 1 | `tests/test_077_lotH_vecu_et_cadence.py` | 24 | **passent inchangés** |
| 2 | `tests/test_100_lot2_canal_lu.py` | 33 | **livré** — R12 à R23, plus la correction du défaut du 22/09 |
| 3 | `tests/test_100_lot3_jugement.py` | 22 | **livré** — R24 à R31 |
| 4 | `tests/test_100_lot4_foyer.py` | 28 | **livré** — R32 à R42, plus les quatre gardes G1 à G4 |
| 5 | `scripts/tests/test_100_lot5_sorties.py` | 17 | **livré** — R43 à R50, figure unique et tableau des quatre voies compris |
| 6 | — | — | **livré** : levier `EVENEMENT=`, alias, montage, E6 levé, `evenements.md` |

Suite `services/llm-agents` : **1888 passés, 6 ignorés, 0 échec**. Suite `scripts` : **63 échecs,
identiques avant et après**, vérifié par rejeu sur l'arbre remisé.

**Il reste une seule chose au ticket** : le run court de non-régression sur `c6_voiture_suspecte`,
qui conditionne la suppression de `llm/chocs.py` (Q11). Le test en or rejoue une trace, pas un
run : il ne dit rien du chemin GAMA.

Suite `services/llm-agents` : **1835 passés, 6 ignorés, 0 échec**. Suite `scripts` : 63 échecs,
**identiques avant et après**, vérifié en rejouant sur l'arbre remisé — tableau de bord Streamlit,
météo, forêt, includes GAMA, aucun lié à ce ticket.

**Ce que les lots ont changé au contrat, et pourquoi.**

- **Q10 tombe.** Le plan prévoyait de renommer les colonnes `Choc` et `Jour relatif au choc` de
  `moves.csv`, avec une double graphie en lecture pendant une version. Elles ont été **gardées**
  et deux colonnes ajoutées à côté (`Rôle`, `Raison d'exposition`) : les renommer aurait cassé
  la relecture des runs archivés, qui portent les chiffres publiés du § 7.2, pour un gain de
  vocabulaire. R44 n'a plus d'objet sous cette forme.
- **R28 change de motif.** L'ablation `jugement: aucun` reste, mais elle n'est plus un bras de
  campagne : l'auteur a tranché (Q4, 2026-09-22) que la prochaine campagne remplacera
  l'existante. Elle reste le mode du test en or.
- **R44 tombe avec Q10**, et R48 change de forme : le tableau des quatre voies ne se contente
  pas de laisser une cellule vide, il **compte et nomme** les décisions où l'événement n'a été
  retrouvé par aucune voie. Une ligne de cellules vides se lit trop facilement comme « cela n'a
  pesé sur rien ».
- **L'attribution par `agent_id=`** n'était pas prévue. Elle est nécessaire pour le canal `lu` :
  tous les lecteurs d'un même article partagent le même texte, donc chercher le texte seul ne
  dirait pas qui l'a vu.
- **La séparation lecture / armement** n'était pas au contrat. `charger()` vérifie une
  déclaration qu'on ne veut pas jouer — sans quoi on ne pourrait pas contrôler que les cinq
  articles concordent avec leur manifeste ; `initialiser()` refuse d'armer un run. Le cas qui
  l'exige aujourd'hui est un `canal: lu` sans jugement.

**Deux règles ont changé de forme en chemin, et c'est dit plutôt que silencieux.** R6 du lot 1
portait « ce qui n'est pas livré est refusé en nommant son lot » ; le lot 2 ayant livré le canal,
la prise et la règle `foyers`, il ne reste sous R6 que le refus d'une valeur hors vocabulaire, et
le jugement non livré a son propre test (lire une déclaration et armer un run sont deux choses).
R23, la frontière « aucun moteur d'itinéraire », s'applique au paquet entier et non au seul
fichier, ce qui la durcit.

---

## Ce qui n'est pas testé ici, et pourquoi

**Le comportement des agents.** Aucun test de ce contrat ne dit qu'un article change une décision,
ni qu'une croyance se propage. Ce sont des résultats de campagne, ils se mesurent sur un run et se
préenregistrent ailleurs — au 059 pour la presse, au 095 pour la durée. Un test unitaire qui les
affirmerait ne ferait que vérifier sa propre doublure.

**Le chemin GAMA.** Le test en or rejoue une trace, pas un run. Le lot 6 demande un run court de
non-régression sur `c6_voiture_suspecte` avant la suppression de `llm/chocs.py` : c'est le seul
endroit où l'intégration se vérifie, et il coûte des appels.

**Le volume du prompt de consolidation.** D1 y ajoute la journée entière de chaque autre membre ;
c'est la seule addition du ticket dont le volume n'est pas borné par une règle d'ancrage. Le
chiffre se relève sur run, pas en test — mais R35 garantit qu'une troncature ne passe jamais
inaperçue.
