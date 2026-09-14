# Ticket 063 — Campagne expérimentale longitudinale d'hystérésis et d'érosion mémorielle (Étape 3a)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ce ticket cadre l'exécution technique, les runs et le traitement des données de l'Étape 3a pour le Chapitre 7 (`docs/paper/article/fr/07_untabulated_regimes.md`).
> Il est directement articulé avec le ticket de cadrage conceptuel : [Ticket 041](ticket_041_etape_3a_hysteresis_longitudinale.md) et le protocole détaillé [`docs/paper/methode/experience_plan/ETAPE_3A_PLAN_LONGITUDINAL.md`](../paper/methode/experience_plan/ETAPE_3A_PLAN_LONGITUDINAL.md).
> **Principe de neutralité empirique :** ce document ne préjuge d'aucun résultat chiffré avant l'exécution complète de la campagne.

---

## 1. Périmètre de la Campagne Expérimentale

La campagne compare la trajectoire décisionnelle d'une sous-cohorte d'agents sur plusieurs jours simulés consécutifs autour d'un incident de transport aigu (panne majeure au jour J2, rétablissement nominal à J3) sur trois bras d'évaluation :

1. **Bras M (LLM + Mémoire) — Tâche 37 :**
   - Modèle de référence sous prompt calibré avec module de mémoire épisodique actif (persistance des retards et souvenirs d'incidents).
2. **Bras A (LLM Amnésique — Contrôle) — Tâche 38 :**
   - Même modèle et même prompt, mais mémoire réinitialisée à chaque décision (mesure de la réaction pure sans mémoire).
3. **Bras O (Oracle Tabulaire — Contrôle) — Tâche 39 :**
   - Décideur LightGBM tabulaire recevant l'offre physique à chaque pas (mesure de la reprise nominale instantanée par construction).
4. **Bras Variantes de Sensibilité (Taux d'oubli $\lambda$) — Tâche 40 :**
   - Exploration paramétrique de la vitesse d'érosion du souvenir pour tester la robustesse de l'inertie cognitive.

---

## 2. Données à Collecter & Traitements

Pour chaque agent, chaque jour $t \in [1, D]$ et chaque déplacement récurrent :
- Distribution de probabilité verbalisée émise par le modèle.
- Mode effectif retenu (tirage probabiliste seedé).
- Souvenirs présentés dans le contexte de prompt.
- Justification textuelle qualitative de l'évitement ou de la fidélité.
- Métriques de retour : taux d'évitement à J+1, demi-vie de résorption de l'incident, part résiduelle permanente de report modal.

---

## 3. Livrables & Dépendances

1. Fichiers de logs et d'échanges (`moves.csv`, `llm_exchanges.jsonl`, instantanés mémoire).
2. Script de dépouillement et de génération des courbes d'hystérésis pour la Figure 4 du Chapitre 7.
3. Renseignement des métriques observées dans `07_untabulated_regimes.md`.
