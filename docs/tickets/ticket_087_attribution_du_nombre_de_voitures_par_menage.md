# Ticket 087 — D'où vient le nombre de voitures d'un ménage, et est-il ajusté sur l'enquête ?

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-16 à la demande de l'auteur, en marge de la clôture du volet « partage de
> véhicule » du [ticket 057](ticket_057_audit_et_reflexion_double_lecture_tabulaire.md).
>
> **Nature du ticket** : **vérification de filière.** Le trait `number_of_cars` porte une valeur
> fine (0, 1, 2, 3) dans la cohorte scellée, et le 057 vient de montrer qu'aucune règle du
> simulateur ne s'en sert au-delà d'un booléen. Avant de décider si une v2 de la règle de chaîne
> doit l'exploiter, il faut savoir **ce que cette valeur vaut** : d'où elle vient, par quelle
> chaîne elle arrive au persona, et sur quoi elle est ajustée.

---

## 1. Ce que l'ouverture sait déjà

Trois faits établis le 2026-09-16, qui posent la question plutôt qu'ils n'y répondent.

**La valeur fine existe et vient de l'enquête.**
`scripts/progedo_logit/build_mode_choice_dataset.py:278` lit `number_of_cars` directement dans
`M6` du fichier ménages EMC² (« Nombre de véhicule (VP) du ménage »), sans recodage. Le persona
porte aussi `household.id` (`population.json`, à côté d'`identity`).

**Le contrôle de marges, lui, n'en voit que trois classes.**
`scripts/AAMAS/reference_marges.py:211` — `MOTORISATION[min(n, 2)]` : tout ménage à deux voitures
ou plus tombe dans « deux voitures et + ». Les trois marges conformes du sceau
(`motorisation_personne`, `motorisation_menage`, `couronne_x_motorisation`) portent donc sur
**0 / 1 / 2+**. La distinction entre deux, trois et quatre voitures n'est contrôlée par rien.

**Et sous cette agrégation, un écart apparaît.** Distribution du nombre de VP par ménage :

| voitures | EMC² 2023, pondéré COE0 | cohorte v6 (499 ménages) | écart |
|---:|---:|---:|---:|
| 0 | 19,4 % | 19,0 % | −0,4 |
| 1 | 45,3 % | 45,1 % | −0,2 |
| 2 | 28,5 % | 29,1 % | +0,6 |
| 3 | 5,3 % | **6,8 %** | **+1,5** |
| 4 et plus | **1,5 %** | **0,0 %** | **−1,5** |

Les deux premières classes collent au dixième — c'est ce que les marges garantissent. La suite
ne colle pas, et **le surplus sur « 3 » égale exactement le déficit sur « 4 et plus »**. Cela
ressemble à un plafond à 3 quelque part dans la filière, qui reporterait les ménages à quatre
voitures et plus sur la valeur 3. Ressemble : ce ticket est là pour le vérifier, pas pour le
supposer.

---

## 2. Ce qu'il faut établir

### 2.1 La filière, bout à bout
- Où `number_of_cars` naît-il exactement (eqasim ? recopie de `M6` ? imputation ?), par quels
  fichiers il transite, et quel code le pose sur le persona. La piste `M6` est établie pour le
  jeu d'apprentissage des modèles tabulaires ; **rien ne dit encore que la cohorte scellée suit
  le même chemin** — le vivier vient de la synthèse eqasim, pas du fichier ménages.
- Y a-t-il un plafond, un `min(n, k)`, un recodage, une troncature de type de colonne ? Si oui,
  où, et déclaré où ?
- Le trait `car_availability` (`none` / `some` / `all`, 135 / 283 / 582 sur la cohorte) sort-il
  de la même source, et dit-il la même chose ? Il n'est plus servi au modèle depuis le
  ticket 018 — mais il reste dans les données et dans le jeu des modèles tabulaires.

### 2.2 L'ajustement
- Les marges contrôlent 0 / 1 / 2+ : est-ce un choix, et lequel ? Le rapport AUAT publie-t-il
  une ventilation plus fine, ou l'agrégation vient-elle de la source ?
- La descente par échanges de ménages (`seal_population.py`) optimise sur les classes agrégées :
  peut-elle dégrader la distribution fine tout en améliorant la marge contrôlée ?
- Vérifier l'écart de +1,5 point sur « 3 » : effet de plafond, effet de tirage, ou effet du
  vivier eqasim lui-même ? Le vivier compte 11 329 personnes — mesurer la distribution fine du
  vivier tranche entre « la sélection déforme » et « le vivier était déjà comme ça ».

### 2.3 La base ménage du contrôle
`CONTROLE.md` publie `motorisation_menage` avec « Base menage, n = 1000 » et les effectifs
136 / 377 / 487 — qui sont ceux de la **base personne**, alors que les pourcentages affichés
(19,2 / 45,4 / 35,4) sont bien des pourcentages de ménages. À vérifier : libellé trompeur, ou
effectif erroné dans la table publiée.

---

## 3. Ce que le ticket livre

1. **La filière écrite** : de `M6` (ou d'ailleurs) jusqu'à `traits_json.number_of_cars`, avec
   chaque transformation nommée et son fichier.
2. **Un verdict sur l'écart** de la distribution fine, avec sa cause.
3. **Une recommandation** : faut-il contrôler une marge plus fine, corriger un plafond, ou
   laisser en l'état en le déclarant ?

## 4. Ce que ce ticket NE fait pas

Il ne touche pas à `vehicle_chain.py`. L'usage du nombre de voitures par la règle de chaîne a
été chiffré et **clos** au ticket 057 le 2026-09-16 : 0,07 point de composite, dix-huit fois
sous la résolution de l'instrument, aucun run à rejouer. Si ce ticket-ci trouvait la valeur
fausse, cela ne rouvrirait pas le 057 — la règle n'en lit que le signe.

## Critères de clôture
- [ ] La filière de `number_of_cars` est écrite, du fichier source au persona, sans trou.
- [ ] L'écart « 3 voitures » / « 4 et plus » a une cause établie, pas une hypothèse.
- [ ] La distribution fine du vivier eqasim est mesurée, ce qui départage sélection et source.
- [ ] Le point 2.3 sur la base du contrôle est tranché.
- [ ] Une recommandation est posée sur l'opportunité d'une marge plus fine.

## Coût
Aucun appel LLM, aucune exécution relancée. Lecture seule sur les fichiers standards
`Toulouse_2023_std_men.csv`, le vivier eqasim et le sceau de la cohorte v6. Convention
`lil-1750` : aucune microdonnée ne sort, agrégats seulement.
