# Ticket 105 — Un repli par défaut n'est pas une décision

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-23, après l'arrêt de la campagne c3 v4 sur saturation amont : quatre
> décisions prises par l'index 0 s'étaient inscrites dans la fenêtre de mesure sans que rien ne
> s'arrête ni ne le signale.

---

## 1. La question, en une phrase

Quand le modèle ne répond pas, un run d'expérience doit-il **continuer** avec le premier
itinéraire de la liste, ou **s'arrêter** ?

Le projet a déjà répondu, le 2026-09-21, dans le ticket 077 (axe 3) : *« le run s'arrête plutôt
que de laisser l'index 0 se faire passer pour une décision du modèle »*. Mais la condition posée
alors ne regarde qu'un seul motif — `genre_erreur == "quota_journalier"`. Tous les autres motifs
traversent le garde-fou.

## 2. Ce que ça a coûté, le 2026-09-23

La campagne `e_c3_attribution_861500_v4` a tourné 2 h 22 avant d'être arrêtée à la main.

| | |
|---|---|
| Avant le choc | 0 / 48 replis — ligne de base propre |
| Fenêtre de mesure | **4 / 39 = 10,3 %** |
| Position des replis | +5,8 ; +6,5 ; +6,6 ; +7,8 jours après le choc |

Cause amont, réponse de Google mot pour mot : `HTTP 503 — "This model is currently experiencing
high demand. Spikes in demand are usually temporary."`, statut `UNAVAILABLE`. 54 occurrences sur
la journée, montant de 1–2 par tranche de 10 min à 15 au plus fort. **Aucune erreur de quota ce
jour-là** : `RESOURCE_EXHAUSTED` = 0.

Une saturation ne renvoie donc pas de `genre_erreur` du tout — `error_kind` ne connaît
aujourd'hui que `quota_journalier` et `restriction_instances`. Le garde-fou du 077 ne pouvait pas
la voir.

## 3. Pourquoi c'est disqualifiant, et pas seulement du bruit

Un repli n'est pas une mesure manquante qu'on laisserait en blanc dans un tableau. Le code fait :

```python
plan_index = 0
selection_method = "LLM Error (Default index)"
```

puis `plan = itineraries[plan_index]`. **Le trajet a lieu.** L'agent part, arrive, et s'en
souvient. Ce souvenir fait partie de ce qu'il est le lendemain, et le mode emprunté entre dans la
statistique « habitude / rupture par activité » que l'expérience mesure. Quatre trajets choisis
par défaut dans la fenêtre où l'on cherche si le souvenir du choc casse l'habitude sont quatre
points versés au dénominateur de la réponse.

Écarter ces lignes après coup ne suffit pas : elles ont produit des effets en aval qu'aucun filtre
ne retire.

## 4. Ce qui change

### 4.1 Le garde-fou compte les replis, pas les motifs

Le critère d'arrêt ne cherche plus *pourquoi* le modèle n'a pas répondu. Il compte les décisions
**consécutives** qui n'ont pas été prises par le modèle, et arrête au seuil
(`replis_consecutifs_max`, 3 par défaut).

C'est délibérément plus large que la saturation : un motif qui n'existe pas encore sera couvert
sans qu'on ait à le prévoir. C'est aussi pourquoi le seuil n'est pas 1 — un 503 isolé est rattrapé
par les tentatives et ne produit aucun repli ; ce qu'on veut attraper est un régime, pas un
incident.

Le chemin `quota_journalier` du ticket 077 reste en place, inchangé : il sait, lui, à quelle heure
la reprise est possible.

### 4.2 Armé dans les expériences, muet ailleurs

`run_sequential_cohort.py` pose déjà `EXPERIMENT_HIBERNATE_ON_QUOTA=1` sur toute campagne. Le
garde-fou ride sur ce même verrou : **armé d'office dans les expériences sur la mémoire**, silencieux
dans un run ordinaire. La variable est renommée `EXPERIMENT_STOP_ON_FALLBACK` — elle ne parle plus
seulement de quota — et l'ancien nom reste admis comme alias.

### 4.3 Une reprise à chaud ne dédouble plus les trajets

Défaut découvert en instruisant ce ticket, indépendant de la saturation :
`reprise.restaurer_si_demande` n'appelle `ecarter_les_sorties_du_rejeu` que dans la branche
**« aucun point de reprise trouvé »**. Quand un point *est* trouvé, GAMA rejoue quand même les
jours déjà vécus, et `move_logger.py` n'a aucune connaissance du gel : les trajets rejoués
s'ajoutent à `moves.csv`, indiscernables des originaux.

C'est exactement le défaut qui avait dédoublé 84 trajets sur le run du ticket 075, et la fonction
écrite pour l'empêcher n'était pas appelée sur ce chemin-là. Elle l'est désormais sur les deux.

### 4.4 Un repli se voit

- Le repli était journalisé en `logger.debug` — invisible. Il passe en `logger.error` avec le
  préfixe `[ALARME]`, et nomme la personne, l'instant simulé et le compteur de replis consécutifs.
  `make error` le montre.
- `make report` compte les replis de `moves.csv`, **séparés avant / après l'événement**, avec le
  taux. C'est le chiffre qu'il a fallu reconstituer à la main le 2026-09-23 pour décider d'arrêter.

### 4.5 Le compteur journalier de Redis dit qu'il est local

Le 2026-09-23, ce compteur a été lu comme un budget et a servi à reporter une relance d'une
journée, pour rien. Le code disait pourtant déjà le contraire, depuis l'incident du 2026-09-08 :

> *« Le compteur local ne voit que le trafic de ce gateway, alors qu'une clé est aussi consommée
> par `scripts/synthesis/*` et `prompt_calibration` — le 2026-09-08 il affichait 49 requêtes sur
> 500 pendant que Google refusait pour dépassement des 500. »*

La docstring n'a pas suffi parce qu'elle n'est pas là où on lit le chiffre. Le **nom de la clé**
l'est : `rpd:` devient `rpd_local_seulement:`, `tpd:` devient `tpd_local_seulement:`, et les
accesseurs prennent le même suffixe. Un `redis-cli --scan` dit maintenant sa limite.

Au passage, `_mark_quota_exhausted` — la variante qui déciderait depuis le compteur local — est
**supprimée** : elle n'a aucun appelant depuis le 097, et du code mort qui ressemble à du code
vivant est précisément ce qui fait rebasculer dans l'erreur.

**Deux lecteurs de production existent**, contrairement à ce que laissait croire un premier
relevé trop court : `balancer/router.py` (dictionnaire de statut lu par le tableau de bord) et
`api/metrics.py` (jauges Prometheus). Aucun des deux ne **décide** — ils affichent. Leurs appels
sont renommés, mais **les noms de champ et de métrique restent inchangés** : le tableau de bord et
Grafana les lisent, et les casser coûterait sans rien apprendre à personne. Le commentaire posé à
ces deux endroits dit que le chiffre affiché sous-estime la consommation réelle.

## 5. Ce qui ne change pas

- Aucun repli dégradé n'est introduit ni toléré ailleurs : la règle reste qu'on attend plutôt que
  de servir une décision qui n'en est pas une.
- Le chemin `quota_journalier` et son marqueur `en_attente_quota.json` gardent leur comportement,
  heure de réouverture comprise.
- La marge déclarative de `providers.yaml` reste informative et ne décide toujours rien (ticket
  097).
- Hors expérience, un run continue de se rabattre comme avant : le garde-fou n'est pas armé.

## 6. Critères d'acceptation

- [ ] Trois replis consécutifs arrêtent proprement un run d'expérience ; deux replis séparés par
      une décision réussie ne l'arrêtent pas.
- [ ] Le garde-fou est muet quand le verrou d'expérience n'est pas posé.
- [ ] Le chemin `quota_journalier` existant conserve son comportement et son marqueur.
- [ ] Une reprise depuis un point valide met `moves.csv` de côté avant le rejeu.
- [ ] Un repli produit une ligne `[ALARME]` visible par `make error`.
- [ ] `make report` rend le taux de replis avant et après l'événement.
- [ ] Les clés Redis portent `local_seulement` ; `_mark_quota_exhausted` n'existe plus.
- [ ] Suite complète au vert.

## 7. La question ouverte, tranchée

**Un repli n'est pas mémorisé dans la trace de rejeu, et c'est le bon comportement.**

`rejeu_decisions.tracer` est appelé dans `llm_agent.py`, à l'intérieur du bloc où un `chosen_plan`
existe — donc uniquement sur une décision que le modèle a réellement prise. Le repli, lui, est
fabriqué plus loin, dans le contrôleur, après que l'agent a rendu un index invalide. Il ne passe
jamais par `tracer`.

Conséquence sur un rejeu qui traverserait une fenêtre contaminée : `chercher()` ne trouve rien,
la décision est **redemandée au modèle**, et le compteur `_manquees` monte. Au-delà de 20 % de
clés manquées (`SEUIL_ALARME_MANQUEES`), une alarme dit que le rejeu a divergé.

C'est préférable à l'inverse : tracer un repli le graverait dans la reprise, et chaque rejeu
ultérieur le resservirait. Le rejeu n'est alors plus identique au bit près — mais il est
**meilleur**, et la divergence est comptée et annoncée au lieu d'être silencieuse.

Rien à modifier. Sans effet sur la reprise décidée le 2026-09-23 de toute façon : le point
`jour_017` (1ᵉʳ avril 03:00) précède le premier repli (1ᵉʳ avril 19:38), la fenêtre rejouée est
propre.
