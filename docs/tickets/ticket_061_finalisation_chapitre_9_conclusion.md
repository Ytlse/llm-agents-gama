# Ticket 061 — Finalisation et consolidation du Chapitre 9 (Conclusion & Enseignements fondamentaux)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ce ticket cadre la structure conceptuelle et la rédaction finale du Chapitre 9 (`docs/paper/article/fr/09_conclusion.md`).
> **Principe de neutralité empirique :** ce document est strictement agnostique sur les chiffres finaux ; aucun résultat prématuré n'est figé avant la stabilisation de l'ensemble des runs et des audits.

---

## 1. Contexte & Enjeux

Le Chapitre 9 constitue la conclusion générale de l'article pour AAMAS 2027. Son objectif est de synthétiser les contributions scientifiques, de dépasser les oppositions binaires (« LLM vs Machine Learning tabulaire ») et d'apporter des enseignements méthodologiques durables et transférables à la communauté des systèmes multi-agents (MAS).

---

## 2. Structure des 4 Enseignements Fondamentaux

Le chapitre articule la conclusion autour de quatre axes majeurs :

### 2.1 Délimitation du périmètre des LLMs face à la prédiction de masse statique
- Rappeler les limites fondamentales des agents LLM lorsqu'ils sont employés hors contexte pour reproduire des distributions statistiques de masse sans calage ad hoc.
- Souligner l'adéquation des modèles supervisés / économétriques spécialisés pour les flux nominaux de routine (vitesse de traitement, coût nul en inférence, alignement direct avec les distributions observées).

### 2.2 La valeur ajoutée propre des agents cognitifs : contexte, sémantique et mémoire
- Situer l'apport irremplaçable des LLMs là où les modèles statistiques sont structurellement inopérants (incompressibilité tabulaire).
- Mettre en valeur la prise en compte du bon sens urbain, des événements qualitatifs imprévus (presse locale, perceptions sensorielles, paniques morales) et de la persistance temporelle des souvenirs (dynamique d'hystérésis et d'évitement post-incident).

### 2.3 Enseignement méthodologique transférable pour la communauté multi-agents
- Formuler l'avertissement central sur la métrologie des agents : *l'évaluation d'un agent de simulation doit être réalisée dans son environnement opérationnel dynamique (contraintes physiques de réseau, chaînage temporel des activités, conservation des véhicules), et non sur un benchmark statique décontextualisé.*
- Démontrer le risque de décorrélation entre une bonne performance de classification isolée sur table et une mauvaise simulation systémique.

### 2.4 Synthèse prospective de l'architecture hybride en cascade
- Proposer l'hybridation modulaire comme voie de dépassement pragmatique : délégation des flux standards aux modèles tabulaires rapides, et réservation des capacités agentiques génératives aux situations d'exception et contextes riches.

---

## 3. Livrables

1. Rédaction finale et harmonisation du texte dans `docs/paper/article/fr/09_conclusion.md`.
2. Injection des chiffres et ordres de grandeur définitifs une fois l'ensemble des campagnes consolidées.
3. Alignement avec les orientations de l'Abstract (Chapitre 0) et de l'Introduction (Chapitre 1).
