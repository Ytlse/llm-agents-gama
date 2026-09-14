# Ticket 064 — Campagne expérimentale de presse locale à 5 conditions et scoring de réfutation (Étape 3b)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ce ticket cadre l'exécution technique des simulations et le dépouillement statistique de l'Étape 3b pour le Chapitre 7 (`docs/paper/article/fr/07_untabulated_regimes.md`).
> Il est directement articulé avec le ticket de cadrage méthodologique : [Ticket 059](ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees.md) et la grille pré-enregistrée [`docs/paper/sources/actualites/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md`](../paper/sources/actualites/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md).
> **Principe de neutralité empirique :** ce document ne préjuge d'aucun score chiffré avant la finalisation de la campagne d'inférence.

---

## 1. Périmètre de la Campagne d'Évaluation

La campagne applique le protocole à cinq conditions expérimentales sur les scénarios majeurs d'actualité locale toulousaine (sélection du Top 5 comportemental : vent d'Autan, crise des punaises de lit, grève des éboueurs, spectacle La Machine, vélos partagés électriques en colline) :

1. **Exécution des 5 conditions expérimentales (Tâche 41) :**
   - **Condition C1 (Nominal) :** Inférence baseline sans contexte presse.
   - **Condition C2 (Article Brut) :** Injection du texte journalistique réel.
   - **Condition C3 (Paraphrase sans indice modal) :** Injection de la version réécrite neutralisant tout nom de mode de transport.
   - **Condition C4 (Article Placebo) :** Injection d'un article local neutre/sans impact mobilité.
   - **Condition C5 (Oracle Encodé) :** Référence tabulaire avec perturbation physique/météo encodée numériquement.

2. **Scoring et test formel de réfutation (Tâche 42) :**
   - Extraction des reports modaux observés pour chaque condition.
   - Confrontation à la grille pré-enregistrée gelée (direction attendue et intensité ordinale de $0$ à $3$ étoiles).
   - Calcul des métriques de validation : taux d'accord de signe $S_{\text{sign}}$, test binomial contre l'hypothèse nulle ($50\,\%$), et concordance ordinale ($\kappa$ de Cohen pondéré).
   - Application stricte des critères de réfutation de l'hypothèse $H_3$.

---

## 2. Livrables & Dépendances

1. Scripts d'injection textuelle et d'orchestration des requêtes (`scripts/analysis/eval_presse_locale.py` ou runner dédié).
2. Tableau de résultats consolidé des 5 conditions pour chaque scénario.
3. Rapport statistique de validation directionnelle et mise à jour de `07_untabulated_regimes.md`.
