# Ticket 093 — Des personas qui décident, et de quoi voir une habitude se rompre

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-16. Contrat de tests à écrire avant le code, dans `specs/ticket_093/tests.md`.
>
> **Objet.** Choisir des agents dont les décisions sont observables, et produire de quoi voir une
> habitude tenir ou se rompre — en CSV pour l'analyse, dans Grafana pour la surveillance.

---

## 1. Trois personas sur cinq n'apportent rien

Mesuré sur le run `2026-09-16_15_58`, dix jours simulés :

| Agent | Trajets | Itinéraire **unique** | Modes choisis |
|---|---|---|---|
| 609 | 34 | **50 %** | voiture 100 % |
| 41275 | 34 | **50 %** | voiture 100 % |
| 11195 | **19** | 0 % | voiture 95 % |
| 899549 (Corinne) | 35 | 23 % | voiture 69 %, marche, TC, vélo |
| 616478 | 35 | 0 % | marche 71 %, TC 29 % |

609 et 41275 n'ont **qu'un seul itinéraire proposé une fois sur deux** : la moitié de leurs
« décisions » n'en sont pas. Et quand on leur en propose deux ou trois, ils prennent la voiture à
100 %. 11195 ne vit que 19 trajets contre 34-35 aux autres.

**On observe donc la mémoire de deux agents, pas de cinq** — et on paie le modèle pour cinq.

### Le critère de sélection

Mesurable **avant** le run, donc reproductible et défendable : sur une journée de référence,
≥ 4 trajets, **toujours** plus d'un itinéraire proposé, et ≥ 2 modes réellement choisis.

Passé au crible d'un run de 1 000 agents, ce critère retient **234 candidats**. Les premiers :

```
 920187 : 15 trajets · 4 modes · 5-9 options · marche 9, TC 4, train 1, voiture 1
1250941 : 13 trajets · 4 modes · 5-9 options · voiture 7, vélo 4, marche 1, TC 1
 991203 : 11 trajets · 4 modes · 5-9 options · vélo 4, TC 3, marche 2, voiture 2
```

**Dix personas** : Corinne (habitude voiture + alternative crédible — le sujet du choc) et 616478
sont conservés, huit sont ajoutés pour couvrir les quatre modes dominants. La sélection est
scriptée et rejouable, pas choisie à la main.

---

## 2. Ce qu'on mesure

### Choix modal, par agent et par jour simulé

Part de chaque mode dans les trajets du jour — 0,20 si le vélo fait un cinquième des trajets,
0,30 le lendemain. Plus le nombre de trajets, et la **part des trajets réellement décidés**.

⚠ Cette dernière n'est pas un ornement. Sans elle, « voiture 100 % » peut vouloir dire « il a
choisi la voiture » ou « on ne lui a rien proposé d'autre », et **rien ne distingue les deux**.
C'est ce qui rendait deux personas illisibles ci-dessus.

### Habitude et rupture

Deux taux, parce qu'ils ne détectent pas la même chose :

| Mesure | Ce qu'elle voit |
|---|---|
| **Reprise de la veille** — même activité, même mode qu'hier | une bascule franche, le jour où elle arrive |
| **Conformité à l'habitude des 5 derniers jours** — mode majoritaire sur fenêtre glissante | une dérive lente, qu'un seul jour ne révèle pas |

**Par activité, pas seulement par agent.** Le trajet domicile-travail et le trajet de loisir n'ont
aucune raison de basculer ensemble, et les agréger masquerait précisément le changement qu'on
cherche.

### Mémoire

Taille du vivier de rappel — mesurée à **11 candidats au jour 1, 26 au jour 10, sans jamais
décroître**. Durée de vie médiane par type de souvenir. Et les **opérations de concept par jour** :
créé, confirmé, précisé, contredit.

Cette dernière courbe est la plus importante du lot. Sur le run du 2026-09-16 :

```
créé       38  (38 %)
confirmé   61  (61 %)
contredit   1  ( 1 %)
```

**Une seule contradiction en dix jours et cinq agents** — celle de Corinne, le jour du choc. Sans
événement injecté, la mémoire n'a jamais rien révisé. C'est le mécanisme même de l'étude, et il
faut une courbe pour le suivre.

### Choc

Exposés et minutes injectées par jour, et **si le souvenir du choc figure dans ce qui est servi à
la décision**. Un souvenir écrit mais jamais rappelé ne change rien à un comportement.

---

## 3. Deux supports, deux usages

⚠ **Grafana trace en temps réel, pas en temps simulé.** Une journée simulée dure environ six
minutes, donc les courbes sont lisibles, mais l'axe des abscisses n'est pas « jour 1, jour 2 ».

| | Usage |
|---|---|
| **Prometheus → Grafana** | surveiller **pendant** le run : voir une bascule au moment où elle arrive |
| **CSV par jour simulé** | source de l'analyse et des figures ; survit à l'arrêt des conteneurs |

Le CSV fait foi. Le tableau Grafana est un instrument de bord, pas une source de résultat.

---

## 4. Recette : deux jours et un redémarrage

Avant tout run long, et comme critère d'acceptation de ce ticket :

1. Lancer deux jours simulés.
2. Arrêter, puis reprendre en nommant le run (ticket 091).
3. Vérifier que la reprise repart au bon endroit, que les décisions sont **resservies** depuis la
   trace au lieu d'être repayées (ticket 090), et que **les courbes sont continues de part et
   d'autre de la coupure**.

Ce dernier point est le vrai test : une métrique qui saute ou se dédouble à la reprise est une
métrique fausse, et on ne le verrait plus sur un run de vingt jours.

---

## 5. Ce que le ticket ne fait pas

Il ne change ni la mémoire, ni le routage, ni la règle de choc. Il ne corrige pas non plus le
double comptage des journées rejouées dans `moves.csv`, ni le défaut de planification du soir de
11195 — deux défauts mesurés le 2026-09-16, chacun signalé pour son propre ticket.
