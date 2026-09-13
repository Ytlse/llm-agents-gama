# Ticket 022 — Le rabattement voiture + transports collectifs : une cible en partie hors d'atteinte

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité.
>
> **Nature du ticket** : *correction et neutralisation*. Il traite l'axe **A7** du
> [ticket 020](ticket_020_perimetre_population_cerema.md), qui portait le verdict
> « à publier ». La mesure par strate faite pour ce ticket-ci le rend **plus grave que le
> chiffre global ne le disait**, et donc plus urgent qu'« à publier ».
>
> Le ticket a deux moitiés, et il faut les tenir séparées : une **correction de code de
> trois lignes** qui ne coûte rien, et une **neutralisation dans le scoring** qui passe
> par un post-traitement de la population. Faire le rendu du parcours-relais dans le
> calculateur d'itinéraires n'est *pas* dans ce ticket.

## Le problème, en deux mécanismes distincts

### M1 — La hiérarchie de mode principal est inversée (correction de code, latente)

Un déplacement mêlant plusieurs modes reçoit **un** mode principal, des deux côtés. Mais
pas le même.

[`move_logger._plan_transport_mode`](../../llm-agents/urban_mobility_agents/utils/move_logger.py)
teste la **voiture d'abord** :

```
if modes & _CAR_MODES:      return "Voiture Privée"
if modes & _BUS_MODES:      return "Transports_collectifs"
```

L'enquête fait l'inverse. Sur ses **770 déplacements** mêlant un trajet voiture et un
trajet en transports collectifs, **760 sont codés « transports collectifs »** et 10
seulement « voiture ».

Cette divergence ne coûte **rien aujourd'hui** : OTP est interrogé mode par mode, donc
aucun itinéraire simulé ne mêle les deux. Vérifié sur les combinaisons de jambes du run
courant — `car` et `foot,bus,foot` n'apparaissent jamais dans le même plan, et **zéro
déplacement est mal classé**. C'est une bombe à retardement, pas un bug actif : le jour où
un itinéraire mixte apparaît, le classement bascule en silence.

#### M1 a explosé le 2026-09-03 — pas sur la voiture, sur le car et le train

*Constat chiffré, déposé le 2026-09-04. Aucune décision prise : la hiérarchie des modes
reste l'objet de ce ticket. Ce qui suit remplace l'intuition par des nombres.*

L'itinéraire mixte que M1 attendait est arrivé. Pas `car` + `bus` — OTP est toujours
interrogé mode par mode pour la voiture — mais **`bus` + `rail`** : depuis l'entrée du TER
et des 309 lignes d'autocar liO dans le graphe OTP (ticket 031, q. 16), un même itinéraire
porte couramment une jambe d'autocar ou de bus **et** une jambe de train. Or la cascade
teste `_BUS_MODES` **avant** `_RAIL_MODES` :

```
if modes & _CAR_MODES:      return "Voiture Privée"
if modes & _BUS_MODES:      return "Transports_collectifs"   ← gagne
if modes & _RAIL_MODES:     return "Train"                   ← n'est jamais atteint
```

**Mesure** (sonde OTP du 2026-09-04, mêmes conditions que le ticket 031 q. 16 : population
`population_1000_AAMAS_v4`, lundi 16 mars 2026 8 h, six candidats par trajet, 2 580 points
→ 11 288 itinéraires ; rejeu `docs/traces/2026-09-04_09-10_rail_categorisation_et_gama/`) :

| | Itinéraires | Part de l'offre |
|---|---:|---:|
| Itinéraires portant un train | 1 883 | 16,7 % |
| dont **train + bus/car** → classés « Transports_collectifs » | **1 177** | **62,5 % de l'offre rail** |
| dont train seul → classés « Train » | 706 | 37,5 % de l'offre rail |
| **Total classé « Train » par l'ordre actuel** | **706** | 6,3 % des itinéraires |
| **Total classé « Train » par la hiérarchie (train d'abord)** | **1 883** | 16,7 % des itinéraires |

Par couronne de résidence, la part de l'offre rail que l'ordre actuel masque :

| Couronne | Itinéraires avec train | dont train + bus | Part masquée |
|---|---:|---:|---:|
| Toulouse | 73 | 45 | 61,6 % |
| 1ʳᵉ couronne | 1 215 | 838 | **69,0 %** |
| 2ᵉ couronne | 351 | 223 | 63,5 % |
| 3ᵉ couronne | 244 | 71 | 29,1 % |

Les seules combinaisons observées sont `rail` seul (706), `bus+rail` (751), `bus+metro+rail`
(263) et `metro+rail` (163) — **aucun** itinéraire ne mêle `car` et un mode collectif, donc
le M1 d'origine (voiture avant TC) reste bien latent.

#### L'ARBITRAGE, rendu le 2026-09-04 : la hiérarchie du dépôt est celle de l'enquête

*Décision de l'auteur du dépôt : « l'ordre des tests décide du mode principal : sur ce point
il faut s'aligner à l'enquête ». Ce qui suit est cet alignement, livré. Trace :
[`docs/traces/2026-09-04_10-17_hierarchie_modes_enquete/`](../traces/2026-09-04_10-17_hierarchie_modes_enquete/README.md).*

**Il n'y avait rien à postuler : l'ordre est publié.** Le rapport AUAT/CEREMA de l'enquête
donne en annexe, **page 53** (« Hiérarchie des modes »), les **36 modes enquêtés dans
l'ordre** — celui qui, dit le même rapport p. 12, « découle d'une hiérarchisation des modes
définie au niveau national ». Le paragraphe ci-dessus cherchait une convention ; c'était une
citation.

Ramené au vocabulaire des jambes de la simulation :

| Rang | Famille | Rangs publiés | Libellé `moves.csv` | Cran mesuré sur les microdonnées |
|---:|---|---|---|---|
| 1 | `metro` | 1 | Transports_collectifs | bat tout, 0 exception sur ~2 000 obs. |
| 2 | `tram` | 2 | Transports_collectifs | bat bus (62–0), car (20–0), rail (6–0) |
| 3 | `cableway` | 3 (Téléo) | Transports_collectifs | bat bus (12–0), car (3–0) ; **vs tram : non tranché** (1 déplacement), rang pris à l'annexe |
| 4 | `bus` | 4 bus/navette, 5 TAD, 6 autocars liO **et scolaires**, 7 TAD régional | Transports_collectifs | bat **rail (34–1)**, car (185–0), vélo (15–0) |
| 5 | `rail` | 8 TER, 9 TGV, 10 autre TER, 11 Intercités | Train | bat car (58–0), vélo (15–0), 2RM (2–0) |
| 6 | `car` | 14-15 taxi/VTC, 16-17 fourgon, 19-20 VP | Voiture Privée | bat vélo (24–0), 2RM (2–0) |
| 7 | `motorbike` | 21-22 | Deux-roues motorisé | bat vélo (2–0) ; effectifs minces, rang confirmé par l'annexe |
| 8 | `bicycle` | 23-29 | Vélo | perd contre tous les rangs ci-dessus |
| 9 | `foot` | 36 « Marche à pied UNIQUEMENT » | Marche | **résidu mesuré** : `MODP = 01` ⇔ aucun trajet mécanisé (14 842 / 54 585, et 0 des 39 743 détaillés) |

Rangs publiés **volontairement non importés**, faute de contrepartie dans la simulation :
12 cars longue distance (Flixbus — hors graphe), 13 transport d'employeur, 18 autres modes,
30-32 EDPM/roller/fauteuil, **33 « autre réseau urbain »**, 34 fluvial, 35 avion. Le rang 33
mérite d'être signalé : il est **sous la voiture** (mesuré, 10 obs. sur 10), ce qui ferait
un contresens si on l'importait dans la famille `bus`.

**Le contrôle, généralisé depuis A7.** Pour chaque paire de modes co-présents dans un même
déplacement de l'enquête, quel mode `MODP` retient-elle ? 39 743 déplacements détaillés,
2 281 mixtes, **2 607 observations informatives**, **53 paires de codes tranchées** (seuil :
3 observations concordantes), **53 conformes sur 53**. Une seule observation à contre-courant
— et elle est *conforme à l'annexe* : un `Flixbus + TER` codé TER, le Flixbus étant au rang
12, sous le TER. 70 paires restent non tranchées faute d'effectif ; leur rang vient de
l'annexe seule, et la ressource gelée le dit paire par paire.

**Réponse aux deux questions ouvertes du paragraphe précédent :**

1. **Un déplacement mixte car/bus + train est un déplacement en BUS.** Rangs 4 et 8 ;
   mesuré 34 sur 35. Le constat « la colonne Train de `moves.csv` sous-compte le rail de
   62,5 % » **s'inverse** : les 1 177 itinéraires concernés sont *correctement* étiquetés
   `Transports_collectifs`. L'ordre `_BUS_MODES` avant `_RAIL_MODES` était conforme ;
   c'étaient `mode_choice` et `task_worker`, qui testaient le train **en tête**, qui
   divergeaient de l'enquête.
2. **La séparation TER / TC urbain des parts modales publiées n'est pas une hiérarchie.**
   Le rapport publie le TER à part (≈ 10 % contre 24 % Tisséo) parce que c'est une lecture
   par *réseau exploitant*, pas par mode principal — la même annexe p. 53 range les rangs
   1 à 13 sous un seul libellé, « transports en commun », train compris.

**La correction du tableau « quatre tables, trois réponses ».** Trois des quatre lignes
étaient fautives, mais pas celles annoncées :

| Table | Verdict pour car liO + TER | Conforme à l'enquête ? |
|---|---|---|
| `move_logger._plan_transport_mode` | `Transports_collectifs` | ✅ sur le train — ❌ sur la **voiture testée en premier** |
| `mode_choice.canonical_mode` | `train` | ❌ le train était testé avant le collectif |
| `task_worker._extract_primary_mode` | `train` | ❌ idem |
| `simulation_controller._primary_mode` | `transit` | ✅ — ce sont les 4 catégories agrégées de l'enquête, où le train EST dans les TC. Fautif seulement sur la **voiture testée en premier** et sur `transit` comme **défaut muet** |

Et **Grafana 07 ne compare pas quatre modes à cinq** : le `label_replace` mappe
`public_transport|train → tc` d'un côté, `transit → tc` de l'autre. Les deux séries sont
ramenées aux mêmes quatre catégories EMC². Cette phrase du paragraphe précédent est à
retirer, pas à corriger.

**Ce qui est livré** (lot 1, plus la moitié de C7) :

- `llm_module/data/mode_hierarchy_emc2.json` — la hiérarchie **gelée**, avec sa provenance
  (empreintes SHA-256 des deux fichiers de microdonnées, effectifs, date), les 36 rangs
  publiés, la matrice complète des paires et les contrôles ;
- `scripts/progedo_logit/export_mode_hierarchy.py` — l'export qui la produit et son
  `--check` ;
- `llm_module/core/mode_hierarchy.py` — **le seul endroit** où l'ordre est lu. Une famille
  manquante, une version inattendue ou une ressource absente lèvent ; un mode inconnu rend
  `None`, jamais le fourre-tout d'à côté ;
- `move_logger` : les cinq listes littérales sont devenues des **vues** de la hiérarchie, la
  cascade de `if` a disparu, et un mode hors hiérarchie lève une `[ALARME]` sur front
  montant au lieu d'aller muettement dans « Autres modes » (qui est **exclu** du scoring) ;
- `mode_choice` : la cascade est réordonnée et son ordre est **vérifié à l'import** contre la
  ressource ;
- `task_worker` : suit la hiérarchie ; le Téléo et le car scolaire cessent de tomber dans
  `other` **avec un `logger.error` à chaque décision** ;
- `simulation_controller` : `_primary_mode` (hiérarchie, métrique, regroupement) est séparé
  de **`_vehicle_mode`** (chaîne de véhicules) — voir ci-dessous ;
- tests : `llm_module/tests/test_mode_hierarchy.py` (22), `llm-agents/tests/test_hierarchie_modes.py`
  (19), et les deux tests de parité étendus pour lire la **ressource de production** au lieu
  d'un littéral.

**La distinction qui manquait, et qui est la moitié du problème.** Un mode principal et un
mode de véhicule sont deux grandeurs différentes. La chaîne du ticket 008 demande « où est la
voiture », pas « quel est le mode principal » : sur un rabattement, l'enquête classe le
déplacement en TC *et* la voiture doit être garée à destination. `_primary_mode` servait les
deux usages — le jour où un itinéraire mixte apparaît, aligner la hiérarchie aurait fait
**perdre la voiture au verrou de retour**. Les deux lectures sont désormais distinctes, et un
test vérifie qu'elles divergent bien sur un plan `car + bus`.

**Effet chiffré AVANT application** (versions « avant » extraites par `git show`, jamais
recopiées ; six témoins vérifient que le rejeu reproduit le comportement d'avant avant de
conclure) :

| Table | Jeux gelés (385 888 occ.) | Décisions en cache (444 055) | Run `2026-09-04_01_09` (17 258) |
|---|---|---|---|
| `_plan_transport_mode` — colonne du scoring EMC² | **0** | **0** | **0** |
| `canonical_mode` — colonnes `P(...) %` | **0** | **0** | **0** |
| `_primary_mode` — `trip_mode_by_purpose_total` | 0 | 1 libellé / 10 occ. *(artefact de mesure)* | **0** |
| `_extract_primary_mode` — compteurs de diagnostic | 17 / 686 (0,18 %) | 7 / 145 (0,03 %) | 10 / 150 (0,87 %) |

**Le critère C2 est donc vérifié par la mesure, et non par argument** : rejouer le run
archivé donne exactement les mêmes libellés de mode sur les 17 258 options que les agents ont
vues ; le plafond de 6 reste atteint dans 44,7 % des décisions et la distribution des modes
distincts offerts (22,6 / 28,6 / 35,1 / 13,7 %) est inchangée. **Aucun résultat publié ne
bouge.** Aucun libellé des trois corpus ne contient `rail`, `train` ni `ter` : le cran
bus/train n'a aucun effet rétroactif.

**Ce qui n'est PAS livré, et pourquoi.** `_select_candidates` groupe les candidats par
`_primary_mode` : un train pur et un bus + train partagent donc l'unique créneau `transit`,
et le plus rapide des deux l'occupe. Sur les 440 points où une option de train pur existe,
**122 (27,7 %)** sont écartés au profit d'un bus + train plus rapide, et le train ne s'offre
jamais comme choix distinct à l'agent. De même, `numTripPatterns = 6` prive 45 points d'une
option ferroviaire qu'un `20` leur rendrait. Les deux corrections **changent le prompt**,
donc les décisions et le cache : elles restent des décisions de l'auteur.

**Quatre tables, trois réponses, pour le même trajet.** C'est la forme la plus nette du
problème :

| Table | Verdict pour un trajet car liO + TER |
|---|---|
| `move_logger._plan_transport_mode` (colonne « Mode de transport Choisi ») | `Transports_collectifs` |
| `mode_choice.canonical_mode` (répartition `P(...)`) | `train` |
| `task_worker._extract_primary_mode` (priorité déclarée train > métro > tram > bus) | `train` |
| `simulation_controller._primary_mode` (métrique `trip_mode_by_purpose_total`) | `transit` — il n'émet JAMAIS `train` |

Conséquences directement lisibles, à ne pas confondre avec le scoring EMC² : la colonne
« Train » de `moves.csv` sous-compte de **62,5 %** l'usage du rail, et le graphe d'écart de
Grafana 07 (`trip_mode_by_purpose_total` vs `llm_mode_probability_pct_total`) compare une
base à **quatre** modes à une base à **cinq**. Le scoring EMC², lui, est indifférent :
`frames.CHOSEN_MODE_MAP["Train"]` et `CANONICAL_TO_CAT["train"]` fusionnent tous deux le
train dans `transports_collectifs`, et la référence du dépôt ne publie pas de part « train »
distincte. **Ce constat ne change donc aucune part modale publiée** — il change ce que le
journal permet de lire.

### M2 — Une partie de la cible « transports collectifs » est structurellement inatteignable

C'est l'effet miroir, et c'est lui qui mord. Puisque la simulation ne peut pas produire de
déplacement mixte, elle ne peut pas produire les déplacements que la cible compte comme
transports collectifs **parce qu'ils sont mixtes**.

Globalement, ils pèsent **1,41 point** de part modale — 11,5 % de la cible de 12,2 %. C'est
le chiffre publié par le ticket 020, et il **masque l'essentiel**. Mesuré par strate,
pondéré `COEP`, sur les déplacements internes au périmètre :

| Couronne de résidence | Cible TC | dont rabattement | **TC atteignable** | Part de la cible perdue |
|---|---:|---:|---:|---:|
| Toulouse | 21 % | 0,70 pt | 20,3 % | 3 % |
| 1ʳᵉ couronne | 8 % | 1,73 pt | 6,3 % | **22 %** |
| 2ᵉ couronne | 7 % | 2,19 pt | 4,8 % | **31 %** |
| 3ᵉ couronne | 6 % | 1,67 pt | 4,3 % | **28 %** |

| Tranche de distance | Cible TC | dont rabattement | **TC atteignable** | Part de la cible perdue |
|---|---:|---:|---:|---:|
| 0-1 km | 3 % | 0,00 pt | 3,0 % | 0 % |
| 1-2 km | 9 % | 0,05 pt | 9,0 % | 1 % |
| 2-5 km | 15 % | 0,46 pt | 14,5 % | 3 % |
| 5-10 km | 22 % | 2,83 pt | 19,2 % | 13 % |
| 10-20 km | 16 % | 6,25 pt | 9,8 % | **39 %** |
| 20-50 km | 13 % | 7,70 pt | 5,3 % | **59 %** |
| plus de 50 km | 12 % | 7,72 pt | 4,3 % | **64 %** |

**Sur la tranche 20-50 km, près de six dixièmes de la cible « transports collectifs » sont
hors d'atteinte par construction.** Le modèle de choix modal est jugé, sur cette tranche,
contre un objectif que le jeu d'options ne lui permet pas d'approcher — et il en sera
d'autant plus « corrigé » qu'il en sera plus loin. C'est le pire cas de figure : un écart
attribué au modèle alors qu'il vient de l'instrument.

Profil des déplacements concernés, ce qui explique la concentration : **médiane 11,1 km
contre 1,9 km** pour l'ensemble ; motifs dominés par le retour au domicile (42 %) et le
travail fixe (14 %) ; **3,1 % des personnes mobiles** en font au moins un la veille.

---

## Ce qui rend la neutralisation non triviale

La tentation est de retirer le rabattement de la cible TC. **C'est faux**, et il faut le
dire avant que quelqu'un le fasse : ces voyageurs se déplacent quand même. Privés d'option
mixte, ils feront dans la simulation un trajet **soit tout voiture, soit tout TC** — et on
ne sait pas lequel.

La cible atteignable n'est donc pas un point, c'est un **intervalle** :

- **borne basse de TC** = cible − rabattement (tous les rabatteurs basculent en voiture) ;
- **borne haute de TC** = cible (tous restent comptés en TC, comme le fait la simulation
  aujourd'hui avec sa hiérarchie inversée).

Pour la 2ᵉ couronne, la part TC simulée doit donc être jugée contre **[4,8 % ; 7 %]** et non
contre 7 %. Pour la tranche 20-50 km, contre **[5,3 % ; 13 %]**. C'est le même raisonnement
que la grille de sensibilité de [`terminal_time.yaml`](../../llm-agents/config/terminal_time.yaml)
(décision T6 du ticket 013) : quand une entrée est incertaine, on rapporte si la conclusion
en dépend, on ne choisit pas la valeur qui arrange.

---

## Le post-traitement de la population : à quoi il sert exactement

Les bornes ci-dessus sont des marginales EMC². Elles supposent que la population synthétique
a la même composition de rabatteurs potentiels que l'enquête — ce qui n'est **pas** vérifié,
et ce qui est précisément le genre de supposition que le ticket 020 a démoli.

Le post-traitement pose donc sur chaque persona un trait **`rabattement_plausible`**, tiré
de la propension mesurée dans EMC², pour que l'intervalle soit calculé **sur la population
en main** et non sur des marginales d'enquête.

Propension mesurée (au moins un déplacement mixte la veille), pondérée `COEP` :

| Strate | Propension |
|---|---:|
| Ensemble | 3,14 % |
| Toulouse | 1,76 % |
| 1ʳᵉ couronne | 3,62 % |
| 2ᵉ couronne | 4,61 % |
| 3ᵉ couronne | 3,95 % |
| Ménage sans voiture | 1,14 % |
| Ménage à 1 voiture | 2,32 % |
| Ménage à 2 voitures et + | 4,32 % |

⚠ **Un ménage sans voiture fait quand même du rabattement** (1,14 %) : passager, dépose,
autopartage. Conditionner le trait à la possession d'une voiture serait donc faux — c'est le
motif exact des tickets 016 et 017, un coefficient appris sur une variable et appliqué à une
autre. Le trait se conditionne à la **couronne et à la motorisation**, pas à un droit d'accès.

Le trait exploite deux acquis : la **couronne de résidence** posée par le
[ticket 021](ticket_021_couronne_residence_post_traitement.md) — sans elle, le
conditionnement géographique retomberait sur le classement métrique erroné — et
`number_of_cars`, déjà présent. Côté population de référence, 66,9 % des personas sont des
conducteurs potentiels (voiture au foyer **et** permis), donc le vivier existe.

**Ce trait ne fait pas rabattre l'agent.** Il ne change aucune décision, aucun jeu
d'options, aucun cache. C'est un trait de **mesure** : il dit « ce persona appartient à la
population qui, dans l'enquête, fait du rabattement », donc « la part TC qu'on lui oppose
doit être lue dans un intervalle ». Le distinguer d'un trait de comportement est le point le
plus important de ce ticket.

---

## Les axes à instruire

| # | Axe | Question | Attendu |
|---|---|---|---|
| C1 | **Ordre de la hiérarchie** | Aligner `_plan_transport_mode` sur l'enquête (TC avant voiture) ? Et le train, le vélo ? | ✅ **RENDU le 2026-09-04** : neuf rangs, sourcés sur l'annexe p. 53 du rapport et contrôlés sur les microdonnées (53 paires / 53 conformes). Le bus passe **avant** le train ; le vélo + TC (58 déplacements, tous TC) est couvert par `bicycle` au rang 8 |
| C2 | **Non-régression** | Le changement d'ordre déplace-t-il un seul déplacement du run courant ? | ✅ **ZÉRO, mesuré** sur les 17 258 options du run archivé, les 385 888 des jeux gelés et les 444 055 décisions en cache. Le constat « latent » du ticket 020 est confirmé |
| C3 | **Forme du trait** | Booléen `rabattement_plausible`, ou propension continue ? | Trancher. Un booléen tiré par hachage est cohérent avec `personal_bike` / `housing_type` ; une propension évite de fabriquer un tirage là où on ne veut qu'une pondération |
| C4 | **Bornes atteignables** | Où vivent-elles : dans `cerema_values.yaml`, ou dans une ressource séparée ? | **Séparée.** `cerema_values.yaml` porte ce que l'enquête mesure ; une borne d'atteignabilité est une propriété de *notre* instrument, pas de l'enquête. Les mélanger rendrait la cible non recoupable |
| C5 | **Rendu dans le scoring** | Comment la page de synthèse affiche-t-elle un intervalle plutôt qu'un point ? | Une bande sur la dimension `distance` et sur `lieu_residence`, et un composite rapporté avec et sans neutralisation |
| C6 | **Effet sur le score** | De combien le composite bouge-t-il quand la cible TC devient un intervalle ? | Chiffré à décisions constantes. Sens attendu : **amélioration** — et c'est un signal d'alerte à traiter comme tel (cf. critères) |
| C7 | **Périmètre du rabattement** | Le train + voiture compte-t-il ? Le TAD ? Le vélo + TC ? | Les inclure ou les exclure explicitement. Le vélo + TC existe (58 déplacements) et la simulation ne le produit pas non plus |

---

## Lots

1. ✅ **Lot 1 — La hiérarchie, mesurée puis corrigée. LIVRÉ le 2026-09-04.**
   `scripts/progedo_logit/export_mode_hierarchy.py` mesure l'ordre de priorité observé dans
   EMC² sur tous les couples de modes co-présents, le confronte à l'annexe **p. 53** du
   rapport publié, et gèle le résultat dans
   `llm_module/data/mode_hierarchy_emc2.json`. `llm_module/core/mode_hierarchy.py` le sert à
   `move_logger`, `mode_choice`, `task_worker` et `simulation_controller` — plus une seule
   cascade de `if` écrite à la main. Non-régression **mesurée à zéro** (axe C2). Portée
   au-delà du lot : `_primary_mode` (mode principal) est séparé de `_vehicle_mode` (chaîne
   de véhicules), sans quoi l'alignement aurait cassé le verrou de retour du ticket 008.

2. **Lot 2 — La table d'atteignabilité.** `scripts/progedo_logit/export_reachable_targets.py`
   → `llm_module/data/reachable_targets.json` : pour chaque strate de `lieu_residence` et de
   `distance`, la cible TC publiée, la part de rabattement, et l'intervalle
   `[cible − rabattement ; cible]`. Un test vérifie que la borne haute est la cible de
   `cerema_values.yaml` — sinon les deux fichiers ont divergé.

3. **Lot 3 — Le post-traitement (étage D).**
   `scripts/data/population/enrich_rabattement.py` + `llm_module/core/rabattement.py`, sur
   le modèle de `enrich_housing_type.py` : propension conditionnée à la couronne **et** à la
   motorisation, tirage déterministe par hachage de l'identifiant du persona, `None` quand la
   couronne est absente (population non traitée par le ticket 021) — jamais un repli sur la
   marginale d'ensemble, qui est exactement l'aplatissement que le ticket 019 a corrigé.
   `--check` confronte la part de rabatteurs par couronne aux propensions EMC². Cible
   `make rabattement`.

4. **Lot 4 — Le rendu.** `scripts/synthesis/frames.py` et `render.py` : la dimension TC
   s'affiche avec sa bande d'atteignabilité, et le composite est rapporté **avec et sans**
   neutralisation. Trace avant/après dans `docs/traces/`.

5. **Lot 5 — La limite qui reste.** Ce ticket ne fait pas rabattre les agents. Écrire aux
   limites de la publication que le jeu d'options ne contient pas d'itinéraire mixte, avec
   l'amplitude par strate — jusqu'à 59 % de la cible TC sur la tranche 20-50 km.

---

## Critères d'acceptation

- [x] La hiérarchie de mode principal est **lue dans une table mesurée sur EMC²**, pas
      écrite en cascade de `if`. Le vélo + TC est traité, pas seulement voiture + TC.
      *(2026-09-04 — et l'ordre est en plus **sourcé** sur l'annexe p. 53 du rapport publié,
      la mesure servant de contrôle : 53 paires tranchées, 53 conformes.)*
- [x] Rejouer le run courant après le lot 1 donne **exactement** les mêmes modes. Si un seul
      déplacement bouge, le constat « divergence latente » du ticket 020 est faux et il faut
      le corriger là-bas avant de continuer.
      *(2026-09-04 — zéro bascule sur les 17 258 options du run, les 385 888 des jeux gelés
      et les 444 055 décisions en cache. Le constat « latent » est confirmé.)*
- [ ] La cible TC est un **intervalle** partout où le rabattement pèse, et la borne haute est
      identiquement la cible de `cerema_values.yaml` — vérifié par un test.
- [ ] `cerema_values.yaml` n'est **pas** modifié. Une borne d'atteignabilité décrit notre
      instrument ; l'y mélanger rendrait la cible non recoupable sur les microdonnées.
- [ ] Le trait `rabattement_plausible` est explicitement **un trait de mesure** : son
      docstring dit qu'il ne fait rabattre personne, et aucun prompt ne le lit.
- [ ] La propension est conditionnée à la couronne **et** à la motorisation, et **n'exclut
      pas** les ménages sans voiture (1,14 % de propension mesurée).
- [ ] Aucun cache invalidé, aucune `version` bumpée dans `terminal_time.yaml`, aucun run à
      rejouer pour les lots 1 à 4.
- [ ] ⚠ **Le score va s'améliorer, et il faut le justifier ligne par ligne.** Contrairement
      au [ticket 021](ticket_021_couronne_residence_post_traitement.md) dont la correction
      dégrade la note, celle-ci l'améliore mécaniquement en élargissant la cible. Publier
      l'amélioration **par strate** et montrer qu'elle vient bien du rabattement mesuré, pas
      d'un élargissement commode. Une neutralisation qui améliore le score sans justification
      strate par strate est indistinguable d'un ajustement sur la cible — ce que la décision
      T2 du ticket 013 interdit.

## Hors périmètre

- **Produire des itinéraires de rabattement.** C'est le vrai remède, et c'est un autre
  ticket : OTP est interrogé mode par mode ; offrir « voiture jusqu'au parking-relais puis
  métro » demande un nouveau type d'option, des parkings-relais localisés, et invalide le
  cache de plans **et** le cache de décisions. Ce ticket rend la limite chiffrée et bornée
  en attendant ; il ne la lève pas.
- **La chaîne de véhicule d'un rabattement.** Un agent qui laisse sa voiture au
  parking-relais le matin doit la retrouver le soir — le verrou de retour du ticket 008 et la
  position des véhicules du ticket 014 sont concernés. Hors sujet ici, à traiter avec le
  ticket d'itinéraires.
- **Les quatre autres limites du ticket 020** (A3 pondération, A5 variance météo, A8 grappes
  incomplètes, A9 concentration spatiale).

## Ce qu'il faut savoir avant de commencer

- **Le chiffre global de 1,41 point est trompeusement rassurant.** Il ne dit rien de la
  tranche 20-50 km, où 59 % de la cible TC est perdue. Ne pas dimensionner l'effort sur la
  marginale : c'est l'erreur que le ticket 020 a trouvée trois fois.
- **Le trait dépend du ticket 021.** Sans la couronne de résidence corrigée, le
  conditionnement géographique de la propension retomberait sur le classement métrique — qui
  se trompe sur 24,4 % des personas, dont 66 déplacés de la 1ʳᵉ couronne (propension 3,62 %)
  vers Toulouse (1,76 %). Le ticket 021 est donc un **prérequis**, pas une simple voisine.
- **Le sens du mouvement du score est inversé par rapport au ticket 021.** Là-bas la
  correction dégrade et c'est le critère de réussite ; ici elle améliore et c'est un signal à
  justifier. Les deux tickets sortent du même audit : ne pas transporter le raisonnement de
  l'un à l'autre.
- **42 % des déplacements de rabattement ont pour motif le retour au domicile.** Ils vont donc
  par paires avec un aller. Compter les deux bouts est correct — l'enquête les compte tous
  les deux — mais toute mesure « par personne » doit s'attendre à un facteur 2.

## Sources

- [ticket 020](ticket_020_perimetre_population_cerema.md), axe A7 — le constat d'origine, et
  le contrôle qui a levé le soupçon sur la marche d'accès.
- [`docs/arch/perimetre-population.md`](../arch/perimetre-population.md), § A7.
- [ticket 021](ticket_021_couronne_residence_post_traitement.md) — **prérequis** : la couronne
  de résidence posée sur le persona.
- [`docs/arch/population-post-traitements.md`](../arch/population-post-traitements.md) — où le
  trait s'insère (étage D).
- Microdonnées EMC² Toulouse 2023, ProGEDO/ADISP `lil-1750` : fichier trajets (`T3`, mode du
  trajet) croisé au fichier déplacements (`MODP`, mode principal ; `TYPD`, localisation ;
  `D11`, distance) et au fichier personnes (`COEP`).
- [Méthodologie des Enquêtes Mobilité Certifiées Cerema](https://www.cerema.fr/fr/actualites/enquetes-mobilite-certifiees-cerema-methodologie)
  — définition du déplacement à mode principal.
- Modèles pour le lot 3 :
  [`enrich_housing_type.py`](../../scripts/data/population/enrich_housing_type.py) (ticket 019),
  [`enrich_personal_bike.py`](../../scripts/data/population/enrich_personal_bike.py) (ticket 015).
