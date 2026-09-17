# Mesures par jour simulé — personas, habitudes, mémoire, choc

> Ticket 093. Contrat de tests : `specs/ticket_093/tests.md`. Questions tranchées et défauts
> signalés : `specs/ticket_093/questions.md`.

Ce document décrit **ce qui est mesuré**, **d'où ça vient**, et **ce qu'il ne faut pas lire** dans
ces chiffres.

---

## 1. Pourquoi une colonne de plus change tout

Sur le run `2026-09-16_15_58` — dix jours, cinq personas —, trois personas n'apprennent rien
d'observable. `609` et `41275` n'ont qu'un seul itinéraire proposé une fois sur deux, et prennent
la voiture à 100 % le reste du temps ; `11195` ne vit que 19 trajets contre 34-35 aux autres.

Et ce qui manquait pour le dire n'était pas une analyse plus fine, c'était une **colonne**.
« Voiture 100 % » désigne indifféremment « il a choisi la voiture » et « on ne lui a rien proposé
d'autre ». Tant que la **part des trajets réellement décidés** n'est pas écrite à côté de la part
modale, les deux lectures restent indiscernables.

---

## 2. Choisir des personas dont les décisions sont observables

`scripts/data/population/selectionner_personas_mesurables.py` — `make personas-mesurables RUN=…`

Le critère ne porte pas sur les traits d'un agent mais sur son **comportement mesuré** dans un run
déjà joué : au moins **4 trajets**, **toujours** au moins **2 itinéraires** proposés, au moins
**2 modes réellement choisis**. Il porte sur les modes **choisis**, jamais sur les modes proposés :
un agent à qui l'on propose neuf options et qui prend toujours la voiture est parfaitement
visible — et parfaitement inutile, sa mémoire n'aura rien à faire basculer.

Trois choses à savoir avant de relancer la sélection :

- **Le critère est un plancher, pas un objectif.** Les candidats sont pris du plus observable au
  moins observable — modes, puis trajets, puis choix offert — l'identifiant numérique ne servant
  qu'à départager. Trier par identifiant donnait dix agents minimalement conformes.
- **Une sélection ne vaut que pour son run de référence.** `41275` passe le critère sur le run de
  mille agents et le manque sur celui à cinq personas : autre modèle, autre variante de prompt. Le
  MANIFEST nomme donc le run et écrit son empreinte.
- **« Journée » de référence ne veut pas dire « date ».** Sur le run de référence, les départs
  s'étalent du 16 mars 04 h 13 au 18 mars 06 h 47 : une chaîne commencée tard déborde sur le
  lendemain. Le MANIFEST écrit les journées couvertes.

La population livrée est `data/population/population_10_mesurables_093/` — dix agents, quatre
modes dominants couverts, Corinne (`899549`, sujet du choc) et `616478` conservés.

**Elle est versionnée**, contrairement à `population_5_memoire_075` qui ne l'est pas. Ce n'est pas
un détail de confort : le run de référence dont elle est tirée vit sous `data/experiences/`, que
git ignore. Hors git, la population n'existerait que sur la machine qui l'a produite, et son
critère resterait théorique.

`make personas-verifier` contrôle qu'elle est bien celle que son manifeste décrit — empreinte,
effectif, existence et empreinte de la source. **Ce n'est pas un sceau AAMAS** et cela ne prétend
pas l'être : `scripts.AAMAS.seal_population` tire des ménages par strates et contrôle treize marges
à ± 1 point, ce qui n'a aucun sens à dix agents et n'est pas le but. La garantie ici est plus
modeste : une population retouchée à la main cesse de se réclamer d'un critère mesuré.

---

## 3. Ce qui est mesuré, et où ça s'écrit

`make mesures RUN=<run>` écrit cinq CSV dans `<run>/mesures/`. Pendant un run, le contrôleur les
réécrit **à chaque point du jour**, à 3 h simulées.

| Fichier | Clé | Ce qu'il porte |
|---|---|---|
| `choix_modal_par_jour.csv` | jour, agent | trajets, **trajets décidés**, part décidée, part de chaque mode |
| `habitudes_par_activite.csv` | jour, agent, **activité** | mode, mode de la veille, reprise, mode habituel, conformité |
| `memoire_par_jour.csv` | jour, agent | vivier de rappel, souvenirs servis, **opérations de concept**, entrées |
| `duree_de_vie_par_type.csv` | jour, agent, type | durée de vie médiane, en jours |
| `choc_par_jour.csv` | jour, agent, choc | expositions, minutes injectées, souvenir du choc servi |

L'habitude est mesurée **par activité** : le trajet domicile-travail et le trajet de loisir n'ont
aucune raison de basculer ensemble, et les agréger masquerait le changement cherché. Deux mesures,
parce qu'elles ne voient pas la même chose — la **reprise de la veille** voit une bascule franche
le jour où elle arrive, la **conformité à l'habitude** (mode majoritaire des cinq dernières
observations de cette activité) voit une dérive lente.

---

## 3 bis. Deux repères temporels, et ils ne disent pas la même chose

`moves.csv` porte **`Temps simulé`** — l'instant où la décision a été prise — et
**`Heure de départ`** — l'instant où le trajet part. Les confondre fausse tout, et l'écart n'est
pas marginal : sur `2026-09-16_15_58`, 30 lignes sur 270 les écartent de plus d'une heure et
demie, dont **19 exactement de 48 heures** — des décisions prises le samedi 21 mars pour des
départs reportés au lundi 23, la simulation ne faisant rouler personne le week-end.

| Usage | Repère | Ce qu'on casserait avec l'autre |
|---|---|---|
| **Dédupliquer** les journées rejouées | `Temps simulé` | deux décisions distinctes d'une même activité fusionneraient |
| **Dater** la journée vécue | `Heure de départ` | une journée « samedi » à 19 trajets apparaîtrait, et le lundi en perdrait 19 sur 35 |

Sur ce run, la déduplication écarte **113 activités-jour** rejouées.

⚠ La colonne `Jour relatif au choc` n'est **jamais** lue par les mesures : elle mélange deux
conventions si la configuration du choc a bougé pendant le run. Les jours relatifs se redérivent
des horodatages de `chocs.jsonl`. Un test le verrouille.

---

## 4. Quatre règles de lecture

**La journée simulée commence à 3 h**, comme le point de reprise : un retour à 00 h 30 appartient
à la soirée de la veille.

**« La veille » est le jour VÉCU précédent.** Le calendrier saute les week-ends — les départs du
samedi et du dimanche sont reportés au lundi. Comparer au jour calendaire viderait la mesure tous
les lundis, pour un week-end où l'agent n'a rien vécu.

**Une cellule vide n'est pas un zéro.** Habitude que la fenêtre ne détermine pas, ex æquo, type de
souvenir absent, trace éteinte, souvenir de choc non appariable : la cellule est vide. Dans ce
dépôt, le zéro est le score parfait, et une vacuité écrite `0` se cite comme une conformité totale
ou une contradiction jamais survenue.

**Flux et état ne se recalculent pas pareil.** Les flux (trajets, parts, vivier, opérations)
viennent de journaux datés et sont **réécrits en entier** à chaque passage. Les états (entrées en
mémoire, durée de vie) sont lus dans le **point de reprise** qui clôt la journée, et **écrits une
seule fois** : un état ne se reconstitue pas — la `force` d'un souvenir croît à chaque rappel, et
le rejeu d'une reprise écrase les points des journées déjà vécues avec l'état gelé.

---

## 5. Prometheus et Grafana

Tableau de bord **09 · Mémoire & personas**, provisionné automatiquement.

⚠ **Son abscisse est le temps réel, pas le temps simulé** : une journée simulée dure environ six
minutes. Les séries sont réglées une fois par journée, et portent le **dernier jour clos** —
jamais le jour en cours, dont les parts monteraient au fil des départs.
`persona_dernier_jour_clos` dit de quelle journée il s'agit.

**Le CSV fait foi.** Grafana sert à voir une bascule *pendant* le run ; l'analyse et les figures
se prennent dans les CSV, qui survivent à l'arrêt des conteneurs.

Toutes les familles sont des **Gauges réglées**, jamais des `Counter`. Un compteur incrémenté au
fil des décisions se dédoublerait au rejeu d'une reprise : sur `2026-09-16_15_58`, 113 trajets et
81 rappels ont été rejoués.

---

## 6. Activer

Deux réglages, éteints par défaut :

| Réglage | Effet |
|---|---|
| `agent.trace_concepts_enabled` | écrit `operations_concept.jsonl` — une ligne par opération de concept |
| `agent.mesures_jour_enabled` | recalcule et réécrit les CSV à chaque point du jour, et règle les séries |

Sans la trace des concepts, les colonnes d'opérations restent **vides** — et c'est voulu : « aucune
contradiction » et « on ne mesure pas les contradictions » ne doivent pas se lire pareil. Le
démarrage le journalise en WARNING.

---

## 7. La recette : deux jours et un redémarrage

Avant tout run long, et comme critère d'acceptation du ticket :

```bash
# 1. deux jours simulés, puis arrêt
make stop-run
# 2. copier les CSV AVANT la reprise
cp -r experiments/archive/<run>/mesures /tmp/mesures_avant
# 3. reprendre en NOMMANT le run (ticket 091)
make run OFFLINE=1 CONT=1 REPRISE=<run>
# 4. vérifier que les courbes sont continues
make mesures-continuite AVANT=/tmp/mesures_avant APRES=experiments/archive/<run>/mesures
```

La vérification refuse, avec un code de sortie non nul, une clé dédoublée, un jour **ouvré**
manquant, ou une valeur d'un jour antérieur à la coupure qui a changé. Un week-end sauté n'est pas
un trou et ne fait pas échouer la recette.

C'est le vrai test du lot : une métrique qui saute ou se dédouble à la reprise est fausse, et sur
un run de vingt jours personne ne la verrait plus.

---

## 8. Ce que ces mesures ne disent pas

**Si le souvenir d'un choc a pesé sur une décision.** Rien ne relie un choc au souvenir qu'il
produit : le vécu injecté — « The engine made a grinding noise and the car stalled twice » — n'est
jamais recopié tel quel, la réflexion le reformule. L'appariement par texte ne rend aucun
identifiant, et `scripts/analysis/memoire/choc.py` a le même angle mort. La colonne vaut donc
**vide** et jamais « non servi ». Un lien explicite doit être posé à la source.

**Comment la mémoire a grandi pendant les journées rejouées d'une reprise.** Les points de reprise
de ces journées sont écrasés avec l'état gelé. La parade — un état écrit une fois n'est jamais
réécrit — protège les runs à venir, pas ceux qui sont déjà archivés.

**Une part modale de population.** Dix agents ne représentent rien. La référence de l'article reste
`data/population/population_1000_AAMAS_v6`.
