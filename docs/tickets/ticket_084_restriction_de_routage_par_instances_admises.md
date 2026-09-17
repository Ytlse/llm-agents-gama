# Ticket 084 — Une requête peut désigner les instances admises à la servir

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert et **livré le 2026-09-16**, 27 tests dédiés. Contrat : `specs/ticket_084/tests.md`,
> écrit avant le code.
>
> **Objet.** Permettre à une requête de déclarer la **liste** des instances de passerelle
> autorisées à la servir, et faire honorer cette liste **à la sélection** — donc avant qu'un
> appel ne soit payé.

---

## 1. Le besoin, et pourquoi rien ne le couvrait

Mener une expérience sur une famille de modèles pendant que la passerelle en sert d'autres à un
autre travail. Le cas concret du 2026-09-16 : une session mesure la mémoire des agents sous
gemini 3.1 tandis qu'une autre a besoin de gemini 3.5 et des neuf autres instances Google.

Trois mécanismes existaient, aucun ne répond.

| Mécanisme | Ce qu'il fait | Pourquoi il ne suffit pas |
|---|---|---|
| `LLM_GATEWAY_PROVIDERS_FILE` | restreint le jeu d'instances chargées | **global à la pile** : api, worker et contrôleur partagent une seule valeur, donc un seul travail à la fois |
| `force_provider` | épingle **une** instance | pas de basculement entre deux clés d'un même modèle : le run s'arrête au premier quota plein |
| `allowed_providers` (côté client) | refuse une réponse venue d'ailleurs | **après coup** : l'appel est déjà payé, et la passerelle n'a jamais su qu'une liste existait |

Le troisième est instructif : il a été ajouté après un incident du 2026-09-07 où une substitution
silencieuse avait invalidé une mesure. Il constate la violation, il ne l'empêche pas.

---

## 2. Ce qui est ajouté

Un champ `instances_admises` sur la requête, honoré par l'unique point de décision du routage.

```
llm_agent.py (payload)
  └─ LLMRequest.instances_admises          ← déclaré, sinon ignoré EN SILENCE (§ 4)
      └─ compute_batch_key                 ← sinon deux restrictions fusionnent (§ 4)
          └─ process_batch_task (Celery)
              └─ LoadBalancer.select_provider(admises=…)   ← LE point de décision
```

`None` ou liste vide : comportement rigoureusement identique à avant le ticket. C'est la
condition pour que les mesures déjà prises restent comparables.

**Les trois branches de la sélection** sont couvertes : fournisseur forcé, cascade, rotation
pondérée. La cascade **conserve son ordre** et ne réduit que l'ensemble : la priorité déclarée
dans la configuration reste la priorité sous restriction. Dans la rotation, le curseur avance
même sur une instance écartée, si bien que deux requêtes aux restrictions différentes ne se
décalent pas l'une l'autre.

---

## 3. Les cinq règles qui font la valeur du lot

**Une restriction fausse n'est jamais « aucune restriction ».** Une liste qui ne désigne aucune
instance connue, ou qui en mêle des inconnues, lève `RestrictionInstances`. Une faute de frappe
qui vaudrait « sers-toi partout » rendrait douteuse toute mesure prise sous restriction, sans
qu'aucune ligne ne le signale. Une liste à moitié fausse est une erreur de configuration, pas une
restriction partielle à deviner.

**Aucun recours hors de l'ensemble.** Toutes les admises saturées lève une erreur qui **les
nomme** et ne propose pas les autres. C'est la règle du dépôt : on attend le renouvellement, on
ne dégrade pas.

**Deux contraintes contradictoires sont refusées.** Un fournisseur forcé hors des admises ne
donne lieu à aucun arbitrage silencieux : servir l'épinglé ignorerait la restriction, l'inverse
ignorerait l'épinglage.

**La restriction survit à la bascule.** C'est le point que la première rédaction du plan avait
manqué. Le worker relance la tâche avec un autre fournisseur après une erreur 4xx, une réponse
illisible ou des crédits épuisés, et ce rejeu repartait en rotation **libre**. Sans report
explicite, la restriction disparaissait au premier incident et le lot pouvait finir servi par un
modèle exclu. Les trois chemins de bascule la reportent désormais.

**Le dimensionnement suit.** La taille maximale d'un lot et le seuil de dispatch se calculent sur
les instances admises, pas sur l'ensemble des fournisseurs : dimensionner sur des capacités
inatteignables produirait des lots que personne ne peut servir.

---

## 4. Deux pièges qui ne se voient pas

**`LLMRequest` n'interdit pas les champs supplémentaires.** Un champ posé par le client sans être
déclaré dans le modèle est ignoré par la validation — ni exception, ni journal. Une restriction
qui n'aurait jamais existé, et une mesure réputée restreinte. Le cas B1 du contrat garde cette
propriété.

**La clé de lot est la seule garde contre le mélange.** Un lot est servi par UNE instance : deux
requêtes aux restrictions différentes fusionnées dans le même lot feraient servir l'une par un
fournisseur qu'elle excluait. Les instances entrent dans la clé **triées et dédupliquées** —
c'est un ensemble, pas une séquence.

⚠ **Défaut antérieur repéré et NON corrigé ici** : le budget de sortie (`min_output_required`)
n'entre pas dans la clé de lot, alors que le fournisseur forcé et le débit minimal y sont. Deux
requêtes aux budgets différents peuvent déjà se retrouver dans le même lot. Hors périmètre,
signalé, à traiter dans son propre ticket.

---

## 5. Usage

```yaml
# services/llm-agents/config/config.yaml
llm:
  instances_admises: [google_gemini31_key1, google_gemini31_key2]
```

Les onze instances Google restent chargées pour les autres travaux ; les décisions de ce run ne
peuvent être servies que par les deux clés gemini 3.1, avec basculement de l'une à l'autre.

---

## 6. Ce que le ticket ne change pas

Le filtre client `allowed_providers` est **conservé** et devient une défense en profondeur : il
constate après coup ce que la restriction empêche désormais. Il ne devrait plus jamais se
déclencher quand la liste est transmise, et s'il se déclenche c'est une régression côté
passerelle — ce qui est exactement l'emploi d'un filet.

Une requête sans restriction se comporte comme avant, sur les trois branches de la sélection.

---

## 7. Une régression trouvée en chemin

Le réglage `llm_params` de la configuration de run **remplace** le dictionnaire par défaut au
lieu de s'y ajouter. En y posant la variante de prompt, température, top_p et budget de sortie
avaient disparu des appels. Trouvé par le test de régénération du journal du ticket 081, qui a vu
la colonne « Température » diverger. Les trois valeurs sont désormais recopiées dans le bloc, avec
l'avertissement qui explique pourquoi.
