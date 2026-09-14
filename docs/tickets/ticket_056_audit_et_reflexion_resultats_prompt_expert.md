# Ticket 056 — Audit méthodologique, vérification de la chaîne de mesure et réflexion sur les résultats du prompt expert (v2/v4)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 suite à l'arbitrage de la tâche 13 de [`docs/paper/suivi_actions_publication.md`](../paper/suivi_actions_publication.md).
>
> **Nature du ticket** : **Tâche d'audit critique, de vérification expérimentale « ceinture et bretelles » et de réflexion méthodologique.** Il ne s'agit pas d'acter prématurément un résultat spectaculaire dans le texte de l'article, mais de disséquer la chaîne de mesure, d'éprouver la robustesse des chiffres observés et de comprendre les causes réelles avant d'en tirer des conclusions pour le Chapitre 6.

---

## 1. Contexte & Déclencheur

La synthèse des runs récents sur la cohorte scellée v5 fait apparaître une rupture inattendue :
- Sous prompt minimal, Gemini 3.5 obtient un composite de **$8{,}94$** (et Gemini 3.1 **$14{,}22$**).
- Sous prompt expert v2 (`expert_gem_3.8_v2`), le composite chute brutalement à **$5{,}3452$** et la métrique 2 (distribution des parts) tombe à **$8{,}091$**, passant en apparence devant les modèles tabulaires en chaîne (LightGBM : $10{,}4569$).
- Mais la variante v3 (`expert_gem_3.8_v3`) remonte aussitôt à **$9{,}3232$**.

Face à une amélioration aussi brutale et non monotone, l'exigence de rigueur scientifique impose de refuser tout triomphalisme prématuré. Avant d'affirmer un tel résultat dans un papier AAMAS, il faut impérativement vérifier qu'il ne s'agit pas d'un biais de mesure, d'une fuite d'information ou d'un artefact méthodologique.

---

## 2. Programme d'Audit « Ceinture et Bretelles »

### 2.1 Audit de la chaîne de calcul des métriques
* **Homogénéité stricte des formules** : Vérifier terme à terme que la fonction de calcul des métriques (`score-synthesis`, `metrics.py`, `eval_mode_choice.py`) traite les fichiers de résultats tabulaires et LLM de manière rigoureusement identique.
* **Vérification de la Métrique 2 et du Composite** : 
  - Comment sont calculés exactement le $5{,}3452$ (composite) et le $8{,}091$ (métrique 2) ?
  - La gestion des poids par persona, des décisions contraintes et des cas d'exclusion est-elle strictement identique entre le bras tabulaire et le bras LLM ?
* **Contrôle des dénominateurs et effectifs** : S'assurer que le nombre effectif de décisions scorées est rigoureusement le même sur les deux bras (contrôle du dénominateur d'évaluation).

### 2.2 Audit du contenu du prompt expert v2
* **Chasse aux fuites d'information (*Data Leakage*)** :
  - Vérifier méticuleusement le texte de `expert_gem_3.8_v2` : contient-il, sous une forme ou une autre, des priors implicites calqués sur l'enquête toulousaine (ex. formulation orientant vers le ratio modal exact de l'agglomération) ?
  - Le prompt respecte-t-il rigoureusement la « Règle du zéro seuil » (aucun chiffre de distance, aucun seuil kilométrique, aucune part cible) ?
* **Différentiel v2 vs v3** :
  - Poser un `diff` textuel exhaustif entre la variante v2 ($5{,}34$) et la variante v3 ($9{,}32$).
  - Identifier la modification exacte qui a provoqué une telle dégradation : est-ce un effet de sur-spécification ? Une formulation contradictoire ? Une rupture de format ?

### 2.3 Protocole de réplication et validation croisée (v4)
* **Test de réplication multi-graines sur la v2** : Rejouer la condition `expert_gem_3.8_v2` avec 2 ou 3 autres graines aléatoires pour vérifier si le $5{,}34$ est stable ou s'il s'agit d'un artefact d'échantillonnage chanceux.
* **Évaluation de la variante v4 en cours** : Mesurer la v4 sur le même jeu et observer si la tendance se confirme ou si le comportement diverge.
* **Inspection qualitative des décisions** : Comparer 50 décisions unitaires où le prompt minimal échouait et où la v2 bascule vers le choix de l'enquête : l'explication verbale fournie par le LLM relève-t-elle d'un raisonnement contextuel plausible ou d'une heuristique artificielle ?

---

## 3. Ce que le ticket livre

1. **Rapport d'audit technique et méthodologique** consigné dans le dépôt (validation de la chaîne de calcul, confirmation ou invalidation de l'intégrité de la mesure).
2. **Comparaison contrôlée v2 / v3 / v4** explicitant les mécanismes textuels qui font varier le score.
3. **Recommandation d'arbitrage pour le Chapitre 6** :
   - Si l'audit confirme la validité et la robustesse de la mesure : formuler les conclusions prudentes sur la frontière macro/micro.
   - Si l'audit révèle un biais, une fuite ou une instabilité stochastique : corriger la méthodologie avant toute rédaction.

## Critères de clôture
- [ ] La chaîne de calcul des métriques a été auditée et validée sans anomalie de code.
- [ ] Le prompt v2 a été audité et certifié sans fuite de priors locaux ni violation du zéro seuil.
- [ ] L'écart v2 vs v3 est scientifiquement expliqué par l'analyse des rationales.
- [ ] La variante v4 a été mesurée et intégrée à l'analyse comparative.
- [ ] Aucune affirmation prématurée n'est introduite dans `fr/06_ablation.md` tant que cet audit n'est pas validé.
