# Fiche des conditions d'une expérience, et marqueurs « en cours / planifiée » dans le registre

## Problème

Le nom calculé d'une expérience (`exp_gemini-35-fl_proexp04_jtir_pop-1000_AAMAS_v6_jeu-20260316_EN_t0_nosim`)
porte tous les réglages en abrégé et ne se relit plus : il faut connaître la convention de
nommage pour savoir quel prompt, quel modèle, quelle température ou quelle cohorte ont servi.
Dans le tableau de bord, ni le clic sur une ligne du registre, ni le bloc « ⏳ … en cours »,
ni le volet « Activités en cours » ne disent ces conditions en clair. Enfin, depuis qu'une
campagne enchaîne les expériences, le registre ne distingue pas ce qui tourne de ce qui va
tourner.

## Utilisateurs

Le chercheur qui pilote la plateforme depuis le tableau de bord Streamlit (`make dashboard`),
seul utilisateur, sur son poste. Lecture seule : la fiche n'ajoute aucune action.

## Règles métier

- **R1** — Une *fiche des conditions* se calcule pour toute expérience définie sur le disque.
  Elle porte, dans cet ordre et en toutes lettres : décideur (type et modèle, ou famille de
  l'artefact pour un modèle ajusté), fournisseur, prompt système (variante), température,
  réflexion (niveau ou budget), population (nom de la cohorte), jeu, mode (avec ou sans
  simulateur), calendrier (politique, date simulée), horizon en jours, mémoire, chaîne des
  véhicules, parallélisme, candidats max, attente max, graines (ordre, tirage, décideur si
  définie).
- **R2** — Une valeur absente de la définition n'apparaît pas dans la fiche. On n'écrit ni
  « — », ni un défaut inventé : une fiche dit ce que la définition dit.
- **R3** — Le prompt n'apparaît que si le décideur en lit un (passerelle, Antigravity). Pour
  un témoin, un modèle ajusté ou un rejeu, la ligne « prompt » est absente. Même règle que la
  colonne `prompt` du registre.
- **R4** — Pour une *exécution*, la fiche se lit dans la définition figée de l'exécution
  (`execution.yaml`) quand elle existe, et dans la définition courante sinon. Deux
  exécutions d'une même expérience peuvent donc afficher des fiches différentes. Même règle
  R6 que les colonnes `decideur`, `prompt` et `fournisseur` du registre.
- **R5** — La fiche a deux rendus : une *ligne* (valeurs séparées par « · », pour les barres
  d'avancement) et une *table* (libellé / valeur, pour le détail d'une ligne cliquée). Les
  deux sont produits par la même fiche : ils ne peuvent pas se contredire.
- **R6** — Dans le registre, cliquer une ligne affiche la table des conditions de cette
  ligne (exécution figée si la ligne en est une, définition sinon), au-dessus du détail par
  sous-catégorie, sous les boutons d'action.
- **R7** — Dans le registre, chaque bloc « ⏳ expérience / exécution — en cours » porte la
  ligne des conditions de cette exécution sous sa barre d'avancement.
- **R8** — Dans le volet « Activités en cours », chaque exécution en cours porte la ligne des
  conditions sous sa barre d'avancement. Le rendu compact de la vue d'ensemble ne la porte
  pas.
- **R9** — Dans le registre, la cellule `etat` d'une exécution `en_cours` est préfixée de ⏳.
- **R10** — Dans le registre, la cellule `etat` d'une ligne dont l'expérience est *planifiée*
  par une campagne est préfixée de 📅 et suffixée de « · planifiée (campagne <nom>) ». Est
  planifiée une expérience présente dans les `restantes` de l'état d'une campagne **vivante**,
  et qui n'est pas elle-même `en_cours`.
- **R11** — Une campagne est vivante si son `etat.json` existe, ne porte pas de `terminee_le`,
  n'a pas de demande d'arrêt (fichier `STOP`) et si le processus dont elle a écrit le `pid`
  existe encore sur l'hôte. Une campagne morte ne planifie rien : aucune 📅 ne subsiste
  après un `kill` ou un redémarrage.
- **R12** (déduite) — Les préfixes ⏳ et 📅 décorent la cellule affichée, jamais la valeur
  filtrable ni triable : filtrer sur `etat = en_cours` retourne les mêmes lignes qu'avant.
- **R13** (déduite) — Une définition illisible (YAML tronqué, fichier absent, exécution dont le
  dossier a disparu) donne une fiche vide, pas une exception : la page reste debout, comme
  pour tous les fichiers écrits par le conteneur pendant qu'on les lit.
- **R14** (déduite) — Une expérience présente dans plusieurs campagnes vivantes est marquée
  une fois, avec le nom de la première campagne dans l'ordre alphabétique.
- **R15** (déduite) — Une ligne à la fois `en_cours` et dans les `restantes` d'une campagne
  (c'est le cas de la `courante`) porte ⏳ seulement : ce qui tourne n'est plus « à venir ».
- **R16** (déduite) — Une exécution `terminee` ne porte jamais 📅, même si l'état du pilote la
  liste encore dans ses `restantes` : la campagne compte faite une expérience terminée et ne
  la rejoue pas. L'état du pilote n'est réécrit que par moments ; entre deux écritures, une
  exécution peut finir.

## Critères d'acceptation

- **R1** — définition passerelle gemini-3.5-flash-lite, T=0.0, thinking_level high, prompt
  `prompt_expert_04`, population `population_1000_AAMAS_v6`, sans simulateur → la fiche
  contient, dans cet ordre, ces valeurs-là.
- **R2** — définition sans `parametres.thinking_level` ni `thinking_budget` → aucune ligne
  « réflexion » ; aucune valeur « — » dans la fiche.
- **R3** — décideur `aleatoire` avec `gabarit.variante: minimal_persona` → pas de ligne
  « prompt » ; décideur `passerelle` avec la même variante → ligne « prompt : minimal_persona ».
- **R4** — définition courante `passerelle/gemini-3.5`, `execution.yaml` figé `modele/klr`
  → la fiche de l'exécution dit `modele:klr` (décideur figé), celle de la définition « gemini-3.5 ».
- **R5** — la ligne et la table d'une même fiche portent exactement les mêmes valeurs, dans
  le même ordre.
- **R6** — ligne cliquée → le faux Streamlit reçoit une table dont la première colonne est la
  liste des libellés de R1 présents.
- **R7** — exécution `en_cours` → sous sa barre, un texte contenant le modèle et le prompt.
- **R8** — `rendre_activites(compact=False)` → une légende par exécution avec le modèle ;
  `compact=True` → aucune.
- **R9** — ligne `en_cours` → cellule affichée « ⏳ en_cours ».
- **R10** — état de campagne vivant, `restantes = [A]`, A `definie` → cellule
  « 📅 definie · planifiée (campagne X) » ; A absente des `restantes` → « definie ».
- **R11** — même état avec `pid` d'un processus inexistant, ou `terminee_le` renseigné, ou
  fichier `STOP` présent → aucune 📅.
- **R12** — filtre `etat ∈ {en_cours}` → mêmes lignes retenues avec et sans décoration.
- **R13** — `experience.yaml` tronqué → fiche vide, aucune exception ; la table cliquée dit
  « conditions illisibles ».
- **R14** — A dans deux campagnes vivantes `alpha` et `beta` → suffixe « (campagne alpha) ».
- **R15** — A `en_cours` et dans `restantes` → « ⏳ en_cours », sans 📅.
- **R16** — A `terminee` et dans `restantes` d'une campagne vivante → « terminee », sans 📅.

## Non-goals

- Ne pas changer le nom calculé ni la convention de nommage (N1–N5) : la fiche le glose, elle
  ne le remplace pas.
- Ne pas ajouter de colonne au registre : les colonnes affichées et leur mémoire sur disque
  restent telles quelles.
- Ne pas afficher la fiche sur les jeux en construction ni sur les cibles `make`.
- Ne pas réécrire `campagne.libelle()` de l'onglet Campagne dans ce ticket ; s'il doit
  converger vers la fiche, ce sera une tâche à part.
- Ne pas afficher le texte du prompt lui-même, seulement sa variante.
- Ne pas planifier au-delà de ce qu'écrit le pilote de campagne : la page ne déduit pas
  l'ordre de passage, elle lit `restantes`.

## Sécurité

Lecture seule de fichiers locaux écrits par la plateforme (`experience.yaml`,
`execution.yaml`, `campagnes/<nom>/etat.json`). Ces fichiers peuvent être tronqués ou
incomplets pendant la lecture : toute lecture est tolérante (R13). Le `pid` lu dans
`etat.json` sert uniquement à tester l'existence d'un processus (signal 0), jamais à lui
envoyer autre chose. Aucun secret ni clé : la fiche affiche le nom d'un modèle et d'un
fournisseur, jamais une clé d'API. Aucune donnée personnelle : la population est nommée par
son dossier.

## Questions ouvertes

Aucune bloquante. Deux choix sont retenus par défaut et ouverts à discussion à la validation
du plan :

1. Les marqueurs ⏳ / 📅 décorent la cellule `etat` plutôt qu'une nouvelle colonne d'icônes
   (une colonne nouvelle n'apparaîtrait pas dans la vue mémorisée sur disque tant qu'on ne la
   réinitialise pas).
2. La vue d'ensemble (rendu compact) ne porte pas la ligne des conditions, pour rester une
   ligne par exécution.
