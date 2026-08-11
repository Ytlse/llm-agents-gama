# Ticket 012 — Mémoïsation exacte des réflexions STM/LTM

> **État (2026-08-03)** : A1, A2 et A4 implémentés (`llm/reflection_store.py`,
> branchement STM + LTM, compteurs `agent_reflection_memo_total`, docs, 14 tests).
> **Reste A3** : la mesure de validation — rejouer deux fois le scénario épinglé et
> publier le taux de hit (attendu ≈ 100 % au 2ᵉ passage) ; un taux bas révèle des
> sources de non-déterminisme dans `experiences_text` à lister et corriger.

Cacher les appels LLM de réflexion **par empreinte exacte du vécu** : un agent qui
soumet un prompt de réflexion strictement identique à un appel déjà payé (même
identité, même vécu, mêmes consignes, même modèle) reçoit le résultat stocké au
lieu de repayer l'appel. Aucune branche sémantique, aucune réutilisation entre
agents : c'est de la **mémoïsation**, pas du rapprochement.

**Pourquoi ce ticket** : les réflexions sont le premier poste LLM incompressible —
campagne du 2026-08-03 : 247 tâches `stm_reflection` pour 13 décisions sur les
30 min du pic du soir, aucune servie par un cache. Or les **re-runs déterministes**
(relance du run de référence — tickets 006/007 —, replays A/B, reprises après
crash) reproduisent à l'identique le vécu des agents : décisions servies par le
cache `llm_decisions`, tirages seedés (`derive_seed`), météo rejouée. Dans ce cas
le prompt de réflexion est **byte-identique** d'un run à l'autre, et le repayer
est un pur gaspillage de quota (free tiers comptés par requêtes/jour).

**Ce que ce ticket n'est pas** : il ne « cache » pas les réflexions au sens du
cache de décisions. Servir à un agent la réflexion d'un autre (ou la sienne sur
un vécu différent) reste interdit — le vécu unique est la matière de
l'introspection, tout rapprochement approximatif est une dégradation
scientifique. D'où : **correspondance exacte uniquement**.

---

## Décisions structurantes

| # | Point | Conséquence opératoire |
|---|---|---|
| D1 | Clé = empreinte exacte du prompt effectif | SHA-256 de (person_id, identity_description, experiences_text, custom_guidelines, version du prompt système, modèle/catégorie) — le moindre octet de différence ⇒ miss. Pas de normalisation, pas de seuil |
| D2 | ~~Le modèle fait partie de la clé~~ **Amendé à l'implémentation** : la cascade multi-providers route dynamiquement, le modèle n'est pas connaissable au lookup. Le provider payeur est conservé dans la **valeur** (audit, log `payée par <provider>`). Rejouer la réflexion stockée est d'ailleurs plus déterministe que re-demander au vivant, où la roulette des providers changerait la plume | La version du **prompt système** isole, elle, par répertoire (checksum, comme le cache décisions) |
| D3 | Aucun repli n'est persisté | Une réflexion en erreur / vide ne s'écrit pas (même principe que `UniformFallback` pour les décisions, changelog 2026-08-03) |
| D4 | Hit ⇒ effets identiques à un appel réel | STM consommée, entrées REFLECTION/concepts écrites en LTM, mêmes logs — seul l'appel réseau disparaît |

## Actions

### A1 — Store de mémoïsation
KV persistant adressé par contenu (SQLite ou collection Qdrant dédiée `stm_reflections`,
lookup par filtre exact sur le hash — **pas d'embedding**, il n'y a rien à
rapprocher). Valeur : `reflection`, `concepts`, horodatage, modèle. Répertoire
voisin du cache décisions (`data/cache/llm/...`), partagé entre runs d'une même
population.

### A2 — Branchement dans `reflect_on_short_term_memory` (et réflexion LTM)
Calcul du hash avant `llm_client.execute` ; hit ⇒ D4, miss ⇒ appel puis store
(sauf D3). Compteurs dédiés (`reflection_cache_hits/misses`) exposés au cockpit,
distincts du cache décisions.

### A3 — Validation du déterminisme du vécu
Le gain repose sur des `experiences_text` identiques entre re-runs. Auditer le
contenu des observations STM : toute fuite d'horloge **réelle** (wall-clock,
latences, ordre d'arrivée non déterministe) casse l'empreinte. Mesure de
référence : rejouer le scénario épinglé deux fois et publier le taux de hit —
c'est LE critère d'acceptation (attendu : ≈ 100 % au 2ᵉ passage ; constaté bas ⇒
lister et corriger les sources de non-déterminisme).

### A4 — Doc
`docs/arch/cache-memory.md` : nouvelle section « Mémoïsation des réflexions »,
avec la frontière explicite décisions (cache par contexte, sémantique autorisée)
vs réflexions (mémoïsation exacte uniquement). `docs/arch/memory-stm-ltm.md` :
le hit n'altère pas la sémantique mémoire (D4).

## Critères d'acceptation

1. Re-run du scénario de référence : taux de hit réflexions ≈ 100 %, zéro appel
   LLM de réflexion payé au 2ᵉ passage (A3).
2. Premier run d'un scénario neuf : comportement inchangé (0 % de hit, aucun
   surcoût mesurable du hash).
3. Aucune réflexion servie à un autre agent ou pour un vécu différent —
   garanti par construction (D1), vérifié par test unitaire sur la clé.
4. Compteurs cockpit distincts du cache décisions (A2).

## Articulation avec le ticket 010

Complémentaires, pas concurrents : la mémoïsation annule le coût des réflexions
sur les **re-runs** ; le drainage nocturne (010) absorbe le pic du soir sur les
**premiers runs**, où le hit est nul par définition. Les deux ensemble couvrent
les deux régimes.

## Contexte chiffré

- 2026-08-03 (1 000 agents, NO_GOOGLE) : 247 réflexions / 30 min au pic du soir,
  0 % cachées ; décisions au même moment : 99 % de hits.
- Chaque réflexion ≈ 1 requête pleine (identité + vécu complet) sur le quota
  requêtes/jour — le poste dominant d'une relance de run de référence.
