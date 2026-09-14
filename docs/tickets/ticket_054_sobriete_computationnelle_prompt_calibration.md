# Ticket 054 — Cadrage de sobriété computationnelle et réécriture du chapitre 4.5 (Calibration du prompt)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 suite à l'arbitrage de la tâche 7 de [`docs/paper/suivi_actions_publication.md`](../paper/suivi_actions_publication.md).
>
> **Touche l'article** : réécriture et calage de [`docs/paper/article/fr/04.5_prompt_calibration.md`](../paper/article/fr/04.5_prompt_calibration.md).

## Contexte & Arbitrage Éditorial (Sobriété & Green AI)

Le brouillon initial du chapitre 4.5 consacrait un développement important à l'échec des algorithmes génétiques aveugles et à l'explosion computationnelle des tokens en simulation multi-agents.

L'arbitrage scientifique retenu réoriente profondément cette section :
1. **L'objet de l'article n'est pas le benchmark d'optimiseurs de prompts** : détailler des mécanismes génétiques invite les relecteurs à contester des hyperparamètres de recherche d'ordre zéro qui ne constituent pas le cœur scientifique de l'étude.
2. **Posture de sobriété computationnelle et écologique (*Green AI*)** : affirmer clairement qu'une optimisation combinatoire automatisée de prompts — qui exigerait des dizaines de milliers d'appels LLM redondants pour converger sur une population distribuée — a été **délibérément écartée par souci écologique et méthodologique**.
3. **Explication synthétique du principe sans étalage d'artéfacts** : expliquer succinctement ce qu'une telle optimisation aurait requis (espace discret, évaluation distributionnelle), pourquoi elle est disproportionnée, et comment le prompt qualitatif retenu (Palier 2) a été stabilisé de manière sobre et transparente (zéro seuil chiffré, hypothèses comportementales explicites).

## Ce que le ticket livre dans `fr/04.5_prompt_calibration.md`

1. **Allègement du § 4.5.2 (Abandon du génétique lourd) :**
   - Remplacer l'exposition longue des équations génétiques par un argument de sobriété : la recherche combinatoire aveugle est disproportionnée d'un point de vue énergétique et environnemental.
   - Mentionner en une phrase ce qu'aurait impliqué un tel schéma ($G \times P \times N$ inférences) pour justifier immédiatement son exclusion au profit d'une approche parcimonieuse.
2. **Recentrage du § 4.5.3 sur la conception qualitative sobre :**
   - Présenter le prompt calibré (Palier 2) non comme le produit d'une usine à gaz automatisée, mais comme un jeu d'hypothèses comportementales réfléchies (coûts fixes d'accès au véhicule, pénibilité perçue).
3. **Maintien ferme des garde-fous (§ 4.5.4) :**
   - Sanctuariser l'absence totale de seuils numériques ou de pourcentages locaux (« règle du zéro seuil ») pour garantir la transférabilité.
4. **Ajout du footer des tickets associés** au bas de `04.5_prompt_calibration.md`.

## Critères d'acceptation
- [ ] Le texte du chapitre 4.5 n'étale plus de calculs lourds d'algorithmes génétiques.
- [ ] L'argument de sobriété écologique et computationnelle est clairement posé.
- [ ] Le statut du Palier 2 comme prompt qualitatif sans seuil est préservé.
- [ ] Le footer de `04.5_prompt_calibration.md` référence le ticket 054.
