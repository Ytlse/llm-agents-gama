# Ticket 093 — Contrat de tests

Écrit AVANT le code.

## Le besoin

Sur le run `2026-09-16_15_58` — dix jours, cinq personas —, trois personas sur cinq n'apprennent
rien d'observable : `609` et `41275` n'ont qu'un seul itinéraire proposé une fois sur deux et
prennent la voiture à 100 % le reste du temps, `11195` ne vit que 19 trajets contre 34-35 aux
autres. On observe la mémoire de deux agents et on paie le modèle pour cinq.

Et ce qui manque pour le dire n'est pas une analyse plus fine : c'est une **colonne**. « Voiture
100 % » désigne indifféremment « il a choisi la voiture » et « on ne lui a rien proposé d'autre ».
Tant que la part des trajets réellement décidés n'est pas écrite à côté de la part modale, les deux
lectures restent indiscernables, et c'est précisément ce qui a rendu deux personas illisibles.

Vérifié avant d'écrire ce contrat, sur `exp_gemini-35-fl_proexp08_…/executions/2026-09-15_12_38_15/moves.csv`
(1 000 agents, une journée) : le critère du ticket retient **234 candidats**, et `920187` y compte
15 trajets — marche 9, TC 4, train 1, voiture 1. Les chiffres du ticket se retrouvent à
l'identique ; ce run est donc le run de référence de la sélection.

## Le principe

**Un seul calcul, deux sorties.** Les mesures se calculent dans un module pur, à partir du
répertoire de run. Le CSV et les séries Prometheus sortent du même calcul : ils ne peuvent pas
diverger, et le CSV fait foi.

**Recalcul complet, jamais d'ajout en fin de fichier.** Chaque écriture réécrit les CSV en entier
depuis les sources dédupliquées du rejeu. La continuité à la reprise devient une propriété de
construction, et non une précaution que quelqu'un devra penser à reprendre.

**Toutes les métriques sont des Gauges réglées.** Aucun `Counter` incrémenté au fil des décisions :
un compteur qui s'incrémente se dédouble mécaniquement au rejeu d'une reprise. C'est exactement le
défaut que le § 4 du ticket demande de rendre impossible.

**La journée simulée commence à 3 h.** Même frontière que le point de reprise du ticket 075,
choisie parce qu'à cette heure les tampons sont vides et que presque personne n'est en trajet. Un
retour à 00 h 30 appartient donc à la soirée de la veille, et non au matin du lendemain.

**« La veille » est le jour VÉCU précédent, pas le jour calendaire précédent.** Mesuré sur le run
`2026-09-16_15_58` : les dates vont du 16 au 27 mars **en sautant les week-ends** — les départs du
samedi et du dimanche sont reportés au lundi. Comparer au jour calendaire précédent viderait la
reprise de la veille tous les lundis, soit un jour sur cinq, pour un week-end où l'agent n'a rien
vécu et n'a donc rien pu reprendre.

**Un état de mémoire se lit dans un instantané daté, jamais reconstitué après coup.** La `force`
d'un souvenir croît à chaque rappel : la médiane calculée aujourd'hui sur les souvenirs créés au
jour 2 n'est pas celle qu'ils avaient au jour 2. La recalculer chaque soir ferait bouger
rétroactivement une valeur déjà écrite — ce que le cas F1 interdit. Les mesures d'**état** (entrées
en mémoire, durée de vie médiane) sont donc lues dans le **point de reprise** qui clôt la journée,
et restent **vides** pour une journée qui n'en a pas encore. Les mesures de **flux** (trajets,
parts modales, vivier, opérations de concept) viennent de journaux datés et se recalculent sans
jamais changer.

**L'absence de mesure ne vaut jamais zéro.** Une habitude que la fenêtre ne détermine pas, un type
de souvenir absent, une trace éteinte : la cellule est **vide**. Dans ce dépôt, le zéro est le score
parfait ; une vacuité écrite `0` se lit comme une conformité totale ou une contradiction jamais
survenue, et se cite comme telle.

---

## Cas

### A — Sélection des personas

| Cas | Ce qui est vérifié |
|---|---|
| A1 | Moins de 4 trajets sur la journée de référence : recalé (`11195`, 2 trajets) |
| A2 | Un seul trajet à une option présentée suffit à recaler, quel que soit le nombre de trajets |
| A3 | Un seul mode choisi : recalé, même avec des options en nombre (`609` et `41275`, 3 options, voiture seule) |
| A4 | Les trois conditions réunies : candidat (`920187`) |
| A5 | Sur le run de référence, le critère retient **234** candidats — la sélection est mesurée, pas décrétée |
| A6 | Les agents de `--conserver` (`899549`, `616478`) sont retenus **de droit**, et le MANIFEST écrit s'ils passent le critère ou non : une conservation muette serait une sélection truquée |
| A7 | Dix agents au total, les quatre modes dominants couverts tant que les candidats le permettent |
| A8 | Deux exécutions sur la même source rendent les mêmes dix identifiants, dans le même ordre |
| A9 | Les agents sont recopiés **tels quels** du sceau : aucun champ ajouté, normalisé ni réordonné |
| A10 | Moins de dix candidats : refus nommant le manque. Le script ne complète jamais hors critère |
| A11 | Le MANIFEST porte le run de référence, son empreinte, les seuils du critère, et les chiffres mesurés agent par agent |

### B — Choix modal, par agent et par jour simulé

| Cas | Ce qui est vérifié |
|---|---|
| B1 | Les parts modales d'un agent-jour somment à 1 |
| B2 | Part décidée = trajets à ≥ 2 options / trajets du jour |
| B3 | Une journée entièrement mono-option donne une part décidée de **0,0** — mesurée, donc écrite |
| B4 | Un agent sans trajet ce jour-là n'a **pas de ligne** : pas une ligne de zéros |
| B5 | Les trajets rejoués après une reprise ne comptent qu'une fois, clé `(personne, activité, instant simulé)` |
| B6 | Chaque ligne porte l'index du jour simulé **et** sa date simulée |
| B7 | Un mode hors vocabulaire n'est pas rangé en silence dans « autres » : il est compté à part et signalé |
| B8 | Un départ à 00 h 30 compte dans la journée de la veille, pas dans celle du lendemain |
| B9 | Le numéro de jour simulé se compte depuis la première journée vécue, et la date simulée est écrite à côté |

### C — Habitude et rupture, par activité

| Cas | Ce qui est vérifié |
|---|---|
| C1 | Même activité, même mode que le **jour vécu précédent** : reprise de la veille = 1 |
| C2 | Même activité, mode différent : 0 |
| C2bis | Un week-end sauté n'est pas une veille : le lundi se compare au vendredi, et non au dimanche vide |
| C3 | Activité absente du jour vécu précédent : **vide**, jamais 0 |
| C4 | Conformité = mode majoritaire des **5 derniers jours OÙ CETTE ACTIVITÉ A ÉTÉ OBSERVÉE**, le jour courant exclu |
| C5 | Aucune observation antérieure : vide |
| C6 | Ex æquo dans la fenêtre : vide — un ex æquo tranché fabriquerait une habitude |
| C7 | La fenêtre saute les trous : activité observée aux jours 1, 4, 5, 7, 9 et 12, la fenêtre du jour 14 porte sur 4, 5, 7, 9 et 12 — jamais sur les jours 9 à 13 |
| C8 | Moins de cinq observations antérieures : la fenêtre porte sur ce qui existe, et le nombre d'observations est écrit à côté de la mesure |
| C9 | Deux activités d'un même agent basculent indépendamment : une ligne par activité, et l'agrégat par agent ne masque aucune des deux |
| C10 | Plusieurs trajets d'une même activité le même jour : le mode retenu est celui du **premier départ**, et le nombre d'occurrences est écrit |

### D — Mémoire

| Cas | Ce qui est vérifié |
|---|---|
| D1 | Vivier de rappel : minimum, médiane et maximum des candidats du jour |
| D2 | Un rappel à 0 candidat entre dans la mesure : c'est un vivier vide, pas une ligne à jeter |
| D3 | Les souvenirs servis du jour sont sommés séparément du vivier |
| D4 | Les quatre opérations de concept — créé, confirmé, précisé, contredit — sont comptées par agent et par jour |
| D5 | Pendant le gel du rejeu, **aucune** opération n'est tracée : un rejeu ne gonfle pas la courbe |
| D6 | Une opération hors des quatre n'est pas rangée dans l'une d'elles : comptée à part et signalée |
| D7 | Trace des concepts éteinte : les colonnes d'opérations sont **vides**, pas à 0 — « aucune contradiction » et « on ne mesure pas » ne se confondent pas |
| D8 | Durée de vie médiane par type de souvenir = médiane de la force, en jours, lue dans le **point de reprise** qui clôt la journée |
| D8bis | Une journée sans point de reprise — la journée en cours — a ses colonnes d'état **vides**, et elles se remplissent quand le point est écrit |
| D8ter | Recalculer deux fois à des instants différents rend la **même** valeur d'état pour une journée close : elle ne bouge plus |
| D9 | Un type de souvenir absent ce jour-là : cellule vide |

### E — Choc

| Cas | Ce qui est vérifié |
|---|---|
| E1 | Expositions et minutes injectées par agent et par jour, depuis `chocs.jsonl` |
| E2 | Le souvenir du choc est repéré par le texte du vécu, puis par son identifiant de document |
| E3 | Le jour où ce document figure dans les souvenirs servis, la colonne vaut 1 |
| E4 | Choc écrit mais jamais rappelé : expositions > 0 **et** servi = 0 — le cas que le ticket cherche à voir |
| E5 | Aucun choc déclaré : aucune ligne, pas des lignes de zéros |

### F — Continuité de part et d'autre d'une coupure

C'est le critère d'acceptation du ticket : deux jours simulés, un arrêt, une reprise nommée
(ticket 091), et les courbes doivent être continues.

| Cas | Ce qui est vérifié |
|---|---|
| F1 | Les lignes des jours antérieurs à la coupure sont **identiques** avant et après la reprise |
| F2 | Aucune clé `(jour, agent)` — ni `(jour, agent, activité)` — n'apparaît deux fois |
| F3 | Aucun jour manquant entre le premier et le dernier jour écrit |
| F4 | Les CSV sont réécrits en entier : un run repris ne laisse aucun reliquat de l'écriture précédente |
| F5 | Une gauge relue après le rejeu de trois jours porte la valeur du jour, jamais son double |
| F6 | Le vérificateur de continuité **refuse**, avec un code de sortie non nul, un cas dédoublé ou troué fabriqué pour l'occasion |
| F7 | Un run coupé puis repris et un run continu de même durée produisent les mêmes lignes |

### G — Séries et tableau de bord

| Cas | Ce qui est vérifié |
|---|---|
| G1 | Une famille de métrique par mesure, et des labels bornés — agent, mode, activité, opération, type |
| G2 | Toutes les familles sont des Gauges : aucun Counter dans le lot (vérifié sur le registre) |
| G3 | Chaque requête du tableau de bord 09 ne cite que des familles **réellement exposées** par le code |
| G4 | Les couleurs de modes du tableau de bord suivent la palette officielle du dépôt |
| G5 | Le tableau de bord porte, en tête, que son axe est en temps réel et non en temps simulé, et que le CSV fait foi |

### H — Activation, sûreté, effets de bord

| Cas | Ce qui est vérifié |
|---|---|
| H1 | Éteint par défaut : aucun fichier écrit, aucune famille publiée |
| H2 | Le répertoire des mesures est créé à la **première écriture**, jamais à l'import — un import ne sème pas un répertoire de run |
| H3 | Une erreur de calcul lève une `[ALARME]` et ne remonte jamais à la boucle de synchronisation |
| H4 | Une source absente — pas de trace de rappel, pas de chocs — n'empêche pas d'écrire les mesures qui, elles, sont calculables |
| H5 | Le calcul ne sollicite aucun modèle et n'écrit rien en mémoire : il observe, il ne participe pas |

---

## Ce que ce contrat ne couvre pas

Le double comptage des journées rejouées **dans `moves.csv` lui-même** : les mesures le
neutralisent à la lecture, elles ne le corrigent pas à la source. Le défaut de planification du
soir de `11195` non plus. Chacun a son ticket.

Et rien ici ne teste une règle de mémoire, de routage ou de choc : ce ticket n'en change aucune.
La seule écriture nouvelle dans le chemin de la mémoire est la trace des opérations de concept, qui
consigne ce qui se produit déjà sans rien décider.
