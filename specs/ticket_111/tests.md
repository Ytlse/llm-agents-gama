# Ticket 111 — Contrat de tests

> Fichier cible : `services/llm-agents/tests/test_111_lecture_et_relais.py`, plus un test de
> gabarit dans `packages/mobility_llm/tests/` et un test du contrôle dans `scripts/tests/`.
> Lancement : `services/llm-agents/.venv/bin/python -m pytest …` (les scripts `bin/` du venv ont
> des shebangs cassés).
>
> Aucun de ces tests n'appelle un vrai modèle : le client LLM est un faux qui rend une réponse
> écrite dans le test.

## T1 — La première décision du jour de lecture porte l'article *(demandé par l'auteur)*

Lecteur d'un foyer de quatre, jour de lecture J. Sa décision du trajet de J 05:57 est construite
**la veille à 07:00**, avec une mémoire longue qui ne contient pas encore l'article. Les trois
épisodiques rappelés sont des bilans « tout s'est bien passé », comme sur l'archive.

- Les lignes d'historique rendues par le vrai constructeur de mémoire de `LLMAgent` (mémoire
  longue simulée en RAM, rappel vectoriel simulé) contiennent
  `[ PRESSE ] This morning I read in the paper:`.
- Même décision reconstruite après l'injection, l'article étant en mémoire longue à 0,30 : la
  ligne y est **exactement une fois**.

## T2 — Cinq jours de déplacement, week-end exclu

Lecture un jeudi : la ligne est servie jeudi, vendredi, lundi, mardi et mercredi ; elle ne l'est
ni le samedi, ni le dimanche, ni le jeudi suivant. Avec `no_weekend_departures` faux, cinq jours
calendaires consécutifs.

## T3 — Le relais, par destinataire

Faux client LLM rendant un relais pour trois membres : un adulte informé, un mineur informé, un
membre sans message.

- L'adulte voit `[ FOYER ] Arthur told me this morning: « … »` dès sa décision du jour J.
- Le mineur voit `[ FOYER ] My parents decided this morning: « … »`.
- Le membre sans message ne voit aucune ligne `[ FOYER ]` ni `[ PRESSE ]`.
- Trois demandes simultanées pour le même foyer produisent **un** appel.
- Le gabarit reçoit, pour chaque membre, `mineur` correctement posé (âge < 18).

## T4 — Un relais invalide ne produit rien

Quatre réponses : vide, `agent_id` inconnu, membre manquant, `parle: true` avec un message vide.
Chacune → `RelaisRefuse`, une `[ALARME]` nommant le foyer et la raison, aucune ligne servie dans
le foyer, aucun texte de repli.

## T5 — L'injection à 00:00

- Le lecteur et chaque informé sont jugés, chacun avec **sa** propre identité.
- Mémoire courte et longue écrites pour chaque informé, `origine: entendu`, préfixe `[ FOYER ]`.
- L'écriture en mémoire longue est attendue : l'entrée est lisible dès le retour de l'injection.
- `evenements.jsonl` : une ligne pour le lecteur, une par informé, aucune pour un non-informé.
- `relais_foyer.jsonl` : une ligne pour le foyer, qui liste aussi le non-informé.

## T6 — Ce qui est entendu ne repart pas

Un concept `entendu` issu du relais n'est jamais proposé par `foyer.croyances_partagees`
(garde G3, non-régression).

## T7 — Exposition non avenue après un premier service

Une décision a déjà porté la ligne, puis le jugement de l'injection est refusé : `[ALARME]` avec
le nombre de décisions concernées, levée une seule fois ; les décisions suivantes ne portent plus
la ligne.

## T8 — Le cache ne sert jamais une décision qui doit porter une ligne

Cache actif, jour de service **hors** de la fenêtre de tirage (là où `cache_coupe` ne coupe plus) :
`llm_cache.lookup` n'est pas appelé, et le contournement est compté.

## T9 — La reprise relit le relais

`relais_foyer.jsonl` présent au démarrage : le relais est relu, **zéro** appel LLM, même texte.

## T10 — Rien ne change hors du dispositif

Sans événement déclaré, avec un choc vécu (`moment: arrivee`), et pour un foyer témoin : le bloc
de mémoire est identique octet pour octet à celui produit avant le ticket. Les tests du ticket 071
(lot 4) passent inchangés.

## T11 — La déclaration

- Refus : `relais` sur `canal: vecu` ; `relais` sans la règle `foyers` ; `mode` inconnu ;
  `jours_de_deplacement` à 0 ou non entier.
- Clés absentes : comportement d'avant, et une ligne de journal le dit.
- Les cinq articles `a07`, `a09`, `a13`, `a18`, `a25` se chargent avec leurs deux clés.

## T12 — L'enquête d'affinité voit la même ligne

Une enquête tenue un jour de service rend, dans son bloc de mémoire, la ligne servie à la décision
du même jour.

## T13 — Le contrôle après run

Sur des fixtures de `llm_exchanges.jsonl` (objets JSON concaténés, prompts à plusieurs agents) :

- il détecte une décision du jour de service sans la ligne, et l'accepte quand elle y est ;
- il n'attribue pas à un co-résident la ligne présente dans le bloc du lecteur d'un même prompt ;
- la section de `make report` rend les succès **et** les 🔴 ;
- un run sans événement produit une section qui le dit, pas une section vide.

## T14 — La catégorie `evenement_relais`

Le gabarit se rend avec son schéma de sortie, et la catégorie est présente dans le bundle chargé
par la passerelle.

## Recette sur archive (manuelle, hors suite)

`2026-09-24_17_50` : le contrôle du lot 6 sort 🔴 pour 286920, décision du 26/03 05:57. Aucun run
neuf n'est lancé pour ce ticket tant que l'auteur ne l'a pas demandé.
