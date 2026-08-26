# Protocole — corriger un paramètre exogène sans rejouer de simulation

Un paramètre **exogène** est une valeur que le modèle consomme sans la produire : temps
terminal d'un trajet véhiculé, temps d'attente, pénalité de correspondance. Le dépôt en
interdit l'ajustement sur un score (`terminal_time.yaml`, décision T2 du ticket 013) — mais
il n'interdit pas de le **re-sourcer** sur une mesure, et c'est même ce que son
`provenance: sourced` réclame.

Ce document décrit la méthode suivie le 2026-08-24 pour aligner le temps terminal de la
voiture sur EMC². Elle est réutilisable telle quelle pour tout paramètre du même genre, et
son intérêt tient à une seule propriété : **elle chiffre l'effet avant de payer un run de
simulation**, qui coûte des heures.

Voir aussi : [prompt_calibration.md §10 et §11](prompt_calibration.md) (l'outillage d'A/B),
[velo-equipement.md](velo-equipement.md) (le même esprit appliqué à un trait de population).

---

## Vue d'ensemble

| Étape | Coût | Ce qu'elle produit | Ce qu'elle ne dit pas |
|---|---|---|---|
| 0 · **Vérifier l'exclusion** (à la main depuis le 2026-08-26) | 0 | qu'aucun run ne consomme le même quota | ce que fait la campagne cloud — et, sans jeton, la PREUVE que la vérification a eu lieu |
| 1 · Mesurer le paramètre dans l'enquête | 0 | une **loi**, pas une moyenne | si le modèle y réagit |
| 2 · Réécrire un jeu gelé | 0 | un jeu `vN+1`, une variable de plus | ce qu'une simulation produirait |
| 3 · A/B apparié sur le moteur de calibration | ~15 appels/bras | l'effet sur la loss et les parts modales | l'effet des chaînes de véhicule |
| 4 · Exporter, archiver, publier | 0 | traces committées + page horodatée | — |
| 5 · **Porte de décision** | — | production, ou rejet | — |

L'ordre n'est pas cosmétique. L'étape 3 est **le test qui peut démentir l'hypothèse**, et
elle passe avant toute modification de production. L'étape 0 passe avant tout : une mesure
prise pendant un run concurrent n'est pas une mesure imprécise, c'est une mesure dont on ne
sait pas ce qu'elle décrit. Depuis le 2026-08-26 elle n'est plus outillée — c'est une
vigilance, plus un verrou. Si l'effet mesuré est nul, on a dépensé
trente appels LLM au lieu d'une nuit de calcul et d'un paramètre faussé.

---

## 0 · L'exclusion — plus de verrou, une vigilance

**Aucun appel LLM de ce protocole ne devrait se passer pendant qu'un run tourne.** Ce n'est
pas une règle d'hygiène, c'est une condition de validité : la mesure et la simulation
consomment le **même quota**, et quand un fournisseur sature la cascade bascule sur le
suivant. Si la bascule survient entre le premier et le second bras, **les deux bras n'ont pas
été évalués par le même modèle** — un facteur confondu avec le traitement, et invisible dans
les agrégats.

Deux autres ressources sont partagées, et les deux abîment silencieusement :

| Ressource | Ce qui casse |
|---|---|
| Store content-addressed | deux procédures écrivant sous la même clé `ds=` |
| Lien `experiments/current` | `make run` le repointe ; une archive en cours archiverait le mauvais run |

**Le jeton d'exclusion qui automatisait cette vérification a été retiré le 2026-08-26.** Il
n'y a plus ni `make protocol-lock`, ni garde-fou dans les scripts `ab_*.py` : ceux-ci
démarrent désormais sans rien vérifier.

⚠ **La condition de validité, elle, n'a pas disparu — seul son contrôle l'a.** Avant une
mesure, il reste à s'assurer à la main qu'aucun run ni service consommateur ne tourne
(`docker compose ps` doit être vide, ou au moins sans `controller` ni `worker`), et que la
campagne génétique de la VM cloud est en pause (`systemctl is-active calib-ga` → `inactive`).
Ce que le verrou apportait et qui manque désormais : la **preuve**. Une trace ne peut plus
citer un jeton horodaté avec ses instantanés de quota ; elle ne peut plus qu'affirmer que la
vérification a été faite. À une mesure près, la différence est mince ; à l'échelle d'une
campagne, c'est ce qui distingue un dossier opposable d'un souvenir.

Les mesures antérieures au 2026-08-26 gardent leur preuve : leurs jetons sont committés dans
leurs traces (`docs/traces/2026-08-25_ab_meteo/protocol_lock.json`).

## 1 · Mesurer le paramètre dans l'enquête

Le paramètre doit exister dans la source qui sert de **cible**, sinon la correction n'est
qu'un autre réglage. Pour le temps terminal : `T2` (marche au départ), `T6` (marche à
l'arrivée) et `T11` (durée de recherche du stationnement) du fichier trajets d'EMC².

```bash
make terminal-time      # → llm_module/data/terminal_time_emc2.json
```

**Publier un contrôle de validité avec la loi.** Une variable d'enquête peut valoir zéro
parce qu'elle n'est pas renseignée, pas parce que la chose n'existe pas. Le doute légitime
ici : si la marche vers la voiture était codée comme un trajet à pied *distinct*, `T2`/`T6`
vaudraient 0 par construction. Deux contrôles, tous deux dans la ressource :

- **négatif** — sur les 24 481 déplacements comportant un trajet voiture, aucun ne porte de
  trajet à pied : la marche terminale ne peut être *que* dans `T2`/`T6` ;
- **positif** — sur les trajets en transports collectifs, de structure identique, `T2 + T6`
  donne 6 minutes en médiane. L'instrument sait enregistrer un temps terminal.

Sans le contrôle positif, un zéro partout serait indistinguable d'une variable morte.

**Servir une loi, pas une moyenne — quand la moyenne n'est pas représentable.** Ici la
moyenne d'enquête est *inférieure à la minute* (0,36 min d'accès à Toulouse) alors que le
rendu n'affiche que des minutes entières. Une constante devrait donc valoir 0 partout, ce
qui effacerait une queue réelle : 2 à 4 % des trajets ont vraiment 5 minutes ou plus. Le
tirage garde la moyenne **et** la queue.

Et **ce n'est pas une cloche** : la distribution est massée à zéro (87 à 96 % selon la
couronne) et étirée à droite. Une gaussienne produirait des valeurs négatives et détruirait
la masse à zéro. On sert l'histogramme observé, pas une forme choisie pour sa commodité.

## 2 · Réécrire un jeu gelé, en local

C'est l'étape qui évite la simulation, et elle n'est licite que sous deux conditions —
à vérifier, pas à supposer :

1. **le paramètre est séparable** de ce qu'on ne sait pas recalculer. Le temps terminal est
   additif et indépendant du temps réseau : `terminal_time.yaml` acte déjà cette séparation
   en versionnant à part `version` (les plans) et `routing_version` (le réseau) ;
2. **le jeu porte le paramètre de façon lisible.** Les jeux gelés décomposent chaque option
   sous-puce par sous-puce, donc la réécriture est mécanique. Vérifié avant de commencer :
   100 % des options voiture de `v5` sont décomposées.

```bash
cd prompt_calibration
python rewrite_terminal_time.py --src v5 --dst v6 --dry-run   # chiffre, n'écrit rien
python rewrite_terminal_time.py --src v5 --dst v6
```

**Une seule variable bouge.** Les sous-puces à zéro sont *conservées*
(« Rejoindre la voiture : 0 minute ») plutôt que supprimées : effacer les composantes
nulles changerait la **structure** du rendu en même temps que les durées, et l'A/B
mesurerait deux choses à la fois.

**Le tirage est déterministe** (hachage), pour deux raisons cumulées : le jeu doit être
reproductible, et le cache d'éval du store est indexé sur le nom de version — un jeu qui
change de contenu sous un nom stable ferait servir une éval périmée.

**Ce que la réécriture ne peut pas faire**, et qui doit accompagner tout résultat : elle ne
change pas *quelles* options ont été offertes, et ne rejoue pas les **chaînes de véhicule**,
où le choix d'un jour se répercute sur les offres du lendemain.

## 3 · Valider par le moteur de calibration

On réutilise les *mécanismes* de la calibration sans sa boucle : même `RunConfig`, même
`Evaluator`, même loss, même store content-addressed, mêmes jeux gelés. `calibrate run`
serait deux ordres de grandeur trop cher — il évalue la graine sur `train` **puis** lance
l'attribution initiale par omission (N+1 évals).

```bash
python ab_terminal.py --dry-run     # annonce le coût, dit ce qui est déjà en cache
python ab_terminal.py
```

Quatre exigences, chacune pour une raison :

- **chiffrer avant de dépenser.** `--dry-run` annonce le nombre d'appels et s'arrête ;
- **comparatif apparié** — mêmes personas, mêmes options des deux côtés. La variance du Δ
  s'en trouve très réduite ;
- **l'effectif opposable est celui des personas distincts**, pas des décisions : les
  déplacements d'un même agent partagent son profil ;
- **le jeu `test` est refusé** par le script : il porte le regard unique du protocole.

Le modèle d'éval doit être **épinglé** et non un alias flottant (`-preview`) : le garde-fou
`assert_pinned_eval_model` le refuse sur un store neuf, parce qu'un alias re-résout au fil
du temps et mélangerait deux modèles sous une même clé de cache.

## 4 · Exporter, archiver, publier

Le store et les jeux dérivés sont **gitignorés** — régénérables, donc volatils. Une mesure
citée ailleurs ne peut pas s'appuyer sur eux seuls.

```bash
python archive_ab.py --out ../docs/traces/<date>_<sujet>    # agrégats committés
cd .. && make terminal-page                                 # page horodatée + graphiques
```

Trois formes du même contenu, toutes **générées** depuis le store : `README.md` (lisible
dans le dépôt), `results.json` (relisible par un script), `index.html` (lisible au
navigateur). Pas trois documents à tenir en phase à la main.

⚠ `docs/experiments/` serait attrapé par la règle `experiments*/` du `.gitignore` — faite
pour les dossiers de run, qui pèsent des gigaoctets. L'archive irait rejoindre ce qu'elle
archive. D'où `docs/traces/`.

La page de mesure est **horodatée** et vit à côté d'`index.html` sans y entrer :
`index.html` score un *run*, cette page score des *jeux gelés*. Les mêler sous un même
composite ferait perdre le seul repère qui compte, de quoi le chiffre parle.

## 5 · Porte de décision

**Rien ne part en production avant cette étape.** L'étape 3 dit ce que la correction vaut ;
elle ne dit pas s'il faut la faire — c'est une décision de modélisation, et elle appartient
à qui répond du modèle.

Trois issues, et le rejet est une issue normale :

| Issue | Quand | Suite |
|---|---|---|
| **Adoption** | l'effet est significatif et la source fait autorité | correction en production, bump de version, garde-fou de non-régression |
| **Rejet** | l'effet est nul, ou la source ne tranche pas | on garde la trace de la mesure négative — elle vaut, elle ferme une hypothèse |
| **Report** | l'effet est réel mais la source est douteuse | on documente la tension et on ne touche rien |

Le rejet doit rester **aussi archivé** que l'adoption. Le premier A/B de la journée — la
puce « Chaîne de la journée » du prompt — a donné +0,11 point de vélo, soit rien : c'est
une hypothèse éliminée, et sa trace est dans le même dossier que celle qui a réussi. Sans
elle, quelqu'un la reformulerait dans six mois.

### En cas d'adoption : trois choses à ne pas oublier

1. **La bonne version de cache.** Bumper celle qui indexe les plans et les décisions
   (`version`), pas celle du routage (`routing_version`) si le temps réseau n'a pas changé
   — sinon on repaie des heures de calcul pour rien.
2. **Un garde-fou de non-régression.** Un test qui refuse un retour aux anciennes valeurs.
   C'est ce qui distingue une correction d'un correctif : sans lui, la régression revient
   au prochain conflit de fusion, silencieusement.
3. **Ne livrer que ce qui a été mesuré** — ou mesurer ce qu'on ajoute. Voir ci-dessous.

---

## Le second piège : quand le traitement ne touche qu'une petite part du jeu

Découvert le 2026-08-24 en appliquant cette méthode à un **trait de population**
(`car_availability`, ticket 018) et non plus à une durée. Ce piège-là ne produit pas un
chiffre imprécis : il produit un **faux positif spectaculaire**, et il a bien failli
passer.

Le temps terminal réécrivait *toutes* les options voiture — la quasi-totalité du jeu
bougeait. Un trait de population, lui, ne corrige que les personas concernés : sur
`car_availability`, 72 personas sur 818, soit **9 à 10 % des records**. Les 90 % restants
sont identiques dans les deux bras — mais ils sont **ré-évalués** dans chacun, puisque
`eval_params_key()` porte `ds=<version>`. Ils n'apportent donc aucun signal et tout le
bruit de non-déterminisme du modèle.

### Ce qui s'est passé

Premier A/B sur `rank`, le jeu par défaut : effet traité **+7,27 pt de voiture**, une
amplitude qui recoupait presque exactement l'effet marginal connu de la politique logit
(−7,3 pt en passant de `all` à `some`). Tout concordait. C'était faux.

Trois garde-fous ont rattrapé le coup, dans cet ordre :

**1 · Le placebo a montré que l'agrégat mentait sur le signe.** La décomposition se
reconstruit à l'unité près sur les quatre modes :

| Canal | Δ part voiture | Masse | Contribution à l'agrégat |
|---|---|---|---|
| Traitement (personas basculés) | +7,27 pt | 9,9 % | +0,72 pt |
| Placebo (records identiques) | −1,12 pt | 90,1 % | −1,01 pt |
| **Agrégat observé** | | | **−0,29 pt** |

Lire l'agrégat aurait conclu que corriger le biais **baisse** la part voiture. Le bruit
pesait neuf fois le signal parce qu'il portait sur neuf fois plus de masse.

**2 · La dispersion a montré que la moyenne mentait sur l'ampleur.** Les +7,27 pt se
décomposaient en 5 personas en hausse, 1 en baisse, 3 immobiles — pour une **médiane de
+1,3 pt**. Deux cas passant de 70 % à 100 % portaient toute la moyenne. À neuf personas,
ce n'était pas un résultat.

**3 · Le plancher lui-même était mal posé.** Comparer un Δ mesuré sur 22 unités de masse
à un plancher mesuré sur 201 oppose une estimation bruyante à un plancher serré : c'est un
faux test, et il déclare « signal » la variance du petit sous-ensemble. Le plancher doit
être **ramené à la masse traitée**, en 1/√n :

    plancher_opposable = plancher_placebo × √(masse_placebo / masse_traitée)

Sur `rank` cela porte le plancher de 1,58 à **4,79 pt** — l'effet de +7,27 n'est plus qu'à
1,5 fois le bruit. Sur `val`, de 1,74 à **5,49 pt**, ce qui fait basculer un « signal »
apparent de +4,25 pt du bon côté de la barre. C'est le cas qui trompe le plus : *au-dessus
du plancher brut, sous le plancher mis à l'échelle*.

**4 · Le jeu plus large a tranché.** Sur `train` — 35 personas traités au lieu de 9 —
l'effet voiture tombe à **+0,24 pt pour un plancher mis à l'échelle de 2,38 pt**. Et le
composite se dégrade légèrement (+0,46) au lieu de s'améliorer.

**5 · La mise en commun a donné le chiffre de tête.** Sur les 45 personas traités des deux
jeux **disjoints** (`train` + `val`), l'effet voiture vaut +1,34 pt pour un plancher de
1,31 — un rapport de 1,02, soit exactement le niveau du bruit.

Et c'est **l'amplitude qui a tranché, pas la significativité** : en prenant le point estimé
au pied de la lettre, l'effet agrégé vaut **+0,12 pt de part voiture**, contre les 5,28 de
composite qu'avait rapportés la correction du temps terminal. Quand la reconstruction donne
un dixième de point, la question de la significativité devient secondaire — et c'est une
conclusion beaucoup plus solide qu'un test.

⚠ **Et les deux jeux ne sont même pas indépendants** : le manifeste dit
`rank ⊂ screen ⊂ train`. Les 9 personas de `rank` sont *inclus* dans les 35 de `train`.
Il n'y a donc jamais eu deux mesures en désaccord — il y a eu **une sous-population de 9
qui fluctuait**, et la lecture complète qui ne confirme pas. Vérifier la filiation des
jeux avant d'appeler « réplication » deux lectures est une étape du protocole, pas un
détail : `val` est le seul jeu réellement indépendant de `train`, `test` restant fermé.

### Le cas symétrique : quand le traitement touche PRESQUE TOUT le jeu

Le dispositif ci-dessus suppose un traitement partiel. Le cas inverse existe et il retire le
témoin, ce qui est facile à ne pas voir : mesuré sur le ticket 023 (fenêtre de tirage de la
météo), le traitement touche **98,90 %** des enregistrements. Le canal placebo ne pèse alors
que **1,10 %, soit 23 enregistrements** — et la mise à l'échelle en
`√(masse_placebo / masse_traitée)` prescrite ci-dessous l'amplifierait par **9,5**, rendant
tout test vide de sens. Un plancher estimé sur vingt-trois enregistrements n'est pas un
plancher.

**Substitut : le témoin nul à pleine masse.** Un troisième bras qui subit *le même mécanisme
de réécriture* sans changement de distribution — pour un tirage, la même liste de jours avec
une autre graine. Il porte la même quantité de brassage que le traitement et un effet attendu
de zéro : son Δ est le plancher de bruit, à la bonne masse. Il coûte un bras d'A/B.

Sur le ticket 023, ce témoin a **renversé une lecture** avant tout appel LLM : le traitement
déplace la part d'enregistrements sous la pluie de −1,20 pt, mais le témoin nul la déplace de
**−5,08 pt**. L'effet « pluie » du traitement est quatre fois plus petit que le bruit de
re-tirage — il n'existe pas. Seul l'effet thermique subsiste (−4,90 °C contre −0,02 au
témoin).

**Règle générale :** avant de choisir le témoin, mesurer la **masse traitée**. Sous 50 %, le
placebo du protocole ; au-dessus, un témoin nul à pleine masse. Entre les deux, les deux.

### La règle qui en découle

Dès que le traitement ne touche pas la majorité du jeu :

1. **Publier trois lectures** — *traité* (où vit l'effet), *placebo* (les records
   identiques, dont le Δ devrait valoir zéro et donne le **plancher de bruit** ; témoin
   **gratuit**, il était déjà payé) et *agrégat* (diluée, interprétable seulement au
   regard du plancher).
2. **Reconstruire** l'effet agrégé (traité × part traitée) au lieu de le lire.
3. **Un effet traité sous le plancher placebo n'est pas un effet**, quel que soit son signe.
4. **Regarder la dispersion, pas la moyenne** : médiane, nombre de cas en hausse et en
   baisse. Une moyenne portée par deux personas n'est pas un effet de population.
5. **Ramener le plancher à la masse traitée** (× √(masse_placebo / masse_traitée)) avant
   de le comparer à quoi que ce soit. Un plancher brut sur un petit traité est un faux test.
6. **L'effectif opposable est le nombre de personas TRAITÉS**, pas les records du jeu — et
   quand il est petit, dimensionner le jeu là-dessus avant de payer.
7. **Vérifier l'indépendance des jeux** avant de parler de réplication, et ne mettre en
   commun que les jeux disjoints.
8. **Conclure sur l'amplitude reconstruite** autant que sur le test : un effet agrégé d'un
   dixième de point ferme la question quel que soit son statut statistique.

**Le placebo est aussi un test de l'instrument.** Un Δ placebo anormalement grand ne dit
rien du traitement mais beaucoup de l'éval : température, cascade de fournisseurs,
troncature. Il vaut d'être regardé pour lui-même — sur `train`, un placebo de −0,76 pt sur
les transports collectifs, de même signe que le Δ traité, signale une dérive systématique
entre bras et non du bruit pur.

Outillage : `prompt_calibration/ab_car_availability.py` implémente les trois lectures et
refuse un jeu où rien ne diffère.

---

## Le piège de cette méthode : la dérive entre mesuré et livré

C'est le défaut qui s'est produit le 2026-08-24, et il est instructif parce qu'il vient
d'une bonne intention.

L'A/B a mesuré la **voiture seule** : le jeu `v6` réécrit les jambes terminales des options
voiture et laisse le vélo à ses valeurs `tt2` (1 min par bout). Le gain mesuré, −4,52 de
composite, porte donc sur cette correction-là et sur aucune autre.

Or la correction livrée en production (`tt3`) a **aussi** aligné le vélo : 1,00 → 0,11 min
par bout. La raison était défendable — l'enquête donne une source pour le vélo aussi, et
corriger la voiture seule aurait laissé un biais non documenté en face d'un biais corrigé.
Mais elle **n'a pas été mesurée**, et son sens va contre le gain : rendre le vélo 1,8 minute
plus rapide le rend plus attractif, donc annule une partie de ce que la correction voiture
avait gagné. Sur un trajet vélo typique de 10 minutes, c'est ~18 % de temps en moins.

La leçon n'est pas « ne corrigez qu'une chose ». C'est : **si le périmètre livré dépasse le
périmètre mesuré, il faut le dire et le mesurer**, sinon le chiffre publié ne décrit plus
ce qui tourne. Le correctif est un jeu `v7` alignant les deux modes, et un A/B `v5` contre
`v7` — quinze appels de plus.

Le symptôme est reconnaissable et se cherche à la relecture : comparer le diff de production
au diff du jeu de test. S'ils ne portent pas sur les mêmes lignes, l'écart est la partie non
validée.

**Ce que le correctif a chiffré.** `v7` aligne les deux modes et donne un composite de
24,83 contre 27,00 pour `v5` : le gain réellement livré est de **−2,17**, non de −4,52.
L'alignement du vélo rend **+2,35**, soit 52 % du gain mesuré sur la voiture seule — la
moitié. Le gain net reste franc et la correction reste celle que la source réclame, mais
le chiffre opposable a changé de moitié entre la mesure et la livraison. C'est l'ordre de
grandeur qu'il faut avoir en tête : ce piège ne coûte pas une décimale.

**Le trou a été refermé le 2026-08-24** : `rewrite_terminal_time.py` prend désormais un
`--modes`, et trois jeux coexistent — `v5` (temps de la config), `v6` (voiture alignée) et
`v7` (voiture **et** vélo alignés, soit le périmètre exact de `tt3`). L'A/B se lit sur les
trois colonnes, et celle du milieu dit précisément ce que l'alignement du vélo coûte au
gain. Huit tests verrouillent le périmètre (`TestPerimetreDesModes`) : qu'aligner la
voiture laisse le vélo intact, que chaque mode garde sa clause terminale, et que les deux
tirent indépendamment — la clé de tirage porte le mode, sans quoi voiture et vélo d'une
même option recevraient la même durée.

**Un piège de second ordre, rencontré en refermant le premier.** Ajouter le mode à la clé
de tirage change les valeurs tirées, donc le **contenu** de `v6` — alors que son nom, lui,
ne change pas. Or la clé de cache d'éval (`ds=v6`) porte le nom de version, pas une
empreinte du contenu : l'éval en cache décrivait un jeu qui n'existait plus. Il a fallu la
purger explicitement avant de remesurer. **Règle** : toute modification du mécanisme de
tirage invalide les évals des jeux qu'il a produits, et le store ne le détectera pas pour
vous.
