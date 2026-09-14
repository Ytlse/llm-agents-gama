# Ticket 053 — Modalités d'accès aux données d'enquête pour la recherche et protocole de reproductibilité (Chapitre 4 & Annexe G)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 suite à l'arbitrage de la tâche 6 de [`docs/paper/suivi_actions_publication.md`](../paper/suivi_actions_publication.md).
>
> **Touche l'article** : [`docs/paper/article/fr/04_metrics_and_substrate.md`](../paper/article/fr/04_metrics_and_substrate.md) (§ 4.4 & § 4.5) et [`docs/paper/article/fr/99_annexes.md`](../paper/article/fr/99_annexes.md) (Annexe G).

## Contexte & Enjeux

Les microdonnées de l'enquête ménages-déplacements certifiée Cerema de la grande agglomération toulousaine (EMC² 2023) constituent le socle de référence externe et le jeu d'entraînement des oracles statistiques. 

Ces données sont des **données publiques ouvertes à la recherche scientifique**, diffusées au niveau national par le portail Quetelet-Progedo-Diffusion (ADISP) sous le numéro de commande/convention `lil-1750`.
Conformément aux engagements légaux de non-cession à des tiers, ces microdonnées brutes ne peuvent pas être redistribuées dans une archive ZIP publique. En revanche, **tout relecteur ou chercheur tiers peut librement formuler une demande d'accès auprès du diffuseur officiel** pour obtenir les données et ré-exécuter le protocole d'évaluation.

## Ce que le ticket livre

1. **Précision dans le corps de l'article (Chapitre 4 § 4.4 & § 4.5) :**
   - Indiquer explicitement que les microdonnées d'enquête sont des données publiques de recherche accessibles auprès du diffuseur national (Quetelet-Progedo) sous protocole d'utilisation de recherche, sans redistribution directe dans le dépôt.
   - Pointer vers l'Annexe G pour la procédure d'accès détaillée et l'URL du portail.

2. **Documentation exhaustive dans l'Annexe G ([`fr/99_annexes.md`](../paper/article/fr/99_annexes.md)) :**
   - Fournir l'adresse exacte et la procédure pour les relecteurs :
     * Portail de diffusion : **Quetelet-Progedo-Diffusion** (ADISP) — `https://commande.progedo.fr/`
     * Référence catalogue de l'enquête : *Enquête Mobilité Certifiée Cerema (EMC²) de la Grande Agglomération Toulousaine, 2023* (Tisséo Collectivités / Cerema).
     * Modalités : demande d'accès en ligne avec engagement de recherche scientifique et respect du secret statistique.
   - Fournir le modèle officiel de citation obligatoire de la source.
   - Expliquer comment positionner les microdonnées téléchargées dans l'arborescence locale pour ré-exécuter en aveugle le pipeline d'évaluation (`eval_llm_on_survey.py`, découpage scellé des 13 045 trajets par ménage).

3. **Frontière claire de l'archive de soumission :**
   - L'archive de soumission (Supplementary Material) contient l'intégralité du code, des configurations (`experiments.yaml`), des graines et de la cohorte synthétique scellée v5 (auditable immédiatement sans démarche).
   - Les données réelles d'enquête sont récupérables directement via le portail officiel par tout pair souhaitant vérifier le volet d'entraînement de l'oracle.

## Critères d'acceptation
- [ ] Le Chapitre 4 mentionne clairement que les données sont publiques pour la recherche et indique où les obtenir.
- [ ] L'Annexe G contient l'URL du portail Quetelet-Progedo et les instructions pas-à-pas pour les relecteurs.
- [ ] Le modèle officiel de citation Cerema / Tisséo est formalisé.
- [ ] Le footer du Chapitre 4 référence le ticket 053.
