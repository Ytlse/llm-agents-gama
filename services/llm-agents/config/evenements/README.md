# Événements déclarés — un seul canal, deux prises

Ticket [100](../../../docs/tickets/ticket_100_un_seul_canal_d_evenement_pour_le_vecu_et_le_lu.md).
Un événement, c'est **un texte** posé dans la mémoire d'agents désignés à des jours désignés,
avec **au plus un fait mesuré**.

Ce répertoire remplace `config/chocs/`, qui reste lu une version de plus avec un avertissement.

## Les deux prises

| `moment` | Quand | Ce que l'agent sait en décidant | Cas |
|---|---|---|---|
| `arrivee` | après la décision | l'offre nominale, rien d'autre | le choc du ticket 079 |
| `reveil` | avant la première décision | ce qu'il a lu ce matin | l'article du ticket 059 — **lot 2** |

La différence n'est pas un détail d'implémentation. À l'arrivée, **le jour de l'événement ne
mesure aucun choix** : tout l'effet des jours suivants est imputable au souvenir, et à rien
d'autre. Au réveil, l'agent décide en sachant — et c'est le contraste que le chapitre 7 mesure.

## Lancer

```bash
make run CHOC=c6_voiture_suspecte CACHE=0
```

⚠ **Coupez le cache.** Sa clé exacte ne porte pas la mémoire de l'agent, et sa branche
sémantique n'écarte une décision qu'en dessous de 0,95 de similarité : une ligne de souvenir
ajoutée à un bloc n'y suffit pas toujours. Une `[ALARME]` se lève si on l'oublie.

## Ce que la déclaration refuse

Communs aux deux canaux, repris du 079 : consigne (« avoid », « you should »), verdict sur un
mode (« this line is unreliable »), intention (« from now on I will… »), adresse à la deuxième
personne, jour hors run, règle d'exposition inconnue, mode hors hiérarchie, deux entrées pour le
même jour, retard négatif, **un champ `gravite` posé à la main**.

Un texte qui conclut à la place de l'agent fabrique le résultat qu'on prétend mesurer : la
croyance est ce que la réflexion doit produire. Le run du 19 septembre l'a payé — « I no longer
trust this car at all » dans le vécu, et le soir même un concept qui n'en était que la
reformulation.

## État de livraison

| Champ | Valeur | Livré |
|---|---|---|
| `canal` | `vecu` | lot 1 |
| `canal` | `lu` | **lot 2** |
| `moment` | `arrivee` | lot 1 |
| `moment` | `reveil` | **lot 2** |
| `exposition.regle` | `mode`, `tirage`, `agents` | lot 1 |
| `exposition.regle` | `foyers` | **lot 2** |
| `exposition.lecteurs` (lecteurs désignés, règle `foyers`) | — | 2026-09-25 |
| `texte` (fichier cité + empreinte) | — | **lot 2** |
| `calendrier` (fenêtre tirée par foyer) | — | **lot 2** |
| `jugement` | `aucun` | lot 1 |
| `jugement` | `a_l_injection` | **lot 3** |

Ce qui n'est pas livré est **refusé au chargement**, avec un message qui nomme le lot. Un champ
accepté et sans effet est pire qu'un champ refusé : rien ne le signale, et le run part sur un
protocole qui n'est pas celui qu'on a écrit.

## Pourquoi `jugement: aucun` sur les huit cas migrés

C'est l'état d'avant le ticket 100 : la gravité d'un choc se calcule sur ce que la simulation a
mesuré, sans que l'agent en dise rien. La décision D4 veut que l'agent juge dans les deux
régimes ; ce sera le lot 3. `jugement: aucun` y restera comme **ablation déclarée** — le bras
qui mesure ce que le jugement ajoute — et c'est aussi le mode sous lequel la migration se
vérifie.
