# Ticket 017 — Le permis de conduire : un niveau et un gradient, pas un mécanisme

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité. Ce qui suit est une **spécification** : rien n'en est implémenté.

## Le problème, en une mesure

`has_license` est **recopié** du donneur ENTD 2008 apparié à la personne
([enriched.py:57-62](../../eqasim-toulouse/synthesis/population/enriched.py)). Confronté à
EMC² Toulouse 2023 (`lil-1750`, variable `P7`, pondération `COEP`, enquêtés `PENQ = 1`) sur
`toulouse_population_1000.json` **du 2026-08-21 15:23** — les livraisons des tickets 015 et
019 ont réécrit ce fichier sans changer une seule de ces valeurs, le permis n'étant touché par
aucun des deux :

| Âge | EMC² 2023 | Population synthétique | Écart | n synthétique |
|---|---|---|---|---|
| 18-24 | **58,1 %** | **85,4 %** | **+27,3** | 123 |
| 25-34 | 84,3 % | 89,5 % | +5,2 | 172 |
| 35-49 | 91,8 % | 98,5 % | +6,7 | 196 |
| 50-64 | 94,3 % | 94,4 % | +0,1 | 180 |
| 65-74 | 93,8 % | 87,4 % | −6,4 | 87 |
| 75 et + | 88,9 % | 86,7 % | −2,2 | 98 |
| **18 et +** | **85,9 %** | **91,5 %** | **+5,6** | 856 |

| Genre (18 et +) | EMC² 2023 | Population synthétique |
|---|---|---|
| Hommes | 88,6 % | 94,1 % |
| Femmes | 83,4 % | 89,0 % |

L'écart est modéré en agrégat — 5,6 points — et **concentré sur les jeunes adultes** :
+27,3 points sur les 18-24 ans, soit 6 écarts-types sur cet effectif. L'écart-type
d'échantillonnage à 18-24 vaut 4,5 points ; ce n'est pas un artefact de petit nombre.

À titre indicatif, le permis par occupation dans l'enquête (18 ans et +) : plein temps
**94,8 %**, retraité **92,6 %**, temps partiel **86,5 %**, chômeur **69,4 %**, au foyer
**63,9 %**, étudiant **59,2 %**.

## Ce que ce ticket n'a pas à faire

C'est ce qui le distingue du [ticket 015](ticket_015_acces_velo_progedo.md), et il faut
l'écrire avant la spécification pour ne pas construire un étage inutile : **la structure de
foyer du permis est déjà correcte.** Ménages de deux adultes, nombre de titulaires :

| Titulaires | EMC² observé | Binomial indépendant | Population synthétique |
|---|---|---|---|
| 0 | 2,9 % | 1,2 % | 1,8 % |
| 1 | 14,8 % | 19,7 % | 16,9 % |
| 2 | **82,3 %** | 79,0 % | **81,3 %** |

*(EMC² n = 2 107 ménages dont les deux adultes sont enquêtés ; synthétique n = 166 grappes
complètes à deux adultes.)*

La surdispersion réelle vaut **×1,13** (variance 0,223 contre 0,197 en indépendance) : le
permis est **presque** une pièce lancée séparément pour chaque adulte, contrairement au
vélo dont la surdispersion mesurée est ×2,4. Et la recopie de donneur la reproduit
correctement, parce que `any_cars` — la motorisation du ménage — fait partie des attributs
d'appariement et corrèle les membres d'un même foyer.

**Conclusion : pas d'étage « combien dans le ménage », pas de tirage sans remise, pas de
ménage à reconstituer.** Un logit individuel suffit, et c'est tout ce que ce ticket demande.

## Où est l'erreur exactement

**La classe d'âge de l'appariement.** `matching_attributes` utilise `age_class` avec les
bornes `[14, 29, 44, 59, 74]`
([matched.py:191](../../eqasim-toulouse/synthesis/population/matched.py)) : une seule classe
couvre 15 à 29 ans. Dans EMC², le permis y traverse toute son échelle :

| Âge | Permis | n |
|---|---|---|
| 15-17 | **0,0 %** | 454 |
| 18-24 | 58,1 % | 1 791 |
| 25-29 | **78,3 %** | 906 |

Le vivier de donneurs mélange les trois lignes. Le mécanisme ne peut structurellement
produire qu'une valeur pour un rapport de 0 à 78 %.

**Et l'ENTD 2008 est nationale, quinze ans plus vieille.** Le recul du permis chez les
jeunes adultes urbains est postérieur à cette enquête : la population synthétique hérite
d'un taux de 2008 appliqué à une cohorte de 2023. Les deux causes s'additionnent, et
expliquent que le taux simulé à 18-24 (85,4 %) dépasse même la moyenne de la classe 15-29
observée aujourd'hui.

Le croisement âge × genre montre où l'erreur se logera après correction : à 18-24 ans,
60,7 % des hommes et 55,6 % des femmes ; à 65 ans et plus, 97,7 % des hommes contre
**86,5 %** des femmes. Un modèle sans interaction âge × genre manquera ce dernier point.

## Pourquoi ça compte

Le permis est un **verrou dur** : sans lui, le mode voiture n'est pas proposé du tout
([`_can_drive`](../../llm-agents/urban_mobility_agents/simulation_controller.py:298),
appliqué avec l'âge légal). Et il alimente `car_availability`, recalculée par ménage
([fix_minor_traits.py](../../scripts/data/population/fix_minor_traits.py), règle 4).

Effet marginal moyen sur le booster déployé (faux → vrai, pondéré `COEP`) :

| Trait | vélo | voiture | TC | marche |
|---|---|---|---|---|
| `has_driving_license` | −0,9 pt | **+8,1 pt** | −3,1 pt | −4,2 pt |

*(Artefact de politique déployé, contrat de variables v2, ré-entraîné le 2026-08-21. Sous le
contrat v1 l'effet valait +6,5 pt : il a gagné 1,6 point au ré-entraînement, ce qui rend ce
ticket un peu plus rentable qu'estimé au départ.)*

Biais induit : **+2,2 pt de voiture et −1,1 pt de marche pour les 18-24 ans**, +0,5 pt de
voiture en agrégat. C'est modéré, et c'est cumulatif avec les deux autres tickets
d'équipement — le même jeune adulte reçoit un permis qu'il n'a pas
(+1,8 pt voiture) et perd l'abonnement qu'il a (−3,7 pt TC, cf.
[ticket 016](ticket_016_abonnement_tc_progedo.md)). Les deux erreurs poussent dans le même
sens sur la même cohorte.

## Le trait produit

```
traits_json.has_driving_license : true | false
```

Inchangé, et les deux garde-fous existants sont conservés tels quels : `_flag()` traite le
NaN comme « non » ([llm_agents.py:26-34](../../eqasim-toulouse/synthesis/population/llm_agents.py))
et l'âge légal est vérifié à l'export comme à la lecture. Un modèle bien calé ne dispense
pas d'un verrou : c'est ce verrou qui a arrêté les 131 mineurs porteurs du permis du
ticket 008.

## Spécification

### Étage unique — la propension individuelle au permis

- **Cible** : `P7 == 1`. Attention à la troisième modalité : `P7 = 3` vaut « Conduite
  accompagnée et leçons de conduite », **266 personnes enquêtées (1,7 %)**, âge médian 18
  ans, dont 155 majeures. Elles ne sont pas titulaires : elles comptent « non », et il faut
  l'écrire dans le module plutôt que de laisser un `== 1` l'affirmer en silence.
- **Source** : `Toulouse_2023_std_pers.csv` restreint à `PENQ = 1` (15 775 personnes),
  pondération `COEP`.
- **Covariables** :
  - `P4` **âge en clair**, et une interaction avec le genre — c'est le cœur du ticket ;
  - `P2` genre ;
  - `P9` occupation principale et/ou `PCSC` catégorie sociale (étudiant 59,2 % contre plein
    temps 94,8 %) ;
  - `M6` motorisation du ménage — la covariable qui porte la corrélation intra-foyer
    mesurée ci-dessus, et qui est **observée** dans la population synthétique ;
  - zone fine du domicile → densité et distance au centre.
- **Pas de covariable de déplacement** : un permis est un stock. Même argument que le
  ticket 015 sur `D12`.
- **Plancher légal en dur** : aucune propension n'est évaluée sous 18 ans, le trait vaut
  `false` par construction. L'enquête le confirme (0,0 % à 15-17 ans), et un seuil légal
  n'est pas un paramètre de modèle.
- **Tirage** : Bernoulli, clé de hachage `(adresse du domicile, index de la personne, sel
  versionné)`, déterminisme de [housing_type.py](../../llm_module/core/housing_type.py).
- **Ordre d'application obligatoire** : le permis se corrige **avant** `car_availability`,
  qui en dérive. Un script qui inverse l'ordre laisse `car_availability` calculée sur les
  anciens permis, sans que rien ne le signale.

### La contrainte du consommateur

Comme pour le [ticket 016](ticket_016_abonnement_tc_progedo.md), elle joue dans le bon
sens : la politique a été **entraînée** sur `has_driving_license = (P7 == 1)`
(fonction `build_person` de [build_mode_choice_dataset.py](../../scripts/progedo_logit/build_mode_choice_dataset.py)).
Imputer depuis `P7` aligne les définitions. Aucun ré-entraînement nécessaire.

Une seule vigilance : la politique consomme aussi `car_availability`, elle-même reconstruite
depuis le nombre de titulaires du ménage. Corriger le permis **déplace** cette variable
seconde, et le déplacement doit être mesuré, pas subi (cf.
[ticket 018](ticket_018_partage_voiture_foyer.md), qui traite la définition même de
`car_availability`).

## Critères d'acceptation

- [ ] ensemble des 18 ans et + : **85,9 %** (± 1,5 pt)
- [ ] courbe par âge — 18-24 **58,1** / 25-34 **84,3** / 35-49 **91,8** / 50-64 **94,3** /
      65-74 **93,8** / 75+ **88,9 %** (± 3 pts par point), le point 18-24 étant celui qui
      échoue aujourd'hui de 27 points
- [ ] genre : **88,6 %** des hommes, **83,4 %** des femmes (± 2 pts), et l'écart de genre
      chez les 65 ans et + (**97,7 %** contre **86,5 %**) reproduit à ± 4 pts
- [ ] courbe par occupation — plein temps **94,8** / retraité **92,6** / temps partiel
      **86,5** / chômeur **69,4** / au foyer **63,9** / étudiant **59,2 %** (± 5 pts)
- [ ] **non-régression de la structure de foyer** : ménages de deux adultes, deux
      titulaires **82,3 %** (± 3 pts). C'est le seul critère qui est déjà satisfait
      aujourd'hui, et c'est précisément pour cela qu'il figure ici : un logit individuel mal
      spécifié le casserait sans que rien d'autre ne le montre
- [ ] zéro titulaire sous 18 ans (verrou légal, déjà tenu)
- [ ] validation croisée **groupée par ménage**, jamais par personne
- [ ] effectifs de cellule publiés ; toute cellule sous 30 observations pondérées est
      signalée, pas lissée
- [ ] `car_availability` recalculée après correction, et son déplacement mesuré
- [ ] aucune cible atteinte par absence de mesure

## Hors périmètre

- **La conduite accompagnée** comme état intermédiaire : 266 personnes, comptées « non ».
  Le trait est booléen parce que le contrôleur l'est.
- **Les permis autres que voiture** (moto, poids lourd) : `P7` porte le permis voiture.
  Le deux-roues motorisé est traité en annexe du
  [ticket 018](ticket_018_partage_voiture_foyer.md).
- **La date d'obtention** et l'ancienneté : absentes du fichier standard.
- **L'aptitude effective** (permis détenu mais conduite abandonnée par l'âge) : `P7` est une
  possession. L'enquête ne dit pas si le titulaire conduit encore ; les 88,9 % de titulaires
  à 75 ans et + doivent donc être lus comme un stock, pas comme un usage.

## Où le modèle écrase la sortie eqasim

Identique au [ticket 016](ticket_016_abonnement_tc_progedo.md) : **voie 1** par script de
post-traitement sur le JSON (toutes les covariables y sont déjà, aucun ménage à
reconstituer sauf pour le recalcul de `car_availability`, qui a déjà son code dans
`fix_minor_traits.py`), puis **voie 2** dans le fork eqasim en remplacement de la recopie
ENTD.

## Découpage en lots

1. **Lot 1 — le logit.** `P(permis | âge × genre, occupation, motorisation, zone)` appris
   sur `P7`, validation croisée groupée par ménage.
2. **Lot 2 — voie 1.** Script de post-traitement, puis recalcul de `car_availability` dans
   le bon ordre.
3. **Lot 3 — recette sur le jeu commun.** Déplacement de la part voiture, par âge et en
   agrégat.
4. **Lot 4 — voie 2.** Remontée dans le fork.

Les lots 1 et 2 sont **communs avec le [ticket 016](ticket_016_abonnement_tc_progedo.md)** :
même fichier, même restriction, même pondération, même cause. Un seul chargeur, deux
cibles.

## Sources

- Microdonnées **EMC² Toulouse 2023**, ProGEDO/ADISP `lil-1750`, fichier standard `pers` —
  variable `P7` « POSSESSION DU PERMIS DE CONDUIRE VOITURE », pondération `COEP`,
  restriction `PENQ = 1`.
- Dictionnaire `Dico_Dessin_StandardV17_Corrige.xls`, onglet `Dico` : les trois modalités de
  `P7`, dont « Conduite accompagnée et leçons de conduite ».
- Politique de choix modal du dépôt pour les effets marginaux moyens.
- [ticket 008](ticket_008_run_24h_mesures_synthese.md), action A1.a — les garde-fous d'âge
  qui restent valables après correction.
