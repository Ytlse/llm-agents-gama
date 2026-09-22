# Banc de tests fonctionnels — ticket 100

Spécification complète : [`specs/ticket_100/tests_fonctionnels.md`](../../../specs/ticket_100/tests_fonctionnels.md).

**But** : trouver les défauts **avant** qu'une campagne de quarante jours ne consomme le quota.
Un maximum de vérifications pour un minimum d'appels.

## Lancer

```bash
python -m scripts.experiment.banc_fonctionnel.famille_a
```

**Zéro appel, quelques secondes.** Fabrique un run complet — population, décisions, mémoire,
événement, points de reprise — sans simulateur ni modèle, puis fait tourner dessus la vraie
chaîne d'analyse. **Si elle échoue, ne lancez pas la famille B** : elle paierait pour rien.

```bash
python -m scripts.experiment.banc_fonctionnel.famille_b --test B2
```

**27 appels au total**, en série, sur les instances déclarées. L'ordre par défaut est
**B2 → B3 → B1**, et il n'est pas arbitraire : B2 est le test dont l'échec est *silencieux* en
production.

| | Ce qui est demandé au modèle | Appels |
|---|---|---|
| **B2** | dit-il `source: heard` quand le foyer lui a parlé ? | 4 |
| **B3** | le même jugement, répété, rend-il le même échelon ? | 8 |
| **B1** | l'échelle des cinq échelons est-elle utilisée ? | 15 |

## La passerelle

**Aujourd'hui : Groq seul** (décision de l'auteur, 2026-09-22). Les tests longue durée passeront
sur d'autres modèles — d'où un **paramètre**, pas une constante :

```bash
python -m scripts.experiment.banc_fonctionnel.famille_b --instances google_gemini31_key1
```

⚠ **Aucun repli.** Si le quota est épuisé, le banc **attend** ou **s'arrête** ; il ne bascule sur
aucune autre instance. Une instance non déclarée qui aurait servi fait échouer l'appel et
nomme le problème : une mesure obtenue sur une passerelle qu'on n'a pas déclarée n'est pas la
mesure qu'on croit lire.

⚠ **La limite qui mord n'est pas le RPM.** Groq a été écarté des campagnes le 2026-09-08 pour une
limite mesurée de **1 000 jetons de sortie par minute**, invisible hors du corps des 429, et la
passerelle n'a pas été corrigée. Les 30 req/min et 1 000 req/jour ne seront jamais atteints ici ;
l'OTPM le sera. D'où les appels en série, `max_tokens` serré, et un budget de jetons de sortie
que le banc surveille lui-même (`--budget`, défaut 6 000) plutôt que de découvrir la limite dans
un 429 muet.

## Ce que le banc écrit

Dans `docs/traces/banc_fonctionnel_100/`, réécrit **après chaque appel** — une interruption de
quota ne doit rien faire perdre de ce qui a été payé.

| Fichier | Ce qu'il sert |
|---|---|
| `jugements.csv` | **Figure du papier** : ce que l'agent a compris de chaque texte, confronté à la grille — sans attendre un déplacement |
| `plancher_jugement.csv` / `.md` | Le plancher de bruit du **jugement**, à déclarer avec tout résultat de gravité — comme les 3,2 % du 095 se déclarent avec tout écart de part modale |
| `provenance.csv` | Dit si l'étage de diffusion est observable **avant** de payer une campagne |
| `passerelle.csv` | Instance servante, jetons de sortie, hors-schéma, par appel |

## Ce que le banc ne teste pas

- **Le chemin GAMA.** Le run court de non-régression sur `c6` reste le seul test de cette
  frontière, et aucun stub ne le remplace.
- **Un effet de comportement.** Aucun agent ne se déplace ici.
- **La durée.** On peut écrire une entrée vieille de trente jours ; pas les trente jours de
  rappels qui l'ont usée.

Un banc vert ne prouve pas un effet. Un banc rouge évite de payer quarante jours pour l'apprendre.

## Le garde-fou du jugement (ticket 095)

```bash
python -m scripts.experiment.banc_fonctionnel.garde_fou_jugement
```

**32 appels, une douzaine de minutes.** Depuis la décision du 2026-09-22, la gravité d'un
souvenir est celle que l'agent estime, et elle seule : c'est elle qui fixe la durée de vie du
souvenir. Ce script vérifie, **avant** qu'une campagne de cinquante jours ne parte, que le
jugement de l'agent tombe encore dans la plage qu'on avait en tête en analysant les textes.

Il lit `specs/ticket_095/grille_attendus.yaml`, où chaque texte déclare une **plage** d'échelons
(pas une valeur : deux personnes sensées ne jugent pas identiquement un article sur des punaises),
les modes sur lesquels cela devrait porter, et le motif de la plage.

Il refuse la campagne dans quatre cas, et chaque refus dit quoi faire :

| Refus | Pourquoi il est bloquant |
|---|---|
| un appel sans réponse | une exposition non jugée n'est pas anodine : elle n'a pas eu lieu |
| moins de 3 échelons distincts | toutes les durées seraient voisines et l'expérience ne mesurerait rien |
| les trois incidents hors de l'ordre prédit | c'est l'hypothèse même de l'expérience |
| trop de jugements **aveugles** hors plage | la plage a été écrite sans avoir vu une réponse |

⚠ **Le champ `deja_vu` sépare deux populations qui ne se mélangent jamais.** Une plage écrite
après avoir vu des réponses ne prouve presque rien : son taux hors plage se **signale** et ne
bloque jamais. Seules les prédictions aveugles peuvent refuser une campagne. Aujourd'hui, deux
des huit textes sont aveugles — `c2_crevaison` et `c3_panne_reseau`, deux des trois bras.

La logique de verdict est exercée **sans un seul appel** par
`scripts/tests/test_095_garde_fou_jugement.py` : un garde-fou qu'on ne peut vérifier qu'en le
lançant coûte trente appels par vérification, et on cesse de le vérifier.
