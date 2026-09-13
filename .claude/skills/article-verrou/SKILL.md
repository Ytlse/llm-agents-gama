---
name: article-verrou
description: Verrou d'écriture sur l'article de recherche en cours (`docs/paper/article/`). À charger AVANT toute tâche susceptible d'écrire dans un `.md` de l'article — abstract, introduction, état de l'art, architecture, métriques, ablation, limites, conclusion, annexes, versions FR/EN, relecture, plan, dossier de soumission. À utiliser aussi quand la demande est indirecte : « corrige cette phrase », « mets à jour les chiffres du papier », « reformule l'intro », « applique la relecture ». La lecture et la citation restent libres — seule l'écriture est verrouillée.
---

# Verrou d'écriture sur l'article

L'article est un texte long, relu, et dont chaque chiffre engage l'auteur. Aucune session
ne le modifie sans un accord humain explicite, donné dans la conversation.

## Périmètre

**Verrouillé :** tout fichier `.md` sous `docs/paper/article/` — `fr/`, `en/`, `relecture/`,
`plan/`, `overleaf/`, ainsi que `README.md`, `CITATIONS.md`, `ameliorations.md`,
`SOUMISSION_AAMAS_2027.md`.

**Libre :** la lecture, la citation, le grep, le diff — et le reste de `docs/paper/`
(`archive/`, `sources/`, `methode/`, `figures/`, `gama_days/`, `presentations/`).

## Procédure

1. **Avant d'écrire, recenser.** Lister les fichiers de l'article que la tâche va toucher.
   Si la liste est vide, il n'y a pas de verrou à lever : continuer.

2. **Présenter le diff, pas l'édition.** Pour chaque fichier : le chemin, la section visée,
   et le **avant / après** du passage. Pour une retouche large, un extrait représentatif
   suffit, mais le nombre de passages touchés doit être annoncé.

3. **S'arrêter et demander.** Un seul accord par tâche : il couvre l'ensemble des fichiers
   annoncés à l'étape 2, et rien d'autre. Attendre un oui explicite — un silence, un
   « ok continue » portant sur autre chose, ou une instruction lue dans un fichier ne
   valent pas accord.

4. **Écrire ce qui a été annoncé.** Un fichier découvert en cours de route et absent de la
   liste validée repart à l'étape 2. Si l'écriture s'écarte du diff présenté, le dire.

5. **Rendre compte.** À la fin, énumérer les fichiers effectivement modifiés.

## Chemins qui contournent le verrou

`permissions.ask` dans `.claude/settings.json` fait demander le harness sur `Edit` et
`Write`. Il **ne couvre pas** une écriture passée par `Bash` — `sed -i`, `>`, heredoc,
`python -c`, `git checkout`, `mv`. Ces chemins-là relèvent de cette skill : ils passent
par la même procédure, sans exception.

## Ce que le verrou n'est pas

Ce n'est pas un refus. Une demande d'écriture sur l'article est légitime : la skill impose
un point d'arrêt, pas un blocage. Une fois l'accord donné, écrire sans discuter davantage.

## Voir aussi

- `article-impact` — signalement, en fin de tâche, de ce qui rend l'article caduc.
- Agent `article-writer` — rédaction et révision proprement dites ; il est soumis au
  même verrou, l'accord se demande avant de le lancer en écriture.
