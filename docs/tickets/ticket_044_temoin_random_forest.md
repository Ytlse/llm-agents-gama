# Ticket 044 — Le témoin random forest : d'où vient l'avantage du booster ?

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-11, rien n'est lancé.
>
> Prérequis livrés : [ticket 042](ticket_042_second_oracle_logit_multinomial.md). Ce ticket
> est le **moins coûteux** des deux ouverts ce jour (l'autre est le
> [043](ticket_043_troisieme_famille_regression_logistique_noyau.md)) et devrait passer en
> premier.

## La question, en une phrase

Le booster devance le logit de 1,9 point d'exactitude et de 0,0017 de L1 sur les parts. **Cet
avantage vient-il des arbres, ou du boosting ?** Un random forest répond : il est fait
d'arbres comme le booster, mais agrégés par *bagging* et non par descente de gradient.

- RF ≈ booster → l'avantage est celui des **arbres** : non-linéarités et interactions que le
  logit ne peut pas représenter. Alors le levier est le contrat de variables, pas la méthode
  d'agrégation.
- RF nettement en dessous → l'avantage est celui du **boosting**, et une troisième famille
  d'arbres n'apportera rien.

C'est un témoin, pas un candidat : personne ne propose de remplacer l'oracle par un RF. Sa
valeur est de **rendre réfutable** une phrase qu'on s'apprête à écrire dans l'article.

## Ce qu'il faut faire

- `scripts/progedo_logit/fit_mode_choice_forest.py` : même parquet, même colonne `split`
  étanche au ménage, même `sample_weight`, même `encode_features`, mêmes métriques
  (`mode_choice_eval.evaluate_proba`). Ce sont les quatre conditions de la comparabilité.
- `RandomForestClassifier`, réglage (`n_estimators`, `max_depth`, `min_samples_leaf`,
  `max_features`) par la **même** validation croisée 5 plis groupée par ménage dans le train.
  Le split test n'est jamais lu pour régler.
- **Ni `class_weight` ni rééquilibrage**, comme pour le booster : repondérer les classes
  détruit la calibration, et ce sont les probabilités qui produisent les parts modales.
- **Point à vérifier avant d'écrire** : le traitement des manquants. Les arbres de
  scikit-learn routent les `NaN` selon la version et le splitter ; si ce n'est pas acquis, il
  faut réutiliser les **règles déclarées** de `mode_choice_logit.py` (modalité `__missing__`,
  moyenne + indicatrice) et l'écrire dans l'artefact. Le point n'est pas anodin :
  `density_orig`/`density_dest` manquent sur les zones sans ménage enquêté, et
  `socioprofessional_class` sur 498 décisions du run épinglé.
- Sérialisation : soit un artefact autoportant sur le patron des deux autres (format
  `rf_mode_choice_policy`), soit — puisque c'est un témoin et non un décideur — **seulement
  un fichier de métriques**. À trancher à l'ouverture ; la seconde option coûte une heure de
  moins et suffit à répondre à la question posée.

## Les chiffres à battre

| Substrat | LightGBM | Logit |
|---|---|---|
| Exactitude pondérée (test scellé, 13 045 trajets) | 0,785 | 0,766 |
| CEL / GMPCA | 0,5402 / 0,583 | 0,5954 / 0,551 |
| L1 masse / L1 mode élu | 0,0269 / 0,0730 | 0,0286 / 0,1003 |
| Rappel vélo | 0,138 | à mesurer |

La classe à regarder est le **vélo** : 4 % des déplacements, rappel 0,138 chez le booster
alors que sa masse est bien calibrée. C'est là que toute méthode d'ensemble se juge, et là
que le réglage du booster avait payé (passer de 31 à 5 feuilles).

## Coût

Une heure, aucun appel LLM, aucun réseau, `sklearn` déjà installé. C'est le rapport
information/coût le plus élevé des mesures ouvertes aujourd'hui.

## Hors périmètre

- Ne pas toucher au contrat des 21 variables (même raison qu'au ticket 043 : un seul
  changement à la fois, sinon le gain n'est attribuable à rien).
- Ne pas en faire un décideur d'expérience tant que la question posée n'est pas tranchée.
