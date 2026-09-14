# Ticket 067 — Relecture critique chapitre par chapitre selon les standards d'exigence AAMAS (@reviewer-aamas)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ce ticket confie au skill **`reviewer-aamas`** (Senior Meta-Reviewer / Area Chair AAMAS) une revue critique systématique et impitoyable du manuscrit, chapitre par chapitre (`docs/paper/article/fr/`), en s'appuyant sur les standards de publication d'AAMAS et l'analyse rétrospective des meilleures publications 2020-2025.

---

## 1. Objectif & Posture d'Évaluation

Soumettre l'article à un audit de relecture au niveau d'exigence des meilleurs relecteurs de l'IFAAMAS :
- **Traquer le « mono-agent déguisé »** : vérifier que l'article justifie pleinement son ADN multi-agent (interactions, contraintes de ménage, dynamique de population, chaîne des véhicules).
- **Contrôler le standard « Dual Core »** : équilibre strict entre formalisation théorique rigoureuse (quadruplet d'agent, espace d'action, hypothèses pré-enregistrées) et validation empirique irréprochable (cohorte v5 scellée, parité 21 variables, double lecture tabulaire).
- **Anticiper les attaques déstabilisantes en phase de Rebuttal (*Rebuttal Killers*)** pour blinder l'argumentation avant la soumission.
- **Viser le niveau *Strong Accept (Award Candidate)*** en identifiant les faiblesses rédactionnelles et méthodologiques résiduelles.

---

## 2. Protocole de Revue Chapitre par Chapitre

La revue porte sur l'ensemble des chapitres de l'article dans `docs/paper/article/fr/` selon la séquence suivante :

| Chapitre | Fichier source | Points d'attention critiques AAMAS |
|---|---|---|
| **Ch. 0 & 1** | `00_abstract.md`, `01_introduction.md` | Clarté de la contribution, adéquation au track AAMAS, formulation des hypothèses $H_0$ à $H_3$, calibrage des 241 mots. |
| **Ch. 2** | `02_related_work.md` | Exhaustivité face au SOTA (SILICA, Baronchelli, GTA, ABM de transport), absence d'angles morts bibliographiques. |
| **Ch. 3** | `03_architecture.md` | Formalisation mathématique de l'agent (Ticket 050), rigueur du modèle de mémoire CoALA/ACT-R (Ticket 051). |
| **Ch. 4 & 4.5** | `04_metrics_and_substrate.md`, `04.5_prompt_calibration.md` | Sanctuarisation du substrat v5, asymétrie d'évaluation (Ticket 046), sobriété Green AI (Ticket 054). |
| **Ch. 5** | `05_factual_neutral_prompt.md` | Benchmark multi-modèles, quantification de la dispersion $\tau=0,0$, test de McNemar apparié (Ticket 055). |
| **Ch. 6** | `06_ablation.md` | Test de $H_0$, audit de la double lecture en chaîne vs hors chaîne (Ticket 057), audit unitaire à parité (Ticket 058). |
| **Ch. 7** | `07_untabulated_regimes.md` | Étape 3a (hystérésis longitudinale, Ticket 041/063) et Étape 3b (presse locale, plan 5 conditions, Ticket 059/064). |
| **Ch. 8** | `08_limits_and_hybrid.md` | Limite de l'itinéraire mixte (Ticket 049), formalisation de la cascade hybride (Ticket 060). |
| **Ch. 9** | `09_conclusion.md` | Portée des 4 enseignements fondamentaux, leçons transférables à la communauté MAS (Ticket 061). |
| **Ch. 99** | `99_annexes.md` | Complétude des Annexes A à G, citation Quetelet-Progedo (Ticket 053/062), reproductibilité de l'archive. |

---

## 3. Grille de Restitution pour Chaque Chapitre

Pour chaque chapitre analysé, `@reviewer-aamas` doit produire un rapport d'audit structuré :
1. **Note d'adéquation et verdict AAMAS** (sur l'échelle officielle 1 à 8).
2. **Points forts (*Strengths*)** : éléments différenciants qui valorisent le papier face au comité de programme.
3. **Faiblesses majeures (*Weaknesses*)** : failles conceptuelles, imprécisions de formulation, risques de sur-revendication.
4. **Attaques anticipées de Rebuttal** : les 2 ou 3 questions pièges qu'un relecteur hostile formulera.
5. **Recommandations chirurgicales de correction** : modifications textuelles précises pour lever les objections.

---

## 4. Livrables

- Fiche de revue détaillée pour chaque chapitre consigée dans `docs/paper/article/relecture/`.
- Synthèse globale méta-reviewer avec score prédictif consolidé pour AAMAS 2027.
