# Ticket 019 — Le type de logement : conditionner l'imputation à la taille du ménage

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité. Ce qui suit était une **spécification** ; les **quatre lots sont livrés le
> 2026-08-21**, et ce qui tourne est décrit dans
> [population-post-traitements.md § Le conditionnement du logement](../arch/population-post-traitements.md#le-conditionnement-du-logement-ticket-019).
> Les chiffres de la spécification ci-dessous sont ceux de l'étude préalable ; ceux du
> mécanisme réellement livré sont publiés par `make housing-type` dans le bloc
> `validation` de la ressource, et diffèrent à la décimale (erreur absolue moyenne
> **3,00 → 0,75 pt** au lieu de 2,62 → 0,63 : le rejeu du mécanisme antérieur est fait
> ici sur la table de personnes exacte, et le poids du repli a suivi le changement
> d'unité — 12 ménages au lieu de 18 personnes). La conclusion est la même, et le
> critère d'acceptation (< 1 pt) est tenu.
>
> **Urgent, et pour une raison précise** : il conditionne la recette du
> [ticket 015](ticket_015_acces_velo_progedo.md), dont le deuxième critère d'acceptation
> est l'axe habitat. Livré après, il obligerait à rejouer cette recette.

## Le problème, en une mesure

L'imputation ne pose qu'une question : **où habites-tu ?** Le type de logement est tiré
dans la loi de la zone fine du domicile
([housing_type.py](../../llm_module/core/housing_type.py),
[export_housing_type.py](../../scripts/progedo_logit/export_housing_type.py)). La taille du
ménage n'entre nulle part.

Or dans une même zone, les familles sont dans les maisons et les personnes seules dans les
appartements. Le tirage par zone seule mélange les deux.

Mesuré **à l'intérieur d'EMC²**, donc sans aucun biais de périmètre : on remplace le `M1`
de chaque ménage enquêté par la loi de sa zone — c'est-à-dire qu'on fait tourner le
mécanisme du dépôt sur des ménages dont on connaît la vérité. Part d'**individuel isolé** :

| Taille du ménage | Observé | Imputé par la zone seule | Population synthétique | n EMC² |
|---|---|---|---|---|
| 1 personne | **15,7 %** | **25,4 %** | **27,2 %** | 4 778 |
| 2 | 46,4 % | 42,6 % | 40,6 % | 3 620 |
| 3 | 45,5 % | 45,8 % | 40,0 % | 1 114 |
| 4 et + | **53,9 %** | 49,4 % | **36,1 %** | 1 271 |

Le mécanisme aplatit le gradient ; la population synthétique le supprime presque. Sur les
cinq modalités et les quatre tailles, l'erreur absolue moyenne du mécanisme actuel vaut
**2,62 point**, et elle est concentrée sur la personne seule (+9,7 pts d'individuel isolé)
et le grand ménage (−4,5 pts).

*(La population synthétique compte 498 ménages reconstitués à l'adresse du domicile — 191
d'une personne, 165 de deux, 70 de trois, 72 de quatre et plus. À n = 191, l'écart de 11,5
points sur la personne seule vaut 4,4 écarts-types : ce n'est pas du bruit.)*

## Pourquoi c'est urgent

**1. C'est l'axe de recette du ticket 015.** Son critère n° 2 exige de reproduire
l'équipement vélo par type d'habitat, **71 % en individuel isolé → 38 % en grand
collectif**. Si l'axe habitat est lui-même aplati, ce critère peut échouer sans que
l'imputation vélo soit en cause — ou passer alors qu'elle est fausse.

**2. Et cet axe n'est pas indépendant de la taille du ménage.** Équipement vélo des ménages
EMC² par habitat, brut puis standardisé sur la structure de taille de l'ensemble
(standardisation directe : on donne à chaque habitat la même répartition de tailles) :

| Habitat | Brut | Standardisé sur la taille |
|---|---|---|
| Individuel isolé | **70,9 %** | 63,8 % |
| Individuel accolé | 64,8 % | 60,1 % |
| Petit habitat collectif | 41,1 % | 46,0 % |
| Grand habitat collectif | **37,5 %** | 43,0 % |
| **Amplitude du gradient** | **33,4 pts** | **20,8 pts** |

**38 % du gradient habitat de l'équipement vélo est de la composition de ménages**, pas de
l'habitat. Valider les vélos sur cet axe suppose donc que le **croisement** habitat × taille
soit juste dans la population synthétique. Il ne l'est pas aujourd'hui.

**3. Ça débloque un piège que le ticket 015 laisse ouvert.** Il note que conditionner `k` sur
l'habitat « n'apporte rien au-delà de la zone », puisque l'habitat n'est qu'une réécriture de
la zone. C'est exact **pour cette imputation-là**, et ça cesse de l'être dès que la loi
devient `P(M1 | zone, taille)` : l'habitat porte alors une information propre.

**4. Accessoirement, l'habitat pèse dans la politique de choix modal** : `housing_type` est
la 6ᵉ variable de la décision marche (|SHAP| moyen 0,199 sur le bloc exploratoire,
[progedo_walk_shap_blockA.csv](../../scripts/progedo_logit/progedo_walk_shap_blockA.csv)),
devant `number_of_cars`.

## Où est l'erreur exactement

Ce n'est pas un bug, c'est le périmètre d'origine du module. L'action A2 avait besoin d'un
axe habitat qui n'existait nulle part dans la chaîne de génération ; la zone fine était le
seul conditionnement disponible, et le module le documente honnêtement. Ce qu'il fait
aujourd'hui :

- loi `P(M1 | zone fine)`, pondérée par les coefficients **personnes** (`COEP`) ;
- lissage hiérarchique zone → secteur de tirage → périmètre, poids du repli
  `PRIOR_WEIGHT = 18` (l'effectif médian d'une zone en personnes enquêtées) ;
- tirage par hachage de l'**adresse**, pour que deux personas d'un même foyer partagent le
  type ;
- `None` hors couche de zones fines, jamais de repli silencieux.

Tout cela est conservé. **Il manque une dimension, pas une réécriture.**

## Ce qu'on ne peut pas faire

Servir la loi brute `P(M1 | zone fine, taille)`. Mesuré :

| | Valeur |
|---|---|
| Zones fines | 704 |
| Ménages enquêtés par zone, médiane | **12** |
| Zones à 30 ménages ou plus | 103 / 704 |
| Cellules (zone, taille) | 2 145 |
| Ménages par cellule, médiane | **3** |
| Cellules à 30 observations ou plus | **18 / 2 145** |

Trois ménages par cellule : servir cette loi ferait passer du bruit d'échantillonnage pour
de la géographie, exactement ce que `PRIOR_WEIGHT` existe pour éviter. **La taille doit
entrer autrement que par un croisement brut.**

## La règle proposée — et son test avant implémentation

Transfert de rapport de cotes (*raking* à une dimension) : on garde la loi de zone comme
géographie, et on lui applique un **levier de taille** estimé au niveau du périmètre, puis
on renormalise.

```
P(M1 = m | zone, taille) ∝ P(M1 = m | zone) × [ P(M1 = m | taille) / P(M1 = m) ]
```

Testée à l'intérieur d'EMC² — chaque ménage enquêté reçoit la loi de sa zone corrigée du
levier de sa taille, puis on compare à son `M1` réel. Part d'individuel isolé, et erreur
absolue moyenne sur les 20 cellules (5 modalités × 4 tailles) :

| Taille | Observé | Zone seule, `COEP` *(actuel)* | Zone seule, `COE0` | **Zone `COE0` + levier de taille** |
|---|---|---|---|---|
| 1 | 15,7 % | 25,4 % | 23,3 % | **15,0 %** |
| 2 | 46,4 % | 42,6 % | 40,4 % | **46,3 %** |
| 3 | 45,5 % | 45,8 % | 43,5 % | **47,5 %** |
| 4 et + | 53,9 % | 49,4 % | 46,8 % | **55,6 %** |
| **Erreur absolue moyenne** | — | **2,62 pt** | 3,19 pt | **0,63 pt** |

**Quatre fois moins d'erreur**, et la géographie n'est pas déplacée : la marginale
d'ensemble reste sur place (individuel isolé 34,7 % observé → 34,9 % raké, accolé
12,9 → 13,0, petit collectif 28,2 → 27,9, grand collectif 23,6 → 23,5).

**Deux enseignements à écrire dans le module :**

- **La pondération n'est pas le sujet.** Passer des poids personnes aux poids ménages *sans*
  le levier de taille **dégrade** le résultat (2,62 → 3,19 pt) : la pondération personnes
  compense partiellement l'absence de taille, par coïncidence. Il ne faut donc pas toucher
  la pondération seule. En revanche, une fois la taille conditionnée, la pondération
  **ménages** est la bonne — un ménage tire une fois — et la marginale personnes se
  reconstitue d'elle-même puisque la taille est dans le conditionnement.
- **Le résidu est réel et petit** : le raké dépasse d'environ 2 points aux tailles 3 et 4+.
  L'hypothèse de transfert (le levier de taille est le même dans toutes les zones) n'est
  pas exacte ; elle est bonne à 0,63 point. Un levier estimé **par secteur de tirage** plutôt
  qu'au périmètre est l'amélioration suivante, à ne tenter que si le critère de recette
  l'exige — un secteur compte 174 personnes enquêtées en médiane, la cellule
  (secteur, taille) reste mince.

## Le trait produit

Contrat inchangé :

```
traits_json.housing_type : "Individuel isolé" | "Individuel accolé" | "Petit habitat collectif"
                         | "Grand habitat collectif" | "Autres" | None
```

Trois changements, tous internes :

- la ressource `llm_module/data/zf_housing_type.json` gagne un bloc de **leviers par
  taille** (4 tailles × 5 modalités) et les effectifs correspondants ; son champ `version`
  passe de 1 à 2, et le module refuse une ressource v1 plutôt que d'imputer sans levier ;
- la loi par zone passe en pondération **ménages** (`COE0`), la taille étant désormais
  conditionnée — et jamais l'un sans l'autre, cf. la mesure ci-dessus ;
- le sel de tirage passe à `housing_type_v2`. **Cela rebat toutes les imputations
  existantes** : c'est un acte délibéré et daté, à annoncer au changelog, pas un effet de
  bord. Le hachage reste celui de l'**adresse** — deux personas d'un même foyer doivent
  continuer à partager leur logement.

**Piège à écrire dans le module** : la taille à utiliser est le `household_size` **nominal**
du persona, pas le nombre de membres présents dans le fichier. 118 des 498 grappes d'adresse
de `toulouse_population_1000.json` sont partielles (filtrage par bbox) ; tirer sur le nombre
de présents mettrait des familles de quatre dans des lois de personne seule. Même règle que
l'étage 2 du ticket 015.

## Critères d'acceptation

- [ ] test interne EMC² (chaque ménage enquêté reçoit la loi de sa zone corrigée, on compare
      à son `M1`) : erreur absolue moyenne sous **1 point** sur les 20 cellules
      (5 modalités × 4 tailles) — aujourd'hui 2,62
- [ ] population synthétique, part d'individuel isolé par taille : **15,7 / 46,4 / 45,5 /
      53,9 %** (± 4 pts par point), et le **signe** de la pente entre la personne seule et
      le ménage de quatre est un critère à part entière — c'est lui qui est faux aujourd'hui
      (27,2 % → 36,1 % simulé contre 15,7 % → 53,9 % observé)
- [ ] marginale d'ensemble **préservée** : 34,7 / 12,9 / 28,2 / 23,6 / 0,6 % (± 1,5 pt par
      modalité). Le raking ne doit pas déplacer la géographie ; si elle bouge, c'est que le
      levier écrase la zone
- [ ] le lissage hiérarchique existant est **conservé et vérifié** : la ressource compte
      704 zones dont **132 sous 5 personnes enquêtées** (médiane 18, minimum 1), qui doivent
      continuer à s'effacer derrière leur secteur puis le périmètre. Le compte par niveau de
      repli est publié à chaque enrichissement
- [ ] effectifs de cellule écrits dans la ressource, comme aujourd'hui pour les zones ; toute
      cellule sous 30 observations pondérées est signalée, pas lissée en silence
- [ ] **le critère n° 2 du [ticket 015](ticket_015_acces_velo_progedo.md) est rejoué** après
      correction, et l'écart avant/après est mesuré : c'est la raison d'être de ce ticket
- [ ] `housing_type = None` reste `None` : aucun repli silencieux, et un `None` massif doit
      faire échouer la validation, pas la réussir

## Hors périmètre

- **Le statut d'occupation** (`M2` : propriétaire, locataire) et le nombre de pièces :
  covariables candidates du même fichier, aucun consommateur aujourd'hui.
- **Un levier par secteur de tirage** plutôt qu'au périmètre : mesuré comme la prochaine
  amélioration possible, non nécessaire pour tenir la recette (résidu 0,63 pt).
- **Le statut d'axe imputé** : `housing_type` reste **imputé**, et tout ce qui le publie doit
  continuer à le dire. Conditionner sur la taille rend l'imputation meilleure, pas observée.
- **La couche de zones fines** et la ressource de lois restent hors dépôt, régénérables,
  jamais committées — inchangé.

## Où le modèle écrase la sortie eqasim

Nulle part : **ce ticket n'a pas de voie 2.** `housing_type` n'existe pas dans eqasim, il est
posé après coup par
[enrich_housing_type.py](../../scripts/data/population/enrich_housing_type.py) sur une
population déjà générée. Tout se joue donc dans la ressource et le module, et une
ré-imputation des populations existantes suffit — aucune régénération, aucun accès aux
données sources au-delà de celui qu'exige déjà `make housing-type`.

C'est ce qui rend ce ticket court malgré son urgence.

## Découpage en lots

1. **Lot 1 — le levier.** `export_housing_type.py` calcule et écrit les leviers de taille et
   leurs effectifs ; la loi par zone passe en `COE0`. Le test interne EMC² est livré **avec**,
   comme critère exécutable et non comme promesse.
2. **Lot 2 — le module.** `housing_type.py` lit le bloc de leviers, applique la
   renormalisation, prend la taille nominale du persona, passe le sel en `v2`. Le repli
   hiérarchique existant est conservé tel quel.
3. **Lot 3 — ré-imputation et recette.** `make housing-type` puis `enrich_housing_type.py`
   sur les populations en service (10, 100, 1 000 agents), avec les tables de recette et les
   comptes de repli.
4. **Lot 4 — dépendance ticket 015.** Rejouer le critère n° 2 du ticket 015 sur la population
   ré-imputée, et publier l'écart avant/après.

## Sources

- Microdonnées **EMC² Toulouse 2023**, ProGEDO/ADISP `lil-1750`, fichier standard `men` —
  variable `M1` « Type d'habitat » (1 individuel isolé, 2 individuel accolé, 3 petit
  collectif R+1 à R+3, 4 grand collectif R+4 et plus, 5 autres), pondération `COE0` ;
  taille du ménage reconstituée depuis le fichier `pers`.
- [housing_type.py](../../llm_module/core/housing_type.py) et
  [export_housing_type.py](../../scripts/progedo_logit/export_housing_type.py) — le
  mécanisme actuel, son lissage hiérarchique et son `PRIOR_WEIGHT`.
- [ticket 015](ticket_015_acces_velo_progedo.md) — critère n° 2 (axe habitat) et
  § *Étage 1*, piège de l'habitat comme réécriture de la zone.

---

## Amendement du 2026-08-21 — livré, et ce que la recette dit vraiment

**Livré le jour même de la spécification** par la session qui tenait `housing_type.py`,
`export_housing_type.py` et `enrich_housing_type.py` (loi par zone en `COE0`, levier de taille
au périmètre, sel `housing_type_v2`, `--check` sur le signe du gradient). Le détail
d'implémentation vit dans [../arch/population-post-traitements.md](../arch/population-post-traitements.md)
§ *Le conditionnement du logement*.

Mesuré après ré-imputation sur `toulouse_population_1000.json` du 15:23 — part d'individuel
isolé par taille de ménage. La colonne « après » est celle de la recette de l'implémentation,
qui **scinde les grappes d'adresse en collision par `household_size`** comme le spécifie
l'étage 2 du ticket 015 ; entre parenthèses, ma propre mesure avec un regroupement naïf par
adresse, qui sous-estime les grands ménages (une grappe en collision y devient un seul gros
foyer) :

| Taille | Observé EMC² | Avant | **Après** | Écart | 1 écart-type |
|---|---|---|---|---|---|
| 1 personne | 15,7 % | 27,2 % | **14,5 %** *(14,0)* | −1,2 | 2,5 pt |
| 2 | 46,5 % | 40,6 % | **41,8 %** *(41,8)* | −4,7 | 3,7 pt |
| 3 | 45,5 % | 40,0 % | **36,9 %** *(36,0)* | −8,6 | 5,9 pt |
| 4 et + | 53,9 % | 36,1 % | **52,1 %** *(49,4)* | −1,8 | 5,5 pt |

**Le critère de signe passe largement** : la pente vaut **+37,6 points** (contre +38,2
observés), là où elle valait +9,5 points avant — et elle allait dans le mauvais sens sur les
tailles 1 à 3. L'inversion est levée, et c'était l'objet du ticket.

Le test interne EMC², exécuté désormais à chaque `make housing-type` et publié dans la
ressource, donne **3,00 pt → 0,75 pt** d'erreur absolue moyenne sur les 20 cellules, sous le
critère de 1 point, marginale géographique préservée. L'écart avec les 2,62 → 0,63 pt de
l'étude préalable ci-dessus est expliqué dans l'en-tête du ticket : table de personnes exacte
au rejeu, et poids du repli passé en ménages plutôt qu'en personnes. La conclusion ne bouge
pas — c'est bien le conditionnement sur la taille qui divise l'erreur par quatre.

**Et le critère de tolérance, tel que je l'avais écrit, ne discrimine pas.** Les ± 4 points
par cellule sont **sous l'erreur d'échantillonnage** d'une population de mille agents : à
n = 75, un écart-type vaut 5,7 points. Les quatre écarts observés valent 0,5 / 1,3 / 1,5 /
0,3 écart-type — la population est donc statistiquement compatible avec la cible sur les
quatre cellules (deux d'entre elles dépassent les ± 4 pts stricts et restent dans la marge de
2 σ), et elle l'aurait été avec des écarts bien pires. **Le critère est à évaluer sur la
population de 10 000 agents**, où l'erreur d'échantillonnage tombe sous 2 points, ou à
assortir d'un intervalle de confiance plutôt que d'une tolérance fixe. Une tolérance plus
étroite que le bruit qu'elle mesure n'est pas un critère : c'est un tirage au sort.

C'est le même principe que « aucune cible atteinte par absence de mesure », appliqué à
l'effectif au lieu du champ manquant.

**Effet de bord vérifié sur le ticket 015** : la cible opposable de son critère n° 2 —
l'amplitude du gradient habitat de l'équipement vélo, diluée par le fait que l'axe est imputé
— s'est resserrée de **19,9 à 26,8 points** au seul passage à l'habitat v2 (accord habitat
imputé/observé 47,6 % → 50,2 %), sans qu'une ligne du modèle vélo change. La cible publiée
reste à 33,4 points. C'est la vérification que la dilution mesurait bien la qualité de l'axe.
