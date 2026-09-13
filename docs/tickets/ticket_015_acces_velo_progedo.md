# Ticket 015 — Le vélo de l'agent : apprendre l'équipement sur EMC² au lieu de l'imputer

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité.
>
> **Lots 1 à 3 livrés le 2026-08-21.** L'implémentation et les décisions retenues sont
> documentées dans [../arch/velo-equipement.md](../arch/velo-equipement.md).
>
> **Lot 4 REJETÉ le 2026-08-24** — le post-traitement est obligatoire dans tous les cas,
> donc la même loi n'a pas à vivre à deux endroits (voir le lot 4 ci-dessous).
> **Trois critères d'acceptation ci-dessous ont été restatés, mesure à l'appui** : ils
> étaient inatteignables comme écrits — voir « Amendements » en fin de ticket.

## Le problème, en une mesure

`personal_bike` est tiré dans eqasim par `p = min(1, vélos_du_donneur / taille_ménage)`
([enriched.py:120-134](../../eqasim-toulouse/synthesis/population/enriched.py)). Le nombre
de vélos vient d'un ménage réel de l'ENTD 2008, apparié **sans** la taille du ménage ni le
type d'habitat parmi les attributs d'appariement. Résultat mesuré sur
`toulouse_population_1000.json` face aux microdonnées EMC² Toulouse 2023 (lil-1750) :

| Croisement | EMC² 2023 | Population synthétique |
|---|---|---|
| Personnes dotées d'un vélo | 50,9 % | 53,3 % |
| dont ménage d'1 personne | 33,4 % | **76,4 %** |
| dont ménage de 2 personnes | 47,8 % | 61,9 % |
| dont ménage de 3 personnes | 55,8 % | **46,0 %** |
| dont ménage de 4 personnes | 65,4 % | **35,7 %** |
| Ménages équipés, habitat individuel isolé | 70,9 % | 50,0 % |
| Ménages équipés, grand habitat collectif | 37,5 % | 52,8 % |
| Part de VAE | 7,7 % du parc | 13,4 % des porteurs |

La colonne EMC² des personnes dotées est calculée à l'identique de ce que produira le
mécanisme spécifié ici — `min(k, taille)` vélos attribués par ménage, pondération `COE0` —
pour que la comparaison porte sur la même grandeur. *(Pour mémoire, la part de personnes
**vivant dans** un ménage équipé, qui est la définition qu'utilise la politique de choix
modal, vaut 63,2 % en pondération `COEP` : cf. § La contrainte du consommateur.)*

**Le total est déjà à peu près juste ; c'est la répartition qui est fausse**, et le gradient
de taille de ménage est carrément inversé. Ce ticket ne cherche donc pas à corriger un
volume, mais à mettre les vélos chez les bonnes personnes.

## Où est l'erreur exactement

Deux étages se composent : combien de vélos dans le ménage (`k`), puis qui dans le ménage.

**L'étage « qui » est presque bon.** Comparons la formule actuelle à la réalité observée,
pour un ménage à 1 vélo :

| | Taille 1 | Taille 2 | Taille 3 | Taille 4+ |
|---|---|---|---|---|
| EMC² observé | 75,8 % | 46,0 % | 38,6 % | 25,6 % |
| formule actuelle | 100 % | 50 % | 33 % | 25 % |

24 points d'écart sur la personne seule, moins de 6 points partout ailleurs. L'écart ne
devient grave qu'à partir de 2 vélos, où la formule sature à 100 % alors que la réalité
plafonne entre 60 et 85 % — il y a toujours des membres qui ne roulent pas, même bien
équipés.

**L'étage `k` est le coupable.** eqasim ne calcule pas `k` : il le **recopie** du ménage
ENTD 2008 apparié à la personne. Le nombre lui-même est vrai — c'est un vrai ménage
enquêté — mais il est attaché au mauvais foyer, parce que l'appariement se fait sur
`age_class`, `sex`, `any_cars`, `socioprofessional_class`, `departement_id` et **pas** sur
la taille du ménage ni l'habitat. Un célibataire toulousain peut donc hériter des 3 vélos
d'une famille de cinq, et une famille de cinq hériter du zéro vélo d'un couple âgé. Deux
biais s'y ajoutent :

- la variable ENTD lue est `V1_JNBVELOADT`, les **vélos adultes** — la colonne
  `V1_JNBVELOENF` existe dans le même fichier et n'est jamais chargée : **25 % du parc
  ignoré**, et 4,2 % des ménages classés « aucun vélo » alors qu'ils n'ont que des vélos
  d'enfants ;
- l'ENTD 2008 est nationale et vieille de quinze ans, quand EMC² 2023 décrit l'aire
  toulousaine.

## Le trait produit : un seul champ individuel

Décision d'architecture : **le JSON ne porte pas le ménage.** Le foyer n'existe que pendant
la génération, le temps de tirer `k` et de le répartir ; l'agent ne reçoit qu'une valeur.

```
traits_json.personal_bike : "Pas de vélo" | "vélo normal" | "VAE" | None
```

`None` uniquement hors couche de zones fines, et il doit se voir — jamais de repli
silencieux.

## Spécification

### Étage 0 — prérequis

| # | Prérequis | État |
|---|---|---|
| 0.1 | `_owns_bike` : champ absent ⇒ **`[ALARME]`**, pas « vélo pour tout le monde » ([simulation_controller.py](../../llm-agents/urban_mobility_agents/simulation_controller.py)) | **fait** — repli « pas de vélo », alarme une fois par processus, compteur `alarme_total{source="personal_bike_absent"}` sur tous les cas |
| 0.2 | Sortir du champ du loader les populations sans `personal_bike` | **fait** — 7 fichiers déplacés dans `data/population/old/`, cf. son `LISEZ_MOI.md` |
| 0.3 | Couche de zones fines + rattachement domicile → `ZF` | disponible (`scripts/progedo_logit/export_zone_layer.py`, `llm_module/core/housing_type.py`) |

Il n'est **pas** nécessaire d'exporter `household_id` : les deux étages tournent dans le
pipeline de génération, où le ménage existe encore (`household_id` est présent dans
`df_population` d'eqasim, et dans `toulouse_persons.csv`).

### Étage 1 — combien de vélos dans le ménage

- **Cible** : `k = M21`, écrêtée à `4+`. Logit ordinal ou multinomial.
- **Source** : `Toulouse_2023_std_men.csv`, 10 783 ménages, pondération **`COE0`**.
- **Covariables** : `M1` (type d'habitat), taille du ménage, `M6` (nombre de VP), `M2`
  (occupation du logement), et la zone via `ZFM` (densité de ménages, distance au centre —
  déjà calculées par `build_mode_choice_dataset.py`). Aucune covariable individuelle ici.
- **Application** : un tirage de `k` **par ménage synthétique**, remplaçant la recopie du
  donneur ENTD. Le nombre de vélos cesse d'être indépendant du foyer qui le reçoit — c'est
  tout l'objet du ticket.
- **Piège à trancher et à écrire dans le module** : `housing_type` du persona est lui-même
  imputé depuis la loi de la zone fine ([housing_type.py](../../llm_module/core/housing_type.py)).
  Conditionner `k` sur l'habitat n'apporte donc rien au-delà de la zone ; il faut soit
  conditionner sur (zone, taille), soit assumer explicitement que l'habitat n'est qu'une
  réécriture de la zone.
- **Bénéfices immédiats** : `M21` compte **tous** les vélos, et `ML21` donne le nombre de
  VAE — deux informations que l'ENTD 2008 ne porte pas.

### Étage 2 — qui, dans le ménage, tient les vélos

Le principe, et c'est le point à ne pas inverser : **`k` décide combien, la propension
décide seulement qui.**

- **Cible d'apprentissage** : `P20 ∈ {plusieurs jours/semaine, plusieurs jours/mois,
  occasionnellement}` — la pratique déclarée en tant que **conducteur**. C'est le meilleur
  indicateur disponible de « à qui est ce vélo », et il n'y en a pas d'autre : l'enquête ne
  demande jamais qui possède quoi.
- **Source** : `Toulouse_2023_std_pers.csv` restreint à **`PENQ = 1`** (15 775 personnes sur
  20 890), pondération **`COEP`** — qui vaut exactement 0 pour les non-enquêtés, donc toute
  statistique pondérée `COEP` est déjà correctement restreinte.
- **Covariables** : `k`, taille du ménage, âge (`P4`), genre (`P2`), occupation
  (`P9`/`PCSC`), et le rattachement de résidence (zone fine → densité, distance au centre).
  **Pas de distance de déplacement** : un stock doit être invariant au trajet, sinon le même
  agent a un vélo pour la boulangerie et plus pour le travail, et le verrou de chaîne de
  véhicule perd son sens. (`D12` est en outre endogène au mode et déjà marquée
  « contaminée » dans la politique existante ; `DP15` vaut 0 pour 54,6 % des personnes.)
- **Règle d'attribution — l'ordre, précisément.** Tirage sans remise pondéré par la
  propension (schéma d'Efraimidis–Spirakis) : chaque membre éligible reçoit une clé
  `key_i = u_i ** (1 / p_i)` où `p_i` est sa propension estimée et `u_i` un uniforme tiré par
  hachage déterministe de (adresse du domicile, index de la personne, sel versionné) ; on
  classe par clé décroissante et on attribue un vélo aux **`min(k, éligibles)` premiers**.
  Propriétés voulues : le nombre attribué est exactement le stock du ménage, la probabilité
  d'être servi croît avec la propension, et il n'y a **aucun ordre déterministe** (pas de
  « toujours l'aîné », pas d'artefact de tri sur les ex æquo).

  Le classement ne fait que **hiérarchiser** ; c'est `k` qui fixe le niveau. Les derniers
  vélos échoient donc à des membres de faible propension : **ce sont les vélos dormants**, et
  il est juste de les représenter. Leur porteur ne les utilisera pas — c'est au modèle de
  choix modal et à l'agent de décider de ne pas les prendre, pas à l'imputation de les faire
  disparaître.

  Conséquence à assumer : la probabilité d'inclusion réelle de ce schéma n'est pas
  exactement `p_i` (elle est déformée par la contrainte de comptage). La table
  `P(pratique | k, taille)` ci-dessous n'est donc pas une identité mais un **critère de
  validation** : on vérifie après coup que le mécanisme la reproduit, on ne la suppose pas.

- **Éligibilité** : membres de **5 ans et plus** — c'est le champ de la question `P20`, et ça
  interdit structurellement d'attribuer le vélo du foyer à un enfant de trois ans. Si
  `k > éligibles`, le surplus n'est porté par personne : un vélo est un objet du ménage, et
  le JSON ne portant que des individus, un vélo sans titulaire n'y apparaît simplement pas.

- **Ménages partiellement présents** : le filtre par bbox ne garde que les agents dont le
  domicile est dans la zone — **26 %** des agents de `toulouse_population_1000.json`
  appartiennent à un ménage dont tous les membres ne sont pas dans le fichier (grappes
  d'adresse plus petites que `household_size`). Il faut tirer sur la taille **nominale**
  (`household_size`) et ne matérialiser que les membres présents, sinon on concentre les `k`
  vélos du foyer sur les seuls agents retenus et on les sur-équipe. Mise en œuvre : compléter
  la liste des éligibles par `household_size − présents` places « absentes » portant la
  propension moyenne du foyer, tirer, puis ne lire que les places présentes.
- **Contrôle de cohérence** — le nombre de pratiquants par ménage doit rester compatible
  avec la courbe observée (numérateur `COEP` sur enquêtés, dénominateur `COE0` sur ménages) :

  | Vélos du ménage | Personnes 5+/ménage | Pratiquants/ménage | Pratiquants/vélo |
  |---|---|---|---|
  | 1 | 1,62 | 0,84 | 0,84 |
  | 2 | 2,24 | 1,25 | 0,62 |
  | 3 | 2,88 | 1,69 | 0,56 |
  | 4 et + | 3,34 | 2,15 | 0,54 |

  Lecture : environ **11 points** de la population tiendront un vélo sans le pratiquer
  (≈ 51 % de porteurs contre 39,5 % de pratiquants). C'est la masse dormante, et elle est
  attendue.

- **Table de référence `P(pratique | k, taille)`**, pondérée `COEP`, que le modèle doit
  reproduire à quelques points près :

  | Vélos | Taille 1 | Taille 2 | Taille 3 | Taille 4+ |
  |---|---|---|---|---|
  | 1 | 75,8 % | 46,0 % | 38,6 % | 25,6 % |
  | 2 | 77,2 % | 64,6 % | 52,4 % | 39,1 % |
  | 3 | 80,7 % | 68,4 % | 59,1 % | 54,4 % |
  | 4 et + | 84,3 % | 75,2 % | 63,4 % | 62,9 % |

- **Limite d'identification, à assumer et à écrire** : **67 %** des ménages n'ont qu'une
  seule personne enquêtée (7 238 sur 10 783). On peut estimer `P(pratique | covariables)`,
  on ne peut **pas** observer qui, parmi trois frères et sœurs, roule. L'attribution sera
  donc indépendante conditionnellement à `k`, sans corrélation intra-foyer modélisée.

### Étage 3 — quel type de vélo

- **7,7 %** du parc en VAE (`ML21 / M21` ; rapport AUAT p. 26 : 8 % des ménages ont ≥ 1 VAE).
  Tirage **par vélo attribué**, pas par personne : l'erreur actuelle applique 14,8 %, qui est
  la part des *ménages équipés* possédant un VAE — d'où 1,7× trop de VAE.
- Filtre âge ≥ 14 conservé.
- À documenter : **12 %** des *trajets* vélo sont en VAE (p. 26). L'écart 7,7 → 12 % est un
  effet d'usage, pas de stock ; viser 12 % sur le stock serait une erreur de niveau.

### Pourquoi tirer `k` d'abord (et pas redresser à la fin)

Le nombre de vélos d'un ménage est un **entier partagé** par ses membres : 0, 1, 2, 3 ou
plus. Si on commence par décider individu par individu, chacun de son côté, « celui-là a un
vélo avec 40 % de chances », on obtient des foyers incohérents — trois vélos dans un ménage
qui n'en déclarait qu'un, zéro dans un ménage qui en avait deux. On peut alors rattraper la
*moyenne* d'ensemble (« au total, 54 % des ménages équipés »), mais pas la *répartition* :
il restera trop de ménages à 1 vélo et pas assez à 3, parce qu'une moyenne juste peut cacher
n'importe quelle répartition fausse. C'est exactement le symptôme actuel — bon total,
gradients faux.

**La démonstration, sur les ménages de 4 personnes.** Distribution observée du nombre de
vélos, et ce que produirait un tirage individuel indépendant **calé sur la même moyenne**
(2,62 vélos par ménage, soit `p = 0,654` par personne) :

| Vélos du ménage | EMC² observé | Tirage individuel indépendant |
|---|---|---|
| 0 | **15,7 %** | 1,4 % |
| 1 | 7,5 % | 10,8 % |
| 2 | 16,5 % | 30,7 % |
| 3 | 20,2 % | 38,7 % |
| 4 et + | **40,1 %** | 18,3 % |

Les deux colonnes ont **exactement la même moyenne** — c'est ainsi que `p` a été choisi — et
elles ne décrivent pas le même monde. La réalité est en **tout ou rien** : 16 % de familles
sans aucun vélo, 40 % avec un vélo par personne. Le tirage indépendant, lui, empile tout au
milieu : il ne sait produire ni la famille sans vélo, ni la famille intégralement équipée.
Variance observée 2,13 contre 0,91 en indépendance, soit une **surdispersion ×2,4**.

C'est le point de fond : l'équipement vélo est un **trait de foyer** — on est une famille à
vélo ou on ne l'est pas — pas une pièce lancée séparément pour chaque membre. L'hypothèse
d'indépendance est précisément celle qui est fausse.

Et comme les deux colonnes partagent la même moyenne, **aucun redressement sur la moyenne ne
peut les rapprocher.** Une correction a posteriori déplace le niveau, jamais la forme.

En tirant `k` d'abord dans la loi observée, la répartition est respectée **par construction**
et il n'y a plus rien à redresser. L'étape de correction disparaît, ce qui est le meilleur
sort qu'on puisse réserver à une étape de correction.

### La contrainte du consommateur (à trancher avant le lot 3)

La politique de choix modal PROGEDO consomme une variable `has_bike`, reconstruite depuis
`personal_bike` ([model_on_common_set.py:122](../../scripts/synthesis/model_on_common_set.py)).
C'est sa 2ᵉ variable la plus influente pour la décision vélo (|SHAP| moyen 0,74, derrière la
distance à 1,63). Or elle a été **entraînée** sur `has_bike = M21 > 0`, c'est-à-dire « il y a
un vélo dans le foyer » — vrai pour **63,2 %** des personnes. Le trait spécifié ici, une
attribution nominative, en vise **~51 %**. Les deux côtés ne parleraient pas de la même
chose, et le coefficient appris serait appliqué à autre chose que ce qu'il mesure.

Avec un seul champ individuel, la sortie est de reconstruire **la même variable des deux
côtés** : appliquer la règle d'attribution de l'étage 2 aux ménages de l'enquête (où `k`, la
taille et `P20` sont connus), et ré-entraîner la politique sur cet indicateur construit. Même
définition à l'entraînement et à l'inférence — c'est le prix d'un champ unique, et il est
payable.

### Contrat de sortie

```
traits_json.personal_bike : "Pas de vélo" | "vélo normal" | "VAE" | None
```

Déterminisme calqué sur [housing_type.py](../../llm_module/core/housing_type.py) : tirage par
hachage (clé = adresse du domicile pour l'étage 1, adresse + index de personne pour
l'étage 2), sel versionné, aucun repli silencieux.

### Critères d'acceptation

Cibles publiées ou recalculées sur `lil-1750`, à reproduire par la population synthétique
(tolérance entre parenthèses) :

Vérifiés sur `toulouse_population_1000.json` (976 personas dotés du trait sur 1 021) le
2026-08-21, sauf mention contraire.

- [x] ménages équipés : **54 %** (± 2 pts) → obtenu **51,2 %** contre une cible
      **standardisée** à 48,6 % (cf. amendement A3) ; et **1,22** vélo/ménage (± 0,05) →
      **amendé** en 0,81 vélo *attribué* par ménage, obtenu 0,84 (cf. amendement A2)
- [x] équipement par type d'habitat — **critère amendé (A1)** : la courbe publiée
      71 % → 38 % est inatteignable par construction. Contre la courbe **diluée**
      opposable, recalculée après la livraison du ticket 019 **et exprimée dans la bonne
      unité** (part de PERSONNES dotées, le trait étant individuel — la courbe publiée est
      une part de MÉNAGES équipés) : individuel isolé 58,6 % pour 57,2 % attendus, grand
      collectif 39,4 % pour 37,2 % — écarts de +0,1 à +2,3 pts sur les quatre modalités
      mesurables. *Axe conditionné par le
      [ticket 019](ticket_019_habitat_taille_menage.md) : déjà rejoué à sa livraison
      (amplitude opposable 19,9 → 26,8 pts), à rejouer de nouveau si l'imputation
      d'habitat évolue — `make housing-type && make bike-ownership`*
- [x] personnes dotées d'un vélo : **50,9 %** (± 3 pts) → obtenu **50,3 %**
- [x] gradient de taille de ménage **croissant** → obtenu **34,8 / 49,7 / 60,9 / 67,5 %**
      pour les tailles 1 à 4, contre 33,4 / 47,7 / 54,3 / 63,2 attendus sous les règles du
      mécanisme. **La pente est croissante** : le défaut central du ticket est corrigé. *(Règle de jugement précisée le 2026-09-03 : pente jugée à partir de 100 foyers par taille, inversion tolérée dans l'incertitude combinée — `slope_verdict` ; sur une cohorte de 1 000 le critère s'affiche « non concluant » et se juge sur le vivier.)*
      Les tailles 5 et 6 restent **non concluantes** (19 et 10 ménages seulement)
- [x] pratiquants par vélo : courbe 0,84 / 0,62 / 0,56 / 0,54 → **reproduite à
      l'identique** par le rejeu du mécanisme sur l'enquête (`validation.targets`)
- [x] VAE : **7,7 %** du parc (± 1,5 pt) → obtenu **6,5 %**. Le filtre d'âge est
      renormalisé, sans quoi le parc plafonnait à 6,8 %
- [x] validation croisée **groupée par ménage** → `GroupKFold(5)` sur `hh_id` pour
      l'étage 2 (AUC en place 0,8205, hors-échantillon **0,8180** : pas de sur-ajustement)
- [x] effectifs de cellule publiés avec chaque table, et toute cellule sous 30 observations
      pondérées **signalée** (`thin: true`) — des deux côtés : la ressource signale les
      cellules minces de l'enquête, le rapport d'application signale les cellules de moins
      de 30 **ménages** comme *non concluantes* (cf. amendement A3)
- [x] aucune cible atteinte par absence de mesure : couverture sous 80 % ⇒ échec, **et**
      « zéro contrôle concluant » ⇒ échec. Vérifié : la population de 10 agents sort en
      code 2 avec 0 verdict sur 9, celle de 1 000 en code 0 avec 12 verdicts

## Amendements du 2026-08-21 — trois critères inatteignables comme écrits

Chacun est appuyé sur une mesure, et la mesure est reproductible (`make bike-ownership`
publie les trois dans `validation`). Le détail est dans
[../arch/velo-equipement.md](../arch/velo-equipement.md).

**A1 — l'axe habitat ne peut pas atteindre 71 % → 38 %.** Le `housing_type` du persona est
lui-même imputé et ne coïncide avec l'habitat observé qu'**une fois sur deux** (47,6 % avec
la loi de zone seule, 50,2 % depuis le ticket 019). Croiser le nombre de vélos **vrai de
l'enquête** par l'habitat **imputé** ne rend donc pas les 33,4 points publiés — 19,9 points
avant le 019, **26,8 après** : c'est de la dilution de régression, et aucun modèle de `k` ne
peut la défaire. Le fait que la cible se soit resserrée toute seule à la livraison du 019,
sans retouche du modèle vélo ni de la population, est la meilleure vérification qu'on
mesurait bien la dilution et non un défaut d'imputation vélo.
Viser la courbe publiée reviendrait à sur-corriger le modèle pour compenser le bruit de
l'axe de mesure — c'est d'ailleurs ce que fait un conditionnement de `k` sur l'habitat
imputé, mesuré à +4,0/−4,6 points d'erreur contre 0,6 sans lui. La cible opposable est donc
la courbe diluée, **recalculée à chaque export** (comme le taux d'accord et l'amplitude :
aucun de ces chiffres n'est gelé dans le code). Elle se resserre d'elle-même à chaque gain
de précision de l'imputation d'habitat — ce qu'a fait le
[ticket 019](ticket_019_habitat_taille_menage.md), prérequis déclaré de la présente recette.

**A2 — « 1,22 vélo/ménage » porte sur un `k` non écrêté.** Le modèle est écrêté à `4+`,
comme ce ticket le spécifie lui-même et comme toutes ses tables de référence le sont ; il
plafonne donc à 1,151, soit 0,065 sous la cible, ce qui mange toute la tolérance. Sur la
grandeur que le trait porte réellement — les vélos **attribuables**, `min(k, éligibles)`,
puisqu'un vélo sans titulaire n'apparaît pas dans le JSON — l'écrêtage ne coûte que **0,011**
vélo par ménage et ne touche que **1 %** des ménages : les 4,1 % de foyers à 5 vélos et plus
ont en moyenne moins de 5 membres éligibles.

**A3 — les cibles par catégorie doivent être standardisées, et comptées en ménages.** Deux
corrections de méthode, sans lesquelles la comparaison mesure autre chose que le modèle :

- *Standardisation directe.* Écarter les foyers incomplets ne prélève pas un échantillon
  neutre — un foyer d'une personne est toujours complet, un foyer de cinq presque jamais.
  Les foyers mesurables sont à 50,7 % des personnes seules contre 39,3 % dans l'ensemble ;
  comparer leur équipement au 53,6 % de l'enquête fabrique 5 points d'écart qui n'existent
  pas.
- *L'unité de précision est le ménage.* `k` est tiré une fois par foyer : deux frères ne
  sont pas deux observations. La cellule « individuel isolé » de la population de 100
  agents compte 37 personnes mais **18 adresses**. Chaque tolérance reçoit donc une marge
  de 2 σ calculée sur le nombre de ménages — marge qui se resserre d'elle-même sur un
  fichier plus gros.

Corollaire opérationnel : **seule une population de l'ordre de 1 000 agents rend cette
recette opposable.** En dessous, les cellules sont déclarées non concluantes plutôt que
réussies.

### Hors périmètre

- Le vélo en libre-service (7 % des trajets vélo ; `MODP ∈ {10, 18}` l'isole) : mécanisme
  distinct, à ne pas absorber dans l'attribution intra-foyer. Il explique les 7,9 % de
  pratiquants vivant dans un ménage à zéro vélo.
- Le stationnement (`M23` domicile, `P18A` travail) comme variable de décision : covariable
  candidate seulement, et `P18A` manque à 65 %.
- Le week-end : `P20` porte sur la semaine du lundi au vendredi (le questionnaire a des
  batteries samedi/dimanche, absentes du fichier standard livré). Un cycliste de loisir
  dominical est vu « Jamais » ; l'attribution le sous-estime, sans qu'on puisse mesurer de
  combien.

### Où le modèle écrase la sortie eqasim

Oui, la sortie d'eqasim est écrasée — la question est *où*, et il y a deux endroits, dans
cet ordre.

**Voie 1 — script de post-traitement (à faire d'abord).** Même patron que
[enrich_housing_type.py](../../scripts/data/population/enrich_housing_type.py) : on relit le
JSON produit, on regroupe les agents par **adresse du domicile**, on tire `k`, on attribue,
on réécrit `personal_bike`. Aucune régénération, applicable aux populations existantes.

L'adresse est une clé de ménage utilisable mais imparfaite, et il faut le savoir : sur
`toulouse_population_1000.json`, 547 adresses distinctes pour 1 021 agents, dont **539
grappes cohérentes** (un seul `household_size`, grappe pas plus grande que lui) et **8
grappes en collision** — deux ménages distincts au même point d'adresse, repérables parce que
la grappe dépasse le `household_size` de ses membres, ou en porte plusieurs valeurs. Il faut
les scinder par `household_size` et, en cas d'ambiguïté résiduelle, traiter la grappe comme
autant de ménages que nécessaire — jamais comme un seul gros foyer.

Note : ce même patron d'adresse-comme-clé-de-ménage est **déjà** celui de `housing_type`, qui
hache l'adresse pour que deux personas d'un même foyer partagent le type de logement. La voie
1 ne fait donc pas une hypothèse nouvelle, elle réutilise celle du dépôt.

**Voie 2 — cause racine dans le fork (ensuite).** Remplacer dans
[enriched.py](../../eqasim-toulouse/synthesis/population/enriched.py) la jointure
`number_of_bikes` (recopie du donneur ENTD) et l'imputation `personal_bike` par les deux
étages. Là, `household_id` existe nativement, il n'y a aucune clé à reconstruire, et
`toulouse_households.csv` cesse de contredire le JSON. Coût : accès aux données sources et
régénération complète.

C'est le partage de travail que le dépôt pratique déjà — `fix_minor_traits.py` corrige la
surface, les garde-fous d'eqasim ferment la cause. La voie 1 débloque, la voie 2 rend la
voie 1 inutile.

### Découpage en lots

1. **Lot 1 — garde-fous** *(livré)*. Prérequis 0.1 (l'alarme). Ne change aucun chiffre mais ferme le
   scénario « 100 % des agents à vélo, en silence ».
2. **Lot 2 — étage 1, en voie 1** *(livré)*. `P(k | zone, taille, habitat, motorisation)` appris sur
   EMC², tirage par ménage reconstitué à l'adresse, en remplacement de la recopie ENTD. C'est
   le lot qui répare les gradients, et il est indépendant de l'étage 2 : à ce stade on peut
   garder la répartition interne actuelle, elle n'est pas le problème.
3. **Lot 3 — étages 2 et 3** *(livré)*. Attribution nominative apprise sur `P20` (tirage sans remise
   pondéré), VAE à 7,7 %, et ré-entraînement de la politique de choix modal sur l'indicateur
   construit à l'identique.
4. ~~**Lot 4 — voie 2**. Remontée des deux étages dans le fork eqasim, pour qu'une
   génération neuve soit correcte sans post-traitement.~~ **REJETÉ le 2026-08-24.** Le
   code était écrit dans le fork et n'a jamais été rejoué ; il ne le sera pas.

   **Pourquoi.** Le post-traitement est obligatoire dans tous les cas — c'est l'étape 8 du
   pipeline de génération ([population.md](../setup/population.md)), et les trois scripts
   refusent de tourner si leur ressource d'accès restreint manque plutôt que d'imputer à
   l'aveugle. Porter la même loi une seconde fois dans eqasim serait donc une ceinture
   par-dessus des bretelles, au prix d'un **risque de dérive entre deux implémentations
   d'une même loi** — exactement le motif que les tickets 015 à 019 passent leur temps à
   corriger (« un coefficient appris sur une variable, appliqué à une autre »).

   **L'objection écartée.** On pouvait craindre qu'une population régénérée sans
   post-traitement récupère silencieusement l'ancien gradient inversé. Elle ne le fait pas :
   [`simulation_controller.py:352`](../../llm-agents/urban_mobility_agents/simulation_controller.py:352)
   lève une **`[ALARME]` en ERROR** dès que `personal_bike` est absent, compte tous les
   agents concernés dans `alarme_total{source="personal_bike_absent"}`, traite l'agent
   **sans vélo** (le repli qui prive plutôt que d'offrir), et les sept populations
   dépourvues du trait sont sorties du champ du loader (`data/population/old/`). Son propre
   docstring le dit : si ce chemin est emprunté, « c'est une régression de la chaîne de
   génération, pas un cas normal à absorber ». L'échec est **détecté et bruyant**, ce qui
   était la seule fonction que le lot 4 aurait ajoutée.

## Sources

- Microdonnées **EMC² Toulouse 2023**, ProGEDO/ADISP `lil-1750` — fichiers standard
  (`men`, `pers`, `depl`) et fichier original (variable `ML21`, absente du standard où `M22`
  est **vide**).
- **Rapport d'enquête AUAT** (68 p., 2024), p. 16-18 parts modales, **p. 26 vélo**. Les
  recalculs sur `lil-1750` reproduisent six chiffres publiés au dixième (54 % / 1,22 / 8 % /
  76 % / 18 % / 71-38 %), ce qui valide la chaîne de traitement.
- Questionnaire `211014_questio EMC2_TOULOUSE2023_V6.xlsx`, libellés exacts : `M20`
  « Combien de vélos en état de marche et utilisables sur la voie publique avez-vous à
  disposition dans votre ménage ? », `ML21` « Parmi ces vélos, combien sont équipés d'une
  assistance électrique ? », `P20` batterie « En semaine (du lundi au vendredi), avec quelle
  fréquence vous déplacez-vous … » ligne « À vélo (conducteur) ».
