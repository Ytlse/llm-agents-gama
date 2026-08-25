# A/B `car_availability` — la disponibilité de la voiture réalignée sur EMC²

Mesure du **2026-08-24**, ticket 018, selon [`protocole-parametre-exogene.md`](../../arch/protocole-parametre-exogene.md).

**Verdict : REJET.** L'effet du réalignement sur les parts modales est **sous le plancher de bruit** sur les jeux correctement dimensionnés. La mesure négative est archivée au même titre qu'une adoption : elle ferme une hypothèse.

## Ce qui a été comparé

- `v7` — jeu gelé de production (temps terminal aligné `tt3`, voiture et vélo).
- `v8` — le même, avec `car_availability` réalignée sur EMC² : **72 personas sur 818** basculés `some` → `all`, portant la distribution de 60,9 / 25,6 / 13,6 % à 69,7 / 16,7 / 13,6 % pour une cible de 70,0 / 16,9 / 13,1 %.
- Une seule variable bouge : le statut de conducteur est préservé, `none` n'est pas touché (c'est la motorisation, pas le partage), et l'espacement du rendu est reproduit à l'identique.

Cible mesurée par `make car-availability` → `llm_module/data/car_availability_emc2.json`. Contrôle positif passé : la même lecture reproduit la motorisation publiée (1,25 VP/ménage ; 19,4 / 45,3 / 35,3 % contre 19 / 45 / 35). Contrôle négatif : non-réponse `P7` **nulle** chez les majeurs.

## Résultats

| Jeu | Filiation | Personas traités | Δ voiture (traité) | Plancher brut | Plancher **mis à l'échelle** | Verdict | Composite |
|---|---|---|---|---|---|---|---|
| `train` | moitié [0,50) des personas | 35 / 404 | +0.24 pt | 0.76 pt | 2.38 pt | sous le bruit | +0.46 |
| `val` | moitié [50,70) — indépendant de `train` | 10 / 165 | +4.25 pt | 1.74 pt | 5.49 pt | sous le bruit | -1.94 |
| `rank` | ⊂ screen ⊂ train — NON indépendant de `train` | 9 / 75 | +7.27 pt | 1.58 pt | 4.79 pt | SIGNAL | -2.25 |

### Mise en commun des jeux indépendants (`train` + `val`)

`rank` et `screen` sont **inclus** dans `train` : les mettre en commun compterait deux fois les mêmes personas. Seuls `train` et `val` sont disjoints — **45 personas traités**, masse traitée 145 contre 1423 de placebo.

| Mode | Δ traité | Δ placebo | Plancher mis à l'échelle | Verdict | Effet agrégé reconstruit |
|---|---|---|---|---|---|
| marche | +1.50 pt | +0.71 pt | 2.22 pt | sous le bruit | +0.14 pt |
| velo | +0.14 pt | +0.53 pt | 1.67 pt | sous le bruit | +0.01 pt |
| voiture | +1.34 pt | -0.42 pt | 1.31 pt | SIGNAL | +0.12 pt |
| transports_collectifs | -2.98 pt | -0.82 pt | 2.58 pt | SIGNAL | -0.28 pt |

## Lecture

**Le chiffre de tête est la mise en commun** : sur les 45 personas traités des deux jeux disjoints, l'effet voiture vaut **+1,34 pt contre un plancher de 1,31 pt** — soit un rapport de 1,02, c'est-à-dire *exactement* au niveau du bruit. Deux modes passent tout juste la barre (voiture, transports collectifs), deux non. Aucune lecture ne permet d'affirmer un effet.

**Et c'est l'amplitude, pas la significativité, qui tranche.** En prenant le point estimé au pied de la lettre — donc en supposant l'effet réel — l'effet **agrégé** vaut **+0,12 pt de part voiture**. À comparer aux 5,28 de composite qu'a rapportés la correction du temps terminal par la même méthode. Le biais de niveau est réel et mesuré (+8,7 pts de personas en `some`), mais son canal narratif ne coûte pas un dixième de point. La conclusion tient quelle que soit l'opinion qu'on se fait du test statistique.

**`train` est la mesure individuelle de référence** : 35 personas traités, le plus grand effectif opposable disponible hors jeu de test. Son effet voiture (+0,24 pt) est **sous son propre plancher de bruit** (0,76 pt), et son composite se dégrade légèrement. Il n'y a pas d'effet détectable.

**`rank` avait annoncé +7,27 pt, et c'était un faux positif.** Trois raisons, toutes vérifiables ci-dessus :

1. neuf personas traités seulement, pour une **médiane de +1,3 pt** — 5 en hausse, 1 en baisse, 3 immobiles, la moyenne portée par deux cas passant de 70 % à 100 % ;
2. son propre placebo valait 1,58 pt, un plancher deux fois plus haut que celui de `train` ;
3. surtout, **`rank ⊂ screen ⊂ train`** : ses 9 personas sont *inclus* dans les 35 de `train`. Il n'y a jamais eu deux mesures en désaccord, mais une sous-population qui fluctuait.

**Le piège de l'agrégat, à garder en tête pour les prochains traits.** Sur `rank`, la lecture agrégée donnait −0,29 pt de voiture — le **signe inverse** de son effet traité. Le traitement ne portait que 9,9 % de la masse, le bruit placebo les 90,1 % restants : −1,12 × 0,901 = −1,01 pt, contre +7,27 × 0,099 = +0,72 pt. La reconstruction tombe à l'unité près sur les quatre modes.

## Ce que cette mesure ne dit pas

- **Rien sur la rivalité.** Un jeu gelé ne rejoue ni l'offre d'options ni les chaînes de véhicule. Les 6,1 % de trajets voiture partant alors que toutes les voitures du foyer sont dehors — l'option B du ticket 018 — restent hors de portée de ce protocole. Le rejet porte sur le **canal narratif**, pas sur le partage.
- **Rien contre la politique logit.** Son effet marginal de −7,3 pt (`all` → `some`) est mesuré sur un autre instrument. Ce que la mesure établit est que le **LLM, sous le prompt de production, y est bien moins sensible** — cohérent avec le constat du ticket : `car_availability` ne fait que colorer la phrase, sans jamais restreindre les options.
- **Rien sur le niveau lui-même.** L'excès de `some` (+8,7 pts de personas) est réel et mesuré ; ce qui est rejeté est l'idée qu'il coûte des points de part modale par le narratif.

## Reproduire

```bash
make car-availability                      # la cible d'enquête + ses contrôles
cd prompt_calibration
python rewrite_car_availability.py --src v7 --dst v8 --dry-run
python rewrite_car_availability.py --src v7 --dst v8
python ab_car_availability.py --dataset train --versions v7,v8 --dry-run
python ab_car_availability.py --dataset train --versions v7,v8 --out …
```

Le tirage est déterministe (sel `car_availability_emc2_v1`) : `v8` se régénère à l'identique, et le cache d'éval du store reste valide.

