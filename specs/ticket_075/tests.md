# Ticket 075 — Spécification des tests fonctionnels

> Écrite le 2026-09-14, **avant le code**. Même convention que les lots du ticket 071 : le
> contrat est écrit d'abord, le code ensuite, et la validation se fait par l'échec (casser une
> règle doit casser un test nommé).
>
> Objet du ticket : rendre observable l'évolution de la mémoire des agents sur un run long.
> Quatre chantiers — progression météo, journal de mémoire, reprise à chaud, population de test.

---

## 1. Progression de la date météo (§ A)

Le tirage « une date météo par agent » attribuait une date FIXE pour tout le run
(`weather_draw.date_meteo`, fonction pure de `(graine, person_id)`). Sur soixante jours simulés,
chaque agent relisait donc soixante fois le même bulletin. La date tirée devient une date de
**départ**, avancée d'un jour calendaire par jour simulé écoulé.

| # | Cas | Attendu |
|---|---|---|
| A1 | jour simulé 1 (aucun jour écoulé) | la date rendue est **exactement** celle du tirage historique — une expérience d'un jour déjà mesurée rejoue la même météo |
| A2 | jour simulé 4, départ tiré au 3 octobre | le bulletin lu est celui du 6 octobre |
| A3 | deux agents différents, même jour simulé | dates différentes, et l'écart entre elles est constant sur tout le run |
| A4 | passage du 31 décembre | l'avancement continue au 1ᵉʳ janvier (l'index est (mois, jour), l'année est ignorée) |
| A5 | la progression tombe sur le 29 février | le 29 février est **sauté** (absent de la source, 365 jours) et le jour suivant est lu, une fois journalisé |
| A6 | l'heure murale du départ | conservée à l'identique, comme avant le ticket (le bulletin se lit par créneau de 3 h) |
| A7 | aucune ancre connue (premier timestamp non encore observé) | repli sur « aucun jour écoulé » — jamais d'exception sur le chemin d'une décision, et la dégradation est journalisée |
| A8 | reprise à chaud | l'ancre est relue du point de reprise : la progression ne rembobine pas |

---

## 2. Journal de mémoire (§ B)

Un fichier Markdown par agent, écrit en continu dans `<workdir>/memoires/<person_id>.md`.
**Inactif par défaut** (`agent.journal_memoire_enabled`) : un run à mille agents ne paie rien.

| # | Cas | Attendu |
|---|---|---|
| B1 | réglage désactivé | aucun fichier créé, aucun appel disque, aucune exception |
| B2 | consolidation déclenchée par le plancher de 22 h | une section datée portant le motif « plancher journalier », les entrées de mémoire courte consommées, et l'état complet de la mémoire après |
| B3 | consolidation déclenchée par rupture de gravité cumulée | motif « rupture », avec la gravité cumulée qui a franchi Θ |
| B4 | consolidation déclenchée par le seuil de N entrées | motif « seuil », avec le nombre d'entrées |
| B5 | concept créé | ligne « créé », contenu du concept, gravité, axes |
| B6 | concept confirmé | ligne « confirmé », compteur d'observations avant → après, confiance avant → après |
| B7 | concept précisé | ligne « précisé », **contenu avant → après**, compteurs conservés |
| B8 | concept contredit | ligne « contredit », contre-exemples avant → après, et mention de la mise à l'écart datée si le concept cesse d'être servi |
| B9 | purge d'entrées épisodiques | une ligne par entrée supprimée, avec son âge et sa force |
| B10 | un événement par agent | chaque agent n'écrit que dans SON fichier ; aucune fuite d'un agent à l'autre |
| B11 | l'état complet | tableau : type, contenu, gravité, force, rappels, confiance, axes, statut (servi / hors service / dépassé) |
| B12 | rappels et écritures épisodiques | résumés en une ligne compacte, sans état complet (le fichier reste lisible sur soixante jours) |
| B13 | échec d'écriture disque | journalisé en WARNING, **jamais propagé** : le journal ne fait pas tomber une simulation |
| B14 | reprise à chaud | le journal reprend au point restauré, sans dupliquer les jours déjà écrits |

---

## 3. Reprise à chaud (§ C)

Un point de reprise complet est écrit chaque nuit simulée à 3 h — après le drainage des
réflexions et le plancher de 22 h, quand les tampons de mémoire courte sont vides.

| # | Cas | Attendu |
|---|---|---|
| C1 | point de reprise écrit | `checkpoints/jour_XX/` contient la mémoire long terme, les `.md` du journal, et `reprise.json` (jour simulé, ancre météo, compteurs) |
| C2 | écriture atomique | un point interrompu en cours d'écriture n'est jamais retenu comme valide (répertoire temporaire puis renommage) |
| C3 | reprise sans point | alarme explicite, et démarrage d'un run neuf — jamais d'écrasement silencieux d'une mémoire existante |
| C4 | reprise avec point au jour k | la mémoire long terme et le journal sont restaurés à leur état du jour k |
| C5 | rejeu des jours 1..k | **aucune écriture** de mémoire courte, longue, ni de journal : le gel est total |
| C6 | dégel | au premier instant simulé postérieur au point de reprise, les écritures reprennent, et le dégel est journalisé |
| C7 | dégel qui n'arrive jamais | alarme si le rejeu dépasse le jour k + 1 sans dégeler |
| C8 | ancre météo | relue du point de reprise, jamais réancrée sur le premier timestamp du rejeu |

---

## 4. Population de test (§ D)

| # | Cas | Attendu |
|---|---|---|
| D1 | extraction | exactement cinq agents, tous mobiles, tous avec au moins un déplacement |
| D2 | déterminisme | deux extractions successives depuis la même source rendent les mêmes cinq identifiants |
| D3 | profils | les cinq profils demandés sont distincts et chacun est justifié dans le MANIFEST |
| D4 | intégrité | les agents sont recopiés **tels quels** depuis le sceau, sans modification d'aucun champ |
| D5 | traçabilité | le MANIFEST porte la source, son sha256, les identifiants retenus et le critère de chaque profil |
