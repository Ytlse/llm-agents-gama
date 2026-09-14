# Ticket 062 — Revue, complétion et alignement des Annexes techniques A à G (Chapitre 99)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ce ticket cadre la consolidation, la complétion et la conformité des Annexes techniques de l'article (`docs/paper/article/fr/99_annexes.md`).

---

## 1. Contexte & Rôle des Annexes (Standard AAMAS)

Les annexes techniques portent les détails d'implémentation, les spécifications des variables, les protocoles d'infrastructure et les justifications de reproductibilité indispensables pour garantir la rigueur de la soumission sans alourdir le corps principal de l'article.

---

## 2. Périmètre des Annexes à Consolider

Le fichier `docs/paper/article/fr/99_annexes.md` doit être structuré et harmonisé selon les sections suivantes :

1. **Annexe A — Synthèse de l'infrastructure d'inférence & plateformes :**
   - Documentation du gateway multi-fournisseurs (SWRR) et des quotas de requêtes.
   - Présentation de la plateforme Antigravity pour le pilotage des agents sans simulateur.

2. **Annexe B — Scripts d'évaluation et de benchmark :**
   - Spécification des pipelines d'inférence et d'évaluation unitaire.

3. **Annexe C — Environnement d'inférence locale :**
   - Paramètres de reproductibilité pour les modèles ouverts (vLLM, quantification AWQ, fixation stricte de la graine à température $\tau = 0,0$).

4. **Annexe D — Bilan méthodologique de la prompt calibration :**
   - Historique de la démarche de calibration de prompt et justification du basculement vers l'architecture hybride.

5. **Annexe E — Dictionnaire des 21 variables du contrat d'évaluation :**
   - Description exhaustive des 21 attributs (12 personne/ménage, 3 contexte, 6 géographie) issus de `feature_spec.json`.
   - Traçabilité stricte de la parité informationnelle entre modèles tabulaires et agents LLM.

6. **Annexe F — Journal des corrections méthodologiques :**
   - Recensement transparent de l'ensemble des écarts corrigés et des audits menés au cours des révisions successives du manuscrit.

7. **Annexe G — Source des données d'enquête, citation et convention de recherche :**
   - Recopie in extenso du libellé obligatoire de citation de l'enquête EMC² 2023 sous convention Quetelet-Progedo `lil-1750` (en cohérence avec le [Ticket 053](ticket_053_acces_donnees_recherche_et_reproductibilite.md)).

8. **Annexe H / Complément — Corpus des scénarios qualitatifs de presse locale (Étape 3b) :**
   - Intégration de la grille des 30 événements réels toulousains pré-enregistrés (en cohérence avec le [Ticket 059](ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees.md)).

---

## 3. Livrables

1. Révision et mise en forme complète de `docs/paper/article/fr/99_annexes.md`.
2. Vérification des liens de renvoi entre le texte principal (Chapitres 3 à 8) et les annexes correspondantes.
3. Préparation du matériel pour l'archive de soumission AAMAS.
