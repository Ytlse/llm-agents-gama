# Ticket 006 — Relance d'un run de référence : ce que la sur-représentation du vélo révèle

**Question posée** : faut-il relancer une simulation GAMA, notamment pour prendre en
compte la disponibilité du vélo ?

**Réponse courte** : oui, mais pas tout de suite, et pas pour la raison qu'on croit. Le
garde de possession du vélo **fonctionne déjà** dans le run épinglé. Une relance
récupérerait environ **5,9 des 14,7 points** d'excédent vélo — le reste est un biais de
choix de l'agent LLM, qu'aucune relance ne corrigera. Trois traits de population sont par
ailleurs en attente au même endroit : les produire tous avant de relancer évite de payer
deux fois des heures de simulation.

**Origine** : la page de synthèse (`docs/synthesis/index.html`, régénérée le 2026-07-31)
place le vélo à **18,8 %** de part modale contre **4,1 %** dans l'enquête EMC² 2023. C'est
le plus grand écart de tout le volet 1, devant le déficit de marche (−19,3).

**État** : constat établi et chiffré le 2026-07-31. Aucune correction engagée.

---

## 0 · Registre des décisions

### Décisions adoptées

| # | Décision | Détail |
|---|---|---|
| F1 | **Ne pas relancer immédiatement** | Une relance ne récupère que le vélo fantôme (§3). Payer des heures de simulation pour 5,9 points, puis les repayer quand les autres traits seront prêts, est un gaspillage évitable |
| F2 | **Grouper les traits de population avant relance** | Trois traits manquent au même endroit — génération de population (§5). Un seul run les absorbe tous |
| F3 | **Le vélo fantôme est un défaut réel, à committer** | Le correctif existe déjà en copie de travail et n'est pas commité (§3). Il doit l'être indépendamment de la décision de relance |
| F4 | **L'excédent résiduel est un problème de prompt, pas de disponibilité** | Il persiste dans toutes les tranches d'âge et de distance, y compris implausibles (§4) — il relève de la calibration, pas de l'offre |
| F5 | **`socioprofessional_class = "Retired"` reste manquant** | Remapper serait faux (§5.3). Le combler suppose que la population porte la profession *antérieure* du retraité |

### Décisions écartées (et pourquoi)

| Idée | Raison du rejet |
|---|---|
| Relancer tout de suite pour le vélo | Ne corrige que 40 % de l'écart, et il faudrait relancer à nouveau pour les autres traits (F1, F2) |
| Remapper `Retired` → `Other Inactive` | Dans l'enquête, les retraités portent leur profession antérieure ; « Other Inactive » n'en couvre que 1,8 % (§5.3) |
| Retirer le vélo de l'offre OTP pour réduire l'écart | Traiterait le symptôme en truquant le jeu de choix. L'agent doit apprendre à ne pas choisir le vélo, pas être empêché de le voir |
| Réviser la cible EMC² | La référence n'est pas en cause : 4,1 % est la part vélo mesurée sur l'agglomération toulousaine |

---

## 1 · Le constat

Sur le run épinglé `experiments/archive/2026-07-29_18_34` (5 945 trajets, 881 personnes) :

| Mode | Simulé | Cible EMC² | Écart |
|---|---|---|---|
| Marche | 7,5 | 26,8 | **−19,3** |
| Voiture | 52,4 | 56,7 | −4,3 |
| **Vélo** | **18,8** | **4,1** | **+14,7** |
| Transports collectifs | 21,3 | 12,4 | +9,0 |

Le vélo est le premier contributeur à l'écart, et il domine les « pires croisements » de la
page : Homme × Vélo à 22,7 % contre 5,3 % attendus (n=440), soit le cinquième plus fort
impact toutes dimensions confondues.

---

## 2 · Ce qui fonctionne déjà — le garde de possession

**À ne pas refaire** : la possession du vélo est déjà instrumentée et déjà appliquée dans
le run épinglé. Vérifié sur les données, pas sur le code.

Le trait `personal_bike` est présent sur les **930 personas** de la population, avec trois
modalités :

| `personal_bike` | Personas | Part |
|---|---|---|
| Pas de vélo | 432 | 46,5 % |
| vélo normal | 425 | 45,7 % |
| VAE | 73 | 7,8 % |

Et le filtrage est effectif dans le run :

| | Trajets | dont à vélo |
|---|---|---|
| Personas **avec** vélo | 3 266 | 1 086 (33,3 %) |
| Personas **sans** vélo | 2 813 | **0** (0,0 %) |

Aucun persona sans vélo n'a fait un trajet à vélo. La version commitée de
`simulation_controller.py` portait déjà :

```python
include_bike = (person.identity.traits_json.get("personal_bike", "vélo normal").lower() != "pas de vélo")
```

**Conséquence** : l'excédent de vélo n'est pas dû à des vélos attribués à des gens qui n'en
ont pas. Il est **entièrement concentré sur les 53,5 % de personas qui en possèdent un**, et
il y atteint 33,3 % des trajets.

---

## 3 · Ce qui manque au run épinglé — le vélo fantôme

Une seconde condition existe en **copie de travail, non commitée**, et elle est
**postérieure au run**.

| Élément | Horodatage |
|---|---|
| `moves.csv` du run épinglé | 2026-07-29 22:56 |
| `simulation_controller.py` (copie de travail) | 2026-07-30 14:22 |
| État git du fichier | `M` — modifié, **jamais commité** (`git log -S "planning_vehicle_at"` : aucun résultat) |

Le correctif ajoute la notion de « vélo en main » :

```python
def _bike_available(traits: dict, bike_in_hand: bool) -> bool:
    """Le vélo peut-il être proposé comme option pour ce trajet ?

    Deux conditions, et pas seulement la possession : l'agent doit aussi avoir son vélo
    **là où il se trouve**. Sans la seconde, un agent parti travailler en bus retrouvait
    son vélo pour repartir — sur un run de référence, 352 des 1086 trajets à vélo (5,9
    points de part modale) reposaient sur ce vélo fantôme.
    """
    return _owns_bike(traits) and bike_in_hand
```

**Le « run de référence » de cette docstring est le run épinglé** : il compte exactement
1 086 trajets à vélo (§2), le même nombre. Le chiffre de 5,9 points s'applique donc
directement.

> **Mise à jour (2026-07-31).** La limite du booléen — un agent qui va au travail à vélo
> puis rentre en bus « récupérait » son vélo au domicile alors qu'il l'a laissé au travail
> — est levée : le booléen est devenu une **position** (`planning_vehicle_at`), étendue à
> la voiture, avec verrou de retour au domicile. Le code ci-dessus est celui de l'état
> analysé ici, conservé tel quel ; l'état courant est décrit dans
> [../arch/vehicle-chain.md](../arch/vehicle-chain.md). L'estimation de 5,9 points reste
> valable — elle porte sur la seule condition de disponibilité du vélo.

---

## 4 · Ce qu'une relance corrigerait — et ce qu'elle ne corrigerait pas

| | Part vélo | Écart à EMC² |
|---|---|---|
| Run épinglé, tel quel | 18,8 % | +14,7 |
| Après correctif vélo fantôme (estimation) | ~12,9 % | **+8,8** |
| Cible EMC² | 4,1 % | — |

Une relance récupère donc **40 % de l'écart**. Les 8,8 points restants ne relèvent pas de la
disponibilité, et la ventilation le montre sans ambiguïté : **l'excédent est présent dans
toutes les tranches, y compris celles où le vélo est implausible.**

| Distance | Simulé | Cible | Écart |
|---|---|---|---|
| 0-1 km | 18,8 | 3,0 | +15,8 |
| 1-2 km | 25,8 | 6,1 | +19,6 |
| 2-5 km | 21,6 | 7,2 | +14,4 |
| 5-10 km | 17,9 | 4,1 | +13,8 |
| 10-20 km | 13,8 | 2,1 | +11,7 |
| **20-50 km** | **6,9** | **1,1** | **+5,9** |

| Âge | Simulé | Cible | Écart |
|---|---|---|---|
| **5-9 ans** | **23,3** | **3,1** | **+20,3** |
| 20-24 ans | 32,4 | 4,1 | +28,3 |
| 25-29 ans | 28,5 | 4,2 | +24,3 |
| 50-54 ans | 21,5 | 5,2 | +16,3 |
| **75 ans et plus** | **11,3** | **2,0** | **+9,2** |

Des enfants de 5 à 9 ans à 23 % de vélo, des plus de 75 ans à 11 %, des trajets de 20 à
50 km à 6,9 % : ce n'est pas un problème d'offre, c'est un biais de préférence de l'agent
LLM dès que le vélo figure dans le jeu de choix. **Relever cet excédent relève de la
calibration de prompt (volet 2), pas d'une relance.**

À rapprocher du volet 3 : le modèle PROGEDO, sur le même run, place le vélo à 6,5 % après
renormalisation OTP, pour 4,1 % attendus. Un modèle statistique sans aucune notion de
« vélo en main » fait donc **déjà quatre fois mieux** que l'agent LLM sur cette dimension.

---

## 5 · Les autres traits en attente au même endroit

C'est l'argument central en faveur du groupement (F2). Trois traits manquent tous à la
**génération de population**, et chacun exige un nouveau run pour produire son effet.

### 5.1 Type de logement — prêt, en attente de run

Livré par l'action A2 : le trait est produit et journalisé, imputé conditionnellement à la
zone fine du domicile via le résolveur de l'action A7, déterministe (hachage SHA-256 de
l'adresse, pas d'un RNG, pour que deux personas d'un même foyer ne se retrouvent pas l'un
en maison et l'autre en tour). Distribution à 2,9 points L1 de la loi de l'enquête.

Outillage : `make housing-type` puis
`python -m scripts.data.population.enrich_housing_type <population.json>`.

**L'axe « Type de logement » de la page restera à zéro jusqu'au prochain run épinglé** — le
`moves.csv` actuel porte la colonne vide et la page la relit telle quelle.

### 5.2 Hypercentre — appliqué aux runs futurs seulement

Livré par l'action A9 : `feature_spec.json` fait autorité (43,597347 / 1,444997), lu via
`llm_module/core/geo_reference.py`. L'ancienne constante en dur était à 820 m de là.

Les couronnes de résidence sont calculées **à la journalisation** puis relues telles quelles
par la page. Le run épinglé porte donc encore les couronnes de l'ancien centre.

### 5.3 Profession antérieure des retraités — non résolu

`socioprofessional_class = "Retired"` est porté par **151 personas sur 930 (16,2 %)** et ne
correspond à aucune modalité du contrat du modèle. Il devient donc manquant (NaN), que
LightGBM traite nativement.

Le réflexe — remapper vers `Other Inactive` — est **faux**. Dans le jeu d'entraînement, la
variable `PCSC` encode la profession *exercée avant la retraite* :

| `socioprofessional_class` des retraités (6 754 déplacements) | |
|---|---|
| Employee | 2 094 |
| Executive or Higher Intellectual Professional | 1 783 |
| Intermediate Professional | 1 542 |
| Manual Worker | 670 |
| Craftsperson or Shop Owner | 469 |
| **Other Inactive** | **122** (1,8 %) |
| Farmer | 74 |

Remapper verserait 16,2 % des personas dans une modalité qui n'en couvre réellement que
1,8 %, et effacerait le signal socio-économique — un cadre retraité et un ouvrier retraité
ne se déplacent pas de la même façon.

**Combler proprement suppose que la population synthétique porte la profession antérieure
de ses retraités.** À vérifier côté eqasim. Si la donnée n'existe pas, le manquant est
définitif et c'est le bon comportement.

---

## 6 · Coût d'une relance

Épingler un nouveau run ne se limite pas à la simulation : le run est le substrat commun
des trois volets de la page.

| Action | Effet d'un changement de run | Coût |
|---|---|---|
| Volet 1 (simulation) | Recalculé intégralement | gratuit (`make synthesis`) |
| **A3** — calibration sur jeu commun | **À refaire** : l'échantillon est tiré du run épinglé | **128 appels LLM** (~20 min) |
| **A8** — prédictions du modèle | À refaire, purement local | gratuit (`make common-set-predict`) |
| A2 — type de logement | Se remplit enfin | gratuit |
| A9 — hypercentre | S'applique enfin aux couronnes | gratuit |
| A4 — jeu de test gelé | **Non concernée** — jeux gelés indépendants du run | — |
| A10 / A5 — lignée | **Non concernées** | — |

Rappel quota : free tier Google, RPD 500 par projet et par modèle, réinitialisation à
**minuit Pacific (07:00 UTC)** — et non minuit UTC. Deux clés, seaux distincts.

---

## 7 · Recommandation — phasage

**Phase 1 — sans relance** (aucune heure de simulation)
1. Committer le correctif du vélo fantôme, aujourd'hui en copie de travail non commitée (F3).
2. Trancher §5.3 : eqasim peut-il fournir la profession antérieure des retraités ?
3. Instrumenter le trait de possession de vélo *si* on veut le raffiner — l'enquête porte
   `M21` (nombre de vélos du ménage), déjà utilisé à l'entraînement pour `has_bike`. La
   machinerie d'imputation par zone fine d'A2 (`export_housing_type` + `enrich_housing_type`)
   est directement transposable. **Optionnel** : la distribution actuelle (53,5 % de
   possesseurs) est plausible et n'est pas la cause de l'écart.

**Phase 2 — relance unique**
4. Enrichir la population avec tous les traits prêts (type de logement, et le reste de
   la phase 1 si livré).
5. Lancer le run, l'archiver, l'épingler dans `scripts/synthesis/sources.yaml`.
6. `make common-set-predict` (gratuit), `make common-set-eval` (128 appels), `make synthesis`.

**Phase 3 — l'excédent résiduel**
7. Les ~8,8 points de vélo restants sont un objet de calibration de prompt. À traiter
   comme tel, avec l'avertissement du ticket 004 en tête : à substrat et effectif égaux, la
   calibration actuelle est **moins fidèle** à l'enquête que la simulation nue (36,4 contre
   29,4 sur le jeu commun).

---

## 8 · Critères d'acceptation

À vérifier sur le run relancé, avant de l'épingler :

- [ ] **Vélo fantôme éteint** : aucun trajet à vélo dont le trajet précédent n'était ni à
      vélo ni un retour au domicile. Attendu : part vélo ~12,9 % au lieu de 18,8 %.
- [ ] **Possession respectée** : 0 trajet à vélo parmi les personas `personal_bike = "Pas de
      vélo"` — c'est déjà le cas, c'est une non-régression.
- [ ] **Type de logement renseigné** : les quatre modalités EMC² peuplées dans `moves.csv`,
      l'axe de la page non nul. Résiduel attendu hors couche : ~4,4 % de personas sans trait,
      colonne vide (rien n'est deviné).
- [ ] **Couronnes recalculées** sur l'hypercentre unifié (43,597347 / 1,444997).
- [ ] `make synthesis` : 13 sources présentes, 0 manquante.
- [ ] Suite de tests verte (référence actuelle : **614 passed**).

---

## Annexe — commandes

```bash
make housing-type        # loi du type de logement par zone fine (données PROGEDO requises)
make zones               # couche de zones fines du résolveur
make policy              # ré-entraîne la politique PROGEDO (parquet versionné, pas de données brutes)
make common-set-predict  # volet 3 sur le jeu commun (local, gratuit)
make common-set-eval     # volet 2 sur le jeu commun (128 appels LLM — DRY_RUN=1 pour chiffrer)
make heldout-eval        # volet 2 sur le jeu de test gelé
make synthesis           # régénère la page
```

## Voir aussi

- `docs/arch/score-synthesis.md` — définition du score et des trois volets
- `docs/tickets/ticket_005_mode_choice_model.md` — politique PROGEDO (volet 3)
- `docs/tickets/ticket_004_prompt_calibration_industrialisation.md` — calibration (volet 2)
- `docs/changelog.md` — actions A1 à A10
