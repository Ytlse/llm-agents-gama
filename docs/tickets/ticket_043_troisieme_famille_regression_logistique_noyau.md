# Ticket 043 — La troisième famille : régression logistique à noyau (KLR)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-11, rien n'est lancé.
>
> Prérequis livrés : [ticket 042](ticket_042_second_oracle_logit_multinomial.md) (module de
> métriques partagé, chemin de prédiction commun aux deux oracles, décideur d'expérience
> multi-familles).

## La question

Nous avons aujourd'hui **les deux extrêmes** d'un même axe, et rien entre les deux :

| | Forme de la réponse | Exactitude test | L1 masse | Élasticités |
|---|---|---|---|---|
| LightGBM | escaliers, non lisse | **0,785** | **0,0269** | erratiques par construction |
| Logit multinomial | linéaire en log-odds | 0,766 | 0,0286 | lisses, monotones |

Le booster gagne en exactitude et perd en lisibilité comportementale ; le logit fait
l'inverse. Or c'est précisément ce compromis que Martín-Baos et al. (2023) étudient, et leur
conclusion désigne une famille que nous n'avons pas : la **régression logistique à noyau**
(KLR), qu'ils présentent comme le meilleur compromis entre exactitude prédictive et
plausibilité comportementale. Elle est non linéaire comme le booster et à réponse lisse comme
le logit.

Deux usages, donc, et le second vaut peut-être davantage que le premier :

1. **prédictif** — un troisième chiffre dans la table de l'ablation (niveau 3) ;
2. **comportemental** — un **second arbitre** pour le bloc C du score à deux oracles. Un
   arbitre unique ne se réfute pas : si KLR et logit s'accordent sur le sens d'une variation,
   le désaccord du prompt est un défaut du prompt ; s'ils divergent, le test ne dit rien et
   doit se taire.

## Ce qu'il faut faire

- `scripts/progedo_logit/fit_mode_choice_klr.py`, sur le **même** parquet, la **même**
  colonne `split` étanche au ménage, le **même** `sample_weight`, le **même**
  `encode_features`, et les **mêmes** métriques (`mode_choice_eval.evaluate_proba`). Toute
  entorse à ces quatre points rend la comparaison illisible.
- Noyau RBF avec **approximation de Nyström** : 39 203 lignes d'entraînement interdisent la
  matrice de Gram pleine (1,5 milliard d'entrées). `m` points d'appui entre 500 et 2 000,
  tirés **par ménage** pour ne pas concentrer les appuis sur les gros foyers.
- Réglage de `γ` (largeur du noyau), `λ` (ridge) et `m` par la **même** validation croisée
  5 plis groupée par ménage **dans le train**. Le split test n'est jamais lu pour régler.
- Artefact autoportant sur le patron du logit : points d'appui + coefficients duaux +
  contrat de matrice → évaluateur **pur numpy**, format `klr_mode_choice_policy` v1. Le
  chemin de prédiction du jeu commun (`load_policy`) gagne un troisième format, et
  `bi_oracle` une troisième colonne, sans autre travail.
- Matrice de dessin **réutilisée telle quelle** depuis `mode_choice_logit.py` (indicatrices,
  centrage-réduction, manquants déclarés) : un noyau RBF exige des variables centrées, et
  refaire l'encodage introduirait un décalage silencieux.

## Les chiffres à battre

| Substrat | LightGBM | Logit |
|---|---|---|
| Enquête, split test scellé (13 045 trajets) — exactitude | 0,785 | 0,766 |
| idem — CEL / GMPCA | 0,5402 / 0,583 | 0,5954 / 0,551 |
| idem — L1 masse / L1 mode élu | 0,0269 / 0,0730 | 0,0286 / 0,1003 |
| Jeu gelé AAMAS, composite `emd_jsd` (plateforme) | **4,9182** | 6,1734 |
| Run épinglé, composite `emd_jsd` (volet 3) | 7,40 | 8,11 |

Cible honnête : **entrer entre les deux sur l'exactitude et rester lisse en élasticités**.
Espérer dépasser le booster serait contredit par Wang et al. (2024), qui concluent sur des
centaines de modèles que le contexte des données pèse davantage que la famille choisie.

## Coût et risques

Une demi-journée d'écriture, quelques minutes d'estimation par configuration. Deux risques
concrets : la mémoire de la matrice `39 203 × m` (à `m = 2 000`, 630 Mo en float64 — tenir en
float32 ou réduire `m`), et la **calibration**, qui est ce qui compte ici : ce sont les
probabilités, pas l'exactitude, qui produisent les parts modales. Le banc doit donc écarter
d'office toute configuration dégradant la L1 des parts de plus de 0,005, comme celui du
booster.

## Hors périmètre

- Ne pas toucher au contrat des 21 variables dans ce ticket. Ajouter les temps par mode de
  `mode_skims.parquet` est un changement **orthogonal** et probablement plus payant ; mêler
  les deux rendrait impossible d'attribuer le gain à l'un ou à l'autre.
- Toujours pas de modèle d'utilité aléatoire, donc ni valeur du temps ni disposition à payer.
- Ne pas promouvoir les poids du bloc C du score à deux oracles à cette occasion : un second
  arbitre change ce que le bloc mesure, il ne change pas la règle qui interdit de sélectionner
  un prompt contre un modèle.
