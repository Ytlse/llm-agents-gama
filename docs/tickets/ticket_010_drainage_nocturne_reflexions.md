# Ticket 010 — Drainage nocturne des réflexions STM

Accepter que le stock de réflexions STM se draine **lentement pendant la nuit simulée**,
au lieu de le traiter comme une saturation du pipeline. Les agents dorment : la fenêtre
nocturne n'a presque aucune décision d'itinéraire à servir, c'est la capacité LLM
disponible idéale pour un poste de consommation incompressible.

**Pourquoi ce ticket** : campagne du 2026-08-03 (1 000 agents, `NO_GOOGLE=1`, cascade
mistral/groq/cerebras). En soirée simulée (19 h→22 h), la file LLM a reçu **247 réflexions
STM pour 13 décisions d'itinéraire** sur 30 min : les agents rentrent le soir avec leurs
mémoires pleines (≥ 10 entrées) et déclenchent tous leur réflexion dans la même fenêtre.
Résultat : backlog à 80 % de la population et alarme `[ALARME] Backlog critique` à
13:52:34 — alors que **rien n'était dégradé** : `late_since_last_sync=0` sur tout le run,
décisions servies par le cache à 99 %, providers sains. L'alarme criait au feu sur un
embouteillage bénin.

**Le fond du problème** : les réflexions sont le poste LLM qui ne bénéficie d'aucun
cache sur un **premier run**. Le prompt contient le vécu réel de l'agent
(`experiences_text`, llm_agent.py) : unique par agent et par fenêtre, consommé après
usage, écrit en LTM. Tout rapprochement approximatif (sémantique, inter-agents)
reviendrait à servir l'introspection d'un autre — repli dégradé interdit. Sur un
run inédit, la seule variable d'ajustement est donc **quand** on les exécute, jamais
**si** on les exécute. (Les **re-runs déterministes**, où le vécu est byte-identique,
relèvent de la mémoïsation exacte — ticket [012](ticket_012_memoisation_reflexions.md),
complémentaire.)

---

## Décisions structurantes

| # | Point | Conséquence opératoire |
|---|---|---|
| D1 | Aucune réflexion n'est abandonnée ni tronquée | Pas de dégradation scientifique : on déplace la charge dans le temps, on ne la réduit pas |
| D2 | Échéance naturelle d'une réflexion = le **réveil de son agent** | La LTM du matin doit intégrer la veille : la réflexion doit être terminée avant la première décision du lendemain de l'agent. C'est la deadline EDF, pas une deadline « au plus vite » |
| D3 | Un backlog de réflexions n'est pas un backlog de décisions | L'alarme backlog doit distinguer les deux compositions avant de crier |

---

## Actions

### A1 — Deadline EDF des réflexions = réveil de l'agent
Aujourd'hui les réflexions STM sont ordonnées EDF (échéance posée au déclenchement,
conservée entre retentatives). Poser l'échéance au **réveil de l'agent le lendemain**
(première activité planifiée du jour suivant) plutôt qu'à la soumission : les décisions
d'itinéraire du soir passent mécaniquement devant, et le stock de réflexions se draine
toute la nuit dans l'ordre des réveils (les lève-tôt d'abord).

**Vérification** : sur un run 24 h+, aucune décision d'itinéraire retardée par une
réflexion (comparer les latences de planification soir vs journée) ; aucune réflexion
terminée après la première décision du lendemain de son agent.

### A2 — Alarme backlog : distinguer réflexions et décisions
`[ALARME] Backlog critique` ne doit se déclencher que si des **décisions d'itinéraire**
s'accumulent ou si `late_since_last_sync > 0`. Un backlog dominé par des réflexions
pendant la nuit simulée (agents idle au domicile) est le fonctionnement nominal → log
INFO avec composition (`backlog: N décisions + M réflexions`), pas ERROR.

**Vérification** : rejouer le profil du 2026-08-03 → plus d'alarme à 13:52 ; une
accumulation de vraies décisions déclenche toujours.

### A3 — Drainage post-pause (`simulation_max_days`)
À la pause GAMA de fin d'horizon, le controller doit finir de drainer le stock de
réflexions avant l'arrêt du run (elles écrivent en LTM, utile pour les runs qui
reprennent cette population). Vérifier le comportement actuel, le documenter, et si le
drainage s'interrompt, le maintenir jusqu'à épuisement de la file.

**Vérification** : à la fin d'un run, file de réflexions vide dans les logs ; entrées
REFLECTION présentes en LTM pour les agents dont la réflexion était en attente à minuit.

### A4 — Composition de la file au cockpit
Exposer la métrique file LLM par catégorie (`itinary_multi_agent` vs `stm_reflection`)
pour Grafana : c'est la donnée qui a permis le diagnostic du 2026-08-03, elle doit être
lisible en un coup d'œil au lieu d'un grep dans les logs api.

---

## Critères d'acceptation

1. Run 24 h+ sans Google : zéro décision d'itinéraire retardée par la vague de
   réflexions du soir (`late_since_last_sync=0` maintenu).
2. Chaque réflexion exécutée avant le réveil de son agent (D2) — mesurable dans les logs.
3. L'alarme backlog ne se déclenche plus sur un drainage nocturne nominal, et se
   déclenche toujours sur une vraie saturation de décisions (A2).
4. Panneau Grafana « composition de la file LLM » en place (A4).

---

## Contexte chiffré (run 2026-08-03, référence du diagnostic)

- 1 000 agents (930 après bbox), `NO_GOOGLE=1`, cascade mistral + groq ×4 + cerebras ×3
- Soirée simulée : 247 `stm_reflection` vs 13 `itinary_multi_agent` sur 30 min
- Backlog : 136 (10 h sim) → 821 (22 h sim), croissance monotone
- Cache décisions : 99 % de hits (2 613/2 620) · `late_since_last_sync=0` sur tout le run
- Backpressure : min_interval monté à 21,6 s (cap 30 s) — a fonctionné, mais a caché que
  la charge était des réflexions
