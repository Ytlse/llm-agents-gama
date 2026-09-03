# L'équipement vélo du persona — appris sur EMC², plus recopié de l'ENTD

Le trait `traits_json.personal_bike` décide si un agent peut prendre un vélo. C'est le
seul canal par lequel l'information vélo atteint l'agent, et le vélo est le mode dont la
part modale est la plus scrutée du projet. Cette page dit comment il est produit depuis le
[ticket 015](../tickets/ticket_015_acces_velo_progedo.md), pourquoi la méthode précédente
était fausse, et **quelles cibles sont opposables** à une population synthétique — car
deux des critères d'acceptation du ticket ne le sont pas, et la mesure le montre.

Voir aussi : [population-post-traitements.md](population-post-traitements.md) (les quatre
étages entre eqasim et l'agent), [vehicle-chain.md](vehicle-chain.md) (ce que l'agent fait
du vélo une fois qu'il l'a).

---

## Le problème : bon total, répartition fausse

eqasim tirait le trait par `p = min(1, vélos_du_donneur / taille_ménage)`, où le nombre de
vélos est **recopié** d'un ménage réel de l'ENTD 2008 apparié à la personne. Le problème
n'est pas le nombre — c'est un vrai ménage enquêté — mais le **foyer auquel il est
attaché** : l'appariement porte sur `age_class`, `sex`, `any_cars`,
`socioprofessional_class` et `departement_id`, et **ni sur la taille du ménage ni sur
l'habitat**. Un célibataire toulousain hérite donc des 3 vélos d'une famille de cinq, et
une famille de cinq du zéro vélo d'un couple âgé.

Mesuré sur `toulouse_population_1000.json` face aux microdonnées EMC² Toulouse 2023
(ProGEDO `lil-1750`) :

| Croisement | EMC² 2023 | Ancienne imputation |
|---|---|---|
| Personnes dotées d'un vélo | 50,9 % | 53,3 % |
| dont ménage d'1 personne | 33,4 % | **76,4 %** |
| dont ménage de 2 personnes | 47,8 % | 61,9 % |
| dont ménage de 4 personnes | 65,4 % | **35,7 %** |
| Ménages équipés, individuel isolé | 70,9 % | 50,0 % |
| Ménages équipés, grand collectif | 37,5 % | 52,8 % |
| Part de VAE | 7,7 % du parc | 13,4 % des porteurs |

**Le total était à peu près juste ; la répartition était fausse**, et le gradient de taille
de ménage carrément **inversé**. Deux biais s'ajoutaient : la variable ENTD lue
(`V1_JNBVELOADT`) ne compte que les vélos **adultes** — `V1_JNBVELOENF` n'est jamais
chargée, soit 25 % du parc ignoré — et 14,8 % de VAE est la part des *ménages équipés*
possédant un VAE, pas la part du **parc**, d'où 1,7× trop de VAE.

## Pourquoi tirer le stock du ménage d'abord

Le nombre de vélos d'un ménage est un **entier partagé**. Si on décide individu par
individu, on obtient des foyers incohérents, et surtout on ne peut plus produire la bonne
*forme* de distribution. Sur les ménages de 4 personnes, comparé à un tirage individuel
indépendant **calé sur la même moyenne** (2,62 vélos, `p = 0,654`) :

| Vélos du ménage | EMC² observé | Tirage individuel indépendant |
|---|---|---|
| 0 | **15,7 %** | 1,4 % |
| 1 | 7,5 % | 10,8 % |
| 2 | 16,5 % | 30,7 % |
| 3 | 20,2 % | 38,7 % |
| 4 et + | **40,1 %** | 18,3 % |

Les deux colonnes ont **exactement la même moyenne** et ne décrivent pas le même monde. La
réalité est en tout ou rien : 16 % de familles sans aucun vélo, 40 % avec un vélo par tête
(variance 2,13 contre 0,91, surdispersion ×2,4). Comme les moyennes coïncident, **aucun
redressement sur la moyenne ne peut les rapprocher** : une correction a posteriori déplace
le niveau, jamais la forme. L'équipement vélo est un trait de foyer — on est une famille à
vélo ou on ne l'est pas — pas une pièce lancée pour chaque membre.

---

## Les trois étages

Tout vit dans [`llm_module/core/bike_ownership.py`](../../llm_module/core/bike_ownership.py)
(module pur, I/O confinée à `load`), appris par
[`scripts/progedo_logit/export_bike_ownership.py`](../../scripts/progedo_logit/export_bike_ownership.py)
(`make bike-ownership`) et appliqué par
[`scripts/data/population/enrich_personal_bike.py`](../../scripts/data/population/enrich_personal_bike.py).

### Étage 1 — combien de vélos dans le ménage

Logit **multinomial** sur `k = M21` écrêté à `4+`, 10 783 ménages, pondération `COE0`.
Covariables : taille du ménage, nombre de VP (`M6`), et la zone fine du domicile par sa
**densité de ménages** et sa **distance à l'hypercentre**. Un tirage **par ménage**, en
remplacement de la recopie du donneur : le nombre de vélos cesse d'être indépendant du
foyer qui le reçoit, et c'est tout l'objet du ticket.

Deux covariables du ticket sont **écartées**, pour deux raisons différentes :

- **`M2` (statut d'occupation du logement)** : le persona ne le porte pas. Règle du contrat
  de features du dépôt — une variable non calculable à l'instant de l'application n'entre
  pas.
- **`M1` (type d'habitat)** : c'était le « piège à trancher » du ticket, et la mesure le
  tranche. Le `housing_type` du persona est lui-même **imputé**
  ([housing_type.py](../../llm_module/core/housing_type.py)) et ne coïncide avec l'habitat
  réel qu'**une fois sur deux** (47,6 % avec la loi de zone seule, 50,2 % depuis le raking
  sur la taille du ticket 019). Conditionner `k` sur la zone seule reproduisait la courbe
  d'équipement par habitat imputé à **0,6 point près** ; conditionner sur l'habitat imputé
  la **dégradait** (+4,0 à −4,6 points), parce que c'est appliquer un coefficient appris
  sur une variable observée à une variable fausse une fois sur deux. Surtout, cela
  créerait une dépendance entre deux imputations dont la loi jointe n'est ni la vraie ni
  celle qu'on peut mesurer.

  **Deux réserves à porter, plutôt qu'à taire.** D'abord, ces deux mesures ont été faites
  contre l'imputation d'habitat *antérieure au ticket 019* : la conclusion mérite d'être
  rejouée maintenant que l'habitat porte une information de taille de ménage. Ensuite, le
  raisonnement reste solide sur le fond — cette information de taille, l'étage 1 la
  **conditionne déjà directement**, et plus proprement, puisqu'il lit la taille nominale
  au lieu d'un tirage bruité qui la reflète. Le seul gain résiduel possible serait une
  information de *zone* que `log_density` et `log_dist_center` ne captureraient pas et que
  la loi d'habitat par zone porterait ; c'est mesurable, et ce n'est pas mesuré.

### Étage 2 — qui, dans le ménage, tient les vélos

**`k` décide combien, la propension décide seulement qui.** C'est le point à ne pas
inverser.

La propension est un logit binaire sur `P20 ∈ {plusieurs jours/semaine, plusieurs
jours/mois, occasionnellement}` — la pratique déclarée en tant que **conducteur**, le
meilleur indicateur disponible de « à qui est ce vélo », et il n'y en a pas d'autre :
l'enquête ne demande jamais qui possède quoi. Restreint à `PENQ = 1` (15 775 personnes sur
20 890), pondération `COEP`. Covariables : `k`, taille du ménage, âge, genre, occupation,
densité et distance au centre. **Aucune distance de déplacement** : un stock doit être
invariant au trajet, sinon le même agent a un vélo pour la boulangerie et plus pour le
travail, et le verrou de chaîne de véhicule perd son sens.

L'attribution est un **tirage sans remise pondéré**, schéma d'Efraimidis–Spirakis : chaque
membre éligible reçoit une clé `u ** (1 / p)`, on classe par clé décroissante, on sert les
`min(k, éligibles)` premiers. Trois propriétés voulues : le nombre attribué est *exactement*
le stock du ménage ; la probabilité d'être servi croît avec la propension ; et il n'y a
**aucun ordre déterministe** — pas de « toujours l'aîné », pas d'artefact de tri sur les
ex æquo.

Les derniers vélos échoient donc à des membres de faible propension : **ce sont les vélos
dormants**, et il est juste de les représenter. Leur porteur ne les utilisera pas — c'est
au modèle de choix modal et à l'agent de décider de ne pas les prendre, pas à l'imputation
de les faire disparaître. Mesuré sur l'enquête : **19,6 points** de la population tiennent
un vélo sans le pratiquer, pour **11,1 points** d'écart net entre porteurs (50,5 %) et
pratiquants (39,5 %) — la différence étant les **8,5 points** qui pratiquent *sans* vélo
attribué (libre-service, ménages à zéro vélo). Le flux joue dans les deux sens.

**Éligibilité : 5 ans et plus**, le champ de la question `P20`. Cela interdit
structurellement d'attribuer le vélo du foyer à un enfant de trois ans. Si `k > éligibles`,
le surplus n'est porté par personne : un vélo est un objet du ménage, et le JSON ne portant
que des individus, un vélo sans titulaire n'y apparaît simplement pas.

**Limite d'identification, assumée** : 67 % des ménages (7 238 sur 10 783) n'ont qu'une
seule personne enquêtée. On peut estimer `P(pratique | covariables)` ; on ne peut **pas**
observer qui, parmi trois frères et sœurs, roule. L'attribution est donc indépendante
conditionnellement à `k`, sans corrélation intra-foyer modélisée.

Conséquence à assumer : la probabilité d'inclusion réelle du schéma n'est pas exactement
`p_i`, elle est déformée par la contrainte de comptage. La table `P(pratique | k, taille)`
n'est donc **pas une identité** mais un **critère de validation** — on vérifie après coup
que le mécanisme la reproduit.

### Étage 3 — quel type de vélo

**7,67 % du parc** en VAE (`ML21 / M21`), tiré **par vélo attribué** et non par personne.
`ML21` n'existe que dans le *fichier original* de la livraison — dans le fichier standard,
`M22` est entièrement vide ; le rapprochement se fait sur `(MP2, ECH)` et est vérifié par
`M20 == M21` plutôt que supposé depuis l'ordre des lignes.

Le filtre `âge ≥ 14` est conservé (garde-fou du ticket 008), et il est **renormalisé** :
`VAE_SHARE` est une part du parc entier, enfants compris, donc l'appliquer aux seuls
éligibles ferait sortir le parc *sous* la cible. On applique
`p = VAE_SHARE / (1 − part_des_porteurs_inéligibles)`, la part venant de la ressource
(16,2 % mesurés sur l'enquête). Ce choix est délibérément **indépendant du fichier
enrichi** : une probabilité recalculée sur chaque population ferait dépendre le type de
vélo d'un persona du fichier dans lequel il se trouve, si bien que le même ménage sortirait
en VAE dans la population à 1 000 agents et en vélo musculaire dans celle à 10 000.

À ne pas confondre avec les **12 % de trajets** vélo faits en VAE (rapport AUAT p. 26) :
l'écart 7,7 → 12 % est un effet d'**usage** — un VAE roule plus — pas de stock. Viser 12 %
ici serait une erreur de niveau.

---

## Déterminisme

Aucun RNG. Le tirage est un hachage SHA-256 d'une clé salée (`DRAW_SALT`, versionné) :

| Étage | Clé |
|---|---|
| 1 — stock `k` | adresse du domicile |
| 2 — attribution | `bike-holder:{clé de ménage}:{index de personne}` |
| 3 — type de vélo | `bike-kind:{clé de ménage}:{index de personne}` |

Les sels des étages 2 et 3 sont **distincts** : sans quoi le rang de tirage et le type de
vélo seraient corrélés et les VAE iraient systématiquement aux hautes propensions.
`hash()` de Python est randomisé par processus et n'est jamais utilisé.

Changer `DRAW_SALT` rebat tout le parc : c'est un acte délibéré et daté, pas un effet de
bord.

---

## Voie 1 — le post-traitement (livré, mesuré)

```bash
make bike-ownership   # (ré)apprend le modèle depuis les microdonnées PROGEDO
```

```bash
llm-agents/.venv/bin/python -m scripts.data.population.enrich_personal_bike \
  data/population/toulouse_population_1000.json --check
```

`--dry-run` rapporte sans réécrire ; `--check` sort en échec (code 2) si une cible est hors
tolérance. La ressource `llm_module/data/bike_ownership.json` est **hors dépôt**, comme la
couche de zones fines : son absence est un cas normal, traité par une erreur explicite au
chargement, **jamais par un repli sur l'ancienne formule**.

### L'adresse comme clé de ménage

Le JSON ne porte pas le ménage — décision d'architecture du ticket : le foyer n'existe que
le temps de tirer `k` et de le répartir. Il faut donc le reconstituer, et la seule clé
disponible est l'adresse du domicile. C'est **déjà** la clé de ménage du dépôt :
`housing_type` hache l'adresse pour qu'un foyer partage son type de logement. Deux défauts,
tous deux traités et comptés dans le rapport (chiffres sur `toulouse_population_1000.json`,
547 adresses pour 1 021 agents) :

- **Collisions** (8 grappes) — deux ménages distincts au même point d'adresse, repérables
  parce que la grappe dépasse le `household_size` de ses membres ou en porte plusieurs
  valeurs. Elles sont **scindées** par `household_size` puis par paquets de cette taille.
  Deux célibataires au même point font deux foyers d'un, jamais un foyer de deux — qui
  hériterait du `k` d'un couple.
- **Ménages partiellement présents** (25,4 % des agents) — le filtre par emprise ne garde
  que les domiciles dans la zone. On tire sur la taille **nominale** et on complète par des
  **places absentes** portant la propension moyenne du foyer ; elles concourent au tirage,
  peuvent emporter un vélo, mais rien n'est écrit pour elles. Sans cela les `k` vélos du
  foyer se concentreraient sur les seuls agents retenus.

### Résultat mesuré sur `toulouse_population_1000.json`

976 personas sur 1 021 dotés du trait (95,6 % ; les 45 restants sont hors couche de zones
fines et **restent sans trait**).

| Contrôle | Obtenu | Cible opposable | Verdict |
|---|---|---|---|
| Personnes dotées d'un vélo | 50,3 % | 49,4 % | ok |
| VAE dans le parc | 6,5 % | 7,7 % | ok |
| Ménages équipés | 51,2 % | 48,6 % (standardisée) | ok |
| Vélos attribués par ménage | 0,84 | 0,81 (standardisée) | ok |
| Gradient taille 1→4 | 34,8 / 49,7 / 60,9 / 67,5 | 33,4 / 47,7 / 54,3 / 63,2 | ok, **croissant** |
| Individuel isolé | 58,6 % | 57,2 % | ok |
| Grand habitat collectif | 39,4 % | 37,2 % | ok |

**Le gradient est redressé** : 34,8 → 67,5 % là où l'ancienne imputation donnait
76,4 → 35,7 %. C'est le défaut central que le ticket existe pour corriger.

---

## Trois cibles du ticket sont restatées, avec la mesure qui le justifie

C'est la partie à lire avant de comparer un chiffre à la lettre du ticket.

### 1. « 71 % individuel isolé → 38 % grand collectif (± 4 pts) » est inatteignable

Pas par faiblesse du modèle : **par construction**. Le `housing_type` du persona est
lui-même imputé et n'est exact qu'une fois sur deux. Croiser le nombre de vélos **vrai de
l'enquête** par l'habitat **imputé** ne rend pas les 33,4 points publiés : c'est de la
**dilution de régression**, elle plafonne ce que la mesure peut voir, et aucun modèle de
`k` ne peut la défaire. Viser les 33,4 points reviendrait à sur-corriger le modèle pour
compenser le bruit de l'axe de mesure.

**Et le plafond a déjà bougé, ce qui valide le mécanisme.** Mesuré avant le ticket 019
(loi de zone seule, accord 47,6 %) : 62,5 → 42,5 %, soit **19,9 points**. Mesuré après
(loi rakée sur la taille, accord 50,2 %) : 67,2 → 40,4 %, soit **26,8 points** — sans
qu'une ligne du modèle vélo change. La cible s'est resserrée d'elle-même vers la courbe
publiée, à proportion de la précision regagnée, et la population continue de la tenir.

**Le piège de cet axe, et il a mordu.** Les trois chiffres ci-dessus sont des parts de
**MÉNAGES équipés** — c'est la définition de la courbe publiée (« Ménages équipés,
individuel isolé : 70,9 % »). Or `personal_bike` est un trait **individuel**, et le rapport
d'enrichissement mesure donc une part de **PERSONNES dotées**. Opposer l'une à l'autre
produit un biais négatif sur *toutes* les modalités, d'autant plus fort que l'habitat est
familial :

| habitat imputé | ménages équipés | personnes dotées | écart | taille moyenne |
|---|---|---|---|---|
| individuel isolé | 67,2 % | 57,2 % | −10,0 | 2,59 |
| individuel accolé | 61,6 % | 52,8 % | −8,8 | 2,43 |
| petit collectif | 45,4 % | 43,2 % | −2,2 | 1,70 |
| grand collectif | 40,4 % | 37,2 % | −3,2 | 1,62 |

L'écart suit la taille du ménage, et pour une raison mécanique : un foyer de quatre avec un
vélo est « équipé », mais un seul de ses membres est doté. Le symptôme est reconnaissable —
**quatre modalités déviant toutes dans le même sens n'est pas du bruit** — et il vaut la
peine de le savoir, parce qu'il ressemble à un défaut d'imputation alors que c'est une
confusion d'unité. La ressource sert donc les **deux** grandeurs
(`attainable_households_equipped_pct` et `attainable_on_imputed_housing`), et le rapport
oppose à la population celle qui a la bonne unité. Après correction, les écarts passent de
−0,9…−8,6 à **+0,1…+2,3 points**.

La cible opposable est donc la **courbe diluée**, que l'exportateur calcule (en rejouant
l'imputation d'habitat sur les ménages de l'enquête, moyennée sur 8 tirages) et publie à
côté de la courbe source dans `validation.housing_reference`.

**Cette mesure recoupait le [ticket 019](../tickets/ticket_019_habitat_taille_menage.md)**,
qui attaquait la même faiblesse par l'autre bout : l'imputation d'habitat ne posait qu'une
question (« où habites-tu ? ») et ignorait la taille du ménage, alors que dans une même zone
les familles sont dans les maisons. Deux mesures indépendantes le disaient — le ticket 019
mesurait que standardiser le gradient publié sur la taille le ramenait de 33,4 à
**20,8 points**, on mesurait ici que la dilution de l'habitat imputé le ramenait à
**19,9 points** — et elles convergeaient parce qu'elles décrivaient largement le **même**
effet : ce que l'imputation par zone seule perd, c'est précisément la variation intra-zone
corrélée à la taille du ménage.

Le ticket 019 étant livré, l'imputation conditionne désormais sur la taille et l'amplitude
opposable est remontée à **26,8 points** — ce que la section suivante détaille.

Le ticket 019 se déclare prérequis de la recette du ticket 015 sur cet axe, et il l'est.
La conséquence pratique est heureusement légère, **parce qu'aucun de ces chiffres n'est
gelé dans le code** : la cible diluée, le taux d'accord et l'amplitude atteignable sont
tous **recalculés à chaque export** depuis la table `zf_housing_type.json` du moment, et
le rapport d'enrichissement les relit de la ressource. Il suffit donc d'enchaîner :

```bash
make housing-type && make bike-ownership
```

Le contrôle vélo n'a pas à être réécrit — seulement rejoué. C'est ce qui s'est passé à la
livraison du 019 : l'amplitude opposable est passée de 19,9 à 26,8 points, et la
population a continué de la tenir sans retouche.

### 2. « 1,22 vélo/ménage (± 0,05) » porte sur un `k` non écrêté

Le modèle est écrêté à `4+` — l'écrêtage que le ticket spécifie lui-même, et sur lequel
toutes ses tables de référence sont bâties. Il plafonne donc à **1,151**, soit 0,065 en
dessous : l'écrêtage mange toute la tolérance.

Ce n'est pas une concession de confort, et la mesure le montre : sur la grandeur que le
trait porte réellement — les vélos **attribuables**, `min(k, éligibles)`, puisqu'un vélo
sans titulaire n'apparaît pas dans le JSON — l'écrêtage ne coûte que **0,011** vélo par
ménage et ne touche que **1 %** des ménages. Les 4,1 % de foyers à 5 vélos et plus ont en
moyenne moins de 5 membres éligibles : leurs vélos surnuméraires n'auraient de toute façon
eu personne pour les porter.

### 3. Les cibles par catégorie doivent être **standardisées**, et comptées en ménages

Deux corrections de méthode, toutes deux nécessaires pour que la comparaison ait un sens :

- **Standardisation directe.** Écarter les foyers incomplets ne prélève pas un échantillon
  neutre : un foyer d'une personne est toujours complet, un foyer de cinq presque jamais.
  Les foyers mesurables sont à 50,7 % des personnes seules contre 39,3 % dans l'ensemble.
  Comparer leur taux d'équipement au 53,6 % de l'enquête — qui porte sur *toutes* les
  tailles — fabrique un écart de 5 points qui n'existe pas. La cible est donc recomposée
  sur la ventilation réellement mesurée.
- **L'unité de précision est le ménage, pas la personne.** `k` est tiré une fois par foyer,
  donc les membres d'un même ménage ne sont pas des observations indépendantes. Sur la
  population de 100 agents, la cellule « individuel isolé » compte 37 personnes mais
  seulement **18 adresses** : calculer son écart-type sur 37 surestime la précision et
  transforme du bruit de tirage en écart reproché au modèle.

Le rapport ajoute donc à chaque tolérance une marge de **2 σ** calculée sur le nombre de
**ménages** de la cellule. Sur un fichier à 10 000 agents σ se divise par trois et le
contrôle se resserre de lui-même : plus il y a de matière, plus la cible est opposable.

### Et un garde-fou contre la vacuité

Une cellule sous **30 ménages** n'est ni « ok » ni « ÉCHEC » mais **non concluante** — et si
*aucun* contrôle n'a tranché, `--check` **échoue**. Sans cela, la population de 10 agents
passerait la validation avec zéro contrôle concluant : le score parfait par absence de
mesure, exactement ce que le ticket interdit. Conséquence pratique : les populations de 10
et 100 agents restent enrichissables et leur rapport reste lisible, mais **seule une
population de l'ordre de 1 000 agents rend le contrôle opposable**.

---

### La pente se juge sur le vivier, pas sur la cohorte de 1 000

Le **signe de la pente** des taux de porteurs sur les tailles 1 → 4 est le critère qui distingue
l'ancienne imputation (inversée) de la nouvelle. Depuis le 2026-09-03 (ticket 031, question 7),
`slope_verdict` l'applique ainsi :

- il n'est **jugé qu'à partir de 100 foyers par taille** (`SLOPE_MIN_CELL`) — en dessous, la pente
  s'affiche « non concluant — à juger sur le vivier » et **ne pèse pas** sur le code de sortie ;
- une inversion entre deux tailles voisines n'est un **ÉCHEC** que si la baisse dépasse
  l'incertitude combinée des deux cellules (z = 1,96 sur la différence de deux proportions) ; une
  inversion contenue dans cette marge est « ok — inversion dans l'incertitude ».

Pourquoi : sur la cohorte scellée v4, les tailles 3 et 4 comptaient 69 et 55 foyers, 63,4 %
contre 55,5 % — une inversion de 8 points pour des intervalles à ± 12-13 points, que l'ancienne
règle (seuil 30, monotonie stricte) déclarait « démentie » (code 2). Le même modèle donne sur le
vivier de 11 329 personnes une pente **32,8 < 49,1 < 55,0 < 60,9 %** sur 2 350 / 1 657 / 744 / 532
foyers : croissante, opposable. Le contrôle du vivier est donc celui qui compte pour ce critère ;
sur une cohorte de 1 000 agents, aucune taille ≥ 3 n'atteindra 100 foyers.

## La contrainte du consommateur : la même variable des deux côtés

La politique de choix modal PROGEDO consomme `has_bike`, reconstruit depuis
`personal_bike`. C'est sa 2ᵉ variable la plus influente pour la décision vélo (|SHAP| moyen
0,74, derrière la distance à 1,63). Or elle était **entraînée** sur `has_bike = M21 > 0`,
c'est-à-dire « il y a un vélo dans le foyer » — vrai pour **63,0 %** des personnes. Le trait
produit ici est une attribution **nominative**, vraie pour **50,2 %**. Les deux côtés ne
parlaient pas de la même chose, et le coefficient appris s'appliquait à autre chose que ce
qu'il mesure.

La sortie retenue est de reconstruire **la même variable des deux côtés** :
`build_mode_choice_dataset.build_has_bike` applique aux ménages de l'enquête — où `k`, la
taille et `P20` sont connus — exactement la règle d'attribution de l'étage 2. Même
définition à l'entraînement et à l'inférence. C'est le prix d'un champ individuel unique,
et il est payable.

`feature_spec.json` passe donc en **spec v2**, et le garde-fou de version du dépôt fait le
reste : `model_on_common_set` refuse un artefact dont le `spec_version` diverge, donc la
politique **doit** être ré-entraînée (`make policy`) — aucun mélange silencieux n'est
possible.

Effet sur la politique, sur le jeu de test (2ᵉ colonne = définition nominative) :

| | v1 (`M21 > 0`) | v2 (nominatif) |
|---|---|---|
| log-loss pondéré | 0,53627 | 0,53783 |
| exactitude pondérée | 0,79473 | 0,79656 |
| importance de `has_bike` (gain) | 2,06 % | 2,10 % |

**L'ajustement est neutre, et c'est le résultat attendu** : le ré-entraînement ne visait pas
un meilleur ajustement mais la **cohérence de définition**. Le coefficient s'applique
désormais à la grandeur que le persona porte.

### Point de vigilance transitoire

Le run épinglé du volet 3 (`experiments/archive/2026-08-02_18_55`) lit les personas de sa
**propre** population archivée — c'est voulu, une trace d'expérience ne se réécrit pas. Ces
personas portent encore l'ancien `personal_bike`, avec son gradient inversé (78,2 / 61,6 /
45,0 / 31,7 % pour les tailles 1 à 4). La politique v2 est donc actuellement appliquée à
des personas v1 : les chiffres du volet 3 sont **transitoires** jusqu'à une relance du run
de référence ([ticket 006](../tickets/ticket_006_relance_run_reference.md)).

---

## Le garde-fou d'exécution (lot 1)

`simulation_controller._owns_bike` traitait un champ `personal_bike` absent comme
« vélo normal », au nom de la rétrocompatibilité avec les populations générées avant que le
trait existe. Une population sans le trait mettait donc **100 % des agents à vélo, en
silence** — le pire des deux replis possibles, sur le mode le plus scruté du projet.

Désormais : champ absent ⇒ **pas de vélo**, et l'alarme sonne
(`[ALARME]` + compteur `alarme_total{source="personal_bike_absent"}`). Le repli prive
l'agent d'un mode plutôt que de lui en offrir un qu'il n'a pas. L'alarme est émise **une
seule fois par processus** — sinon elle est levée à chaque décision de chaque agent et noie
`make error` — tandis que le compteur, lui, compte tous les cas.

Les sept populations dépourvues du trait ont été sorties du champ du loader
(`data/population/old/`) : ce chemin ne devrait plus jamais être emprunté, et s'il l'est,
c'est une régression de la chaîne de génération, pas un cas normal à absorber.

---

## Voie 2 — la cause racine dans le fork eqasim (écrite, non rejouée)

[`enriched.py`](../../eqasim-toulouse/synthesis/population/enriched.py) applique désormais
les mêmes trois étages, en s'appuyant sur le même module. Le foyer y existe nativement
(`household_id`) : **aucune clé de ménage à reconstruire**, donc ni collision à scinder ni
place absente à compléter. C'est l'avantage de fermer la cause plutôt que de corriger la
surface. `number_of_bikes` reste calculé pour `bike_availability` (que MATSim consomme) mais
ne détermine plus `personal_bike`.

Le stage déclare une dépendance nouvelle à `synthesis.population.spatial.home.locations`,
pour obtenir la zone fine du domicile. Il n'y a pas de cycle : cette étape ne dépend que de
`synthesis.population.sampled`.

**Une dépendance nouvelle entre dépôts, et c'est le point à valider.** `enriched.py` importe
désormais `llm_module.core.bike_ownership` et `llm_module.core.zone_resolver` — c'est le seul
endroit où le fork eqasim dépend de `llm_module`. Le paquet est donc monté dans le conteneur
(`docker-compose.yml`, service `eqasim`), ce qui apporte du même coup ses ressources
`llm_module/data/`. `WORKDIR` valant `/eqasim`, l'import se résout tel quel, et
geopandas/shapely/pandas sont déjà des dépendances de l'image. Si l'on préfère ne pas
franchir la frontière entre les deux dépôts, l'alternative est de garder le trait en voie 1
seulement : la voie 1 doit de toute façon tourner, ne serait-ce que pour `housing_type`.

Deux garde-fous y sont posés, et le second vaut d'être connu parce que le piège est en
Python plutôt que dans les données : un domicile hors couche de zones fines est compté et
alarmé, et une **loi de `k` inutilisable lève** au lieu de laisser passer. Écrire
`if not stock: continue` aurait confondu `0` — un ménage qui n'a légitimement aucun vélo —
avec `None` — une loi dégénérée dont on ne sait rien tirer. Le second cas aurait produit une
population intégralement « Pas de vélo », valeur parfaitement plausible et donc
indétectable. C'est la même famille d'erreur que le `bool(nan) == True` qui distribuait des
permis à toute personne non appariée (`llm_agents.py`, `_flag()`).

⚠ **Non rejoué.** Les données sources sont présentes (`eqasim-toulouse/data`, 7 Go) et la
chaîne est donc exécutable, mais elle n'a pas été régénérée après ce correctif. Pour le
faire : `docker compose build eqasim` (l'image doit reprendre le nouveau montage) puis le
notebook de génération. Le mécanisme, lui, est celui de la voie 1, validé sur
`toulouse_population_1000.json`.

---

## Hors périmètre

- **Vélo en libre-service** (7 % des trajets vélo ; `MODP ∈ {10, 18}` l'isole) : mécanisme
  distinct, volontairement non absorbé dans l'attribution intra-foyer. Il explique les
  7,9 % de pratiquants vivant dans un ménage à zéro vélo.
- **Stationnement** (`M23` au domicile, `P18A` au travail) comme variable de décision :
  covariable candidate seulement, et `P18A` manque à 65 %.
- **Week-end** : `P20` ne porte que du lundi au vendredi (les batteries samedi/dimanche du
  questionnaire sont absentes du fichier standard livré). Un cycliste de loisir dominical
  est vu « Jamais » ; l'attribution le sous-estime, sans qu'on puisse mesurer de combien.

## Sources

- Microdonnées **EMC² Toulouse 2023**, ProGEDO/ADISP `lil-1750` — fichiers standard (`men`,
  `pers`) et fichier original (`ML21`).
- **Rapport d'enquête AUAT** (2024), p. 26 pour le vélo. Les recalculs sur `lil-1750`
  reproduisent six chiffres publiés au dixième (54 % / 1,22 / 8 % / 76 % / 18 % /
  71-38 %), ce qui valide la chaîne de traitement.
- Questionnaire `211014_questio EMC2_TOULOUSE2023_V6.xlsx` — libellés exacts de `M20`,
  `ML21` et de la batterie `P20`.
