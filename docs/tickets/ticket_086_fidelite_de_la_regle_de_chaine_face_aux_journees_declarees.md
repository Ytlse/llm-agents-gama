# Ticket 086 — La règle de chaîne est-elle fidèle ? La rejouer sur les journées déclarées de l'enquête

> ## ⛔ REJETÉ le 2026-09-16 — doublon du [ticket 057](ticket_057_audit_et_reflexion_double_lecture_tabulaire.md)
>
> Ouvert à 11:08, alors que la mesure qu'il commande avait été faite à 10:52 et écrite au
> § 2.3 de l'audit du 057. Il cite la « Mesure du 2026-09-16 » de ce ticket sans voir l'audit
> complet rédigé en dessous : il argumente contre une version périmée de son propre parent.
>
> **Ce qu'il demandait, et qui existe déjà** : 4,2 % de départs sans voiture dans l'enquête
> contre 18,0 % sur la journée entière du modèle ; verrou de retour conforme à 98,5 % du
> terrain ; 18,2 % contre 18,0 % de retours contraints.
>
> **Sa dichotomie H1/H2 est caduque** : l'excès de blocages de sortie varie avec le seul
> décideur, sur une cohorte unique — 13,8 % pour le prompt calibré, 17,7 – 18,0 % pour les
> familles tabulaires, 30,9 % pour le plancher aléatoire. Ni la règle (H1) ni la synthèse de
> population (H2) ne produisent un gradient pareil.
>
> **Ce qui en survit** — la mesure réimplémentée au lieu d'appeler `vehicle_chain.py`, les
> blocages à tort non isolés, l'absence de ventilation par motif et par couronne — est repris
> comme reliquat en fin du ticket 057, et y devient un critère de clôture. Rien n'est à faire
> ici. Texte d'origine conservé ci-dessous pour mémoire.

---


> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-16, à la demande de l'auteur, pendant la relecture du chapitre 4.
>
> **Objet.** Mesurer combien de fois notre règle de chaîne des véhicules interdirait un
> déplacement que des personnes réelles ont effectivement déclaré avoir fait en voiture.
> Livre le chiffre qui tranche le [ticket 057](ticket_057_audit_et_reflexion_double_lecture_tabulaire.md).

---

## 1. Ce qu'on cherche à savoir

La lecture sous contrainte de chaîne fait perdre **5,9 points de part voiture** aux quatre
familles tabulaires, et l'appariement des décisions montre d'où vient l'écart (ticket 057,
mesure du 2026-09-16) : le **verrou de sortie** retire la voiture de l'offre sur 29 % des
déplacements et y fait tomber la part voiture de 50,3 à 22,0 %, quand le verrou de retour ne
rend presque rien.

Deux causes possibles, et elles appellent des corrections opposées.

| Hypothèse | Ce qui serait en cause | Ce qu'il faudrait corriger |
|---|---|---|
| **H1 — la règle sur-restreint** | `_vehicle_available` ignore la dépose, le partage du véhicule entre membres du ménage et le retour au domicile en milieu de journée | la règle, dans `vehicle_chain.py` |
| **H2 — nos journées sont trop conflictuelles** | les chaînes d'activités de la cohorte synthétique font sortir plus de monde en même temps que la réalité | la synthèse de population, pas la règle |

Aucune des deux ne se départage sur nos propres exécutions : elles produisent le même chiffre.

## 2. La mesure, et pourquoi elle tranche

**La référence est l'enquête elle-même.** EMC² enregistre la journée complète de chaque personne
interrogée, déplacement par déplacement, dans l'ordre, avec le mode déclaré. On fait donc tourner
**notre** règle sur **leurs** journées :

1. pour chaque personne du fichier déplacements, reconstituer la séquence ordonnée de ses
   déplacements du jour d'enquête ;
2. initialiser la position des véhicules possédés au domicile, comme le fait `vehicle_chain.py` ;
3. dérouler la journée en appliquant `_vehicle_available` (possession, position du véhicule,
   condition de conducteur) et `_park_vehicles` à chaque étape ;
4. compter les **blocages à tort** : un déplacement déclaré en voiture que notre règle aurait
   interdit, faute de véhicule au point de départ.

Le résultat se lit directement :

- **beaucoup de blocages à tort sur des journées réelles** ⇒ H1. La règle interdit ce que la vraie
  ville fait tous les jours, et c'est démontré sans aucune hypothèse de modélisation.
- **peu de blocages à tort, mais 29 % de `sortie_bloquee` chez nous** ⇒ H2. La règle est fidèle,
  ce sont nos chaînes qui créent des conflits que la réalité n'a pas.

Sortie attendue, à ventiler par motif et par couronne de résidence : taux de blocage à tort,
taux de `sortie_bloquee` sur les journées réelles, et comparaison au 29 % mesuré sur la cohorte.

## 3. Points d'attention

- **Réutiliser l'implémentation, ne pas la réécrire.** Les helpers `_vehicle_*` de
  `services/llm-agents/urban_mobility_agents/vehicle_chain.py` sont partagés par GAMA et par
  l'exécution sans simulateur depuis le ticket 035. Une seconde implémentation mesurerait autre
  chose que ce qui tourne.
- **Le passager n'est pas un blocage.** `_is_car_passenger` rend la voiture accessible sans test
  de position ; ces déplacements sortent du décompte.
- **Le seuil de 1 km du verrou de retour** (`RETURN_LOCK_MIN_DISTANCE_KM`) s'applique aussi ici.
- **Convention `lil-1750`** : aucune microdonnée redistribuée, seuls des agrégats sortent.
- Fichiers : `Toulouse_2023_std_{depl,pers,men}.csv` du dossier ProGEDO, déjà lus par
  `scripts/progedo_logit/export_mode_hierarchy.py` et `build_mode_skims.py`.

## Critères de clôture
- [ ] Le taux de blocage à tort est mesuré sur les journées déclarées de l'enquête, ventilé par
      motif et par couronne.
- [ ] Il est comparé au taux de `sortie_bloquee` de la cohorte (29 % au 2026-09-16).
- [ ] H1 ou H2 est tranchée, et le verdict est écrit au ticket 057.
- [ ] La limite du chapitre 8 est chiffrée depuis cette mesure, et non depuis une estimation.

## Voir aussi
- [Ticket 057](ticket_057_audit_et_reflexion_double_lecture_tabulaire.md) — audit de la double lecture
- [`docs/arch/vehicle-chain.md`](../arch/vehicle-chain.md) — les trois règles et leurs limites v1
