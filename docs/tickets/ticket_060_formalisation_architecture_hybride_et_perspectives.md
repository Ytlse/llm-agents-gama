# Ticket 060 — Formalisation de l'architecture hybride en cascade, cadre comparatif et perspectives (Chapitre 8)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ce ticket cadre la structure conceptuelle et la rédaction du Chapitre 8 (`docs/paper/article/fr/08_limits_and_hybrid.md`).
> **Principe de neutralité empirique :** ce document est strictement agnostique sur les valeurs numériques finales ; aucun résultat chiffré prématuré n'est présumé, les indicateurs définitifs seront consolidés une fois l'ensemble des campagnes et audits validés.

---

## 1. Contexte & Objectif Scientifique

Le Chapitre 8 tire les leçons de l'évaluation empirique menée dans les chapitres précédents :
- Identifier clairement les limites structurelles de chaque paradigme de modélisation (modèles tabulaires statistiques vs agents génératifs LLM).
- Dépasser l'opposition frontale entre ces approches en formalisant une **architecture hybride en cascade** capable de combiner les forces respectives de chaque composant.
- Établir un cadre comparatif multidimensionnel équilibré et ouvrir les perspectives vers les dynamiques intra-ménage et le chaînage complexe des activités.

---

## 2. Piliers Conceptuels à Rédiger

### 2.1 Formalisation de l'Architecture Hybride en Cascade (§ 8.2)
Définir formellement le mécanisme de décision étagé pour une simulation à grande échelle :
1. **Étage 1 — Filtre Déterministe (Règles physiques et légales) :**
   - Élagage strict de l'espace d'action $\mathcal{A}(o_t, C_i)$ : élimination des modes impossibles (non-possession de permis, indisponibilité d'un véhicule déjà mobilisé par le ménage, inexistence d'offre physique OTP).
2. **Étage 2 — Moteur Tabulaire / Statistique (Flux nominaux de routine) :**
   - Traitement à haute cadence des déplacements standards en régime nominal (déplacements habituels sans perturbation textuelle ni contexte atypique).
3. **Étage 3 — Décideur Génératif LLM (Situations complexes et contextuelles) :**
   - Mobilisation sélective de l'agent cognitif pour les cas d'exception : perturbations informées par la presse locale, chocs imprévus nécessitant mémoire et adaptation, arbitrages qualitatifs ou forte incertitude du modèle statistique.

### 2.2 Cadre Comparatif Multidimensionnel (§ 8.3)
Structurer une grille d'évaluation qualitative et quantitative permettant de confronter rigoureusement les architectures (tout tabulaire, tout LLM, hybride en cascade) sur plusieurs dimensions clés :
- **Efficience computationnelle :** temps d'inférence par déplacement, passage à l'échelle pour des métropoles entières.
- **Sobriété et coût en ressources :** volume de requêtes d'inférence, consommation de tokens.
- **Fidélité macro-distributionnelle :** capacité d'alignement avec les données d'enquêtes de déplacements réelles.
- **Sensibilité contextuelle et écologique :** réactivité aux événements textuels non tabulés, adaptation qualitative.
- **Inertie et mémoire :** persistance des souvenirs post-incidents (hystérésis) vs amnésie instantanée.

*Note : Les cellules quantitatives du tableau comparatif seront complétées uniquement à partir des résultats consolidés des runs archivés.*

### 2.3 Dynamiques Intra-Ménage et Chaînes Spatiales (§ 8.4)
Rédiger la prospective méthodologique sur :
- L'extension de la prise de décision au niveau du ménage (négociation pour l'usage du véhicule unique, trajets d'accompagnement scolaire).
- La préservation des cycles spatio-temporels des véhicules sur plusieurs jours consécutifs.

---

## 3. Livrables

1. Révision et harmonisation complète de `docs/paper/article/fr/08_limits_and_hybrid.md`.
2. Schéma conceptuel formalisé de la cascade hybride.
3. Tableau de synthèse multidimensionnel structuré (prêt à recevoir les métriques finales).
