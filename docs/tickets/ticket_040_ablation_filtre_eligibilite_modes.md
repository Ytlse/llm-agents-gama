# Ticket 040 — Mesurer ce que le filtre d'éligibilité porte dans le score

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité.
>
> **Décision de l'auteur du dépôt (2026-09-09)** : idée consignée, à traiter plus tard. Rien
> n'est lancé ; les mesures ci-dessous sont faites sur les runs déjà archivés et n'ont coûté
> aucun appel LLM.

## La question

Le plancher aléatoire donne un composite de **50,386**, le mode voiture seul **29,912**, et le
LLM à prompt minimal (`gemini-3.5-flash-lite`, température 0) **14,840**. Ce dernier chiffre
n'est pas imputable au seul modèle : entre l'offre d'itinéraires et ce que le modèle voit
passe un **filtre d'éligibilité** qui retire des modes (pas de vélo possédé, voiture garée
ailleurs, pas de permis, retour au domicile avec un véhicule à ramener). Un relecteur AAMAS
posera la question : combien des 35,5 points d'écart entre l'aléa et le LLM viennent du
modèle, et combien de la contrainte ?

## Ce que les traces disent déjà (mesuré le 2026-09-09)

Run de référence de la question : `exp_gemini-35-fl_minper_jtir_t0_nosim_2`, exécution
`2026-09-08_06_40_34` (2 693 déplacements, 2 637 décidés, 35 min, jeu
`population_1000_AAMAS_20260316`).

**1. Le filtre est actif, et il n'est pas marginal.** `synthese.json` du run porte
`ecartees_par_motif` :

| Motif | Options écartées |
|---|---|
| `plafond` (cap à 6 candidats) | 1 661 |
| `non_possede` | 1 530 |
| `vehicule_ailleurs` | 840 |
| `retour_force` | 776 |
| `pas_de_conducteur` | 69 |

Relu par déplacement (relecture de `decisions.jsonl`) : **69,6 % des déplacements subissent au
moins un écart hors-plafond**, et une catégorie modale entière disparaît de ce que le modèle a
sous les yeux dans :

| Catégorie retirée de l'offre présentée | Déplacements | Part |
|---|---|---|
| Vélo | 1 723 | 64,0 % |
| Voiture | 727 | 27,0 % |
| Marche | 194 | 7,2 % |
| Transports collectifs | 124 | 4,6 % |

Marche et TC ne sont jamais écartés par le verrou de sortie (D2) : leurs 318 disparitions sont
toutes des `retour_force`.

**2. Le plafond à 6 est innocent.** Les deux décomptes ci-dessus sont **identiques** qu'on
compte le plafond ou non : sur ce run, `_select_candidates` n'a jamais supprimé une catégorie
entière — la passe de priorité (le plus rapide de chaque groupe d'abord) fait son travail. Le
plafond sort donc du périmètre de l'ablation.

**3. Tous les bras portent le même filtre.** `non_possede` = 1 530 et `pas_de_conducteur` = 69
à l'identique sur `exp_alea_nosim`, `exp_majvoiture_nosim`, `exp_durmin_nosim`,
`exp_lgbm_jtir_nosim`, `exp_gemini-31-fl_minper…` et le run ci-dessus (ces deux motifs ne
dépendent pas des choix passés). `vehicule_ailleurs` et `retour_force` varient d'un bras à
l'autre parce qu'ils sont **endogènes** : ils dépendent du mode retenu au déplacement
précédent. La comparaison 50,386 → 29,912 → 14,840 est donc interne cohérente ; ce qu'elle ne
dit pas, c'est ce que le trio deviendrait filtre coupé.

**4. L'ordre de grandeur en jeu.** Taux de choix **conditionnel à l'offre** sur ce run :

| Mode | Offert sur | Choisi | Taux si offert |
|---|---|---|---|
| Voiture | 1 902 | 1 196 | 62,9 % |
| Transports collectifs | 1 841 | 777 | 42,2 % |
| Marche | 2 246 | 440 | 19,6 % |
| Vélo | 868 | 224 | 25,8 % |

Le vélo pèse déjà **8,49 %** de part modale contre une cible EMC² de **4,12 %** (`gaps` du
scoring : vélo +4,37 pp, TC +16,40, voiture −11,81, marche −8,97). Or il est bloqué sur 64 %
des déplacements. Une projection grossière — vélo offert partout, au même taux conditionnel —
le mettrait à ~26 %, soit six fois la cible. La projection est un **majorant** (le vélo est
offert surtout sur les trajets courts, la sélection est endogène), mais elle suffit à dire que
le filtre porte plusieurs points de composite.

## Ce qu'il faut faire

### La forme du plan expérimental : un 2×2, pas un run isolé

Lancer le seul bras « LLM sans filtre » ne se lit pas : si le composite passe de 14,84 à 22,
on ne sait pas si le modèle a perdu 7 points de qualité ou si la tâche est devenue plus dure
pour tout le monde. Il faut le plancher aléatoire dans la même condition :

|  | Filtre actif | Filtre coupé |
|---|---|---|
| Aléa uniforme | 50,386 (fait) | **à lancer** — gratuit |
| Majorité voiture | 29,912 (fait) | **à lancer** — gratuit |
| Durée minimale | 29,689 (fait) | **à lancer** — gratuit |
| LLM prompt minimal (gemini-3.5-fl) | 14,840 (fait) | **à lancer** — un run LLM |

Ce qui se publie : les deux effets principaux **et l'interaction**. C'est l'interaction qui
répond à la question posée — si l'écart LLM–aléa se conserve filtre coupé, le gain du modèle
ne vient pas de la contrainte ; s'il se réduit, il faut le dire et le chiffrer. Contraste
apparié sur les mêmes agents et les mêmes déplacements (McNemar, comme
`PROTOCOLE_SCIENTIFIQUE` le prévoit déjà pour les phases 4 et 5), IC par bootstrap de grappes
sur l'agent.

### Lot 1 — palier « conventions de modélisation » (aucun code)

Couper **position du véhicule** (`vehicule_ailleurs`) et **verrou de retour**
(`retour_force`) : ce sont des hypothèses de modélisation ajoutées par le ticket 008, pas des
données. C'est le palier qui mesure l'effet d'une règle rigide au sens propre.

- `VEHICLE_CHAIN_ENABLED=false` — vérifié le 2026-09-09 : la variable est bien lue par
  `AgentConfig` (`llm-agents/settings.py:514`), aucun préfixe à mettre.
- `VEHICLE_RETURN_HOME_LOCK=false` — drapeau distinct, à couper aussi (le premier le
  court-circuite déjà, mais l'expliciter évite un run ambigu).
- Reste actif dans ce palier : possession, permis/âge, plafond, filtres d'offre en amont.

### Lot 2 — palier « attributs de la population » (une modification)

Couper en plus **possession** (`non_possede`) et **permis/âge** (`pas_de_conducteur`).
Attention à ce que ce palier signifie : ces deux motifs ne sont pas des heuristiques, ce sont
des **attributs de la cohorte scellée** issus de l'enquête (`personal_bike`,
`number_of_cars`, `has_driving_license`, âge). Les couper ne retire pas une règle, ça donne un
vélo à des gens qui n'en ont pas et une voiture à des mineurs. Le run reste informatif — il
donne le **plafond** de ce que le filtre porte — mais il doit être étiqueté comme tel dans le
papier, jamais présenté comme la condition « sans règle rigide ».

Ce palier demande du code : dans `_vehicle_unavailable_reason`
(`llm-agents/urban_mobility_agents/vehicle_chain.py:237`), possession et permis sont testés
**avant** le garde-fou `if not settings.agent.vehicle_chain_enabled`. Rien ne les désactive
aujourd'hui. Il faut un drapeau propre et nommé (pas un détournement de
`vehicle_chain_enabled`), et il doit être visible dans les métadonnées du run (lot 3).

### Lot 3 — tracer l'état des filtres dans l'archive (prérequis des lots 1 et 2)

**L'état des filtres n'est enregistré nulle part** : ni dans `experience.yaml`, ni dans
`regime_applique` / `empreintes` de `synthese.json`, ni dans le nom canonique calculé par
`experiences/nommage.py`. Deux bras de cette ablation seraient aujourd'hui **indistinguables
dans l'archive**, sauf à relire les compteurs d'écarts pour deviner ce qui tournait. À
livrer avant les runs :

- la configuration des filtres entre dans `experience.yaml` et dans les empreintes de
  `synthese.json` (elle fait partie de ce qui rend un run reproductible) ;
- elle entre dans le nom canonique, de sorte que le bras d'ablation vive dans son propre
  dossier `data/experiences/` (cf. spec `nommage-canonique-experiences`) ;
- `docs/arch/vehicle-chain.md` cite les drapeaux et dit ce que chacun coupe.

## Ce qui rend l'expérience bon marché

L'offre gelée du jeu est calculée avec `include_car=True, include_bike=True` **pour tout le
monde** (`llm-agents/experiences/jeu.py:406`) : l'offre brute enregistrée est déjà
mode-neutre, et tout le filtrage agent est un **post-filtre** appliqué à la décision
(`experiences/decision.py:126`). Donc :

- **aucun recalcul OTP/OSMnx** — le jeu `population_1000_AAMAS_20260316` se réutilise tel
  quel, ce qui rend les deux bras strictement comparables (même offre, filtre en moins) ;
- les trois bras heuristiques ne coûtent **rien** (pas d'appel LLM) ;
- le bras LLM recoûte ~2 048 sollicitations, soit ~100–250 requêtes selon le lotissement :
  très en dessous des 500 RPD de la clé, et ~35 min d'horloge d'après le run de référence.

Le prompt change (plus d'options présentées), donc les décisions doivent être **re-sollicitées** :
le cache de décisions ne peut pas resservir, et c'est voulu.

## Pour mémoire : la carte complète des filtres, par étage

Établie le 2026-09-09, à recopier dans la section « environnement » du papier — la question
« quels filtres sont actifs ? » revient à chaque relecture.

**A. En amont, dans l'offre gelée (le jeu)** — appliqués une fois, identiques pour tous les bras :
- TC non calculés si aucun arrêt à ≤ 1 500 m du départ **ou** de l'arrivée
  (`llm-agents/handle/application.py:284`) ;
- coupures de distance à vol d'oiseau : **marche > 15 km**, **vélo > 30 km**, aucun itinéraire
  produit (`llm-agents/trip_helper/osmnx_direct.py:373`). Ce sont des coupures **techniques**
  de routage, pas une règle de comportement, et elles mordent peu : distance parcourue médiane
  4,81 km, p90 19,07 km. Il n'existe **aucune** règle du type « pas de vélo si c'est trop
  loin » : le vélo reste offert quelle que soit la distance, et le plafond le protège même
  quand il est lent ;
- car scolaire synthétique : 5–17 ans + domicile hors ressort Tisséo + motif `education`
  (ticket 030).

**B. À la décision, par agent** (`experiences/decision.py` → `vehicle_chain.py`), dans cet ordre :
1. `non_possede` — pas de vélo (`personal_bike`), pas de voiture au ménage (`number_of_cars`) ;
2. `pas_de_conducteur` — permis **et** ≥ 18 ans ; sinon voiture offerte seulement en passager
   (ménage > 1) ;
3. `vehicule_ailleurs` — un véhicule est un lieu : non offert s'il n'est pas garé au départ ;
4. `retour_force` — retour au domicile de plus d'1 km avec un véhicule garé au départ ⇒
   options restreintes à ce mode ;
5. `plafond` — 6 candidats, le plus rapide de chaque groupe d'abord (marche / vélo / voiture /
   collectif / ferroviaire).

## Critères d'acceptation

1. `experience.yaml`, les empreintes de `synthese.json` et le nom canonique portent l'état des
   filtres ; deux runs qui ne diffèrent que par lui vivent dans deux dossiers distincts.
2. Le lot 1 tourne sur les quatre bras (aléa, majorité voiture, durée minimale, LLM minimal),
   sur le **même** jeu enregistré, sans recalcul d'offre — vérifié par le sha256 du jeu dans
   les empreintes des huit runs.
3. Le tableau 2×2 est publié avec IC (bootstrap de grappes sur l'agent, 1 000 rééchantillons)
   et l'interaction est chiffrée, pas seulement les effets principaux.
4. Le papier dit explicitement, pour chaque palier, ce qui est coupé et de quelle nature
   (convention de modélisation vs attribut d'enquête). Le lot 2 n'est jamais présenté comme
   « le run sans règle rigide ».
5. La carte des filtres par étage figure dans la section environnement du manuscrit.

## Ce que ce ticket ne fait pas

- Il ne relance rien : les mesures ci-dessus viennent des archives existantes.
- Il ne touche pas aux runs déjà archivés (un run archivé ne se modifie pas) ; l'ablation
  ajoute des bras, elle n'en remplace aucun.
- Il ne rend pas le filtre optionnel en production : le comportement par défaut reste
  filtre actif, conformément à la règle « pas de dégradation scientifique ».
