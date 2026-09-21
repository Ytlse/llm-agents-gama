# Ticket 077 — La mémoire apprend sur des observations fausses, et ne peut pas se corriger

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-15.
>
> **Objet.** Le run de trente jours du [075](ticket_075_journal_de_memoire_et_run_60_jours.md) a
> fonctionné : 276 consolidations, 231 concepts, 50 auto-réflexions, aucun plantage. Il a aussi
> montré que **ce que la mémoire apprend est faux**, et que **le mécanisme de correction des
> concepts n'a jamais pu s'exécuter**. Ce ticket répare les causes, toutes localisées dans le
> code, et instrumente ce qui manque pour mesurer l'effet de la mémoire au run suivant.
>
> **Relation au 071 et au 075.** Le 071 a livré le mécanisme, le 075 l'a rendu lisible et a
> produit le run. Celui-ci ne change **aucune règle** de la mémoire — ni gravité, ni oubli, ni
> score de rappel, ni opérations de concept. Il répare ce qui empêche ces règles de s'appliquer.
>
> **Contrat de test.** `specs/ticket_077/tests.md`, écrit AVANT le code, comme les lots du 071.
>
> **Source des mesures.** `experiments/archive/2026-09-14_23_58` — 5 habitants, 30 jours simulés
> présents (16 mars → 17 avril 2026), 514 lignes de `moves.csv`, `gemini-3.1-flash-lite`.

---

## 0. Ce que le run a montré

L'auteur a ouvert les cinq journaux et posé la bonne question : *pourquoi la même leçon revient-elle
sans cesse ?* La réponse ne tient pas au modèle. Elle tient à quatre défauts de la chaîne, chacun
vérifiable sur les fichiers du run.

| Constat | Mesure | Où |
|---|---|---|
| Concepts produits | 231 | 20 (11195) · 20 (41275) · 35 (609) · 62 (899549) · 94 (616478) |
| Opérations appliquées | 231 créations, 70 confirmations, **0 précision, 1 contradiction** | journaux `memoires/*.md` |
| Concepts restés à confiance 0,50 | 225 sur 231 | métadonnées LTM |
| `known_beliefs` vide à la réflexion | **159 blocs sur 235 (68 %)** | `llm_exchanges.jsonl` |
| Purges, mises hors service en 30 jours | **0** | journaux |
| Marches fantômes dans les observations | **398 événements sur 412** de distance nulle | `agent_memory_events.jsonl` |
| Trajets en voiture journalisés en transport collectif | **253** | idem |
| Auto-réflexions LTM servies à une décision | **2 sur 336 prompts** | `llm_exchanges.jsonl` |

**Le point qui renverse le diagnostic évident.** Quand `known_beliefs` n'est PAS vide, le modèle
confirme : **74 confirmations demandées pour 76 blocs non vides**. Le modèle n'est pas bavard, il
n'a presque jamais rien à corriger. Toute la redondance est produite en amont de lui.

---

## 1. Lot A — Le vocabulaire des modes (cause racine)

`llm/axes.py:mode_canonique()` appelle `primary_canonical()` de la hiérarchie AUAT/CEREMA, qui
attend des **étiquettes de jambes** (`foot`, `bus`, `bicycle`). Le schéma JSON de la réflexion
(`stm_reflection`) impose au modèle un tout autre vocabulaire : les **modes canoniques**
(`walking`, `cycling`, `car`, `public_transport`, `train`, `motorbike`, `any`). Vérifié à
l'exécution :

```
walking          -> None        foot     -> 'walking'
cycling          -> None        bus      -> 'public_transport'
public_transport -> None        bicycle  -> 'cycling'
car              -> 'car'       metro    -> 'public_transport'
```

**Un seul mot sur sept traverse.** Conséquences en cascade, toutes constatées :

1. `axe_objet` vaut `None` sur **211 concepts sur 231** ;
2. le panier `(axe_objet, axe_motif)` ne peut plus désigner de candidats — `_concepts_du_jour`
   rend une liste vide, et `known_beliefs` arrive vide dans le prompt ;
3. le **vivier B** du rappel est vide (alarme tirée dans `app.log` : *« vivier B vide sur 79 % des
   200 dernières décisions »*, puis *« 100 % du top-K vient du SEUL vivier sémantique »*) ;
4. le lot 3 du 071 — un concept se corrige au lieu de s'empiler — **n'a jamais pu s'exécuter**.

La signature est nette dans les chiffres par agent : `known_beliefs` est vide **100 % du temps
(63/63) pour Adrienne (616478)**, qui n'a pas de voiture, et **17 % du temps pour Valérie (41275)**,
qui ne fait que de la voiture. Les seuls concepts porteurs d'un axe objet sont les concepts `car`,
le seul mot que la hiérarchie reconnaît. Les 70 confirmations appliquées du run portent toutes sur
des concepts `car`.

**Ce qui est demandé.** Que `mode_canonique` accepte les deux vocabulaires : un mode déjà canonique
se rend lui-même, une étiquette de jambes passe par la hiérarchie. Aucune cascade écrite à la main,
aucun fourre-tout : un mot hors des deux vocabulaires reste `None` et continue d'être compté par
`MODES_INCONNUS`.

⚠ **Les deux avertissements existaient et ont été émis** (`[axes] mode inconnu de la hiérarchie :
« walking »`, puis « public_transport »), une fois chacun, en WARNING, au milieu de 355 000 lignes
de journal. Ils n'ont alerté personne. Le contrat de test doit donc porter une règle qui **échoue**,
et pas seulement un journal qui prévient : aucun concept écrit ne doit avoir `axe_objet` vide quand
le modèle a renseigné son champ `mode`.

**Effet mesuré de la correction**, en rejouant les 310 concepts du run à travers la fonction
corrigée — c'est la validation par l'échec appliquée aux données, et non à une intuition :

| Agent | Concepts portant un axe d'objet, avant | Après |
|---|---:|---:|
| 11195 Constance | 6 | 24 |
| 41275 Valérie | 43 | 60 |
| 609 Xavier | 7 | 45 |
| 616478 Adrienne | **0** | **95** |
| 899549 Corinne | 11 | 78 |
| **Total** | **67 (22 %)** | **302 (97 %)** |

Les 8 concepts restants portent `any`, qui signifie « ce concept ne porte pas sur un mode » : ils
doivent rester sans axe, et ils ne sont pas comptés comme modes inconnus.

---

## 2. Lot B — Ce que GAMA raconte à la mémoire

Les observations envoyées à la STM décrivent des trajets qui n'ont pas eu lieu. Deux bugs distincts,
tous deux dans `services/GAMA/CityTransport/models/Inhabitant.gaml`.

### B1 — L'attente avant le départ est journalisée comme une marche

`step_started_at` est posé à la réception du plan (ligne 187), alors que l'agent attend
`CURRENT_TIMESTAMP >= schedule_at` pour bouger (ligne 325). Le premier segment absorbe donc toute
l'attente. Preuve : sur les 416 événements `[ WALK ] Walked to ''` de **distance nulle** et sans
arrêt d'origine, **398 ont une durée exactement égale au `departure_delay_s`** de la même arrivée
dans `gama_arrivals.csv`.

Ce sont ces marches-là que les agents ruminent. Xavier (609) prend la voiture **117 fois sur 117**
et **62 de ses 83 réflexions** parlent de marches de cinq à douze heures. Ses dix auto-réflexions
long terme consolident la même chose : *« I have fallen into a habit of walking for over five hours
daily »*. Aucune de ces marches n'a eu lieu.

**Ce qui est demandé.** Que le chronomètre d'étape démarre au **premier déplacement réel**, pas à la
réception du plan. L'attente avant départ, si elle doit être observée, est un événement de son
propre type — jamais un segment de marche.

### B2 — La voiture est journalisée en transport collectif

Le marqueur `__DIRECT_CAR__` passe par `submit_ob_transit` (ligne 350), puis par le gabarit
`ob_transit.j2`, dont les filtres interrogent le GTFS et ne trouvent rien. Résultat, **253 fois** :

```
[ PUBLIC TRANSPORT ] Trip by Unknown Unknown; From: ''; To: ''; Actual duration: 9 minutes.
```

Un agent qui conduit tous les jours lit chaque soir qu'il a pris un transport en commun sans nom,
entre deux arrêts sans nom. Sur les 382 événements `PUBLIC TRANSPORT` du run, **270 sont des
« Unknown Unknown »**, dont la totalité des 253 trajets voiture et 15 trajets réellement collectifs.

**Ce qui est demandé.** Un événement propre pour les modes individuels (`[ CAR ]`, `[ BIKE ]`) avec
durée et distance, et un gabarit qui ne prétend pas nommer une ligne qui n'existe pas. Un trajet
collectif dont la ligne est introuvable au GTFS doit être **signalé**, pas maquillé en « Unknown ».

---

## 3. Lot C — Les trajets à itinéraire unique sont invisibles à la mémoire

**116 trajets sur 514** (méthode « Un seul itinéraire disponible ») n'écrivent **aucune** entrée
`TRAVEL_PLAN` en mémoire courte. Ils sont exécutés, ils produisent des observations d'arrivée, mais
la mémoire ne sait pas qu'une décision a eu lieu.

Cela casse le **journal des habitudes** du lot 4 (bloc « Mes habitudes » du prompt). À l'arrivée,
`simulation_controller.py:2056` remonte le tampon court jusqu'à la **dernière entrée porteuse d'un
`axe_objet`** — donc jusqu'à la dernière décision *prise par le LLM*, qui peut être celle du trajet
précédent. Le motif et le créneau attribués sont alors ceux de ce trajet-là.

Conséquence mesurée : Xavier fait 58 retours à la maison ; son journal d'habitudes n'en compte
**aucun**, et n'affiche que `work|midi: car 46` et `work|matin: car 2` — 48 entrées pour 113
arrivées. Valérie fait 58 retours ; son journal ne connaît que `leisure|midi` et `shop|matin`. Le
bloc « Mes habitudes » ne ment pas seulement par omission : il range les retours sous le motif de
l'aller.

**Ce qui est demandé.** Qu'un trajet à itinéraire unique écrive son entrée de décision comme les
autres — c'est un choix contraint, pas une absence de trajet — et que le journal des habitudes lise
le motif et le créneau de **l'arrivée qu'il enregistre**, jamais d'une entrée antérieure.

---

## 4. Lot D — Ce que le rappel sert

### D1 — Les auto-réflexions long terme ne sont presque jamais servies

Cinquante appels LLM produisent dix synthèses par agent. Elles sont bien écrites en LTM (50 sur 50
retrouvées dans les métadonnées), et elles apparaissent dans **2 prompts de décision sur 336**. Le
dispositif coûte un appel tous les trois jours et ne pèse sur presque aucune décision.

À trancher dans ce ticket, pas plus tard : ou bien la synthèse entre dans le bloc noyau — c'est sa
place, entre « Ce que je sais » et les épisodiques — ou bien l'auto-réflexion est éteinte. La
laisser telle quelle, c'est payer un appel pour un texte que personne ne lit.

### D2 — Le rappel s'auto-renforce

Un rappel augmente la force du souvenir, donc sa probabilité d'être rappelé. Sur les journaux de 609
et 616478, **128 rappels sur 133 servent 10 souvenirs**, et ce sont toujours les mêmes : le souvenir
le plus servi l'est **55 fois** chez Corinne, 48 fois chez Adrienne, 34 fois chez Valérie. Ce sont
les réflexions des premiers jours — donc les plus contaminées par les marches fantômes du lot B.

Le bloc `History` du prompt fait **2 636 caractères en médiane**, dont trois narratifs de 150 mots.
Le prompt passe de 724 à ~2 100 jetons par agent dès le quatrième jour, puis stagne : la mémoire ne
grandit plus, elle tourne.

**Ce qui est demandé.** Une mesure, pas encore un correctif : journaliser, sur la fenêtre déjà en
place, la **concentration des rappels** (part du top-K occupée par les dix souvenirs les plus servis)
et lever une alarme sur front montant au-delà d'un seuil à fixer dans le contrat de test. Le lot B
retire la cause principale ; il faut pouvoir dire si elle a suffi.

---

## 5. Lot E — Ce qui manque pour mesurer l'effet de la mémoire

Le run actuel ne permet pas de dire si la mémoire change les décisions. À instrumenter avant le
prochain :

1. **Les souvenirs servis, par décision** : identifiant, type, vivier d'origine (A/B/C), score
   composite et rang. Aujourd'hui le journal dit « 10 souvenirs servis » et leur incipit.
2. **L'index proposé et l'index tiré, par décision.** `moves.csv` porte la répartition, mais
   `plan_selected_index` n'est renseigné que dans `pipeline_timing.csv`, et seulement pour 66
   trajets sur 514.
3. **Le descriptif de chaque option présentée** (mode, durée, correspondances, attente estimée),
   aujourd'hui reconstructible seulement depuis le texte des prompts. ⚠ **Chiffre corrigé le
   2026-09-15**, après recoupement par le générateur du lot F et recalcul depuis la source :
   l'appariement par `(agent, jour, motif)` puis heure la plus proche retrouve **298 des 314
   décisions passées par un prompt, soit 95 %**. La première rédaction annonçait « 247 sur 430 »,
   avec deux erreurs qui se cumulaient : un appariement exigeant l'heure exacte, et un dénominateur
   incluant les 116 trajets à itinéraire unique, qui n'ont JAMAIS figuré dans un prompt — c'est
   précisément l'objet du lot C. Le besoin reste entier : 16 décisions restent non appariables, et
   l'option effectivement tirée n'est journalisée nulle part.
4. **Les `known_beliefs` montrés et l'opération demandée**, pour mesurer le taux de confirmation
   *possible* contre *réalisé* — le chiffre qui a permis d'innocenter le modèle ici.
5. **Le statut cache ou appel direct**, par décision.
6. **Un run témoin sans mémoire**, mêmes cinq agents, mêmes graines de tirage et de météo. Sans lui,
   la bascule de Corinne vers la voiture en semaines 4 et 5 ne peut pas être attribuée.

⚠ **Deux contaminations à exclure des mesures du run actuel**, et à empêcher au suivant : les **84
trajets rejoués** après le redémarrage de 06:55 (les 16 au 21 mars figurent deux fois dans
`moves.csv` ; l'alarme `[reprise] aucun point de reprise valide` a bien été levée), et les **5
arrivées perdues** de Constance (retours de 18:56 jamais reçus, d'où des « marches » de 36 heures).

---

## 6. Lot F — Le rapport d'analyse par persona

Un générateur, pas un rapport à la main : le prochain run posera les mêmes questions.

`scripts/analysis/memoire/` — bibliothèque standard et SVG en ligne, sur le modèle de
`scripts/synthesis/charts.py`, sans nouvelle dépendance.

| Module | Rôle |
|---|---|
| `sources.py` | lecture de `moves.csv` (rejeu exclu), `gama_arrivals.csv`, `agent_memory_events.jsonl`, `llm_exchanges.jsonl` (JSON concaténé multi-lignes), métadonnées LTM, `memoires/*.md`, population |
| `mesures.py` | redondance des concepts, contamination des observations et des réflexions, décisivité et entropie par semaine, concentration des rappels, part des raisons citant l'expérience |
| `graphiques.py` | `frise_modes` (une ligne par motif, une case par jour, palette officielle du dépôt) · `tableau_itineraires` (une ligne par itinéraire distinct, une colonne par jour, **bleu clair proposé / bleu foncé retenu**) · `courbe_semaines` · `barres_rappels` |
| `rapport.py` | HTML autonome, une section par persona plus une synthèse, CLI `python -m scripts.analysis.memoire.rapport <run> -o <sortie>` |

Sortie sous `docs/traces/<date_heure>_…/`, hors git. Cible `make memoire-rapport RUN=…`.

**Appariement des itinéraires proposés.** Ils ne vivent que dans le texte des prompts. Retenu :
appariement par `(agent, jour, motif)` avec l'heure de départ la plus proche, et une colonne grise
déclarée quand l'option n'est pas retrouvée. Le lot E.3 rend cet appariement inutile au run suivant ;
il reste nécessaire pour relire celui-ci.

⚠ **Les dénominateurs du rapport ne sont pas ceux de ce ticket, et c'est voulu.** Le rapport compte
sur les trajets hors rejeu et énonce sa règle sous chaque tableau ; le ticket compte sur les
événements appariés à une arrivée. Deux mesures d'une même chose sous deux règles explicites valent
mieux qu'un chiffre unique dont la règle est perdue. Ce qui a été recoupé et concorde : les **84
trajets rejoués** (deux méthodes indépendantes — l'heure d'écriture après redémarrage, et la clé
`(personne, activité, temps simulé)`), les **159 blocs de réflexion vides sur 235**, et le souvenir
le plus servi **55 fois**.

---

## 7. Ce que ce ticket refuse, et pourquoi

Un rapport d'analyse indépendant a été produit sur le même run. Il confirme trois choses par une
autre route — le taux de redondance, la vacuité de `known_beliefs`, l'absence de fusion sémantique —
et propose quatre correctifs. Deux sont écartés, et il faut que ce soit écrit.

**Écarté : plafonner la marche dans GAMA à 45 minutes, avec repli taxi ou voiture.** Le diagnostic
sous-jacent est faux : les marches de cinq à douze heures ne sont pas des marches. Leur distance est
**nulle** et leur durée est **exactement** le retard au départ (398 cas sur 412). Aucun agent ne
marche à 4 km/h jusqu'à sa destination. Poser un repli modal reviendrait à ajouter un mécanisme de
dégradation pour masquer un bug de chronomètre — et à fabriquer des parts modales que rien ne
fonde. Le correctif est B1.

**Écarté : déduplication par similarité cosinus au seuil 0,82 avant écriture.** Le lot 3 du 071 a
examiné et rejeté cette voie, en toutes lettres : *« un seuil fixe sur un plongement francophone est
arbitraire et demanderait une calibration que rien ne fonde »*. Le motif est intact. Surtout, le
seuil s'attaquerait à un symptôme dont la cause est connue et tient en une fonction : tant que
`known_beliefs` arrive vide, le modèle **ne peut pas** confirmer, et il le fait 74 fois sur 76 dès
qu'on lui donne de quoi. Réparer le lot A d'abord, mesurer, et rouvrir la question seulement si la
redondance persiste.

**Retenu : sélection sémantique des `known_beliefs`**, en second rideau. Si, le lot A réparé, le
panier exact laisse encore des blocs vides, interroger ChromaDB sur les événements du jour pour
proposer les quelques concepts les plus proches. Condition d'ouverture : une mesure du taux de
blocs vides après le lot A, pas avant.

**Retenu, reformulé : la fusion à l'auto-réflexion.** Elle ne doit pas être un appel de plus. Le
lot D1 tranche déjà le sort de l'auto-réflexion existante : si elle est conservée, c'est là que la
fusion des reformulations a sa place, dans un appel qui a déjà lieu. C'est la règle du 071, lot 3 —
coût marginal nul — appliquée à une autre étape.

---

## 7 bis. État de la livraison (2026-09-15)

Lots A, B, C, D2, E et F livrés. Contrat `specs/ticket_077/tests.md` écrit avant le code, 92 tests
dédiés, suite complète du service à 1 286 tests verts.

**Ce qui a été vérifié, et comment.**

| Vérification | Moyen |
|---|---|
| Le lot A répare bien la cause racine | les 310 concepts du run rejoués à travers la fonction corrigée : 22 % → 97 % d'axes d'objet |
| Le modèle GAMA compile après le lot B | `gama-headless -xml` dans `gamaplatform/gama:2025.06.4`, et une faute de frappe volontaire fait bien échouer la compilation |
| Le rendu des observations | voiture et vélo rendus `[ CAR ]` / `[ BIKE ]` ; ligne connue inchangée ; plus aucun « Unknown Unknown » |
| Les règles structurelles GAML | vérifiées sur la source, faute de banc d'essai GAML, comme le fait déjà le ticket 075 |
| Le rapport du lot F | produit sur le run de référence, ouvert et lu : cinq personas, 28 graphiques, aucune ressource externe, et deux exécutions octet pour octet identiques |

**Run de vérification du 2026-09-15** — cinq habitants, gemini-3.1-flash-lite, 12 jours simulés
obtenus sur 15 demandés (une campagne planifiée a repris la main sur le contrôleur à 11:15).
Détail et réserves : `docs/traces/2026-09-15_11-45_run_15j_apres_ticket_077/`.

| Indicateur | Avant (30 j) | Après (12 j) |
|---|---:|---:|
| Concepts sans axe d'objet | 91 % | **0 %** |
| Réflexions sans aucune croyance montrée | 68 % | **22 %** |
| … pour l'agent sans voiture | 100 % | **13 %** |
| Part de créations parmi les opérations | 76 % | **31 %** |
| Précisions (`refine`) | 0 | **3** |
| Marches fantômes | 398 sur 412 | **0** sur 459 |
| « Trip by Unknown Unknown » | 270 | **0** |
| Concepts par jour simulé | 7,7 | **3,3** |

Xavier (609) portait 35 concepts, presque tous des reformulations d'une marche qui n'a jamais eu
lieu. Il en porte **un**, confirmé 19 fois : *« Driving to work takes a consistent 8 minutes. »*

⚠ **Un défaut trouvé en faisant tourner le code, et corrigé le jour même.** L'alarme de
concentration des rappels (lot D2) s'est levée à 100 % pour quatre agents dès le cinquième jour.
Elle disait vrai et ne mesurait rien : un agent qui possède onze souvenirs et en sert dix les
sert tous. Un rappel n'entre désormais dans la mesure que si le vivier offrait strictement plus
de candidats qu'il n'en a été servi. C'est le motif récurrent du dépôt pris à l'envers —
l'absence de choix produisait ici le score le plus alarmant au lieu du plus parfait.

**Analyse complète du run, 2026-09-15** :
`docs/traces/2026-09-15_13-25_analyse_memoire_apres_correction/`. Elle a fait apparaître trois
choses que les tests ne pouvaient pas dire.

1. **Une régression du lot C lui-même**, corrigée le jour même. Le journal des habitudes cherchait
   la décision dans le tampon de mémoire courte à l'arrivée ; les consolidations le vident entre
   les deux. Résultat : 2 trajets journalisés pour 40 arrivées, et le bloc « Mes habitudes »
   absent des 117 prompts de décision. Le mode retenu est désormais noté à la décision, dans une
   table bornée par activité.
2. **Un défaut que le lot B a démasqué.** Neuf des vingt arrivées de Constance (11195) annoncent un
   retard de plusieurs heures pour un trajet de quatre minutes : son retour du soir est exécuté le
   lendemain matin (`Late order` dans le journal GAMA). Elle apprend un retard qui n'existe pas.
   C'est le prochain à corriger, et il ne relève pas de la mémoire.
3. **Les viviers structurés n'apportent rien, et c'est normal à cette échelle.** 100 % du top-K
   vient du vivier sémantique, mais avec 17 candidats médians pour une mémoire de 20 à 40 entrées,
   la passe sémantique balaie déjà tout. L'alarme du lot 2 ne deviendra informative qu'avec des
   agents portant des centaines de souvenirs.

**Reste à faire.** L'arbitrage du lot D1 — servir l'auto-réflexion dans le bloc noyau, ou
l'éteindre — qui demande une décision de l'auteur et non un choix d'implémentation.

⚠ **Le lot B change les observations de TOUS les runs à venir.** C'est l'effet recherché, mais les
mémoires produites avant le 2026-09-15 ne sont plus comparables à celles d'après.

---

## 8. Ordre et dépendances

1. **Lot A** puis **Lot B** : rien d'autre n'a de sens avant. Les deux sont locaux et testables sans
   run.
2. **Lot C** et **Lot E** : indépendants entre eux, tous deux après A et B.
3. **Lot F** : indépendant de tout, il lit le run existant et servira au suivant.
4. **Lot D1** : décision de l'auteur attendue (servir l'auto-réflexion ou l'éteindre).
5. Le run suivant n'est lancé qu'après A, B, C et E — sinon il réapprendra les mêmes faussetés, et
   trente jours de calcul seront à refaire.

---

## 9. Ce que ce ticket ne fait pas

Il ne touche à aucune règle de la mémoire : gravité, oubli, viviers, score composite, opérations de
concept et seuils restent ceux du 071. Il ne modifie pas la population de test du 075. Il ne produit
aucun chiffre pour l'article : cinq agents observent un mécanisme, ils ne mesurent pas une part
modale, et `population_1000_AAMAS_v6` reste la référence.

---

# 10. Passation — état au 2026-09-17, pour reprendre d'une autre session

Cette section est écrite pour quelqu'un qui n'a pas suivi. Elle dit **où en est l'expérience**,
**ce qui a été réparé pour y arriver**, **comment relancer**, **ce qu'il faut vérifier**, et **ce
qui reste ouvert**. Rien n'y est supposé connu.

## 10.1 L'objectif, en une phrase

Relier la mémoire d'un agent à un changement d'habitude, en injectant un événement daté — le choc
`c6_voiture_suspecte` : la voiture de Corinne (`899549`) fait un bruit de moteur et cale, deux
jours de suite, avec un retard mesuré de 25 puis 12 minutes. Deux bras appariés, mêmes graines :
l'un avec le choc, l'autre sans. Tout écart après le choc lui est imputable.

**Ce bras n'a jamais tourné proprement.** Six tentatives entre le 2026-09-16 et le 2026-09-17,
chacune arrêtée par une cause différente. Les six causes sont maintenant fermées ; c'est l'essentiel
de ce qui a été fait, et c'est ce que cette section transmet.

## 10.2 Les six causes de mort, et ce qui les ferme

| # | Symptôme | Cause réelle | Fermé par |
|---|---|---|---|
| 1 | GAMA tué au jour 1, `close 1011 keepalive ping timeout` | le lanceur coupait la connexion si GAMA ne répondait pas à un ping en **20 s**, alors qu'il se bloque normalement en attendant le LLM (23 pauses, médiane 9 s, max 40,9 s, 3 au-dessus du seuil) | **092** — `ping_timeout` à 20 min, `GAMA_PING_TIMEOUT_S` |
| 2 | même mort, campagne concurrente en cours | contention de pile ; la campagne allongeait la pause fatale sans en être la cause — le symptôme est revenu **sans** campagne | rien à corriger, mais vérifier `pgrep -f "campagne-lancer"` avant un run long |
| 3 | `OOMKilled=true` sur le conteneur GAMA, jour 1 | deux `City.gaml` résidents dans la **même JVM** (12 Go) : `make run` ne redémarrait pas GAMA, chaque lancement chargeait un modèle de plus. Ce qui pèse est le territoire — 453 communes, réseau complet — pas le nombre d'agents | **089** — `make run` commence par `make stop-run` |
| 4 | run complet, `0 exposé(s)` | le choc était déclaré aux **jours 6 et 7**, qui tombent samedi 21 et dimanche 22 mars — journées **sautées** (`agent.no_weekend_departures`). La comptabilité passe du jour 5 au jour 8 sans rien injecter | jours portés à **8 et 9** (= 6ᵉ et 7ᵉ journées **vécues**), tableau de correspondance en tête du fichier de choc |
| 5 | identité de run acceptant n'importe quelle reprise | le champ `choc` valait toujours `"aucun"` : le registre de chocs n'existe qu'au `/init` de GAMA, **après** l'écriture de l'identité | empreinte recalculée depuis le **fichier** déclaré (sha256 des octets), 4 tests |
| 6 | reprise repayant toutes les journées rejouées | la trace de décisions n'était **ouverte** qu'en cas de reprise, donc jamais écrite pendant la vie normale : zéro ligne après deux journées simulées, fonctionnalité inerte | ouverture inconditionnelle au démarrage, 1 test de garde |

⚠ Les causes 5 et 6 sont des défauts **de mon propre code**, trouvés par la recette de deux jours
et non par les tests unitaires : les tests vérifiaient les modules, pas leur branchement. C'est
l'argument le plus fort en faveur de la recette du § 10.5.

## 10.3 Ce qui a été livré autour

| Ticket | Ce qu'il donne |
|---|---|
| **084** | une requête déclare `instances_admises` ; la restriction est honorée **à la sélection**, avant qu'un appel ne soit payé |
| **085** | la restriction appartient au run et non au fichier global ; échec immédiat au lieu de 120 s de timeout |
| **089** | `make run` arrête le run précédent en **première** étape, pour tous les lancements |
| **090** | trace de décisions propre au run, resservie pendant le gel de reprise — **ce n'est pas le cache** : source = ce run, clé = `(personne, activité, instant)`, portée = la fenêtre de gel, manquées comptées et alarmées |
| **091** | identité de run (11 champs) et **reprise nommée** : `REPRISE=<nom>`. Sans le nom, **aucune** réutilisation. Aucune échappatoire |
| **092** | la restriction couvre les **trois** appels (décision, réflexion STM, auto-réflexion LTM) — la consolidation partait chez Mistral ; et le ping GAMA tolère 20 min |
| **093** | dix personas mesurables, cinq CSV par jour simulé, tableau Grafana |

## 10.4 La configuration en place

```yaml
# services/llm-agents/config/config.yaml
llm:   instances_admises: [google_gemini31_key1, google_gemini31_key2]
agent: llm_params: {temperature: 0, top_p: 1.0, max_tokens: 4096,
                    prompt_variant: prompt_expert_05}
       trace_concepts_enabled: true
       mesures_jour_enabled: true
cache: enabled: false          # chaque décision est journalisée
data:  population_file: …/population_10_mesurables_093/population.json
chocs: enabled: true · fichier: …/chocs/c6_voiture_suspecte.yaml   (jours 8 et 9)
```

`sim_params.yaml` : `population_size: 10`, `simulation_max_days: 20`, mémoire et auto-réflexion
actives, accidents coupés.

⚠ **`llm_params` REMPLACE le dictionnaire par défaut, il ne s'y ajoute pas.** N'y poser que
`prompt_variant` efface température, top_p et budget de sortie. Les quatre valeurs doivent rester
écrites ensemble.

## 10.5 Comment lancer, arrêter, reprendre

```bash
# lancement neuf
make run OFFLINE=1 CACHE=0 CHOC=c6_voiture_suspecte

# bras témoin (mêmes graines, aucun choc)
make run OFFLINE=1 CACHE=0 CHOC=0

# arrêt à chaud
make stop-run

# reprise — le nom est OBLIGATOIRE (ticket 091)
make run OFFLINE=1 CACHE=0 CHOC=c6_voiture_suspecte REPRISE=2026-09-17_06_42
```

⚠ **Piège : `make run` ne recrée le contrôleur que si `config.yaml` a changé.** Après une
modification de **code**, il faut forcer la recréation, sinon le contrôleur garde l'ancien code
**et rouvre le répertoire du run précédent** :

```bash
rm -f .config.yaml.applique && make run …
```

**La recette avant tout run long**, et elle a déjà trouvé deux défauts : jouer deux journées,
arrêter, reprendre en nommant le run, puis vérifier trois choses — la reprise repart au bon
endroit, les décisions sont **resservies** depuis `decisions_rejeu.jsonl` au lieu d'être repayées,
et les courbes des CSV sont **continues** de part et d'autre de la coupure. Une métrique qui saute
ou se dédouble à la reprise est fausse, et on ne le verrait plus sur vingt jours.

## 10.6 Ce que les mesures ont déjà montré

Mesuré sur `experiments/archive/2026-09-16_15_58` — 10 jours, 5 personas, gemini 3.1.

**La mémoire s'éteint en trois à cinq jours.** 89 % des réflexions et 74 % des concepts ont une
force ≤ 4,5 jours ; 36 réflexions sur 91 sont à gravité 0,00, donc 2,8 jours. Seul un événement
injecté produit un souvenir qui passe la semaine (0,75 à 1,00 → 15 à 20 jours). **Sur un run de
vingt jours, la mémoire n'est pas longue : c'est une fenêtre glissante de trois à cinq jours.**
C'est l'explication directe du « pourquoi la même leçon revient-elle » du § 0.

**Elle confirme, elle ne révise pas.** 100 opérations de concept : 38 créés, 61 confirmés,
**1 contredit**. L'unique contradiction est celle de Corinne, le jour du choc :

> `contredit` · avant : « Driving my car to work is consistently reliable and efficient »
> contre-exemples 0 → 1 · confiance 0,75 → 0,60

Sans événement injecté, rien n'a jamais été révisé en dix jours et cinq agents.

**Le vivier de rappel ne décroît jamais** : 11 candidats au jour 1, 26 au jour 10.

**Trois personas sur cinq n'apprenaient rien d'observable** — `609` et `41275` n'avaient qu'un
seul itinéraire proposé une fois sur deux, `11195` ne vivait que 19 trajets contre 34-35. D'où la
population de dix du 093, et la colonne **« part décidée »** sans laquelle « voiture 100 % » ne
distingue pas un choix d'une absence d'alternative.

## 10.7 Pièges d'analyse — à lire avant de toucher aux données

1. **`moves.csv` compte les journées rejouées deux fois.** 113 activités-jour en double sur le run
   du 16. Dédupliquer sur `(ID Personne, ID Activité, jour simulé)` en gardant la **première**
   occurrence.
2. **La colonne « Jour relatif au choc » n'est pas fiable** si la configuration du choc a bougé
   pendant le run : deux conventions s'y mélangent. Le repère sûr est `Temps simulé`, horodatage
   absolu, dont tout se redérive.
3. **Le rejeu n'est pas fidèle** tant que la trace du 090 n'est pas active : 12 % des décisions
   rejouées différaient de l'originale sur le run du 16. L'état reconstruit n'était donc pas celui
   d'avant l'arrêt.
4. **`experiments/current` ne prouve rien** : il a pointé deux fois dans la même journée sur un run
   autre que celui qu'on croyait. Retrouver un run par son horodatage sous `experiments/archive/`.

Trois répertoires portent une note expliquant pourquoi ils sont écartés : `2026-09-16_11_40`
(deux tentatives mélangées), `2026-09-16_12_48` (OOM), `2026-09-16_15_58` (choc déplacé en cours
de route — `NOTE-PROVENANCE.md`).

## 10.8 Ce qui reste ouvert

**Défauts mesurés, sans ticket :**

- Le rejeu **écrase les points de reprise** des journées déjà vécues : sur le run du 16, les points
  `jour_002` à `jour_009` portent tous le même contenu, écrits pendant le rejeu. L'historique de la
  mémoire est perdu pour ce run. Le 093 protège les mesures d'état ; la cause — `ecrire_point`
  devrait refuser d'écraser — reste.
- `moves.csv` n'est pas nettoyé des sorties de rejeu (cf. piège 1).
- `11195` exécute ses retours du soir le lendemain matin et apprend un délai de treize heures qui
  n'existe pas.
- `make stop-run` annonce « ✅ Run arrêté » même quand son `pkill` en conteneur échoue (`pkill`
  absent de l'image). L'arrêt réel passe par les gestes côté hôte, mais le message ment.
- `min_output_required` n'entre pas dans la clé de lot de la passerelle.

**Décisions attendues de l'auteur :**

- **Le lien choc → souvenir.** Le vécu injecté est **reformulé** par la réflexion, donc
  l'appariement par texte échoue et la figure « le souvenir du choc a-t-il été servi » reste hors
  d'atteinte — `scripts/analysis/memoire/choc.py` a le même angle mort depuis le 079. Il faudrait un
  `choc_id` porté par l'entrée de mémoire courte et propagé à la réflexion. Ticket propre ou non ?
- **Le comptage en jours vécus.** Demandé le 2026-09-16 : « il faut ignorer les week-ends dans tous
  les comptes ». Une seule fonction, `ancre_run.jours_ecoules`, compte en jours de **calendrier** et
  sert quatre consommateurs (chocs, point de reprise, météo, agent). Non fait. À noter : l'horizon
  `simulation_max_days` est compté par **GAMA**, indépendamment, en secondes depuis `starting_date`.
- **L'horizon.** Un choc au jour 8 dont le souvenir vit 15 à 20 jours s'éteindrait vers le jour 23 —
  **hors** d'un run de 20. Passer à 25 jours donnerait l'arc entier pour ~20 minutes de plus.
- **Lot D1 du présent ticket** : servir l'auto-réflexion dans le bloc de mémoire vive, ou l'éteindre
  (elle n'atteint que 2 prompts de décision sur 336).
- **Supprimer le rejeu** plutôt que son coût : rendre `starting_date` lisible depuis la
  configuration. L'obstacle est la **chaîne des véhicules** — où est garée la voiture de chacun —
  que seul le contrôleur connaît et que GAMA ne reçoit pas aujourd'hui.

## 10.9 L'état exact à la passation

Rien ne tourne. Pile debout, conteneur GAMA arrêté, lanceur arrêté. Le dernier répertoire,
`2026-09-17_06_42`, est une recette interrompue au bout de cinq minutes pour libérer Docker — sans
valeur, à écarter.

**La prochaine action est la recette du § 10.5**, puis, si elle passe, le bras choqué puis le bras
témoin, ~1 h 40 chacun au rythme mesuré de 6,5 minutes par journée vécue.

## 11. Rejeu 30 jours — Décisions de reconception (2026-09-18)

Diagnostic approfondi du run initial (20 jours, persona 899549 « Corinne ») :
traces dans `experiments/archive/2026-09-18_14_31/`.

### 11.1 Trois causes techniques identifiées

1. **Instabilité pré-choc (J1-J5)** : Le LLM assignait systématiquement 55-80 % à la voiture,
   mais le tirage catégoriel de Monte-Carlo (`draw_index`) tombait dans la queue de 9-25 %,
   sélectionnant des modes que l'agent ne voulait pas. Le chaînage des véhicules (`retour_force`)
   propageait ensuite le choix involontaire à tout le reste de la journée.
2. **Non-transmission du choc en mémoire** : Les gravités mesurées (0,6167 au J8, 0,4000 au J9)
   étaient toutes deux inférieures au seuil `memoire__importance_choc = 0,70`. Le choc n'a
   **jamais** été injecté dans la section « Ce qui a changé récemment » du prompt de décision.
3. **Écrasement du choc dans le Top-K ChromaDB** : Le concept de panne (0 rappels) était
   systématiquement éliminé par les souvenirs de routine (15 rappels, similarité supérieure).

### 11.2 Quatre corrections appliquées

| Paramètre | Ancienne valeur | Nouvelle valeur | Justification |
|---|---|---|---|
| `vehicle_chain_enabled` | `true` | **`false`** | Isoler le raisonnement cognitif du blocage physique (Ticket 040, ablation lot 1) |
| `vehicle_return_home_lock` | `true` | **`false`** | Idem — le verrou de retour ne s'applique plus |
| `mode_choice_truncation_threshold` | `0.0` (inexistant) | **`0.15`** | Consideration Set (Hauser & Wernerfelt 1990). Les options < 15 % sont éliminées avant tirage. Supprime le bruit de roulette sur un agent individuel |
| `memoire__importance_choc` | `0.70` | **`0.50`** | Tout incident « gênant » ($G \ge 0,50$) entre immédiatement en mémoire noyau |

⚠ **La quatrième correction a été ANNULÉE le 2026-09-19.** Elle était inutile et elle violait le
§ 9 de ce ticket. La gravité du choc du J15 vaut **exactement 0,70** et la comparaison est `>=` :
le choc franchissait le seuil d'origine sans qu'on l'abaisse. Seul le J16 (0,533) en dépendait,
et le J16 ne s'est jamais appliqué — l'exposition est restreinte aux trajets en voiture, et
l'agent n'en faisait plus. Le seul effet mesurable de l'abaissement a été d'élargir le vivier C
— rappel **sans aucune condition de contexte** — à six souvenirs supplémentaires sur 219.

Le commentaire d'origine de `c6_voiture_suspecte.yaml` plaidait explicitement pour le
sous-seuil : « Le souvenir n'atteint PAS le seuil du vivier des chocs (0,70). Il est donc rappelé
par le vivier par objet — quand la voiture figure dans les options — et non hors contexte. C'est
voulu : un moteur qui fait du bruit n'est pas une panne de réseau. » Cet argument a été supprimé
le 18 septembre, pas réfuté. Le seuil est revenu à 0,70, et une règle du contrat (lot J) interdit
désormais qu'une règle de mémoire soit redéfinie dans `config.yaml`.

### 11.3 Protocole temporel étendu

- **Baseline** : 10 jours ouvrés (J1-J5 + J8-J12, soit 2 semaines calendaires).
  L'habitude se cristallise en LTM (confiance ≥ 0,85 après ≥ 5 observations homogènes).
- **Chocs** : J15 (retard 30 min, gravité 0,70) et J16 (retard 20 min, gravité 0,53).
  Les deux franchissent le seuil de 0,50.
- **Observation post-choc** : J17 à J42 (18 jours ouvrés restants sur 20 prévus).
  Durée de vie du souvenir du J15 : ~14,6 jours → s'éteint vers J30.
  Horizon total : `simulation_max_days = 42` (30 jours de mobilité active).

### 11.4 Fichiers modifiés

- `packages/mobility_llm/src/mobility_llm/mode_choice.py` — `draw_index(min_prob_threshold=)`
- `services/llm-agents/settings.py` — `mode_choice_truncation_threshold: float = 0.0`
- `services/llm-agents/urban_mobility_agents/agents/llm_agent.py` — passage du seuil
- `services/llm-agents/llm/cache.py` — passage du seuil
- `services/llm-agents/experiences/decideur_antigravity.py` — passage du seuil
- `services/llm-agents/config/config.yaml` — paramétrage de l'expérience
- `services/llm-agents/config/chocs/c6_voiture_suspecte.yaml` — recalage J15/J16
- `services/GAMA/CityTransport/config/sim_params.yaml` — `simulation_max_days: 42`
