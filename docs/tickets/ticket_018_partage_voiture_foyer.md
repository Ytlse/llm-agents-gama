# Ticket 018 — La voiture du foyer : un objet partagé traité comme un bien personnel

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité. Ce qui suit est une **spécification**, explicitement **non prioritaire** :
> l'effet mesuré est du second ordre, et les tickets
> [016](ticket_016_abonnement_tc_progedo.md) et [017](ticket_017_permis_progedo.md)
> déplacent davantage la simulation pour moins de travail.

## Le problème, en une mesure

`_owns_car` vaut `number_of_cars > 0`
([simulation_controller.py:370](../../llm-agents/urban_mobility_agents/simulation_controller.py:370)) :
**tout membre d'un foyer motorisé possède « la » voiture**, sans rivalité, sans partage,
sans limite de nombre. Deux adultes d'un ménage à une voiture peuvent la conduire au même
instant, chacun de son côté, et les verrous de chaîne de véhicule
([docs/arch/vehicle-chain.md](../arch/vehicle-chain.md)) n'y changent rien : ils suivent où
**l'agent** a garé son véhicule, jamais combien de véhicules le **ménage** possède.

Mesures sur `toulouse_population_1000.json` (ménages reconstitués à l'adresse du domicile,
498 grappes) et sur le run `2026-08-19_14_36` :

| Mesure | Valeur |
|---|---|
| Ménages motorisés ayant plus de titulaires du permis que de voitures | **20,6 %** (83 / 402) |
| Agents appartenant à un tel ménage | **25,4 %** (236 / 930) |
| Conducteurs « excédentaires » (titulaires − voitures) | 97 |
| Trajets voiture conduits sur le run | 2 505 |
| … pris alors que **toutes** les voitures du foyer sont déjà sorties | **153 (6,1 %)** |

*(Durée d'un trajet estimée à 25 km/h avec un plancher de 5 minutes, passagers exclus. La
convention est grossière et joue vers le bas : à vitesse plus faible, les recouvrements
augmentent. Les deux mesures portent sur la population et le run **antérieurs** aux
livraisons des tickets 015 et 019 : ni l'une ni l'autre ne touche au permis, aux voitures ni
aux chaînes d'activités, mais la vérification demande un run neuf — à refaire au prochain run
de référence.)*

Un vélo dormant est une réalité qu'il faut représenter — c'est la thèse du
[ticket 015](ticket_015_acces_velo_progedo.md). Une voiture conduite deux fois au même
instant n'en est pas une.

## Pourquoi ce n'est pas le ticket 015 transposé

Une voiture est **réellement partagée**, et beaucoup plus qu'un vélo : le foyer s'organise,
se dépose, se prête le véhicule. Attribuer nominativement une voiture à un membre — l'étage
2 du ticket 015 — serait donc **plus faux** que la situation actuelle : cela interdirait au
conjoint non titulaire du véhicule de le prendre, alors que c'est le cas courant.

Le bon objet n'est pas une attribution mais une **capacité de ménage** : `number_of_cars`
véhicules pour `n` membres, disputés dans le temps. Ce qui manque n'est pas un trait, c'est
une **rivalité**.

## Ce que le dépôt fait déjà, et où ça s'arrête

`car_availability` (`none` / `some` / `all`) porte exactement l'information utile : `some`
signifie « voiture à partager dans le foyer ». Elle est calculée par ménage
([enriched.py:78-95](../../eqasim-toulouse/synthesis/population/enriched.py)), recalculée
par les correctifs de surface ([fix_minor_traits.py](../../scripts/data/population/fix_minor_traits.py),
règle 4), et consommée à deux endroits :

- **le narratif du persona** — « peut conduire, voiture à partager dans le foyer,
  conditionné par la nécessité »
  ([llm_agent.py:133](../../llm-agents/urban_mobility_agents/agents/llm_agent.py:133)) ;
- **la politique de choix modal**, où elle pèse lourd : effet marginal moyen mesuré sur
  l'artefact déployé (contrat v2, ré-entraîné le 2026-08-21), en passant de `all` à `some`,
  **−7,3 pt de voiture, +4,1 pt de marche, +2,9 pt de vélo** ; de `all` à `none`,
  **−9,5 pt de voiture, +5,2 pt de marche**.

**Elle n'agit jamais sur le jeu d'options.** Le mode voiture est proposé ou refusé par
`_owns_car` et `_can_drive` ; `car_availability` ne fait que colorer la phrase soumise au
LLM. Un agent en `some` reçoit donc la voiture aussi sûrement qu'un agent en `all` — c'est
au LLM de deviner que « conditionné par la nécessité » veut dire « pas cette fois ».

## Deux biais mesurés sur `car_availability` elle-même

**1. Le niveau est faux, dans le sens du partage.** Distribution pondérée par personnes :

| | EMC² 2023 | Population synthétique | Écart |
|---|---|---|---|
| `all` | 69,5 % | 63,5 % | −6,1 |
| `some` | 16,9 % | 23,8 % | **+6,9** |
| `none` | 13,6 % | 12,7 % | −0,8 |

Le simulateur voit 40 % de partage en trop. Cause principale : l'excès de permis mesuré par
le [ticket 017](ticket_017_permis_progedo.md) (+5,6 pts chez les majeurs) gonfle le nombre
de titulaires du foyer, donc fait basculer des ménages de `all` vers `some`. **Ce biais-ci
se corrige gratuitement en livrant le ticket 017** — raison de plus pour ne pas commencer
par ce ticket-là.

**2. Les deux côtés ne calculent pas la même variable.** À l'entraînement, le nombre de
titulaires du ménage est compté sur **tous** ses membres (l'enquête les liste tous) ; à
l'inférence, la population exportée est un **échantillon** : 118 grappes sur 498 comptent
moins de membres présents que ne l'annonce leur `household_size`. Mesuré :

| Base de calcul | `all` | `some` | `none` |
|---|---|---|---|
| Grappes complètes seulement | 60,3 % | 15,8 % | 23,9 % |
| Toutes les grappes | 64,1 % | 16,7 % | 19,3 % |

Presque **4 points** d'écart sur `all`, dû au seul filtrage spatial : les permis des membres
absents ne sont pas comptés, `cars >= licenses` passe trop souvent. C'est la même « contrainte
du consommateur » que le ticket 015 documente pour `has_bike` — le coefficient appris est
appliqué à autre chose que ce qu'il mesure. `fix_minor_traits.py` compte déjà ces ménages
incomplets et le signale dans son rapport ; personne ne s'en sert.

## Spécification — trois options, à trancher, coût croissant

### Option A — `car_availability` contraint le jeu d'options (la moins chère)

Faire dépendre l'offre du mode voiture de `car_availability`, et non seulement du booléen
`_owns_car` : en `some`, la voiture n'est proposée qu'avec une probabilité — ou sous une
condition de motif/distance — au lieu d'être toujours là. Pas de modélisation de ménage, pas
d'état partagé, une règle locale à l'agent.

Défaut assumé : c'est un tirage, pas une rivalité. Deux membres du foyer peuvent encore
sortir ensemble avec la même voiture, simplement moins souvent.

### Option B — la voiture comme ressource de ménage (la juste)

Un compteur par foyer : `number_of_cars` véhicules, pris et rendus. Un agent qui demande la
voiture alors qu'aucune n'est disponible ne reçoit pas le mode. Cela suppose :

- un **identifiant de ménage** dans le JSON — aujourd'hui absent, reconstruit à l'adresse,
  avec les 8 collisions d'adresse et les 118 grappes incomplètes que le ticket 015 documente
  déjà ;
- un **état partagé** dans le contrôleur, donc une sérialisation et un point de contention
  supplémentaires dans le pipeline ;
- une décision sur les ménages partiellement exportés : un foyer dont deux membres sur
  quatre sont dans le fichier ne doit pas voir sa capacité consommée par les absents, ni
  libérée pour autant.

C'est la modélisation correcte, et c'est un chantier de contrôleur, pas d'imputation.

### Option C — ne rien faire, et l'écrire

6,1 % des trajets voiture conduits sont concernés. Documenter la limite dans
[docs/arch/vehicle-chain.md](../arch/vehicle-chain.md) et la citer parmi les limites de la
publication est une sortie honnête, à condition qu'elle soit **écrite** et non oubliée.

**Recommandation** : livrer d'abord le [ticket 017](ticket_017_permis_progedo.md) (qui
retire à lui seul l'essentiel des 6,9 points de `some` en excès), puis l'option A si la part
voiture reste haute, puis l'option C par défaut. L'option B ne se justifie que si un résultat
publié dépend du partage intra-foyer.

## Résultat du test — 2026-08-24, signal « GO18 » donné : REJET du canal narratif

Le test a été mené selon le protocole ci-dessous. **Verdict : l'effet du réalignement de
`car_availability` sur les parts modales est au niveau du bruit, et son amplitude agrégée
plafonne à un dixième de point.** Trace complète et reproductible :
[`docs/traces/2026-08-24_car_availability/`](../traces/2026-08-24_car_availability/).

**Ce qui a été comparé.** `v7` (jeu gelé de production, temps terminal `tt3`) contre `v8`,
le même jeu avec **72 personas sur 818** basculés `some` → `all` — ce qui porte la
distribution de 60,9 / 25,6 / 13,6 % à 69,7 / 16,7 / 13,6 %, pour une cible EMC² de
70,0 / 16,9 / 13,1 %. Une seule variable bouge : statut de conducteur préservé, `none`
intouché (c'est la motorisation, pas le partage), espacement du rendu reproduit à
l'identique.

**La cible a été recalculée, pas reprise.** `make car-availability` →
`llm_module/data/car_availability_emc2.json`, avec ses deux contrôles. Positif : la même
lecture reproduit la motorisation publiée (1,25 VP/ménage ; 19,4 / 45,3 / 35,3 % contre
19 / 45 / 35). Négatif : la non-réponse de `P7` est **nulle** chez les majeurs. Le
recalcul donne **70,0 / 16,9 / 13,1 %** contre les 69,5 / 16,9 / 13,6 % que ce ticket
citait — le recoupement tient.

**Le résultat.**

| Jeu | Personas traités | Δ voiture (traité) | Plancher mis à l'échelle | Verdict |
|---|---|---|---|---|
| `train` | 35 / 404 | +0,24 pt | 2,38 pt | sous le bruit |
| `val` (indépendant) | 10 / 165 | +4,25 pt | 5,49 pt | sous le bruit |
| `rank` (⊂ `train`) | 9 / 75 | +7,27 pt | 4,79 pt | marginal |
| **mise en commun `train`+`val`** | **45** | **+1,34 pt** | **1,31 pt** | **au niveau du bruit** |

**Effet agrégé reconstruit : +0,12 pt de part voiture.** À comparer aux 5,28 de composite
que la même méthode a rapportés sur le temps terminal. C'est l'amplitude, et non la
significativité, qui ferme la question.

**Le premier chiffre était un faux positif, et son autopsie vaut d'être lue.** Le test
initial sur `rank` annonçait +7,27 pt — une amplitude qui recoupait presque exactement
l'effet marginal connu de la politique logit (−7,3 pt de `all` vers `some`). Tout
concordait. Trois choses l'ont démenti : une **médiane de +1,3 pt** derrière cette moyenne
(5 personas en hausse, 1 en baisse, 3 immobiles, deux cas passant de 70 % à 100 % portant
tout) ; un **plancher de bruit mal posé**, comparant un Δ mesuré sur 22 unités de masse à
un plancher mesuré sur 201 ; et surtout `rank ⊂ screen ⊂ train`, donc **aucune réplication
indépendante** — ses 9 personas sont inclus dans les 35 de `train`. La leçon est versée au
protocole.

**Ce que le rejet ne dit pas.** Il porte sur le **canal narratif** — le seul qu'un jeu gelé
puisse mesurer. Il ne dit **rien de la rivalité** : les 6,1 % de trajets voiture partant
alors que toutes les voitures du foyer sont dehors relèvent de l'option B, hors de portée
de ce protocole par construction. Il ne contredit **pas** la politique logit, mesurée sur
un autre instrument ; il établit que le LLM, sous le prompt de production, y est bien moins
sensible — cohérent avec le constat central de ce ticket, `car_availability` ne fait que
colorer la phrase. Et il ne remet **pas** en cause le biais de niveau lui-même : les
+8,7 pts de personas en `some` sont réels et mesurés.

**Conséquence pour les options.** L'option A (contraindre le jeu d'options) reste
**non mesurée** — le protocole ne sait pas la tester, puisqu'une réécriture de jeu gelé ne
change pas quelles options ont été offertes. Mais le rejet du canal narratif retire
l'argument le plus simple en sa faveur : si dire « voiture à partager » ne déplace pas les
choix, c'est bien le **jeu d'options** qu'il faudrait toucher, donc l'option A ou B, avec
leur coût — pour un enjeu désormais chiffré à un dixième de point sur le narratif et à
6,1 % des trajets voiture sur la rivalité. **L'option C (écrire la limite) devient la
sortie recommandée**, et le ticket 017 continuera de corriger le niveau gratuitement.

---

## Méthode de test — arrêtée le 2026-08-24, appliquée le même jour

Le test suivra [`docs/arch/protocole-parametre-exogene.md`](../arch/protocole-parametre-exogene.md),
la méthode qui a validé le temps terminal du [ticket 013](ticket_013_temps_terminal_itineraires.md) :
mesurer la variable dans EMC², réécrire un **jeu gelé** où une seule variable bouge, faire un
**A/B apparié** sur le moteur de calibration (~15 appels par bras), archiver dans
`docs/traces/`, puis passer la porte de décision. Son intérêt décisif ici : **elle chiffre
l'effet sans payer de run de simulation**, qui coûte des heures — et ce ticket est
précisément celui dont on ne veut pas payer le run avant de savoir s'il vaut quelque chose.

**Deux limites du protocole mordent sur ce ticket-ci**, et doivent accompagner tout
résultat :

- la réécriture d'un jeu gelé **ne change pas quelles options ont été offertes** — or c'est
  exactement l'objet de l'option A (contraindre le jeu d'options). L'A/B saura chiffrer un
  changement de *narratif* `car_availability`, pas une option retirée ;
- elle **ne rejoue pas les chaînes de véhicule**, où le choix d'un jour se répercute sur les
  offres du lendemain — et la rivalité intra-foyer est par nature un phénomène de chaîne.

Autrement dit : le protocole peut trancher le **niveau** de `car_availability` (biais n° 1,
les 6,9 points de `some` en excès) à coût quasi nul, mais l'effet d'une vraie rivalité
(option B) restera hors de sa portée. C'est une raison de plus de livrer d'abord le
[ticket 017](ticket_017_permis_progedo.md), dont le protocole *sait* mesurer l'effet.

**Vigilances reprises du protocole** : contrôle négatif **et** positif sur la mesure
d'enquête (une variable nulle parce que non renseignée n'est pas une variable nulle) ;
`--dry-run` avant de dépenser ; effectif opposable = personas distincts, pas décisions ;
jeu `test` refusé ; modèle d'éval épinglé, jamais un alias flottant ; le **rejet s'archive
autant que l'adoption**. Et le piège documenté le 2026-08-24 : si le périmètre livré dépasse
le périmètre mesuré, le dire et le mesurer.

**Préalable de mesure** : les chiffres de ce ticket (6,1 % de trajets voiture hors capacité,
20,6 % de ménages sur-titularisés) sont antérieurs aux livraisons des tickets 015 et 019.
Ils sont à refaire avant de servir de base de comparaison.

## Critères d'acceptation

Selon l'option retenue :

- [ ] `car_availability`, distribution par personnes : **69,5 / 16,9 / 13,6 %** (± 3 pts) —
      atteignable en grande partie par le seul ticket 017
- [ ] trajets voiture pris au-delà de la capacité du foyer : sous **2 %** (option A) ou
      **0 %** par construction (option B)
- [ ] la définition de `car_availability` est **la même** à l'entraînement et à l'inférence,
      ou l'écart est mesuré et publié (aujourd'hui : 4 pts, non mesuré côté enquête)
- [ ] les ménages partiellement exportés restent comptés et signalés, jamais complétés en
      silence
- [ ] aucune cible atteinte par absence de mesure

## Hors périmètre

- **Le trajet du conducteur accompagnant** : décision D5 du ticket 008. Un enfant conduit à
  l'école ne génère pas le déplacement du parent. Cela reste vrai après ce ticket.
- **L'auto-partage et la location** : `MODP` les distingue mal, et le parc de ménage n'est
  pas le bon objet pour les représenter.
- **Le stationnement au domicile** (`M23`) comme contrainte de disponibilité : covariable
  candidate seulement.

---

## Annexe — le deux-roues motorisé, un mode mesuré à zéro parce qu'il est absent

À traiter avec ce ticket parce qu'il s'agit du même objet : un véhicule motorisé du ménage
qui n'atteint pas l'agent.

**Ce que l'enquête en dit.** `M14` (nombre de deux ou trois-roues motorisés du ménage) :
**9,0 %** des ménages en possèdent au moins un, parc moyen **0,10** par ménage. Côté
déplacements, `MODP` **19** (conducteur) et **20** (passager) — les codes utilisés à
Toulouse, la cylindrée n'étant pas détaillée — totalisent **0,85 %** des déplacements
(0,78 % conducteur, 0,08 % passager), pondération `COEP`.

**Ce que le dépôt en fait.** Rien, et à trois niveaux :

- `number_of_motorcycles` et `use_motorcycle` existent dans eqasim et **n'atteignent jamais
  le JSON** (cf. [population-post-traitements.md](../arch/population-post-traitements.md),
  § *Attributs calculés en amont qui n'atteignent jamais l'agent*) ;
- le journal de déplacements porte une colonne `P(Deux-roues motorisé) %`
  ([move_logger.py:36](../../llm-agents/urban_mobility_agents/utils/move_logger.py)) qui
  vaut **0 sur les 6 681 trajets** du run `2026-08-19_14_36` : le mode n'a jamais été
  proposé, donc jamais choisi ;
- `number_of_vehicles`, qui **somme** voitures et deux-roues, sert à dériver `any_cars`,
  l'un des cinq attributs d'appariement ENTD
  ([matched.py:204](../../eqasim-toulouse/synthesis/population/matched.py)) : un ménage sans
  voiture mais motorisé en deux-roues est apparié comme « motorisé ». Le deux-roues n'existe
  donc nulle part dans la simulation, **sauf** là où il fausse le choix du donneur.

**Ce qui manque pour le valider.** La référence CEREMA/AUAT utilisée par la page de
synthèse ne ventile **pas** le deux-roues motorisé : il est fondu dans `autres_modes`, à 3 %
([cerema_values.yaml](../../scripts/data/population/cerema_values.yaml)), aux côtés du taxi,
du fourgon et du reste — et
[frames.py:44](../../scripts/synthesis/frames.py) mappe bien `P(Deux-roues motorisé) %` sur
`autres`. Il n'y a donc **aucun axe de recette publié** pour ce mode ; seules les
microdonnées permettent de le cibler, à 0,85 % des déplacements.

**Décision du 2026-08-21 : rien n'est entrepris.** Ni trait d'équipement, ni mode de
transport. Ce paragraphe est la trace de ce choix, pour qu'il ne soit pas reconsidéré par
oubli. Le raisonnement qui l'a motivé suit.

**Conclusion, à assumer.** Le gain est inférieur au point de pourcentage de déplacements, le
coût est un trait d'équipement plus un mode de transport complet (itinéraires, vitesses,
stationnement, chaîne de véhicule). C'est un cas de **vacuité** — un mode réel mesuré à zéro
parce qu'il n'est pas modélisé, et non parce qu'il serait juste — et il vaut mieux l'écrire
que le corriger. Le seul point qui mériterait une correction indépendante est le
`number_of_vehicles` qui déguise un scooter en voiture pour l'appariement : celui-là est un
défaut d'entrée, pas un mode manquant.

## Sources

- Microdonnées **EMC² Toulouse 2023**, ProGEDO/ADISP `lil-1750` — `M6` (voitures), `M14`
  (deux/trois-roues motorisés), `P7` (permis), `MODP` 19/20, pondérations `COE0` et `COEP`.
- Dictionnaire `Dico_Dessin_StandardV17_Corrige.xls`, onglet `Modes` : les codes `MODP`
  13-16 (cylindrée détaillée, non servis à Toulouse) et 19-20 (sans détail, servis).
- Run `experiments/archive/2026-08-19_14_36` — `moves.csv`, 6 681 trajets.
- Politique de choix modal du dépôt pour les effets marginaux moyens de
  `car_availability`.
