# Ticket 016 — L'abonnement TC : apprendre l'équipement sur EMC² au lieu de le recopier

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité. Ce qui suit est une **spécification** : rien n'en est implémenté.

## Le problème, en une mesure

`has_pt_subscription` est **recopié** du donneur ENTD 2008 apparié à la personne
([enriched.py:57-62](../../eqasim-toulouse/synthesis/population/enriched.py)). Confronté
aux microdonnées EMC² Toulouse 2023 (`lil-1750`, variable `P12`, pondération `COEP`,
enquêtés `PENQ = 1`) sur `toulouse_population_1000.json` **du 2026-08-21 15:23**, c'est-à-dire
après les livraisons des tickets 015 et 019 :

| Occupation principale | EMC² 2023 | Population synthétique | Écart |
|---|---|---|---|
| Étudiant | 74,3 % *(n = 1 327)* | **35,4 %** *(n = 82)* | **−38,9** |
| Scolaire (jusqu'au Bac) | 33,3 % *(n = 2 229)* | 20,2 % *(n = 163)* | −13,1 |
| Chômeur / recherche d'emploi | 28,8 % *(n = 866)* | 25,0 % *(n = 52)* | −3,8 |
| Personne au foyer | 24,0 % *(n = 370)* | 14,3 % *(n = 56)* | −9,7 |
| Travail à temps partiel | 21,5 % *(n = 850)* | 23,0 % *(n = 100)* | +1,5 |
| Retraité | 17,7 % *(n = 3 858)* | **29,7 %** *(n = 175)* | **+12,0** |
| Travail à plein temps | 14,8 % *(n = 5 950)* | 16,8 % *(n = 393)* | +2,0 |
| **Ensemble (5 ans et +)** | **25,8 %** | **21,9 %** | −3,9 |

Par âge, le même retournement :

| Âge | EMC² 2023 | Population synthétique | Écart |
|---|---|---|---|
| 5-17 | 32,9 % | 20,6 % | −12,3 |
| 18-24 | **63,3 %** | **26,8 %** | **−36,5** |
| 25-34 | 22,7 % | 26,2 % | +3,5 |
| 35-49 | 15,2 % | 13,3 % | −1,9 |
| 50-64 | 14,8 % | 17,8 % | +3,0 |
| 65 et + | 18,9 % | **29,2 %** | +10,3 |

**Le total est à peu près juste — 3,9 points d'écart — et la répartition est retournée** :
l'abonnement passe des étudiants aux retraités. C'est le même diagnostic que le
[ticket 015](ticket_015_acces_velo_progedo.md), sur un trait qui pèse davantage.

## Pourquoi ce trait pèse plus lourd que le vélo

Effet marginal moyen mesuré sur le booster déployé
([mode_choice_policy.json](../../scripts/progedo_logit/mode_choice_policy.json)), passage
faux → vrai, pondéré `COEP` sur les 27 886 déplacements du jeu :

| Trait | vélo | voiture | TC | marche |
|---|---|---|---|---|
| `has_pt_subscription` | −1,6 pt | **−8,0 pt** | **+9,5 pt** | +0,1 pt |
| `has_bike` | +5,7 pt | −2,2 pt | −1,0 pt | −2,5 pt |
| `has_driving_license` | −0,9 pt | +8,1 pt | −3,1 pt | −4,2 pt |

*(Effets mesurés sur l'artefact de politique **déployé**, contrat de variables **v2**,
ré-entraîné le 2026-08-21 sur le `has_bike` nominatif du
[ticket 015](ticket_015_acces_velo_progedo.md). Pour mémoire, les mêmes effets sous le
contrat v1 — où `has_bike` valait « le foyer déclare au moins un vélo » — étaient +9,7 / −1,1
pour l'abonnement, +5,4 pour le vélo et +6,5 pour le permis : le classement des trois leviers
est inchangé, et l'effet du permis a gagné 1,6 point au passage.)*

L'abonnement TC est le **levier d'équipement le plus fort de la politique**, presque le
double du vélo. Croisé avec l'écart de calage, le biais induit vaut :

| Strate | Écart de calage | Biais sur la part TC |
|---|---|---|
| Étudiants | −38,9 pt | **−3,7 pt** |
| Retraités | +12,0 pt | **+1,1 pt** |
| Ensemble | −3,9 pt | −0,4 pt |

Autrement dit : la part TC globale reste presque juste, et **elle est juste pour les
mauvaises personnes**. Un correctif sur le niveau agrégé ne peut rien y faire — c'est
exactement l'argument du ticket 015 (§ *Pourquoi tirer `k` d'abord*), transposé.

Le trait alimente aussi le narratif du persona
([llm_agent.py:134](../../llm-agents/urban_mobility_agents/agents/llm_agent.py:134)) : un
étudiant sur trois seulement arrive au LLM avec son abonnement, alors que deux sur trois
l'ont dans la réalité toulousaine.

## Où est l'erreur exactement

**Deux causes, additives, et aucune n'est un bug.**

**1. La classe d'âge de l'appariement écrase la variable.** `matching_attributes` utilise
`age_class` avec les bornes `[14, 29, 44, 59, 74]`
([matched.py:191](../../eqasim-toulouse/synthesis/population/matched.py)) : une seule
classe couvre 15 à 29 ans. Or dans EMC², l'abonnement s'y effondre :

| Âge | Abonnement TC | n |
|---|---|---|
| 15-17 | 64,0 % | 454 |
| 18-24 | 63,3 % | 1 791 |
| 25-29 | **29,3 %** | 906 |

Le donneur est tiré dans un vivier qui mélange les trois lignes : le mécanisme ne peut
structurellement produire qu'une valeur moyenne pour un rapport de 1 à 2.

**2. L'ENTD 2008 est nationale et antérieure à la tarification jeune.** L'abonnement TC
d'un jeune Toulousain de 2023 (tarification Tisséo scolaire/étudiante) n'a pas d'équivalent
dans un échantillon national de 2008. Aucun raffinement de l'appariement ne rattrapera un
millésime.

**Ce n'est pas un défaut de structure de foyer — mais il y en a une, et elle est perdue.**
Sur les ménages EMC² comptant au moins deux personnes enquêtées :

| | Observé | Sous indépendance | Population synthétique |
|---|---|---|---|
| Tous les enquêtés abonnés | **10,4 %** | 5,3 % | 2,9 % *(indép. attendue 3,4 %)* |
| Aucun abonné | **62,7 %** | 49,9 % | 53,1 % *(indép. attendue 54,3 %)* |

L'abonnement se groupe dans le foyer — d'un facteur 2 sur « tous abonnés » — et la
population synthétique est exactement à son propre niveau d'indépendance. Mais
contrairement au vélo, **il n'y a pas d'entier partagé à respecter** : un abonnement est
nominatif, il n'y a pas de stock de ménage. Le regroupement observé vient d'un contexte
partagé (pas de voiture, desserte du domicile), pas d'un objet indivisible — et ce contexte
est **observé** dans la population synthétique. Mesure à l'appui :

| Motorisation du ménage | Abonnement TC | n |
|---|---|---|
| 0 voiture | **61,8 %** | 2 308 |
| 1 voiture | 25,5 % | 6 423 |
| 2 voitures et + | 16,1 % | 7 044 |

`number_of_cars` vient du recensement et il est **juste** (1,28 voiture/ménage simulé
contre 1,25 mesuré). Conditionner sur lui restitue donc l'essentiel de la corrélation
intra-foyer sans modéliser le ménage. C'est ce qui rend ce ticket plus simple que le 015 :
**un seul étage, pas de tirage sans remise, pas de ménage à reconstituer.**

## Le trait produit

Le contrat de sortie ne change pas :

```
traits_json.has_pt_subscription : true | false
```

Booléen, comme aujourd'hui — le champ est déjà lu par la politique, par le narratif et par
la page de synthèse, et le rendre nullable casserait trois consommateurs pour rien. En
revanche le **repli est explicite et compté** : quand la zone fine du domicile n'a pas
d'effectif suffisant, on remonte au secteur de tirage puis au périmètre entier, comme
[housing_type.py](../../llm_module/core/housing_type.py), et le rapport de sortie publie le
nombre d'imputations par niveau de repli. Jamais un `false` par défaut silencieux.

## Spécification

### Étage unique — la propension individuelle à l'abonnement

- **Cible** : `P12`, recodée en booléen. Le questionnaire prévoit **six** modalités
  (1 gratuit, 2 payant avec prise en charge employeur, 3 payant sans prise en charge,
  4 non, 5 payant sans information, 6 oui sans précision) ; le fichier standard livré
  n'en porte que **deux** : `4` (non, 11 745) et `6` (oui sans précision, 4 030), qui
  totalisent exactement les 15 775 enquêtés. Aucune perte de champ, mais **la prise en
  charge employeur est inexploitable** : elle est à écrire dans le module, pas à deviner.
- **Source** : `Toulouse_2023_std_pers.csv` restreint à `PENQ = 1` (15 775 personnes sur
  20 890), pondération `COEP` — nulle pour les non-enquêtés, donc toute statistique
  pondérée `COEP` est déjà correctement restreinte.
- **Covariables**, toutes disponibles dans `traits_json` ou dérivables du domicile :
  - `P4` **âge en clair**, pas en classe. C'est le cœur du ticket : la classe est
    précisément ce qui casse le mécanisme actuel ;
  - `P9` occupation principale (étudiant / scolaire / actif / retraité…), qui porte
    l'effet tarifaire ;
  - `M6` **motorisation du ménage**, seule covariable de foyer, et celle qui restitue la
    corrélation intra-ménage ;
  - `P2` genre (28,0 % des femmes contre 23,6 % des hommes) ;
  - zone fine du domicile → densité de ménages et distance au centre, déjà calculées par
    [build_mode_choice_dataset.py](../../scripts/progedo_logit/build_mode_choice_dataset.py).
- **Pas de covariable de déplacement.** Ni `DP15` (distance domicile-travail) ni le mode
  observé : un abonnement est un **stock**, il doit être invariant au trajet. Sinon le même
  agent est abonné pour aller travailler et ne l'est plus pour aller faire ses courses, et
  le trait cesse d'être un trait. Même argument que le ticket 015 sur `D12`.
- **Tirage** : Bernoulli de la propension estimée, clé de hachage
  `(adresse du domicile, index de la personne, sel versionné)`, exactement le déterminisme
  de `housing_type.py`. Deux exécutions, deux machines, deux moments donnent le même
  résultat ; changer le sel est un acte daté.
- **Éligibilité** : 5 ans et plus, qui est le champ de `P12` et déjà l'âge minimum de la
  population exportée (âge minimum mesuré : 5 ans). Aucun agent n'échappe donc à
  l'imputation.

### La contrainte du consommateur

Bonne nouvelle, pour une fois : **elle joue dans le bon sens.** La politique de choix modal
PROGEDO a été **entraînée** sur `has_pt_subscription = (P12 == 6)`
(fonction `build_person` de [build_mode_choice_dataset.py](../../scripts/progedo_logit/build_mode_choice_dataset.py)),
c'est-à-dire sur la variable même que ce ticket apprend. Imputer depuis `P12` **aligne**
les deux côtés au lieu de les écarter — là où le ticket 015 doit ré-entraîner sa politique
pour réconcilier `has_bike` (63,2 % de personnes en ménage équipé) avec une attribution
nominative (~51 %). Aucun ré-entraînement n'est nécessaire ici.

Ce qui doit être vérifié après coup, en revanche, c'est le **déplacement de part modale**
que la correction produit sur le jeu commun : attendu ≈ +0,4 pt de TC en agrégat, et
jusqu'à 3,7 pt par strate d'occupation. Un écart d'un autre ordre signalerait que la
propension apprise n'est pas celle qu'on croit.

### Limite d'identification, à assumer et à écrire

**67 %** des ménages (7 238 sur 10 783) n'ont qu'une seule personne enquêtée. On peut donc
estimer `P(abonné | covariables)`, on ne peut **pas** observer qui, parmi deux frères et
sœurs, est abonné. L'imputation sera indépendante conditionnellement aux covariables, et la
corrélation intra-foyer résiduelle — celle que la motorisation et la zone ne portent pas —
ne sera **pas** reproduite. Elle doit être mesurée et publiée, pas tue : c'est le critère
« tous abonnés » ci-dessous.

## Critères d'acceptation

Cibles recalculées sur `lil-1750`, à reproduire par la population synthétique (tolérance
entre parenthèses) :

- [ ] ensemble des 5 ans et + : **25,8 %** (± 2 pts)
- [ ] courbe par occupation — étudiant **74,3** / scolaire **33,3** / chômeur **28,8** /
      au foyer **24,0** / temps partiel **21,5** / retraité **17,7** / plein temps
      **14,8 %** (± 5 pts par modalité). L'écart étudiant − retraité est un critère à part
      entière : **+56,6 pts** observés contre **+5,7 pts** simulés aujourd'hui — le signe
      tient, l'amplitude est écrasée d'un facteur 10
- [ ] **le signe** de l'écart 18-24 ans − 65 ans et + : **+44,4 pts** observés
      (63,3 contre 18,9) contre **−2,4 pts** simulés (26,8 contre 29,2). C'est là que
      l'inversion est réelle, et c'est le critère le plus discriminant du ticket
- [ ] courbe par âge — 5-17 **32,9** / 18-24 **63,3** / 25-34 **22,7** / 35-49 **15,2** /
      50-64 **14,8** / 65+ **18,9 %** (± 5 pts), le point 18-24 étant celui qui échoue
      aujourd'hui de 36 points
- [ ] gradient de motorisation **décroissant** : **61,8 → 25,5 → 16,1 %** (± 5 pts)
- [ ] genre : **28,0 %** des femmes, **23,6 %** des hommes (± 3 pts)
- [ ] corrélation intra-ménage, **critère de validation et non identité** : ménages à 2
      enquêtés ou plus, « tous abonnés » **10,4 %** (± 3 pts) — si le modèle reste à son
      niveau d'indépendance (≈ 3 %), la covariable de motorisation ne fait pas son travail
      et il faut le dire
- [ ] validation croisée **groupée par ménage**, jamais par personne
- [ ] effectifs de cellule publiés avec chaque table ; toute cellule sous 30 observations
      pondérées est signalée, pas lissée en silence
- [ ] part TC sur le jeu commun après correction : déplacement mesuré et commenté, pas
      seulement constaté
- [ ] aucune cible atteinte par absence de mesure : un repli massif au périmètre entier
      doit **échouer** la validation, pas la réussir

## Hors périmètre

- **La prise en charge employeur** (modalités 2, 3, 5 de `P12`) : absente du fichier
  standard livré, donc non modélisable. Elle expliquerait une partie de l'écart
  actifs/inactifs ; on ne peut que le noter.
- **Le type d'abonnement** (scolaire, étudiant, senior, solidaire) : la même modalité `6`
  les couvre tous. Le trait reste un booléen parce que la source l'est.
- **La validité « hier »** : `P12` porte sur la journée d'enquête. Un abonné qui laisse son
  abonnement expirer une semaine est vu non-abonné. L'écart est structurellement
  inconnaissable et joue vers le bas.
- **`P16` (disposition d'une VP pour le trajet de travail)** : covariable candidate, mais
  endogène au mode et manquante hors actifs — écartée pour la même raison que `D12`.

## Où le modèle écrase la sortie eqasim

**Voie 1 — script de post-traitement (à faire d'abord).** Même patron que
[enrich_housing_type.py](../../scripts/data/population/enrich_housing_type.py) : on relit
le JSON, on lit l'âge, l'occupation, le genre, `number_of_cars` et le domicile de chaque
agent, on tire, on réécrit `has_pt_subscription`. Aucune régénération, applicable aux
populations existantes — et **contrairement au ticket 015, aucun ménage à reconstituer** :
le trait est individuel et toutes ses covariables sont déjà dans `traits_json`. C'est le
ticket le moins coûteux des trois.

**Voie 2 — cause racine dans le fork (ensuite).** Remplacer dans
[enriched.py](../../eqasim-toulouse/synthesis/population/enriched.py) la recopie
`has_pt_subscription` du donneur ENTD par l'imputation apprise. Coût : accès aux données
sources et régénération complète.

## Découpage en lots

1. **Lot 1 — le logit.** `P(abonné | âge, occupation, genre, motorisation, zone)` appris
   sur `P12`, validation croisée groupée par ménage, tables d'effectifs publiées.
2. **Lot 2 — voie 1.** Script de post-traitement, déterminisme par hachage, rapport de
   sortie avec les niveaux de repli et les huit tables de recette.
3. **Lot 3 — recette sur le jeu commun.** Re-prédiction de la politique et mesure du
   déplacement de part TC, par strate d'occupation et en agrégat.
4. **Lot 4 — voie 2.** Remontée dans le fork eqasim, pour qu'une génération neuve soit
   correcte sans post-traitement.

Les lots 1 et 2 sont **communs avec le [ticket 017](ticket_017_permis_progedo.md)** (permis
de conduire) : même fichier source, même restriction `PENQ = 1`, même pondération, même
cause (la classe d'âge 15-29), même patron de correction. Les traiter ensemble divise le
coût par deux ; les traiter séparément fait écrire deux fois le même chargeur.

## Sources

- Microdonnées **EMC² Toulouse 2023**, ProGEDO/ADISP `lil-1750`, fichier standard
  `pers` — variable `P12` « POSSESSION D'UN ABONNEMENT TC VALIDE HIER », pondération
  `COEP`, restriction `PENQ = 1`.
- Dictionnaire `Dico_Dessin_StandardV17_Corrige.xls`, onglet `Dico` : les six modalités de
  `P12`, dont deux seulement sont servies par ce fichier.
- Politique de choix modal du dépôt
  ([mode_choice_policy.json](../../scripts/progedo_logit/mode_choice_policy.json)) pour les
  effets marginaux moyens.
