# Ticket 055 — Synthèse du benchmark multi-modèles et variabilité inter-graines sous prompt factuel neutre (Chapitre 5)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 suite à l'arbitrage de la tâche 10 de [`docs/paper/suivi_actions_publication.md`](../paper/suivi_actions_publication.md).
>
> **Touche l'article** : rédaction et calage de [`docs/paper/article/fr/05_factual_neutral_prompt.md`](../paper/article/fr/05_factual_neutral_prompt.md) (§ 5.2 & § 5.3).

## Contexte & Enjeux Scientifiques (AAMAS)

Le chapitre 5 évalue les capacités intrinsèques des modèles de fondation génériques sur étagère placés sous un prompt factuel neutre et circonstancié (Palier 1 de l'ablation, *Zero Prompt Engineering*).

Pour que cette évaluation soit inattaquable lors de la relecture par les pairs :
1. **Indépendance vis-à-vis du fournisseur** : il faut prouver que les résultats observés (effondrement de la marche, sur-représentation du vélo, insensibilité aux courtes distances) ne sont pas un artefact propre à Google Gemini, mais une régularité structurelle commune aux grands modèles de langue.
2. **Variabilité inter-graines pour un même modèle** : il convient de quantifier rigoureusement la dispersion des résultats pour un même modèle exécuté avec différentes graines aléatoires (`seeds = [0, 42, 123, 999, 2026]`), à la fois à l'échelle agrégée (écart-type $\sigma$ des parts modales) et à l'échelle micro-individuelle (taux de bascule individuelle, *churn* décisionnel).

## Ce que le ticket livre dans `fr/05_factual_neutral_prompt.md`

1. **Tableau synthétique multi-modèles au § 5.2 :**
   - Comparer les familles représentatives (Google Gemini 3.1/3.5 Flash-Lite, Mistral Small/Large, Qwen 27B/32B, Gemma) sur la cohorte scellée :
     * Parts modales agrégées (Voiture, TC, Marche, Vélo)
     * Erreur $L_1$ composite et divergence JSD
     * Exactitude désagrégée et entropie croisée
   - Rédiger l'analyse des invariants comportementaux (confirmation du biais structurel universel face à la voirie physique).

2. **Étude de variabilité inter-graines au § 5.3 :**
   - Documenter les résultats des 5 graines indépendantes pour le modèle de référence à température $\tau = 0{,}0$ :
     * Dispersion macro-distributionnelle : écart-type $\sigma$ sur chaque mode (montrant une stabilité globale, ex. $\Delta < 1$ pt).
     * **Taux de bascule individuelle** : pourcentage de décisions dont le mode retenu permute d'un run à l'autre pour le même persona et le même déplacement.
     * Cadrage du **test de McNemar** sur décisions appariées pour discriminer les variations réelles des fluctuations stochastiques résiduelles.

3. **Ajout du footer des tickets associés** au bas de `05_factual_neutral_prompt.md`.

## Critères d'acceptation
- [ ] Le tableau comparatif multi-modèles est inséré et analysé au § 5.2.
- [ ] La quantification de la variabilité inter-graines (macro $\sigma$ et taux de bascule micro) est rédigée au § 5.3.
- [ ] Le protocole de test de McNemar apparié est formellement posé.
- [ ] Le footer de `05_factual_neutral_prompt.md` référence le ticket 055.
