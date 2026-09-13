---
name: article-impact
description: Signale en fin de tâche ce qui, dans le travail accompli, rend l'article de recherche en cours (`docs/paper/article/`) caduc ou daté. À utiliser avant de conclure toute tâche ayant modifié du code, un protocole, une métrique, un jeu gelé, une configuration d'expérience, ou produit des résultats chiffrés. Rend un bloc SIGNALEMENT ARTICLE section par section ; ne réécrit jamais l'article.
---

# Signalement d'impact sur l'article

Une modification du code ou du protocole peut rendre fausse une phrase déjà écrite dans
l'article, sans que rien ne le dise. Cette skill produit ce signalement avant de conclure.

## Quand la lancer

En fin de tâche, dès que le travail a touché à l'un de ces points :

- un **chiffre** susceptible d'être cité (part modale, score, écart, nombre d'agents,
  taille de cohorte, durée) ;
- une **métrique** ou sa définition (L1, EMD, JSD, oracle, agrégation) ;
- un **protocole** ou son paramétrage (jeux gelés, fenêtre météo, variantes de prompts,
  ablation, seuils) ;
- un **comportement décrit dans l'article** (architecture de la passerelle, cycle de vie
  des agents, mémoire STM/LTM, inférence LLM) ;
- le **corpus de référence** (cohorte scellée, empreinte, provider retiré ou ajouté).

Un refactor, un renommage interne ou une correction sans effet observable ne déclenchent
rien : le dire en une ligne et s'arrêter là.

## Procédure

1. **Établir ce qui a bougé** — `git diff --stat` sur la tâche, plus les chiffres produits.

2. **Croiser avec le texte.** Grep sur `docs/paper/article/fr/`, `en/` et `relecture/` :
   les valeurs numériques modifiées, les noms de métriques, de variantes, de providers,
   les termes du protocole touché. Le plan (`plan/PLAN.md`) et le dossier de soumission
   comptent aussi : un résultat qui bouge peut déplacer un argument.

3. **Trier par gravité.** Est **majeur** ce qui : rend un chiffre publié faux, modifie une
   définition de métrique, inverse ou annule un résultat, rend une section caduque, ou
   retire une pièce de référence sur laquelle l'article s'appuie. Le reste est **mineur**
   (formulation datée, exemple à rafraîchir) et se signale en une ligne groupée.

4. **Rendre le bloc.** Format :

   ```
   === SIGNALEMENT ARTICLE ===
   MAJEUR — fr/05_bare_llm.md §3
     A changé : <quoi, avec l'ancienne et la nouvelle valeur>
     Devient faux : « <phrase ou chiffre du texte actuel> »
     Action suggérée : <ce qu'il faudrait réécrire>

   MINEUR — <fichier> : <une ligne>

   Rien à signaler sur : <sections vérifiées et indemnes>
   ```

   Toujours faire figurer la dernière ligne : une vérification muette ne se distingue pas
   d'une vérification non faite.

5. **Ne rien écrire.** Le signalement s'arrête au constat. Toute correction de l'article
   passe par `article-verrou` et un accord explicite.

## Pièges

- **Vacuité ≠ conformité** : un grep sans résultat peut signifier que la section emploie
  un autre libellé, pas que l'article est indemne. Vérifier au moins une section à la main.
- **Chiffres arrondis** : un chiffre du texte peut être arrondi ou exprimé en points de
  pourcentage — chercher aussi les valeurs voisines, pas seulement la chaîne exacte.
- **FR et EN dérivent** : les deux versions se vérifient séparément, `relecture/` aussi.

## Voir aussi

- `article-verrou` — verrou d'écriture sur `docs/paper/article/`.
