# Ticket 096, lot 1 — Contrat de tests

Écrit AVANT le code. Un test par règle, dans `services/llm-agents/tests/test_096_typesafe.py`.

## Le besoin

Le lot 0 a établi que Jev répond, vite, pour rien, et de façon quasi déterministe (§ 7 du
ticket). Il reste à en faire un **décideur de la plateforme** : un huitième au même contrat
`choisir(person, ctx, presentees)`, pour qu'une expérience se rejoue en n'échangeant que lui.

Rien de la présentation n'est réécrit : le texte servi à Jev sort de
`LlmAgent.build_travel_plan_payload`, celui-là même qui sert les bras LLM. Une seconde
implémentation du bloc persona ferait diverger les deux bras en silence, et c'est précisément
ce que « à texte présenté égal » interdit.

## Ce qui change de forme, et pourquoi

| | Bras passerelle (LLM) | Bras `typesafe` |
|---|---|---|
| Ce qui est envoyé | un prompt de chat + schéma JSON | `state` + une question `Choice` typée |
| Les options | dans le texte, lignes `- [n]` | dans `criteria`, clés `option_<i>` |
| La consigne | le `content` de la variante, entier | le même, **amputé de `[Output instructions]`** |
| Les probabilités | rendues par le modèle, à renormaliser | rendues par le type, arrondies à 2 décimales |
| `raison` | rédigée par le modèle | **vide** — Jev ne génère pas de texte |
| Quota | clés, rotation, fenêtre journalière | `sans_quota` : ni clé réservée, ni rotation |

L'amputation est la raison d'être de la règle **C3** : ce que Jev reçoit n'est pas le texte de
la variante, donc l'empreinte de gabarit (qui hache la variante entière) ne suffit plus à
sceller ce qui a été servi.

## Cas — la spécification du décideur

| Cas | Ce qui est vérifié |
|---|---|
| **S1** | `DecideurSpec(type="typesafe", modele="jev-1.13.0")` est valide |
| **S2** | `modele` absent → erreur de validation nommant `decideur.modele` |
| **S3** | `modele="jev-latest"` → **REFUSÉ** ; idem `jev-preview`, et tout ce qui n'est pas `jev-<maj>.<min>.<corr>` |
| **S4** | le message de refus dit qu'un alias est interdit et donne la forme attendue |
| **S5** | `portee` posée sur un décideur `typesafe` → refusée (elle ne vaut que pour `passerelle`) |

## Cas — le nommage

| Cas | Ce qui est vérifié |
|---|---|
| **N1** | `segment_decideur({"type":"typesafe","modele":"jev-1.13.0"})` → `jev-1130` |
| **N2** | deux versions de Jev donnent deux segments différents (`jev-1130` ≠ `jev-1140`) |
| **N3** | la variante de prompt entre dans le nom, comme pour un bras LLM (`…_proexp16_…`) |
| **N4** | **aucun segment de température** : Jev n'en a pas, en écrire un scellerait un réglage inexistant |

## Cas — l'empreinte

| Cas | Ce qui est vérifié |
|---|---|
| **C1** | l'empreinte du décideur porte `type: typesafe` et `modele: jev-1.13.0` |
| **C2** | elle porte `instructions_sha256` |
| **C3** | `instructions_sha256` est le sha du texte **effectivement envoyé** (amputé), pas du `content` brut de la variante |
| **C4** | deux variantes de prompt → deux `instructions_sha256` distincts |

## Cas — la conversion de la réponse

| Cas | Ce qui est vérifié |
|---|---|
| **R1** | `probabilities` → `poids` dans **l'ordre de présentation**, pas l'ordre du dictionnaire rendu |
| **R2** | somme à 0,99 ou 1,01 (arrondi Jev à deux décimales) : acceptée, poids renormalisés à 1 |
| **R3** | somme hors tolérance 0,02 → `non_imputable`, jamais un repli |
| **R4** | une clé d'option manquante dans la réponse → `non_imputable` |
| **R5** | toutes les probabilités nulles → `non_imputable` (le cas `poids_nuls` du décideur modèle) |
| **R6** | l'index est tiré par `_tirer` sur `graine_ordre(ctx.graine_tirage, person, activité)` — **même tirage que les autres décideurs**, vérifié contre la valeur attendue |
| **R7** | `raison` est vide : aucune justification n'est fabriquée à partir des probabilités |
| **R8** | `reponse_brute` porte `probabilities`, `confidence` et `input_tokens` — de quoi rejouer le bras sans le service (§ 6.2 du ticket) |
| **R9** | `distribution` est celle de `mode_distribution` : deux options de même mode s'additionnent |
| **R10** | deux options de **même mode** reçoivent deux clés distinctes et deux poids distincts — aucune ne s'écrase |

## Cas — les échecs

| Cas | Ce qui est vérifié |
|---|---|
| **E1** | 429 / 529 / timeout / erreur de connexion → `erreur` préfixée `passerelle_occupee:` — transitoire, le runner réessaie |
| **E2** | 401 / 422 → `erreur` préfixée `configuration:` — c'est une ligne de configuration, pas un quota |
| **E3** | un échec de transport n'est **jamais** un `non_imputable` : il doit être réessayé, pas archivé comme non-décision |
| **E4** | inversement, une réponse HTTP 200 inexploitable est **toujours** un `non_imputable` : elle ne sera pas réessayée indéfiniment |
| **E5** | `sans_quota` vaut `True` : `_jeu_de_cles_experience` rend l'ensemble vide, aucune clé n'est réservée |

## Cas — le texte présenté

| Cas | Ce qui est vérifié |
|---|---|
| **T1** | le `state` contient la perception, la destination, l'heure de départ, le contexte météo et `day_outlook` du payload — et **provient de `build_travel_plan_payload`**, vérifié en espionnant l'appel |
| **T2** | les options n'entrent **pas** dans le `state` : elles sont dans `criteria` |
| **T3** | `criteria` a une entrée par proposition présentée, clé `option_<i>`, `i` = rang de présentation |
| **T4** | les instructions envoyées ne contiennent pas `[Output instructions]` ni le schéma JSON |
| **T5** | le modèle passé à l'API est celui de la spec, à la lettre (`jev-1.13.0`), jamais un alias |

## Hors périmètre de ce lot

- Le rejeu des jeux gelés et le score composite : c'est le lot 2.
- Toute décomposition en questions atomiques (`Noul` + `Choice`) : lot 3, non planifié.
- Le comportement du runner face aux préfixes d'erreur : inchangé, on se branche sur
  l'existant (`epuise` / `substitution_refusee` / le reste attend). Ce lot n'ajoute aucun
  genre d'erreur au runner.
