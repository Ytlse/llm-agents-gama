# Ticket 058 — Clarification du périmètre et méthodologie de l'audit unitaire à parité des 21 variables (Chapitre 6 § 6.3)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 suite à l'arbitrage de la tâche 15 de [`docs/paper/suivi_actions_publication.md`](../paper/suivi_actions_publication.md).
>
> **Touche l'article** : mise à jour et clarification méthodologique de la section 6.3 de [`docs/paper/article/fr/06_ablation.md`](../paper/article/fr/06_ablation.md).

## Contexte & Enjeux

Le brouillon actuel du chapitre 6 (§ 4.3 du fichier hérité de la v1.6) mentionne un audit unitaire sur un échantillon de $1\,000$ trajets extraits des microdonnées de l'enquête EMC² (`mode_choice_test.csv` issu de `eval_llm_on_survey.py`). 

Or, le reste de l'article a été réaligné sur un substrat unique en simulation : la **cohorte scellée v5** ($1\,000$ personas, $3\,299$ trajets cycliques). 

Il est nécessaire de clarifier et d'auditer méthodologiquement ce que mesure l'audit unitaire désagrégé :
1. **Mesure sur la cohorte scellée v5** : comparer les choix trajet par trajet entre le LLM et les modèles tabulaires sur les $3\,299$ déplacements contraints par les chaînes de la journée.
2. **Mesure sur l'enquête réelle (1 000 trajets)** : évaluer l'accord unitaire direct du LLM face aux choix réels déclarés par les Toulousains dans l'enquête.

## Ce que le ticket livre

1. **Arbitrage méthodologique du périmètre unitaire :**
   - Décider si l'audit unitaire du Chapitre 6 porte sur la cohorte scellée v5 (cohérence globale avec le reste de l'ablation), sur le sous-échantillon d'enquête (confrontation au sol réel), ou sur une présentation articulée des deux.
2. **Harmonisation des métriques micro-décisionnelles :**
   - Définir les indicateurs à publier à ce niveau de granularité : matrice de confusion 4x4, exactitude globale, entropie croisée et rappel par mode.
3. **Mise à jour rédactionnelle du § 6.3 de `fr/06_ablation.md` :**
   - Réécrire la section pour éliminer les anachronismes de la v1.6 et aligner rigoureusement la description sur le substrat et le protocole retenus.
4. **Ajout du footer des tickets associés** au bas de `06_ablation.md`.

## Critères d'acceptation
- [ ] Le périmètre de données de l'audit unitaire est explicitement tranché et documenté.
- [ ] La règle de parité des 21 variables est vérifiée sur les jeux de données évalués.
- [ ] La section 6.3 est réécrite en totale cohérence avec les chapitres 4 et 5.
- [ ] Le footer de `06_ablation.md` référence le ticket 058.
