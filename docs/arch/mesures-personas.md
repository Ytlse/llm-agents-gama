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

**Le branchement fait partie de la mesure.** L'écriture est appelée depuis
`_ecrire_point_de_reprise`, juste après le point, et nulle part ailleurs : c'est le seul endroit
où l'instantané d'état existe. Le module étant *fail-open* et éteint par défaut, il est **muet
quand il ne tourne pas** — un run qui ne produit aucun CSV ressemble en tout point à un run où
la mesure était éteinte.

⚠ **Cette confusion a déjà coûté un run.** Le 19 septembre 2026, une méthode insérée au milieu de
`_ecrire_point_de_reprise` a laissé l'appel aux mesures après un `sys.exit(0)` : plus aucun CSV
pendant quarante-deux jours simulés, sans un mot dans le journal, et les tests du 093 sont restés
verts parce qu'ils vérifiaient le module sans vérifier qu'on l'appelle. Le branchement est
désormais tenu par une règle à lui, `specs/ticket_077/tests.md` section G — et par une garde qui
refuse toute instruction placée après un appel terminal dans le contrôleur.

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

---

## 9. L'enquête du soir : mesurer la croyance, pas seulement le comportement

> Ticket 095, lot B. Contrat de tests : `specs/ticket_095/tests.md`, sections D à F.

Toutes les mesures ci-dessus portent sur ce que l'agent **fait**. L'enquête du soir porte sur ce
qu'il **dit croire** — et sans elle, une part modale qui s'effondre ne permet pas de dire si
l'agent a changé d'avis ou seulement d'itinéraire.

### Ce qu'elle demande

Les six critères d'Adam & Gaudou (2025) — **rapidité, praticité, confort, sécurité, accessibilité
financière, écologie** — sur une échelle de Likert 0-10, avec ancrages verbaux 0/5/10 répétés à
chaque jalon pour que l'échelle ne dérive pas.

**Cinq prompts par jalon et par persona**, à 21 h simulées :

- **quatre prompts de perception**, un par mode, le mode nommé et les trois autres jamais cités.
  Les 24 scores demandés d'un seul coup produisaient une grille plate — la voiture à 9 partout,
  le bus à 3 partout : on payait 24 nombres pour en obtenir 4 ;
- **un prompt de priorités**, qui ne nomme aucun mode.

Ensemble, ils rendent calculable, depuis le seul CSV :

```
score(mode) = Σ  val(mode, critère) × prio(critère)
             critères
```

soit le mode que le modèle symbolique d'Adam & Gaudou prédirait à partir des déclarations de
notre agent, à confronter au mode qu'il choisit réellement le lendemain.

**L'écologie est la question témoin.** Aucun des six chocs déclarés du dépôt ne la vise. Si le
score d'écologie du vélo chute après une crevaison, l'agent n'a pas noté un critère : il a exprimé
une humeur globale, et **l'instrument entier est invalide**. Une question qui doit rester plate est
une garde, pas une dépense.

### Étanchéité en sortie, fidélité en entrée

Deux exigences distinctes, et le module n'en portait qu'une jusqu'au 2026-09-21.

| | Règle | Pourquoi |
|---|---|---|
| **Sortie** | La réponse va dans `affinites_declarees.csv` et nulle part ailleurs — ni STM, ni LTM, ni ChromaDB, ni réflexion nocturne | La sonde ne doit pas contaminer les délibérations qu'elle observe |
| **Entrée** | Le prompt sert **exactement** le bloc `memoire_noyau` du prompt de décision, plus le récit d'identité complet | Sans lui, la sonde mesure le modèle de base et non l'agent |

⚠ **L'enquête LIT la mémoire, elle ne la RAPPELLE pas.** `memoire_noyau` ne touche ni `force` ni
`dernier_rappel` ; le chemin de rappel vectoriel, lui, renforce la force de chaque souvenir servi.
Une sonde qui prolonge la durée de vie de ce qu'elle observe modifie ce qu'elle mesure.

Avant ce lot, la perception servie tenait en quatre champs — nom, âge, genre, occupation. **Telle
qu'écrite, l'enquête mesurait l'a priori du modèle de base sur une femme de 53 ans à temps
partiel** : identique au jour 12 et au jour 29, identique dans les deux bras de fenêtre. Elle
n'aurait rien détecté, et son silence aurait été pris pour une absence d'effet.

### Le fichier

`affinites_declarees.csv`, **format long** : une ligne par (jour, persona, mode, critère, score).
Les six priorités s'écrivent dans le même fichier, avec `mode = critere_priorite`.

| Colonne | Contenu |
|---|---|
| `sim_timestamp`, `date_simulee`, `jour_simule` | quand |
| `persona_id` | qui |
| `mode` | le mode interrogé, ou `critere_priorite` |
| `critere` | `rapidite`, `praticite`, `confort`, `securite`, `cout`, `ecologie` |
| `score` | 0-10, **tel que rendu** |
| `justification` | une phrase pour le bloc entier |
| `provider`, `model` | qui l'a produit (ticket 095, lot E) |

Le format long absorbe le train et le deux-roues sans changer de schéma ; le format large à
24 colonnes obligeait à réécrire l'en-tête dès qu'un mode s'ajoutait.

### Activer

```bash
EXPERIMENT_SURVEY_ENABLED=1 EXPERIMENT_SURVEY_DAYS=12,17,29,40 \
EXPERIMENT_SURVEY_MODES=voiture,transports_collectifs,velo,marche make run OFFLINE=1
```

Un jalon posé un samedi ou un dimanche ne se déclenchera **jamais** — la simulation saute les
départs de week-end — et un avertissement le dit au démarrage.

### Les alarmes

`[ALARME] [enquete]` se lève quand un jalon passe sans aucune réponse, quand un jalon est
incomplet, et quand un score sort du domaine 0-10. **Un score hors domaine est écrit tel quel,
jamais raboté** : un 14 ramené à 10 se lirait comme un avis maximal alors qu'il dit que le modèle
n'a pas respecté l'échelle.

### Ce que l'enquête ne mesure pas

Deux sondes ont été écartées le 2026-09-21, et la section des limites de l'article doit le dire :

- **la préférence déclarée tous modes en concurrence** (répartir 100 points entre les modes),
  jugée redondante avec les prompts de perception. Conséquence : la dissociation entre croyance
  et comportement se lira sur les courbes de perception face aux parts modales, ce qui est moins
  direct qu'une intention déclarée ;
- **le rappel libre** (« que te rappelles-tu de tes déplacements des deux dernières semaines ? »).
  Conséquence : la sortie de fenêtre reste observable depuis le journal, pas depuis l'agent.

Aucune comparaison aux 650 répondants humains d'Adam & Gaudou n'est prévue : hors périmètre, et
le mélange des deux populations ferait dériver l'analyse.
